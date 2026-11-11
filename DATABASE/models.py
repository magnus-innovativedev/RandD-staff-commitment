from werkzeug.security import generate_password_hash, check_password_hash
from DATABASE.Db import db


class User(db.Model):
    __tablename__ = "users"

    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(100), nullable=False)
    email             = db.Column(db.String(150), unique=True, nullable=False)
    password_hash     = db.Column(db.Text, nullable=False)
    role              = db.Column(db.String(10), nullable=False)    # cmo / manager / staff
    manager_id        = db.Column(db.Integer, db.ForeignKey("users.id"))
    attendance_status = db.Column(db.String(10))                    # present / absent / wfh

    # user.manager -> the boss, user.team -> the people reporting to this user
    manager = db.relationship("User", remote_side=[id], backref="team")
    commitments = db.relationship("Commitment", foreign_keys="Commitment.owner_id", backref="owner", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Commitment(db.Model):
    __tablename__ = "commitments"

    id              = db.Column(db.Integer, primary_key=True)
    owner_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    commitment_text = db.Column(db.Text, nullable=False)
    description     = db.Column(db.Text)
    reason          = db.Column(db.Text)  # reason for delay when end_date is over
    start_date      = db.Column(db.Date, nullable=False)
    end_date        = db.Column(db.Date, nullable=False)
    # calculated by PostgreSQL, never set it from Python
    duration_days   = db.Column(db.Integer, db.Computed("end_date - start_date", persisted=True))
    completion_pct  = db.Column(db.Integer, nullable=False, default=0)
    priority        = db.Column(db.String(10), default="medium")
    status          = db.Column(db.String(15), default="pending")
    created_at      = db.Column(db.DateTime, server_default=db.func.now())
    completed_at    = db.Column(db.DateTime)
    assigned_by_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)