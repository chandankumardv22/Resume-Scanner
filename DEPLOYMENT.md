# 🚀 Cloud Deployment Guide: Resume Analyzer

This guide details how to deploy the **Resume Analyzer** (FastAPI backend + React frontend) to the cloud. The repository is pre-configured with production Dockerfiles, Render Blueprints, Railway configurations, Vercel SPA routing, and resilient CORS headers.

---

## 📋 Table of Contents
1. [Pre-Deployment Checklist](#1-pre-deployment-checklist)
2. [Option 1: Render (1-Click Blueprint — Recommended)](#2-option-1-render-1-click-blueprint--recommended)
3. [Option 2: Render (Backend) + Vercel (Frontend)](#3-option-2-render-backend--vercel-frontend)
4. [Option 3: Railway (Single-Container Full-Stack)](#4-option-3-railway-single-container-full-stack)
5. [Option 4: Google Cloud Run or AWS App Runner](#5-option-4-google-cloud-run-or-aws-app-runner)
6. [Option 5: VPS with Docker Compose (AWS EC2 / DigitalOcean)](#6-option-5-vps-with-docker-compose-aws-ec2--digitalocean)
7. [Cloud Database Setup (PostgreSQL)](#7-cloud-database-setup-postgresql)
8. [AWS S3 Document Storage (Optional)](#8-aws-s3-document-storage-optional)
9. [Troubleshooting & FAQs](#9-troubleshooting--faqs)

---

## 1. Pre-Deployment Checklist

Before deploying, ensure you have the required API keys (all keys are optional; the platform gracefully falls back to local heuristic engines if omitted):

| Key / Variable | Source / Purpose | Required? |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) for deep AI resume scoring & roadmaps | Recommended (falls back to local NLP) |
| `RAPIDAPI_KEY` | [RapidAPI JSearch](https://rapidapi.com/letscrape-6bRwvSbBY3u/api/jsearch) for live India job listings | Recommended (falls back to portal search links) |
| `RAPIDAPI_HOST` | `jsearch.p.rapidapi.com` | If using RapidAPI |
| `DATABASE_URL` | PostgreSQL connection string (Supabase, Neon, Render Postgres) | Optional (defaults to persistent JSON store) |
| `REACT_APP_API_URL` | URL of your deployed backend API (e.g. `https://resume-api.onrender.com`) | Only if frontend is hosted separately |

---

## 2. Option 1: Render (1-Click Blueprint — Recommended)

Render provides free hosting for both the Python FastAPI backend and the static React frontend, pre-configured in `render.yaml`.

### Step-by-Step:
1. Push your repository to **GitHub**.
2. Sign in to [Render](https://dashboard.render.com/).
3. Click **New +** > **Blueprint**.
4. Connect your GitHub repository.
5. Render will detect `render.yaml` and configure:
   - **`resume-analyzer-api`**: FastAPI Web Service (`backend/`)
   - **`resume-analyzer-web`**: React Static Site (`frontend/`)
6. Enter your secret keys when prompted:
   - `GEMINI_API_KEY`
   - `RAPIDAPI_KEY`
7. Click **Apply**.
8. Render will build and deploy both services automatically!

---

## 3. Option 2: Render (Backend) + Vercel (Frontend)

This is the most popular decoupled architecture (FastAPI on Render + React on Vercel).

### Part A: Deploy Backend to Render
1. Go to [Render Dashboard](https://dashboard.render.com/) > **New +** > **Web Service**.
2. Connect your GitHub repo.
3. Configure the service:
   - **Name:** `resume-analyzer-api`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install --no-cache-dir -r requirements.txt && python train_role_model.py`
   - **Start Command:** `gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT --timeout 120 main:app`
   - **Health Check Path:** `/health`
4. Add Environment Variables in the Render dashboard:
   - `APP_ENV` = `production`
   - `GEMINI_API_KEY` = `your_gemini_api_key`
   - `RAPIDAPI_KEY` = `your_rapidapi_key`
   - `RAPIDAPI_HOST` = `jsearch.p.rapidapi.com`
   - `CORS_ORIGIN_REGEX` = `^https:\/\/.*\.vercel\.app$`
5. Click **Deploy Web Service** and copy your backend URL (e.g. `https://resume-analyzer-api.onrender.com`).

### Part B: Deploy Frontend to Vercel
1. Go to [Vercel Dashboard](https://vercel.com/) > **Add New...** > **Project**.
2. Import your GitHub repo.
3. Configure project settings:
   - **Framework Preset:** `Create React App`
   - **Root Directory:** `frontend` (or click Edit and select `frontend`)
4. In **Environment Variables**, add:
   - `REACT_APP_API_URL` = `https://resume-analyzer-api.onrender.com` (your Render backend URL)
5. Click **Deploy**.
6. When Vercel finishes, open your app URL. Both frontend and backend are live!

---

## 4. Option 3: Railway (Single-Container Full-Stack)

Railway can deploy the entire full-stack application as a single Docker container using the root `Dockerfile`.

1. Go to [Railway.app](https://railway.app/) and create a new project.
2. Select **Deploy from GitHub repo**.
3. Railway automatically detects `railway.json` and the root `Dockerfile`.
4. Add environment variables in the Railway dashboard:
   - `GEMINI_API_KEY`
   - `RAPIDAPI_KEY`
   - `RAPIDAPI_HOST=jsearch.p.rapidapi.com`
5. Click **Generate Domain**.
6. Railway will build the React frontend and Python backend into a single container and serve both on your generated URL!

---

## 5. Option 4: Google Cloud Run or AWS App Runner

Both Google Cloud Run and AWS App Runner support serverless container execution from the root multi-stage `Dockerfile`.

### Build & Deploy with Google Cloud Run:
```bash
# 1. Build and push to Google Artifact Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/resume-analyzer

# 2. Deploy to Cloud Run
gcloud run deploy resume-analyzer \
  --image gcr.io/YOUR_PROJECT_ID/resume-analyzer \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --port 8000 \
  --set-env-vars GEMINI_API_KEY=your_key,RAPIDAPI_KEY=your_key
```

---

## 6. Option 5: VPS with Docker Compose (AWS EC2 / DigitalOcean)

To run the application on any Linux virtual machine (Ubuntu, Debian, Amazon Linux):

1. SSH into your server:
   ```bash
   ssh ubuntu@your-server-ip
   ```
2. Clone your repository:
   ```bash
   git clone https://github.com/your-username/Resume-scanner-.git
   cd Resume-scanner-
   ```
3. Create your production environment file `backend/.env`:
   ```bash
   cp backend/.env.example backend/.env
   nano backend/.env
   ```
4. Start both frontend and backend in detached mode:
   ```bash
   docker compose up -d --build
   ```
5. Check service logs and health status:
   ```bash
   docker compose ps
   docker compose logs -f backend
   ```
   - Frontend is accessible on port `3000` (e.g. `http://your-server-ip:3000`).
   - Backend API is accessible on port `8000` (e.g. `http://your-server-ip:8000`).

---

## 7. Cloud Database Setup (PostgreSQL)

By default, the backend operates in zero-dependency mode using a file-backed JSON store for registered users and platform metrics.

To connect a cloud PostgreSQL database (e.g. **Supabase**, **Neon**, **Render Postgres**, **AWS RDS**):

1. Provision a free PostgreSQL database on [Supabase](https://supabase.com/) or [Neon](https://neon.tech/).
2. Copy the connection URI:
   ```text
   postgresql://postgres:yourpassword@db.supabase.co:5432/postgres
   ```
3. Set the `DATABASE_URL` environment variable in your cloud backend dashboard:
   ```text
   DATABASE_URL=postgresql://postgres:yourpassword@db.supabase.co:5432/postgres
   ```
4. When the backend starts, it runs `database.init_db()` automatically to create all tables (`users`, `user_sessions`, `analysis_records`, `platform_metrics`).
5. (Optional) Run the migration script to copy existing local JSON user accounts to PostgreSQL:
   ```bash
   python backend/migrate_json_to_db.py
   ```

---

## 8. AWS S3 Document Storage (Optional)

To store uploaded PDF resumes or generated reports in an Amazon S3 bucket with private ACL and presigned download URLs:

1. Create an S3 bucket in your AWS account (e.g. `my-resume-analyzer-storage`).
2. Add the following environment variables to your backend:
   ```env
   AWS_S3_BUCKET_NAME=my-resume-analyzer-storage
   AWS_REGION=ap-south-1
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=wJalr...
   S3_PRESIGNED_URL_EXPIRES_SEC=900
   ```
3. The backend will automatically detect AWS S3 credentials and route file persistence through `s3_storage.py`.

---

## 9. Troubleshooting & FAQs

### Q1: I am getting a CORS error when the frontend calls the backend.
**Solution:**
- If using separate domains, set `CORS_ORIGINS` in your backend environment variables to include your frontend URL:
  `CORS_ORIGINS=https://your-frontend.vercel.app`
- For Vercel preview URLs, the backend already enables `CORS_ORIGIN_REGEX` (`^https:\/\/.*\.vercel\.app$`).
- Ensure `REACT_APP_API_URL` in the frontend does **not** have a trailing slash (e.g. `https://resume-api.onrender.com`).

### Q2: Why is the backend taking 50 seconds to respond on Render free tier?
**Explanation:** Render free tier spins down idle web services after 15 minutes of inactivity. The first request will wake up the instance (cold start). Subsequent requests respond in milliseconds.
**Workaround:** Use a free uptime monitor (e.g., [UptimeRobot](https://uptimerobot.com/)) to ping `https://your-api.onrender.com/health` every 10 minutes to keep it warm.

### Q3: Out of Memory (OOM) error during container startup.
**Solution:**
The backend has been configured to use `WORKERS=2` by default. If deploying to instances with less than 512MB RAM, set the environment variable `WORKERS=1`.

### Q4: How do I test the cloud setup locally before pushing?
Run Docker Compose locally:
```bash
docker compose up --build
```
Then visit `http://localhost:3000` in your browser.

