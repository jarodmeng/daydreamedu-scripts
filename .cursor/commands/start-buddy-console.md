# Start Buddy Console

Start the preferred **Buddy Console** local operator app on the standard AI Study Buddy app ports:

- frontend: `5178`
- backend: `8010`

The current scaffold is seeded from `review_workspace`, so this command starts the copied app under its new package path.

## Backend

From repository root:

```bash
python3 -m pip install -r ai_study_buddy/buddy_console/backend/requirements.txt
python3 -m uvicorn ai_study_buddy.buddy_console.backend.app:app --reload --port 8010
```

## Frontend

From repository root:

```bash
cd ai_study_buddy/buddy_console/frontend
npm install
npm run dev
```

Open:

`http://127.0.0.1:5178/`

## Notes

- This is the preferred unified app for the inventory -> PDF -> review workflow.
- It was initially seeded from `review_workspace`, but now has dedicated inventory and PDF surfaces.
- Existing standalone apps remain available until explicit deprecation.
