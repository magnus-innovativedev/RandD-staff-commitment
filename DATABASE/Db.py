from copy import deepcopy
from datetime import date, datetime, timezone
from threading import RLock
from time import monotonic

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()

_QUERY_CACHE_TTL_SECONDS = 30
_QUERY_CACHE_MAX_ENTRIES = 512
_query_cache = {}
_query_cache_lock = RLock()
_query_cache_generation = 0
_overdue_status_checked_on = None
_attendance_reset_checked_on = None
_schema_updated = False


def init_db(app):
    db.init_app(app)


def _ensure_schema():
    global _schema_updated
    if not _schema_updated:
        try:
            db.session.execute(text("ALTER TABLE commitments ADD COLUMN IF NOT EXISTS reason TEXT;"))
            db.session.execute(text("ALTER TABLE commitments ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;"))
            db.session.execute(text("ALTER TABLE commitments ADD COLUMN IF NOT EXISTS assigned_by_id INTEGER REFERENCES users(id);"))
            db.session.commit()
            _schema_updated = True
        except Exception:
            db.session.rollback()


# models import db from this file, so they are imported inside functions
def _models():
    from DATABASE.models import User, Commitment
    return User, Commitment


def _invalidate_query_cache():
    global _query_cache_generation
    with _query_cache_lock:
        _query_cache_generation += 1
        _query_cache.clear()


def _cached_query(key, load):
    now = monotonic()
    with _query_cache_lock:
        cached = _query_cache.get(key)
        if cached and cached[0] > now:
            return deepcopy(cached[1])
        _query_cache.pop(key, None)
        generation = _query_cache_generation

    value = load()
    with _query_cache_lock:
        if (generation == _query_cache_generation
                and len(_query_cache) >= _QUERY_CACHE_MAX_ENTRIES):
            expired_keys = [
                cache_key for cache_key, entry in _query_cache.items()
                if entry[0] <= monotonic()
            ]
            for cache_key in expired_keys:
                _query_cache.pop(cache_key, None)
            if len(_query_cache) >= _QUERY_CACHE_MAX_ENTRIES:
                _query_cache.clear()
        if generation == _query_cache_generation:
            _query_cache[key] = (monotonic() + _QUERY_CACHE_TTL_SECONDS, deepcopy(value))
    return value


def _ensure_overdue_status_current():
    global _overdue_status_checked_on
    _ensure_schema()
    today = date.today()
    with _query_cache_lock:
        if _overdue_status_checked_on != today:
            mark_overdue_as_missed()
            _overdue_status_checked_on = today


def _commit():
    try:
        db.session.commit()
        _invalidate_query_cache()
    except Exception:
        db.session.rollback()
        raise


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- USERS ----------------
def get_user_by_id(user_id):
    User, _ = _models()
    return db.session.get(User, user_id)


def get_user_by_email(email):
    User, _ = _models()
    return User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()


def get_managers():
    User, _ = _models()
    return User.query.filter_by(role="manager").order_by(User.name).all()


def create_user(name, email, password, role, manager_id=None):
    User, _ = _models()
    if get_user_by_email(email):
        raise ValueError("A user with this email already exists.")
    user = User(name=name.strip(), email=email.strip().lower(),
                role=role, manager_id=manager_id)
    user.set_password(password)
    db.session.add(user)
    _commit()
    return user


def ensure_default_developer(name, email, password):
    """Creates the developer account only if no developer exists yet."""
    User, _ = _models()
    if User.query.filter_by(role="developer").first():
        return None
    return create_user(name, email, password, "developer", None)


def set_attendance(user_id, status):
    """status: 'present', 'absent', 'wfh' or None (not marked)."""
    user = get_user_by_id(user_id)
    user.attendance_status = status
    _commit()


