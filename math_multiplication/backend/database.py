"""Database connection and initialization"""
import os
from flask import Flask, current_app
from models import db, Game

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
    
    return db


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
