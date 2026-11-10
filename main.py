import os
from datetime import date
from functools import wraps

import click
from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect, url_for, session, flash, abort, g)
from flask_wtf.csrf import CSRFProtect, CSRFError

from DATABASE import Db
from DATABASE.Db import init_db
import DATABASE.models  # noqa: F401  (loads the User and Commitment classes)

load_dotenv()

app = Flask(__name__, static_folder="Statics", template_folder="template")

db_url = os.getenv("DATABASE_URL", "")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}  # Neon wakes from idle
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-env-secret-key-stafftrack-2026")
app.config["WTF_CSRF_TIME_LIMIT"] = None  # Prevent random token timeout issues

init_db(app)
CSRFProtect(app)

def seed_developer():
    """On startup, create the developer account if none exists yet."""
    name = os.getenv("DEFAULT_DEV_NAME", "Developer")
    email = os.getenv("DEFAULT_DEV_EMAIL")
    password = os.getenv("DEFAULT_DEV_PASSWORD")
    if not password:
        print("DEFAULT_DEV_PASSWORD is not set; skipping default developer creation.")
        return
    try:
        with app.app_context():
            if Db.ensure_default_developer(name, email, password):
                print(f"Developer account created: {email}")
    except Exception as e:  # for example, tables not created yet
        print("Could not create developer account:", e)


seed_developer()

ATTENDANCE = ("present", "absent", "wfh")
PRIORITIES = ("low", "medium", "high")


# ---------------------------------------------------------------- helpers
@app.before_request
def load_user():
    g.user = None
    if request.endpoint in ("static", "manifest", "service_worker"):
        return
    Db.reset_attendance()
    uid = session.get("user_id")
    if uid:
        try:
            g.user = Db.get_user_by_id(uid)
        except Exception:
            g.user = None
        if g.user is None:
            session.pop("user_id", None)


def login_required(roles=None):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login"))
            if roles and g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash("Session expired or invalid CSRF token. Please try again.", "error")
    return redirect(request.referrer or url_for("login"))


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403,
                           message="You don't have access to this page."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404,
                           message="That page or record doesn't exist."), 404


# ------------------------------- pwa ----------------------------------
@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")


@app.route("/sw.js")
def service_worker():
    response = app.send_static_file("js/sw.js")
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