def get_visible_user_ids(user):
    """The one place that decides whose data a user may see."""
    User, _ = _models()
    if user.role == "cmo":
        return list(db.session.execute(db.select(User.id)).scalars())
    if user.role == "manager":
        team = db.session.execute(
            db.select(User.id).where(User.manager_id == user.id)).scalars()
        return [user.id] + list(team)
    return [user.id]


def get_subordinate_users(user):
    """Returns users that report directly or indirectly under this user."""
    User, _ = _models()
    if user.role == "developer":
        return User.query.filter_by(role="cmo").order_by(User.name).all()
    if user.role == "cmo":
        return User.query.filter(User.role.in_(["manager", "staff"])).order_by(User.role.desc(), User.name).all()
    if user.role == "manager":
        return User.query.filter_by(manager_id=user.id).order_by(User.name).all()
    return []


def update_user_password(user_id, new_password):
    """Updates password for a specific user."""
    User, _ = _models()
    user = db.session.get(User, user_id)
    if not user:
        return False
    user.set_password(new_password)
    _commit()
    return True


def delete_user(user_id):
    """Deletes a user and their associated commitments."""
    User, Commitment = _models()
    user = db.session.get(User, user_id)
    if not user:
        return False
    Commitment.query.filter_by(owner_id=user_id).delete()
    User.query.filter_by(manager_id=user_id).update({"manager_id": None})
    db.session.delete(user)
    _commit()
    return True


# ---------------- COMMITMENTS ----------------
def add_commitment(owner_id, commitment_text, description, start_date, end_date,
                   priority="medium", assigned_by_id=None):
    _, Commitment = _models()
    _ensure_schema()
    c = Commitment(owner_id=owner_id, commitment_text=commitment_text,
                   description=description, start_date=start_date,
                   end_date=end_date, priority=priority,
                   assigned_by_id=assigned_by_id)
    db.session.add(c)
    _commit()
    return c


def can_assign_commitment(assigner, target_user):
    """Check if assigner has permission to assign task to target_user."""
    if not assigner or not target_user:
        return False
    if assigner.id == target_user.id:
        return assigner.role in ("staff", "manager")
    if assigner.role == "developer":
        return True
    if assigner.role == "cmo":
        return target_user.role in ("manager", "staff")
    if assigner.role == "manager":
        return target_user.role == "staff" and target_user.manager_id == assigner.id
    return False


def get_assignable_users(user):
    """Returns users that the given user can assign tasks to."""
    if not user:
        return []
    User, _ = _models()
    if user.role == "cmo":
        # CMO can assign tasks to all managers and all staff
        mgrs = User.query.filter_by(role="manager").order_by(User.name).all()
        staff = User.query.filter_by(role="staff").order_by(User.name).all()
        return mgrs + staff
    elif user.role == "manager":
        # Manager can assign tasks to their staff members
        return (User.query.filter_by(role="staff", manager_id=user.id)
                .order_by(User.name).all())
    elif user.role == "developer":
        return User.query.filter(User.role.in_(("cmo", "manager", "staff"))).order_by(User.name).all()
    return []


