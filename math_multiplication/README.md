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
   - Configure Supabase Auth verification (for Google login):
     ```bash
     # Used to verify Supabase JWTs
     SUPABASE_URL=https://<PROJECT_REF>.supabase.co
     SUPABASE_JWT_AUD=authenticated
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

In production, the frontend is built with Vite and can be deployed to Netlify.

Environment variables:
- `VITE_API_URL` (backend base URL; in dev you can omit it to use the `/api` proxy)
- `VITE_SUPABASE_URL` (e.g. `https://<PROJECT_REF>.supabase.co`)
- `VITE_SUPABASE_ANON_KEY` (Supabase project anon key; safe to expose to the browser)

## Deployment (Production)

### Backend (Cloud Run via Cloud Build)

- **Service**: Cloud Run `math-practice-app` (public)
- **Region**: `asia-south1`
- **Build trigger**: Cloud Build trigger `math-practice-app-backend`
- **Build config**: `math_multiplication/backend/cloudbuild.yaml`
- **Secrets**: `DATABASE_URL` is injected from Secret Manager (e.g. `math-practice-database-url-prod`)
- **Env vars**: `SUPABASE_URL` and `SUPABASE_JWT_AUD` must be set so the backend can verify Google login tokens.

### Frontend (Netlify)

- **Base directory**: `math_multiplication/frontend`
- **Build command**: `npm run build`
- **Publish directory**: `dist`
- **SPA redirects**: handled by `math_multiplication/frontend/netlify.toml`
- **Env vars**:
  - `VITE_API_URL` = your Cloud Run backend URL (for example: `https://math-practice-app-177544945895.asia-south1.run.app`)
  - `VITE_SUPABASE_URL` = `https://<PROJECT_REF>.supabase.co`
  - `VITE_SUPABASE_ANON_KEY` = Supabase anon key

## Google Login Setup (Supabase Auth)

1. **Create Google OAuth credentials**
   - In Google Cloud Console → **APIs & Services** → **Credentials**
   - Create an **OAuth client ID** (Web application)
   - Add **Authorized redirect URI**:
     - `https://<PROJECT_REF>.supabase.co/auth/v1/callback`

2. **Enable Google provider in Supabase**
   - Supabase → **Authentication** → **Providers** → **Google**
   - Enable it and paste your **Client ID** and **Client Secret**

3. **Allow your site URLs**
   - Supabase → **Authentication** → **URL Configuration**
   - Set **Site URL** to your Netlify site (e.g. `https://<your-site>.netlify.app`)
   - Add **Additional Redirect URLs**:
     - `http://localhost:3000`
     - Your Netlify site URL

4. **Set frontend env vars (Netlify)**
   - `VITE_SUPABASE_URL=https://<PROJECT_REF>.supabase.co`
   - `VITE_SUPABASE_ANON_KEY=<anon key>`

5. **Set backend env vars (Cloud Run)**
   - `SUPABASE_URL=https://<PROJECT_REF>.supabase.co`
   - `SUPABASE_JWT_AUD=authenticated`

## Usage

1. Open your browser and go to `http://localhost:3000`
2. **Game Page**:
   - Optionally sign in with Google and set your display name in **Profile**
   - Or play anonymously by entering your name
   - Answer 20 unique multiplication questions (2-12 excluding 10; `a×b` and `b×a` count as the same question)
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

### Profile (Google login)
- `GET /api/profile` - Get/create the current user's profile (requires `Authorization: Bearer <token>`)
- `PUT /api/profile` - Update display name (requires `Authorization: Bearer <token>`)

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

