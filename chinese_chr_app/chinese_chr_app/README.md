# Chinese Character Learning App

A web application to help primary school students learn simplified Chinese characters.

## Project Structure

```
chinese_chr_app/
├── backend/          # Flask backend API
│   ├── app.py       # Main Flask application
│   └── requirements.txt
├── frontend/        # React frontend
│   ├── src/
│   ├── package.json
│   └── vite.config.js
└── extract_characters_using_ai/
    └── output/      # Character data (CSV/JSON)
```

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
```bash
cd chinese_chr_app/backend
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

4. Run the Flask server:
```bash
python3 app.py
```

The backend will run on `http://localhost:5001`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd chinese_chr_app/frontend
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

## Usage

1. Open your browser and go to `http://localhost:3000`
2. Enter a single simplified Chinese character in the search box
3. Click "搜索" (Search) or press Enter
4. If the character is found, both sides of the character card will be displayed side by side

## API Endpoints

- `GET /api/characters/search?q=<character>` - Search for a character
- `GET /api/images/<custom_id>/<page>` - Get character card images (page1 or page2)
- `GET /api/health` - Health check endpoint

**Note:** The backend uses port 5001 instead of 5000 to avoid conflicts with macOS AirPlay Receiver.