def get_user_commitments(user_id):
    User, Commitment = _models()
    _ensure_overdue_status_current()

    def load():
        commitments = (Commitment.query.filter_by(owner_id=user_id)
                       .order_by(Commitment.end_date).all())
        fields = (
            "id", "owner_id", "commitment_text", "description", "reason", "start_date",
            "end_date", "duration_days", "completion_pct", "priority", "status",
            "created_at", "completed_at", "assigned_by_id",
        )
        rows = []
        user_cache = {}
        for commitment in commitments:
            row = {field: getattr(commitment, field, None) for field in fields}
            assigned_by_id = row.get("assigned_by_id")
            if assigned_by_id and assigned_by_id != user_id:
                if assigned_by_id not in user_cache:
                    u = db.session.get(User, assigned_by_id)
                    user_cache[assigned_by_id] = (u.name, u.role) if u else (None, None)
                row["assigned_by_name"], row["assigned_by_role"] = user_cache[assigned_by_id]
            else:
                row["assigned_by_name"], row["assigned_by_role"] = None, None
            if row.get("status") == "completed":
                comp_dt = row.get("completed_at")
                if comp_dt:
                    comp_date = comp_dt.date() if hasattr(comp_dt, "date") else comp_dt
                    row["completed_date_str"] = comp_date.strftime("%d %b %Y")
                elif row.get("end_date"):
                    comp_date = row["end_date"]
                    row["completed_date_str"] = comp_date.strftime("%d %b %Y")
                else:
                    comp_date = None
                    row["completed_date_str"] = "N/A"

                start = row.get("start_date")
                if comp_date and start:
                    diff = (comp_date - start).days
                    if diff <= 0:
                        row["time_taken_str"] = "Same day"
                        row["days_taken"] = 0
                    elif diff == 1:
                        row["time_taken_str"] = "1 day"
                        row["days_taken"] = 1
                    else:
                        row["time_taken_str"] = f"{diff} days"
                        row["days_taken"] = diff
                else:
                    row["time_taken_str"] = None
                    row["days_taken"] = None
            else:
                row["time_taken_str"] = None
                row["days_taken"] = None
                row["completed_date_str"] = None
            rows.append(row)
        return rows

    return _cached_query(("user_commitments", user_id, date.today()), load)


def update_commitment_reason(commitment_id, user_id, reason_text):
    """Updates the reason for delay when a commitment's end date has passed."""
    User, Commitment = _models()
    _ensure_schema()
    c = db.session.get(Commitment, commitment_id)
    if c is None:
        return None
    user = db.session.get(User, user_id)
    if not user:
        return None
    # Allowed if user is owner, CMO/developer, or manager of owner
    if c.owner_id != user.id and user.role not in ("cmo", "developer"):
        owner = db.session.get(User, c.owner_id)
        if not owner or owner.manager_id != user.id:
            return None
    c.reason = reason_text.strip() if reason_text and reason_text.strip() else None
    _commit()
    return c


def update_progress(commitment_id, user_id, pct):
    """Only the owner can update. Keeps status and percentage consistent."""
    _, Commitment = _models()
    c = db.session.get(Commitment, commitment_id)
    if c is None or c.owner_id != user_id:
        return None
    c.completion_pct = pct
    if pct >= 100:
        c.status = "completed"
        c.completed_at = _now()
    elif pct > 0:
        c.status = "in_progress"
        c.completed_at = None
    else:
        c.status = "pending"
        c.completed_at = None
    _commit()
    return c


def delete_commitment(commitment_id, user_id):
    """Only CMO, Manager, or Developer can delete commitments.
    Managers can only delete their own or their subordinates' commitments."""
    User, Commitment = _models()
    c = db.session.get(Commitment, commitment_id)
    if c is None:
        return False
    user = db.session.get(User, user_id) if isinstance(user_id, int) else user_id
    if not user or user.role not in ("cmo", "manager", "developer"):
        return False
    if user.role == "manager" and c.owner_id != user.id:
        owner = db.session.get(User, c.owner_id)
        if not owner or owner.manager_id != user.id:
            return False
    db.session.delete(c)
    _commit()
    return True


# ---------------- SUMMARIES ----------------
def manager_summary(manager_id):
    """One row per staff member under a manager."""
    _ensure_overdue_status_current()
    sql = text("""
        SELECT u.id, u.name AS staff, u.attendance_status,
               COUNT(c.id) AS total,
               COUNT(*) FILTER (WHERE c.status = 'completed') AS completed,
               COUNT(*) FILTER (WHERE c.status = 'missed') AS missed,
               COUNT(*) FILTER (WHERE c.status = 'pending') AS pending,
               COUNT(*) FILTER (WHERE c.priority = 'high') AS high,
               COUNT(*) FILTER (
                   WHERE c.status = 'missed'
                      OR (c.status IN ('pending','in_progress')
                          AND c.end_date < CURRENT_DATE)
               ) AS late,
               COUNT(c.id) FILTER (
                   WHERE c.start_date <= CURRENT_DATE
                     AND c.end_date >= CURRENT_DATE
               ) AS today_commitments,
               ROUND(AVG(c.completion_pct), 1) AS avg_completion_pct
        FROM users u
        LEFT JOIN commitments c ON c.owner_id = u.id
        WHERE u.manager_id = :mid
        GROUP BY u.id, u.name, u.attendance_status
        ORDER BY u.name
    """)
    return _cached_query(
        ("manager_summary", manager_id, date.today()),
        lambda: [dict(row) for row in db.session.execute(
            sql, {"mid": manager_id}).mappings().all()],
    )


