# Deployment Guide

> **Note:** Day-to-day deployment is now handled automatically:
> - **Backend**: Cloud Build trigger on `main` builds the Docker image and deploys to Cloud Run.
> - **Frontend**: Netlify builds and deploys on pushes to `main`.
> Use this document primarily as a reference and for **manual recovery or one-off troubleshooting**, not as the standard deployment workflow.

This document outlines the deployment process for the Chinese Character Learning App.

## Architecture

- **Frontend**: Netlify (static hosting at `chinese-chr.daydreamedu.org/`)
- **Backend**: Google Cloud Run (serverless containers)
- **Images**: Google Cloud Storage bucket (`chinese-chr-app-images`)

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **Required APIs enabled**:
   - Cloud Run API
   - Cloud Build API
   - Container Registry API
   - Cloud Storage API

3. **CLI Tools Installed**:
   - `gcloud` CLI
   - `docker`
   - `netlify` CLI (optional, can use web UI)

## Initial Setup

### 1. Enable Google Cloud APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable storage-component.googleapis.com
```

### 2. Create GCS Bucket for Images

```bash
gsutil mb -p daydreamedu -l us-central1 gs://chinese-chr-app-images
gsutil iam ch allUsers:objectViewer gs://chinese-chr-app-images
```

### 3. Upload PNG Images to GCS

```bash
# Navigate to the chinese_chr_app directory first
cd /path/to/daydreamedu-scripts/chinese_chr_app

# Upload all PNG folders to gs://chinese-chr-app-images/png/
gsutil -m cp -r data/png gs://chinese-chr-app-images/
```

**Important**: You must run this command from the `chinese_chr_app/` directory (where `data/png/` exists), not from your home directory.

Alternatively, you can use the full path:
```bash
gsutil -m cp -r /path/to/daydreamedu-scripts/chinese_chr_app/data/png gs://chinese-chr-app-images/
```

This will create the structure: `gs://chinese-chr-app-images/png/0001/page1.png`, `gs://chinese-chr-app-images/png/0001/page2.png`, etc.

Note: The backend code expects PNG files to be under the `png/` prefix in the bucket.

**Important:** The `chinese_chr_app/data/png/` directory is **not in the repo** (gitignored). So 字卡 images in production only work if you have run this upload at least once from a machine that has the PNG folder (e.g. your laptop or a one-off job). Cloud Build does **not** upload PNGs. After the first upload, re-run this command whenever you add or change character card images locally.

### 4. Build and Deploy Backend (Manual First Time)

```bash
# From the repository root
cd chinese_chr_app/chinese_chr_app/backend

# Build Docker image
# Build context is chinese_chr_app/ (parent directory containing both backend and data)
docker build -t gcr.io/daydreamedu/chinese-chr-app -f Dockerfile ../../

# Push to Container Registry
docker push gcr.io/daydreamedu/chinese-chr-app

# Deploy to Cloud Run (include Supabase vars if using Google login)
gcloud run deploy chinese-chr-app \
  --image gcr.io/daydreamedu/chinese-chr-app \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars CORS_ORIGINS=https://chinese-chr.daydreamedu.org,GCS_BUCKET_NAME=chinese-chr-app-images,SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co,SUPABASE_JWT_AUD=authenticated
```

**Note:** Replace `YOUR_PROJECT_REF` with your Supabase project reference. For database mode and character view logging, also set `USE_DATABASE=true` and `DATABASE_URL` (Supabase connection string) in Cloud Run → Variables & Secrets. Environment variables can be updated after deployment without redeploying the image:
```bash
# Update environment variables
gcloud run services update chinese-chr-app \
  --region us-central1 \
  --update-env-vars CORS_ORIGINS=https://chinese-chr.daydreamedu.org,GCS_BUCKET_NAME=chinese-chr-app-images,SUPABASE_URL=...,SUPABASE_JWT_AUD=authenticated

# Or update a single variable
gcloud run services update chinese-chr-app \
  --region us-central1 \
  --update-env-vars CORS_ORIGINS=https://daydreamedu.org
```

### 5. Deploy Frontend to Netlify

#### Step 1: Prepare Netlify Portal Setup

Before deploying, you need to set up the site in the Netlify portal:

1. **Go to Netlify Dashboard**: https://app.netlify.com
2. **Create a new site**:
   - Click "Add new site" → "Import an existing project"
   - Choose "Deploy with GitHub"
   - Authorize Netlify to access your GitHub account (if not already done)
   - Select your repository: `jarodmeng/daydreamedu-scripts`

3. **Configure Build Settings**:
   - **Base directory**: `chinese_chr_app/chinese_chr_app/frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `dist` (relative to base directory, not full path)
   - **Functions directory**: Leave empty (we don't use Netlify functions)
   
   **Note**: The `netlify.toml` file in your frontend directory should auto-configure these, but verify they match above.
   
   Click "Show advanced" and ensure:
   - **Node version**: Use the latest LTS (or specify in `.nvmrc` if needed)

4. **Set Environment Variables**:
   - Click "New variable" and add:
     - **Key**: `VITE_API_URL`
     - **Value**: `https://chinese-chr-app-177544945895.us-central1.run.app`
     - (Use your actual Cloud Run URL from Step 4)

