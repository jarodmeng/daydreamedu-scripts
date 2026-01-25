from flask import Flask, jsonify, request
from flask_cors import CORS
import os

# Load environment variables from .env file if it exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')
except ImportError:
    pass  # python-dotenv not installed, skip

from database import init_db, get_all_games, save_game
from models import db

app = Flask(__name__)
CORS(app)

# Initialize database
try:
    init_db(app)
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")
    print("Make sure DATABASE_URL environment variable is set")

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/api/games', methods=['POST'])
def create_game():
    """Save a game result"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'time_elapsed', 'rounds', 'total_questions']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Save game to database
        game_data = save_game(
            name=data['name'],
            time_elapsed=data['time_elapsed'],  # in milliseconds
            rounds=data['rounds'],
            total_questions=data['total_questions']
        )
        
        return jsonify({'success': True, 'game': game_data}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games', methods=['GET'])
def get_games():
    """Get all games (for leaderboard)"""
    try:
        games = get_all_games()
        return jsonify({'games': games}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