def cmo_summary(cmo_id):
    """One row per manager under the CMO."""
    _ensure_overdue_status_current()
    sql = text("""
        SELECT m.id, m.name AS manager, m.attendance_status AS manager_attendance,
               COUNT(DISTINCT s.id) AS team_size,
               COUNT(c.id) AS total,
               COUNT(*) FILTER (WHERE c.status = 'completed') AS completed,
               COUNT(*) FILTER (WHERE c.status IN ('pending','in_progress')
                                  AND c.end_date < CURRENT_DATE) AS overdue,
               COUNT(*) FILTER (WHERE c.status = 'missed') AS missed,
               COUNT(DISTINCT s.id) FILTER (
                   WHERE s.role = 'staff'
                     AND NOT EXISTS (
                         SELECT 1
                         FROM commitments today_c
                         WHERE today_c.owner_id = s.id
                           AND today_c.start_date <= CURRENT_DATE
                           AND today_c.end_date >= CURRENT_DATE
                     )
               ) AS no_commitment_today,
               ROUND(AVG(c.completion_pct), 1) AS avg_completion_pct,
               COUNT(DISTINCT s.id) FILTER (WHERE s.attendance_status = 'present') AS present,
               COUNT(DISTINCT s.id) FILTER (WHERE s.attendance_status = 'wfh') AS wfh,
               COUNT(DISTINCT s.id) FILTER (WHERE s.attendance_status = 'absent') AS absent
        FROM users m
        LEFT JOIN users s       ON s.manager_id = m.id
        LEFT JOIN commitments c ON c.owner_id   = s.id
        WHERE m.manager_id = :cid AND m.role = 'manager'
        GROUP BY m.id, m.name, m.attendance_status
        ORDER BY m.name
    """)
    return _cached_query(
        ("cmo_summary", cmo_id, date.today()),
        lambda: [dict(row) for row in db.session.execute(
            sql, {"cid": cmo_id}).mappings().all()],
    )


def cmo_zero_commitment_staff(cmo_id):
    """Staff under a CMO whose commitments do not cover today's date."""
    sql = text("""
        SELECT m.id AS manager_id, m.name AS manager,
               s.id AS staff_id, s.name AS staff
        FROM users m
        JOIN users s ON s.manager_id = m.id AND s.role = 'staff'
        WHERE m.manager_id = :cid
          AND m.role = 'manager'
          AND NOT EXISTS (
              SELECT 1
              FROM commitments c
              WHERE c.owner_id = s.id
                AND c.start_date <= CURRENT_DATE
                AND c.end_date >= CURRENT_DATE
          )
        ORDER BY m.name, s.name
    """)
    return _cached_query(
        ("cmo_zero_commitment_staff", cmo_id, date.today()),
        lambda: [dict(row) for row in db.session.execute(
            sql, {"cid": cmo_id}).mappings().all()],
    )


def cmo_zero_commitment_managers(cmo_id):
    """Managers under a CMO whose commitments do not cover today's date."""
    sql = text("""
        SELECT m.id AS manager_id, m.name AS manager
        FROM users m
        WHERE m.manager_id = :cid
          AND m.role = 'manager'
          AND NOT EXISTS (
              SELECT 1
              FROM commitments c
              WHERE c.owner_id = m.id
                AND c.start_date <= CURRENT_DATE
                AND c.end_date >= CURRENT_DATE
          )
        ORDER BY m.name
    """)
    return _cached_query(
        ("cmo_zero_commitment_managers", cmo_id, date.today()),
        lambda: [dict(row) for row in db.session.execute(
            sql, {"cid": cmo_id}).mappings().all()],
    )