5. **Configure Site Name** (optional):
   - Netlify will auto-generate a name like `random-name-12345`
   - You can change it in Site settings → General → Site details
   - Or set a custom domain later

6. **Click "Deploy site"**

Netlify will:
- Clone your repository
- Install dependencies (`npm install`)
- Build the frontend (`npm run build`)
- Deploy to a Netlify URL (e.g., `https://random-name-12345.netlify.app`)

#### Step 2: Configure Custom Domain (Optional)

If you want to use `chinese-chr.daydreamedu.org`:

1. Go to Site settings → Domain management
2. Add custom domain: `chinese-chr.daydreamedu.org`
3. Follow Netlify's DNS instructions (or let Netlify manage DNS for `daydreamedu.org`)

#### Option A: Using Netlify CLI (Alternative)

If you prefer CLI over the portal:

```bash
cd chinese_chr_app/chinese_chr_app/frontend

# Build the frontend
npm run build

# Deploy (first time - link to site)
netlify deploy --prod --dir=dist

# Or if already linked
netlify deploy --prod
```

### 6. Update Frontend Environment Variable

After deploying the backend, update the frontend's `VITE_API_URL` environment variable in Netlify to point to your Cloud Run URL.

## Automatic Deployment (CI/CD)

### Backend: Cloud Build Trigger

1. Create a Cloud Build trigger:
```bash
gcloud builds triggers create github \
  --repo-name=daydreamedu-scripts \
  --repo-owner=jarodmeng \
  --branch-pattern="^main$" \
  --build-config=chinese_chr_app/chinese_chr_app/backend/cloudbuild.yaml
```

2. Or use the Cloud Console:
   - Go to Cloud Build → Triggers
   - Create trigger from GitHub
   - Set build configuration file: `chinese_chr_app/chinese_chr_app/backend/cloudbuild.yaml`

### Frontend: Netlify Automatic Deploys

If you connected Netlify to GitHub (Option B above), automatic deploys are already enabled. Every push to the main branch will trigger a new deployment.

## Environment Variables

### Backend (Cloud Run)

Environment variables can be set during initial deployment or updated later:

**Set during deployment:**
```bash
gcloud run deploy chinese-chr-app ... --set-env-vars KEY1=value1,KEY2=value2
```

**Update after deployment:**
```bash
gcloud run services update chinese-chr-app \
  --region us-central1 \
  --update-env-vars KEY1=newvalue1,KEY2=newvalue2
```

**Required variables:**
- `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g., `https://chinese-chr.daydreamedu.org`)
- `GCS_BUCKET_NAME`: GCS bucket name for images (e.g., `chinese-chr-app-images`)
- `SUPABASE_URL`: Supabase project URL (e.g., `https://<project_ref>.supabase.co`) — for verifying auth JWTs
- `SUPABASE_JWT_AUD`: JWT audience (use `authenticated`)

**Optional (when using Supabase Postgres from the backend):**
- `USE_DATABASE`: Set to `true` so the backend loads characters from the DB and enables character view logging. If unset, the backend uses JSON files and `/api/log-character-view` returns 503.
- `DATABASE_URL`: Supabase transaction pooler connection string (required when `USE_DATABASE=true`).

**Character view logging:** When `USE_DATABASE=true` and `DATABASE_URL` are set, signed-in users’ character views (Search result) are logged to the `character_views` table (user_id, character, viewed_at, display_name). Display name comes from the app profile or JWT metadata. Create the table once (same DB as feng_characters): from repo root, `cd chinese_chr_app/chinese_chr_app/backend && python scripts/create_character_views_table.py` (requires `DATABASE_URL` or `SUPABASE_DB_URL` in `.env.local` or environment). Cloud Build uses `--update-env-vars`, so `DATABASE_URL` and `USE_DATABASE` set in the Cloud Run Console (Variables & Secrets) are preserved on deploy.

**Note:** `DATA_DIR` is automatically detected - it defaults to `/app/data` in the container (where files are copied during Docker build) or to the relative path for local development. You only need to set it via environment variable if you want to override this behavior.

**Automatic variables:**
- `PORT`: Automatically set by Cloud Run (default: 8080)

### Frontend (Netlify)

- `VITE_API_URL`: Backend API URL (e.g., `https://chinese-chr-app-xxxxx.run.app`)
- `VITE_SUPABASE_URL`: Supabase project URL (e.g., `https://<project_ref>.supabase.co`)
- `VITE_SUPABASE_ANON_KEY`: Supabase anon (public) key — required for Google login

### Google Login (Supabase Auth)

For "Sign in with Google" to work in production:

1. **Supabase Dashboard** → your project → **Authentication** → **Providers** → enable **Google** and set Client ID / Client Secret (from Google Cloud Console).
2. **Authentication** → **URL Configuration**:
   - **Site URL**: set to your **production** frontend URL (e.g. `https://your-app.netlify.app` or `https://chinese-chr.daydreamedu.org`). This is the default redirect after login; if it stays `http://localhost:3000`, production sign-in will redirect to localhost and fail.
   - **Redirect URLs**: add both your production URL and local dev URL so Supabase can redirect there after auth, e.g.:
     - `https://your-app.netlify.app`
     - `https://your-app.netlify.app/**`
     - `http://localhost:3000`
     - `http://localhost:3000/**`

