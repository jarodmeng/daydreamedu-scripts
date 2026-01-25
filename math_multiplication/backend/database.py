"""Database connection and initialization"""
import os
from flask import Flask, current_app
from sqlalchemy import text
from models import db, Game, UserProfile

def init_db(app: Flask):
    """Initialize database connection"""
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # SQLAlchemy defaults `postgresql://` to psycopg2.
    # On Python 3.13 we use psycopg v3, so rewrite the scheme if needed.
    if database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    
    # Configure SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'max_overflow': 2,
        'pool_timeout': 30,
        'pool_recycle': 1800,
    }
    
    # Initialize Flask-SQLAlchemy
    db.init_app(app)
    
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        _ensure_schema()
    
    return db


def _ensure_schema():
    """
    Lightweight schema safety for existing deployments.

    We avoid migrations for this small app; instead we ensure expected tables/columns exist.
    These statements are safe to run multiple times.
    """
    # Add user_id column to games if missing (for authenticated identity linking).
    db.session.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS user_id varchar(36);"))
    db.session.commit()


def get_all_games():
    """Get all games from database"""
    try:
        games = Game.query.order_by(Game.time_elapsed.asc()).all()
        return [game.to_dict() for game in games]
    except Exception as e:
        print(f"Error getting games: {e}")
        return []


def save_game(name: str, time_elapsed: int, rounds: int, total_questions: int):
    """Save a game to database (must be called within app context)"""
    try:
        game = Game(
            user_id=None,
            name=name,
            time_elapsed=time_elapsed,
            rounds=rounds,
            total_questions=total_questions
        )
        db.session.add(game)
        db.session.commit()
        return game.to_dict()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving game: {e}")
        raise


def get_or_create_profile(user_id: str, default_display_name: str) -> UserProfile:
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile:
        return profile
    profile = UserProfile(user_id=user_id, display_name=default_display_name)
    db.session.add(profile)
    db.session.commit()
    return profile


def update_profile(user_id: str, display_name: str) -> UserProfile:
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id, display_name=display_name)
        db.session.add(profile)
    else:
        profile.display_name = display_name
    db.session.commit()
    return profile


def save_game_with_user(user_id: str | None, name: str, time_elapsed: int, rounds: int, total_questions: int):
    """Save a game with optional authenticated user id."""
    try:
        game = Game(
            user_id=user_id,
            name=name,
            time_elapsed=time_elapsed,
            rounds=rounds,
            total_questions=total_questions
        )
        db.session.add(game)
        db.session.commit()
        return game.to_dict()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving game: {e}")
        raise