def cmo_all_staff(cmo_id):
    """All staff members under managers belonging to this CMO."""
    sql = text("""
        SELECT m.id AS manager_id, m.name AS manager_name,
               s.id AS staff_id, s.name AS staff_name, s.attendance_status,
               COUNT(c.id) AS total_tasks,
               COUNT(*) FILTER (WHERE c.status = 'completed') AS completed_tasks
        FROM users m
        JOIN users s ON s.manager_id = m.id AND s.role = 'staff'
        LEFT JOIN commitments c ON c.owner_id = s.id
        WHERE m.manager_id = :cid
          AND m.role = 'manager'
        GROUP BY m.id, m.name, s.id, s.name, s.attendance_status
        ORDER BY m.name, s.name
    """)
    return _cached_query(
        ("cmo_all_staff", cmo_id, date.today()),
        lambda: [dict(row) for row in db.session.execute(
            sql, {"cid": cmo_id}).mappings().all()],
    )


def cmo_all_staff_commitments(cmo_id):
    """All commitments of staff members under managers belonging to this CMO."""
    _ensure_overdue_status_current()
    sql = text("""
        SELECT c.id, c.owner_id, c.commitment_text, c.description,
               c.start_date, c.end_date, c.priority, c.status,
               c.completion_pct, c.reason, c.assigned_by_id,
               c.completed_at,
               s.name AS staff_name,
               m.id AS manager_id, m.name AS manager_name,
               assigner.name AS assigned_by_name
        FROM commitments c
        JOIN users s ON s.id = c.owner_id AND s.role = 'staff'
        JOIN users m ON m.id = s.manager_id AND m.role = 'manager'
        LEFT JOIN users assigner ON assigner.id = c.assigned_by_id
        WHERE m.manager_id = :cid
        ORDER BY c.end_date ASC, c.id DESC
    """)
    rows = db.session.execute(sql, {"cid": cmo_id}).mappings().all()
    out = []
    today_dt = date.today()
    for row in rows:
        d = dict(row)
        d["is_overdue"] = (d["end_date"] < today_dt and d["status"] != "completed")
        d["is_today"] = (d["start_date"] <= today_dt <= d["end_date"])
        out.append(d)
    return out


# ---------------- DAILY JOBS ----------------
def mark_overdue_as_missed():
    db.session.execute(text("""
        UPDATE commitments SET status = 'missed'
        WHERE status IN ('pending','in_progress') AND end_date < CURRENT_DATE
    """))
    _commit()


def reset_attendance():
    """Mark attendance absent once per app-local day."""
    global _attendance_reset_checked_on
    today = date.today()
    with _query_cache_lock:
        if _attendance_reset_checked_on == today:
            return False

        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS attendance_reset_state (
                    id SMALLINT PRIMARY KEY CHECK (id = 1),
                    reset_on DATE NOT NULL
                )
            """))
            initialized = db.session.execute(text("""
                INSERT INTO attendance_reset_state (id, reset_on)
                VALUES (1, :today)
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            """), {"today": today}).scalar_one_or_none()

            reset = False
            if initialized is None:
                reset = db.session.execute(text("""
                    UPDATE attendance_reset_state
                    SET reset_on = :today
                    WHERE id = 1 AND reset_on < :today
                    RETURNING id
                """), {"today": today}).scalar_one_or_none() is not None
                if reset:
                    db.session.execute(
                        text("UPDATE users SET attendance_status = 'absent'")
                    )

            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        if reset:
            _invalidate_query_cache()
        _attendance_reset_checked_on = today
        return reset
