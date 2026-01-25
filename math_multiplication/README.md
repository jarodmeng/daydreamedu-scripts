# Math Multiplication Game

A web application to help lower primary school students practice multiplication of 2 whole numbers (each ranging from 2 to 12) in a fun way.

## Project Structure

```
math_multiplication/
├── backend/          # Flask backend API
│   ├── app.py       # Main Flask application
│   ├── database.py  # Database connection and operations
│   ├── models.py    # SQLAlchemy database models
│   ├── Dockerfile   # Cloud Run container image
│   └── cloudbuild.yaml # Cloud Build: build/push/deploy to Cloud Run
│   ├── requirements.txt
│   ├── .env.local.example  # Environment variable template
│   └── DATABASE_SETUP.md   # Database setup guide
└── frontend/        # React frontend
    ├── netlify.toml # Netlify build + SPA redirect config
    ├── src/
    │   ├── pages/   # Page components (Game, Leaderboard)
    │   ├── App.jsx  # Main router component
    │   ├── NavBar.jsx
    │   └── App.css
    ├── package.json
    └── vite.config.js
```

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
```bash
cd math_multiplication/backend
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip3 install -r requirements.txt
```

4. Set up database (Supabase):
   - See `backend/DATABASE_SETUP.md` for detailed instructions
   - Create a `.env.local` file with your Supabase **transaction pooler** connection string:
     ```bash
     # Recommended (Transaction pooler)
     DATABASE_URL=postgresql://postgres.<PROJECT_REF>:password@aws-<n>-<region>.pooler.supabase.com:6543/postgres?sslmode=require
     ```

5. Run the Flask server:
```bash
python3 app.py
```

The backend will run on `http://localhost:5001`

**Note**: The database tables will be created automatically on first run.

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd math_multiplication/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

In production, the frontend is built with Vite and can be deployed to Netlify. API requests are sent to the backend using the `VITE_API_URL` environment variable set in the deployment settings.

## Deployment (Production)

### Backend (Cloud Run via Cloud Build)

- **Service**: Cloud Run `math-practice-app` (public)
- **Region**: `asia-south1`
- **Build trigger**: Cloud Build trigger `math-practice-app-backend`
- **Build config**: `math_multiplication/backend/cloudbuild.yaml`
- **Secrets**: `DATABASE_URL` is injected from Secret Manager (e.g. `math-practice-database-url-prod`)

### Frontend (Netlify)

- **Base directory**: `math_multiplication/frontend`
- **Build command**: `npm run build`
- **Publish directory**: `dist`
- **SPA redirects**: handled by `math_multiplication/frontend/netlify.toml`
- **Env var**: set `VITE_API_URL` to your Cloud Run backend URL (for example: `https://math-practice-app-177544945895.asia-south1.run.app`)

## Usage

1. Open your browser and go to `http://localhost:3000`
2. **Game Page**:
   - Enter your first name to start
   - Answer 20 unique multiplication questions (2-12 × 2-12)
   - Timer starts automatically when the game begins and tracks total time
   - Progress indicator shows current question number and round number
   - Input box auto-focuses for quick answering
   - Use Enter key to submit answers
   - Visual feedback: green checkmark (✓) for correct, red X (✗) for incorrect
   - Wrong answers are re-asked in randomized order in subsequent rounds until all are correct
   - Game completes when all 20 unique questions are answered correctly
   - Final results show: name, time elapsed (MM:SS.mmm), rounds completed, and total questions answered correctly
3. **Leaderboard Page**: View all game results sorted by completion time (fastest first), showing rank, name, time, rounds, questions, and date (shown in Singapore time)

## API Endpoints

### Games
- `POST /api/games` - Save a game result
  - Body: `{ "name": string, "time_elapsed": number (milliseconds), "rounds": number, "total_questions": number }`
  - Returns: `{ "success": boolean, "game": object }` with timestamp added
- `GET /api/games` - Get all games (for leaderboard)
  - Returns: `{ "games": array }` - array of game objects sorted by time_elapsed

### System
- `GET /api/health` - Health check endpoint

## Game Features

- **20 Unique Questions**: Each game generates 20 unique multiplication questions (2-12 × 2-12, excluding 1)
- **Timer**: Tracks total time from start to completion (displayed as MM:SS during game, MM:SS.mmm in results)
- **Rounds System**: Wrong answers are re-asked in randomized order in subsequent rounds until all 20 unique questions are answered correctly
- **Visual Feedback**: Instant feedback overlay with green checkmark (✓) for correct answers or red X (✗) for incorrect answers
- **Progress Tracking**: Shows current question number (e.g., "Question 5/20") and current round number
- **Auto-focus**: Input box is automatically focused when each question appears for quick answering
- **Keyboard Support**: Enter key submits answers
- **Persistent Storage**: Game results are saved to Supabase PostgreSQL database via backend API for leaderboard
- **Game Logging**: Each question attempt is logged with round number, question, correct answer, user answer, and correctness

**Note:** The backend uses port 5001 instead of 5000 to avoid conflicts with macOS AirPlay Receiver.

