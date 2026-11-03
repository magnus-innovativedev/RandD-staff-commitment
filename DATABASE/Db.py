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


def init_db(app):
    db.init_app(app)


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
                   priority="medium"):
    _, Commitment = _models()
    c = Commitment(owner_id=owner_id, commitment_text=commitment_text,
                   description=description, start_date=start_date,
                   end_date=end_date, priority=priority)
    db.session.add(c)
    _commit()
    return c


def get_user_commitments(user_id):
    _, Commitment = _models()
    _ensure_overdue_status_current()

    def load():
        commitments = (Commitment.query.filter_by(owner_id=user_id)
                       .order_by(Commitment.end_date).all())
        fields = (
            "id", "owner_id", "commitment_text", "description", "start_date",
            "end_date", "duration_days", "completion_pct", "priority", "status",
            "created_at", "completed_at",
        )
        return [{field: getattr(commitment, field) for field in fields}
                for commitment in commitments]

    return _cached_query(("user_commitments", user_id, date.today()), load)


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
    _, Commitment = _models()
    c = db.session.get(Commitment, commitment_id)
    if c is None or c.owner_id != user_id:
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
        SELECT m.id, m.name AS manager,
               COUNT(DISTINCT s.id) AS team_size,
               COUNT(c.id) AS total,
               COUNT(*) FILTER (WHERE c.status = 'completed') AS completed,
               COUNT(*) FILTER (WHERE c.status IN ('pending','in_progress')
                                  AND c.end_date < CURRENT_DATE) AS overdue,
               COUNT(*) FILTER (WHERE c.status = 'missed') AS missed,
               ROUND(AVG(c.completion_pct), 1) AS avg_completion_pct,
               COUNT(DISTINCT s.id) FILTER (WHERE s.attendance_status = 'present') AS present,
               COUNT(DISTINCT s.id) FILTER (WHERE s.attendance_status = 'wfh') AS wfh,
               COUNT(DISTINCT s.id) FILTER (WHERE s.attendance_status = 'absent') AS absent
        FROM users m
        LEFT JOIN users s       ON s.manager_id = m.id
        LEFT JOIN commitments c ON c.owner_id   = s.id
        WHERE m.manager_id = :cid AND m.role = 'manager'
        GROUP BY m.id, m.name
        ORDER BY m.name
    """)
    return _cached_query(
        ("cmo_summary", cmo_id, date.today()),
        lambda: [dict(row) for row in db.session.execute(
            sql, {"cid": cmo_id}).mappings().all()],
    )


# ---------------- DAILY JOBS ----------------
def mark_overdue_as_missed():
    db.session.execute(text("""
        UPDATE commitments SET status = 'missed'
        WHERE status IN ('pending','in_progress') AND end_date < CURRENT_DATE
    """))
    _commit()


def reset_attendance():
    db.session.execute(text("UPDATE users SET attendance_status = NULL"))
    _commit()
