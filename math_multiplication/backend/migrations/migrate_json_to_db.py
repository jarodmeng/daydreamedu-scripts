"""
Migration script to migrate existing games.json data to Supabase database.

Usage:
    python migrations/migrate_json_to_db.py
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask
from dotenv import load_dotenv
from database import init_db
from models import db, Game

# Load environment variables
load_dotenv('.env.local')

def migrate_json_to_db():
    """Migrate games from JSON file to database"""
    app = Flask(__name__)
    
    # Initialize database
    try:
        init_db(app)
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        print("Make sure DATABASE_URL environment variable is set")
        return False
    
    # Find games.json file
    backend_dir = Path(__file__).resolve().parent.parent
    base_dir = backend_dir.parent
    games_json = base_dir / "data" / "games.json"
    
    if not games_json.exists():
        print(f"✗ games.json not found at {games_json}")
        return False
    
    # Load JSON data
    try:
        with open(games_json, 'r', encoding='utf-8') as f:
            games_data = json.load(f)
        print(f"✓ Loaded {len(games_data)} games from JSON file")
    except Exception as e:
        print(f"✗ Error loading JSON file: {e}")
        return False
    
    if not games_data:
        print("No games to migrate")
        return True
    
    # Migrate to database
    with app.app_context():
        migrated_count = 0
        skipped_count = 0
        
        for game_data in games_data:
            try:
                # Check if game already exists (by timestamp and name)
                existing = Game.query.filter_by(
                    name=game_data['name'],
                    time_elapsed=game_data['time_elapsed'],
                    rounds=game_data['rounds'],
                    total_questions=game_data['total_questions']
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Parse timestamp
                if 'timestamp' in game_data:
                    timestamp = datetime.fromisoformat(game_data['timestamp'].replace('Z', '+00:00'))
                else:
                    timestamp = datetime.utcnow()
                
                # Create game record
                game = Game(
                    timestamp=timestamp,
                    name=game_data['name'],
                    time_elapsed=game_data['time_elapsed'],
                    rounds=game_data['rounds'],
                    total_questions=game_data['total_questions']
                )
                
                db.session.add(game)
                migrated_count += 1
                
            except Exception as e:
                print(f"✗ Error migrating game {game_data.get('name', 'unknown')}: {e}")
                continue
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"✓ Successfully migrated {migrated_count} games")
            if skipped_count > 0:
                print(f"  (Skipped {skipped_count} duplicate games)")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error committing to database: {e}")
            return False


if __name__ == '__main__':
    print("Starting migration from JSON to database...")
    print("-" * 50)
    
    success = migrate_json_to_db()
    
    print("-" * 50)
    if success:
        print("✓ Migration completed successfully!")
    else:
        print("✗ Migration failed!")
        sys.exit(1)