## Local Development

### Backend

1. Create `.env.local` in `backend/` directory (copy from `.env.local.example`):
```env
PORT=5001
DATA_DIR=../../data
PNG_BASE_DIR=../../data/png
GCS_BUCKET_NAME=
CORS_ORIGINS=http://localhost:3000
SUPABASE_URL=https://<project_ref>.supabase.co
SUPABASE_JWT_AUD=authenticated
# DATABASE_URL=...  # only when using Supabase Postgres
LOGS_DIR=./logs
```

2. Run:
```bash
cd chinese_chr_app/chinese_chr_app/backend
python app.py
```

### Frontend

1. Create `.env.local` in `frontend/` directory (copy from `.env.example`):
```env
VITE_API_URL=   # empty = use Vite proxy to backend
VITE_SUPABASE_URL=https://<project_ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<your_anon_key>
```

2. Run:
```bash
cd chinese_chr_app/chinese_chr_app/frontend
npm run dev
```

## Troubleshooting

### Backend Issues

- **Images not loading**: Check GCS bucket permissions and `GCS_BUCKET_NAME` env var
- **Data not found**: Ensure `DATA_DIR` points to the correct location in the container

### CORS errors in production ("blocked by CORS policy", "No 'Access-Control-Allow-Origin' header")

If the frontend at `https://chinese-chr.daydreamedu.org` gets CORS errors when calling the backend (e.g. `/api/profile`, `/api/pinyin-search`):

1. **Immediate fix (no redeploy):** In Google Cloud Console → Cloud Run → chinese-chr-app → Edit & deploy new revision → Variables & Secrets, set **CORS_ORIGINS** to include the frontend origin, e.g. `https://chinese-chr.daydreamedu.org` (comma-separate multiple: `https://chinese-chr.daydreamedu.org,https://daydreamedu.org`). Save and deploy the new revision.
2. **Or via gcloud:**  
   `gcloud run services update chinese-chr-app --region us-central1 --update-env-vars CORS_ORIGINS=https://chinese-chr.daydreamedu.org`
3. The backend also allows any `https://*.daydreamedu.org` origin by default (regex). After the next code deploy, production will work even if `CORS_ORIGINS` is unset, as long as the frontend is on a daydreamedu.org subdomain.

### 字卡 (character card) images not showing in production

If the 字卡 section shows a broken image or "字卡图片暂不可用":

1. **Cloud Run**: Ensure `GCS_BUCKET_NAME` is set (e.g. `chinese-chr-app-images`). Without it, the backend tries the local filesystem and returns 404 in the container.
2. **GCS bucket**: Upload PNGs so the structure is `gs://<bucket>/png/<index>/page1.png` and `page2.png` (e.g. `png/0071/page2.png` for 玉). From repo: `gsutil -m cp -r chinese_chr_app/data/png gs://chinese-chr-app-images/`.
3. **Netlify**: Ensure `VITE_API_URL` is set to your Cloud Run URL so the frontend requests images from the correct API (e.g. `https://chinese-chr-app-xxx.run.app`).

### Character view logging returns 503

If the frontend calls `/api/log-character-view` and gets 503: the backend requires `USE_DATABASE=true` and `DATABASE_URL` on Cloud Run. Add both in Cloud Run → chinese-chr-app → Edit & deploy new revision → Variables & Secrets, then deploy. Ensure the `character_views` table exists (run `scripts/create_character_views_table.py` once).

### Frontend Issues

- **API calls failing**: Check `VITE_API_URL` environment variable
- **Sign in with Google not working**: Ensure `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are set in Netlify (production) or `.env.local` (local). In Supabase, enable Google provider and set Site URL / Redirect URLs (see "Google Login" above).
- **"This site can't be reached" / redirect to localhost after Sign in with Google (prod)**: The OAuth callback is going to localhost because Supabase **Site URL** is still set to `http://localhost:3000`. In Supabase → **Authentication** → **URL Configuration**, set **Site URL** to your production frontend URL (e.g. `https://your-app.netlify.app`). Add that URL (and `https://your-app.netlify.app/**`) to **Redirect URLs** if not already there. Then try Sign in with Google again from the production site.
- **Routing issues**: Verify `BrowserRouter` in `App.jsx` has no `basename` and `base: '/'` in `vite.config.js`
- **Build errors**: Ensure all dependencies are installed (`npm install`)

## Cost Estimates

- **Cloud Run**: ~$0.40/month (assuming minimal traffic, 1 instance, 512MB RAM)
- **Cloud Storage**: ~$0.02/month (for ~3000 PNG files, ~500MB)
- **Cloud Build**: Free tier includes 120 build-minutes/day
- **Netlify**: Free tier includes 100GB bandwidth/month

**Total estimated cost**: < $1/month for low traffic
