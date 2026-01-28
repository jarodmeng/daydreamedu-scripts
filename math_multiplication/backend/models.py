import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


def _get_schema_name() -> str | None:
    """
    Pick the Postgres schema for these models.

    - ENVIRONMENT=test  -> use the dedicated "test" schema
    - anything else     -> default to the public schema

    This lets local dev + e2e share the main Supabase project while
    keeping data isolated from production.
    """
    env = os.getenv("ENVIRONMENT", "").strip().lower()
    if env == "test":
        return "test"
    # None means "use the default search_path" (typically "public").
    return None


def _to_utc_iso_z(dt: datetime | None) -> str | None:
    """
    Serialize datetimes as ISO-8601 with an explicit UTC timezone ("Z").

    We store datetimes as naive UTC in the DB (datetime.utcnow). Without a timezone
    suffix, browsers often interpret the string as local time.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Use Z suffix for UTC
    return dt.isoformat().replace("+00:00", "Z")


class Game(db.Model):
    """Game model for storing game results"""
    __tablename__ = "games"
    __table_args__ = {"schema": _get_schema_name()}
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.String(36), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    time_elapsed = db.Column(db.Integer, nullable=False)  # in milliseconds
    rounds = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'timestamp': _to_utc_iso_z(self.timestamp),
            'user_id': self.user_id,
            'name': self.name,
            'time_elapsed': self.time_elapsed,
            'rounds': self.rounds,
            'total_questions': self.total_questions,
            'created_at': _to_utc_iso_z(self.created_at),
        }
    
    def __repr__(self):
        return f'<Game {self.id}: {self.name} - {self.time_elapsed}ms>'


class UserProfile(db.Model):
    """Minimal user profile (kid-safe).

    Keyed by Supabase Auth `sub` (UUID string).
    """
    __tablename__ = "user_profiles"
    __table_args__ = {"schema": _get_schema_name()}

    user_id = db.Column(db.String(36), primary_key=True)
    display_name = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'display_name': self.display_name,
            'created_at': _to_utc_iso_z(self.created_at),
            'updated_at': _to_utc_iso_z(self.updated_at),
        }