# ------------------------------- auth----------------------------------
@app.route("/")
def index():
    if g.user is None:
        return redirect(url_for("login"))
    if g.user.role == "developer":
        return redirect(url_for("add_user"))
    if g.user.role == "cmo":
        return redirect(url_for("cmo_overview"))
    if g.user.role == "manager":
        return redirect(url_for("team"))
    return redirect(url_for("my"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        user = Db.get_user_by_email(email) if email else None
        if user and user.check_password(password):
            session["user_id"] = user.id
            return redirect(url_for("index"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


# ---------------------------------------------------------------- my commitments
@app.route("/my")
@login_required(roles=["staff", "manager"])
def my():
    commitments = Db.get_user_commitments(g.user.id)
    return render_template("my.html", commitments=commitments, today=date.today())


@app.route("/commitments/add", methods=["POST"])
@login_required(roles=["staff", "manager"])
def add_commitment():
    text_ = request.form.get("commitment_text", "").strip()
    description = request.form.get("description", "").strip() or None
    start = parse_date(request.form.get("start_date"))
    end = parse_date(request.form.get("end_date"))
    priority = request.form.get("priority", "medium")
    if priority not in PRIORITIES:
        priority = "medium"

    if not text_ or not start or not end:
        flash("Commitment, start date and end date are required.", "error")
    elif end < start:
        flash("End date can't be before the start date.", "error")
    else:
        Db.add_commitment(g.user.id, text_, description, start, end, priority)
        flash("Commitment added.", "success")
    return redirect(url_for("my"))


@app.route("/commitments/<int:cid>/progress", methods=["POST"])
@login_required(roles=["staff", "manager"])
def update_progress(cid):
    try:
        pct = int(request.form.get("completion_pct", ""))
    except ValueError:
        pct = -1
    if not 0 <= pct <= 100:
        flash("Progress must be a number from 0 to 100.", "error")
    elif Db.update_progress(cid, g.user.id, pct) is None:
        abort(404)
    elif pct == 100:
        flash("Commitment marked as completed.", "success")
    else:
        flash("Progress saved.", "success")
    return redirect(url_for("my"))


@app.route("/commitments/<int:cid>/reason", methods=["POST"])
@login_required()
def update_commitment_reason(cid):
    reason = request.form.get("reason", "").strip()
    updated = Db.update_commitment_reason(cid, g.user.id, reason)
    if updated is None:
        abort(404)
    if reason:
        flash("Reason saved successfully.", "success")
    else:
        flash("Reason cleared.", "success")
    return redirect(request.referrer or url_for("my"))


@app.route("/commitments/<int:cid>/delete", methods=["POST"])
@login_required(roles=["manager", "cmo", "developer"])
def delete_commitment(cid):
    if not Db.delete_commitment(cid, g.user.id):
        flash("You do not have permission to delete this commitment.", "error")
        return redirect(request.referrer or url_for("my"))
    flash("Commitment deleted.", "success")
    return redirect(request.referrer or url_for("my"))


@app.route("/attendance", methods=["POST"])
@login_required(roles=["staff", "manager"])
def set_attendance():
    status = request.form.get("attendance_status") or None
    if status is not None and status not in ATTENDANCE:
        abort(400)
    Db.set_attendance(g.user.id, status)
    return redirect(request.referrer or url_for("my"))


# ---------------------------------------------------------------- manager / cmo
@app.route("/team")
@app.route("/team/<int:manager_id>")
@login_required(roles=["manager", "cmo"])
def team(manager_id=None):
    if g.user.role == "manager":
        if manager_id not in (None, g.user.id):
            abort(403)
        manager = g.user
    else:
        if manager_id is None:
            return redirect(url_for("cmo_overview"))
        manager = Db.get_user_by_id(manager_id)
        if manager is None or manager.role != "manager":
            abort(404)
    rows = Db.manager_summary(manager.id)
    return render_template("team.html", manager=manager, rows=rows)


@app.route("/overview")
@login_required(roles=["cmo"])
def cmo_overview():
    rows = Db.cmo_summary(g.user.id)
    zero_commitment_staff = Db.cmo_zero_commitment_staff(g.user.id)
    return render_template("cmo.html", rows=rows,
                           zero_commitment_staff=zero_commitment_staff)


@app.route("/user/<int:uid>")
@login_required()
def user_view(uid):
    if uid == g.user.id and g.user.role != "cmo":
        return redirect(url_for("my"))
    if uid not in Db.get_visible_user_ids(g.user):   # backend access control
        abort(403)
    person = Db.get_user_by_id(uid)
    if person is None:
        abort(404)
    commitments = Db.get_user_commitments(uid)
    return render_template("user_commitments.html", person=person,
                           commitments=commitments, today=date.today())


@app.route("/users/add", methods=["GET", "POST"])
@login_required(roles=["developer", "manager", "cmo"])
def add_user():
    managers = Db.get_managers() if g.user.role == "cmo" else []
    subordinates = Db.get_subordinate_users(g.user)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role, manager_id = "staff", g.user.id

        if g.user.role == "developer":      # the developer only creates CMOs
            role, manager_id = "cmo", None
        elif g.user.role == "cmo":
            role = request.form.get("role")
            if role == "manager":
                manager_id = g.user.id
            elif role == "staff":
                try:
                    manager_id = int(request.form.get("manager_id", ""))
                except ValueError:
                    manager_id = None
                if manager_id not in [m.id for m in managers]:
                    flash("Choose a manager for this staff member.", "error")
                    return render_template("add_user.html", managers=managers, subordinates=subordinates)
            else:
                flash("Choose a role.", "error")
                return render_template("add_user.html", managers=managers, subordinates=subordinates)

        if not name or not email or len(password) < 6:
            flash("Name, email and a password of at least 6 characters are required.", "error")
        else:
            try:
                Db.create_user(name, email, password, role, manager_id)
                flash(f"{name} was added as {role}.", "success")
                return redirect(url_for("add_user"))
            except ValueError as e:
                flash(str(e), "error")
                return render_template("add_user.html", managers=managers, subordinates=subordinates)
    return render_template("add_user.html", managers=managers, subordinates=subordinates)


@app.route("/users/<int:uid>/password", methods=["POST"])
@login_required(roles=["developer", "manager", "cmo"])
def update_subordinate_password(uid):
    allowed_ids = [u.id for u in Db.get_subordinate_users(g.user)]
    if uid not in allowed_ids:
        abort(403)
    new_password = request.form.get("password", "").strip()
    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "error")
    else:
        if Db.update_user_password(uid, new_password):
            flash("Password updated successfully.", "success")
        else:
            flash("User not found.", "error")
    return redirect(url_for("add_user"))


@app.route("/users/<int:uid>/delete", methods=["POST"])
@login_required(roles=["developer", "manager", "cmo"])
def delete_subordinate_user(uid):
    if uid == g.user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("add_user"))
    allowed_ids = [u.id for u in Db.get_subordinate_users(g.user)]
    if uid not in allowed_ids:
        abort(403)
    target = Db.get_user_by_id(uid)
    name = target.name if target else "User"
    if Db.delete_user(uid):
        flash(f"{name} was deleted successfully.", "success")
    else:
        flash("Could not delete user.", "error")
    return redirect(url_for("add_user"))


# ---------------------------------------------------------------- command line
@app.cli.command("create-user")
@click.option("--name", prompt=True)
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--role", type=click.Choice(["developer", "cmo", "manager", "staff"]), prompt=True)
@click.option("--manager-id", type=int, default=None,
              help="Leave empty for developer and CMO. Managers use the CMO's id.")
def create_user_cmd(name, email, password, role, manager_id):
    """Create a user from the command line."""
    user = Db.create_user(name, email, password, role, manager_id)
    click.echo(f"Created {user.role} '{user.name}' with id {user.id}")


@app.cli.command("daily-jobs")
def daily_jobs():
    """Run once a day (cron): mark overdue commitments and check attendance reset."""
    Db.mark_overdue_as_missed()
    Db.reset_attendance()
    click.echo("Daily jobs done")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
