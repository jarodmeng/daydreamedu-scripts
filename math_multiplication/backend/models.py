from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

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
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
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
            'name': self.name,
            'time_elapsed': self.time_elapsed,
            'rounds': self.rounds,
            'total_questions': self.total_questions,
            'created_at': _to_utc_iso_z(self.created_at),
        }
    
    def __repr__(self):
        return f'<Game {self.id}: {self.name} - {self.time_elapsed}ms>'
