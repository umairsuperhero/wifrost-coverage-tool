# WiFrost TVWS Coverage Tool — Deployment Guide

This guide describes the **live production setup** and how to reproduce it:

| Tier | Platform | Service | URL |
|------|----------|---------|-----|
| Backend (FastAPI) | **Google Cloud Run** | `wifrost-api` (`northamerica-south1`) | `https://wifrost-api-508425876629.northamerica-south1.run.app` |
| Frontend (Next.js) | **Vercel** | `wifrost-coverage-tool` | `https://wifrost-coverage-tool.vercel.app` |

Cloud Run scales to zero when idle (no fixed cost) and cold-starts in well under a
second, so no external keep-alive pinger is required.

---

## 1. Prerequisites

*   [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install) — or use [Cloud Shell](https://shell.cloud.google.com) (pre-authenticated, no local install)
*   A Google Cloud project with **Cloud Run** and **Cloud Build** APIs enabled
*   Node.js (v18+) and npm
*   Python (3.11+)

Authenticate (skip if using Cloud Shell):
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

---

## 2. Deploy the Backend to Google Cloud Run

The backend is packaged as a Docker container (`Dockerfile`). Cloud Run injects
`$PORT` at runtime; the container honours it (see `Dockerfile`).

### Option A — Cloud Build (recommended)
From the project root:
```bash
gcloud builds submit --config cloudbuild.yaml --project=YOUR_PROJECT_ID
```
This builds the image and deploys it as `wifrost-api` in `northamerica-south1`,
printing the public Service URL when done.

### Option B — One-shot source deploy
Cloud Run can build from source without a manual Docker step:
```bash
gcloud run deploy wifrost-api \
  --source . \
  --region northamerica-south1 \
  --platform managed \
  --allow-unauthenticated
```

### Environment variables
Set these on the Cloud Run service (Console → Cloud Run → `wifrost-api` →
Edit & Deploy New Revision → Variables, or via CLI):

| Variable | Purpose |
|----------|---------|
| `OPENTOPOGRAPHY_API_KEY` | SRTM elevation profiles (required for real terrain) |
| `GEMINI_API_KEY` | Google Gemini AI interpreter (optional) |
| `CORS_ORIGINS` | Comma-separated allowed frontends. Defaults to `*` if unset. Currently set to `https://wifrost-coverage-tool.vercel.app`. Set to `*` to also allow Vercel preview URLs. |

Update an env var from the CLI:
```bash
gcloud run services update wifrost-api \
  --region northamerica-south1 \
  --update-env-vars CORS_ORIGINS=*
```

> **Note — ephemeral storage.** Cloud Run's filesystem is in-memory and resets on
> every cold start / new revision. The SQLite simulation history (`/app/data`) and
> the `/api/stats` usage counter are therefore **not durable** across restarts. For
> durable usage analytics, rely on Vercel Analytics (frontend) rather than the
> backend counter.

---

## 3. Deploy the Frontend to Vercel

The frontend is a Next.js app on Vercel, auto-deployed from the `main` branch of
this GitHub repo.

### Backend URL configuration
`NEXT_PUBLIC_API_URL` is a build-time variable baked into the client bundle, so it
must be present **at build time**. This repo pins it in two committed files (no
Vercel dashboard variable is used), which Vercel reads automatically:

*   `frontend/.env.production`
*   `frontend/vercel.json` (`build.env.NEXT_PUBLIC_API_URL`)

To repoint the frontend at a different backend, edit **both** files, commit, and
push — Vercel rebuilds and the new URL is baked into the bundle. Changing it only in
the Vercel dashboard is insufficient because these committed files take precedence.

### Manual / first-time setup
```bash
cd frontend
vercel link          # associate the directory with the Vercel project
vercel --prod        # build & deploy to production
```

---

## 4. Troubleshooting

*   **CORS blocked errors** — Ensure `CORS_ORIGINS` on the Cloud Run service includes
    your frontend origin (or is `*`). Vercel *preview* deployments use random
    `*.vercel.app` subdomains, so only `*` allows them.
*   **Frontend still hitting the old backend** — `NEXT_PUBLIC_API_URL` is baked at
    build time. Confirm `frontend/.env.production` and `frontend/vercel.json` both
    point at the current backend, then trigger a fresh Vercel build.
*   **Leaflet map tiles failing to load** — Leaflet fetches CartoDB tiles over the
    network; verify client connectivity.
*   **Missing elevation profiles** — Confirm `OPENTOPOGRAPHY_API_KEY` is set on the
    Cloud Run service.
