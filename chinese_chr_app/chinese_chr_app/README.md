# Chinese Character Learning App

A web application to help primary school students learn simplified Chinese characters.

Production deployment is live at:

- **Frontend**: `https://chinese-chr.daydreamedu.org/`
- **Backend API**: Google Cloud Run service (e.g. `https://chinese-chr-app-xxxxx-uc.a.run.app`)
- **Images**: Google Cloud Storage bucket `chinese-chr-app-images`

## Project Structure

```
chinese_chr_app/
├── backend/          # Flask backend API
│   ├── app.py       # Main Flask application
│   ├── requirements.txt
│   └── logs/        # Character edit logs
├── frontend/        # React frontend
│   ├── src/
│   │   ├── pages/   # Page components (Search, Radicals, RadicalDetail, Structures)
│   │   ├── App.jsx  # Main router component
│   │   └── App.css
│   ├── package.json
│   └── vite.config.js
└── data/            # Character and dictionary data (JSON)
    ├── characters.json                   # Primary character metadata (from 冯氏早教识字卡, editable in app)
    ├── extracted_characters_hwxnet.json  # Dictionary data extracted from hwxnet (read-only in app)
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

In production, the frontend is built with Vite and deployed to Netlify. API requests are sent to the Cloud Run backend using the `VITE_API_URL` environment variable set in the Netlify site settings.

## Usage

1. Open your browser and go to `http://localhost:3000`
2. **Search Page**: Enter a single simplified Chinese character in the search box
   - Click "搜索" (Search) or press Enter
   - If the character is found, both sides of the character card will be displayed side by side
   - View and edit character metadata (拼音, 部首, 笔画, 例句, 词组, 结构)
3. **Radicals Page**: Click "部首 (Radicals)" in the navigation to browse characters by radical
   - View all radicals sorted by the number of associated characters
   - Click on a radical to see all characters with that radical
   - Characters are sorted by strokes (ascending), then by pinyin
   - Click on any character to search for it

## API Endpoints

### Character Search
- `GET /api/characters/search?q=<character>` - Search for a character
- `PUT /api/characters/<custom_id>/update` - Update character metadata

### Images
- `GET /api/images/<custom_id>/<page>` - Get character card images (page1 or page2)

### Radicals
- `GET /api/radicals` - Get all radicals sorted by character count
- `GET /api/radicals/<radical>` - Get all characters for a specific radical

### System
- `GET /api/health` - Health check endpoint

**Note:** The backend uses port 5001 instead of 5000 to avoid conflicts with macOS AirPlay Receiver.
