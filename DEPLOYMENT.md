# WiFrost TVWS Coverage Planning Tool — Deployment Guide

This guide describes how to deploy the **FastAPI Backend** to Google Cloud Run and the **Next.js Frontend** to Firebase Hosting.

---

## 1. Prerequisites

Ensure you have installed:
*   [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)
*   [Firebase CLI](https://firebase.google.com/docs/cli)
*   Node.js (v18+) and npm
*   Python (3.9+)

Make sure you are logged in to your Google and Firebase accounts:
```bash
gcloud auth login
firebase login
```

---

## 2. Deploy Backend to Google Cloud Run

The backend is packaged as a Docker container. You can deploy it using Google Cloud Build (recommended) or build/push it manually.

### Option A: Deploy via Google Cloud Build (Recommended)
Run the following command from the project root directory (replacing `YOUR_PROJECT_ID` with your Google Cloud Project ID):
```bash
gcloud builds submit --config cloudbuild.yaml --project=YOUR_PROJECT_ID
```
This triggers a remote build and deploys the backend as `wifrost-backend` in the `us-central1` region. Once done, it will output a Cloud Run Service URL (e.g., `https://wifrost-backend-xxxxx-uc.a.run.app`).

### Option B: Deploy Manually
If you want to deploy directly using the local Docker daemon:
```bash
# Build the container
docker build -t gcr.io/YOUR_PROJECT_ID/wifrost-backend .

# Push the container
docker push gcr.io/YOUR_PROJECT_ID/wifrost-backend

# Deploy to Cloud Run
gcloud run deploy wifrost-backend \
  --image gcr.io/YOUR_PROJECT_ID/wifrost-backend \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated
```

### Environment Variables
Configure your active API keys on Google Cloud Run:
1. Go to the **Google Cloud Console** -> **Cloud Run** -> **wifrost-backend**.
2. Click **Edit & Deploy New Revision**.
3. Under **Variables**, add:
   *   `OPENTOPOGRAPHY_API_KEY`: Your OpenTopography API key for SRTM elevation profiles.
   *   `GEMINI_API_KEY`: Your Google Gemini API key.
   *   `FIREBASE_HOSTING_DOMAIN`: Your Firebase Hosting URL (e.g., `https://wifrost-coverage.web.app`) to authorize CORS.

---

## 3. Deploy Frontend to Firebase Hosting

The frontend is built as a static site and deployed to Firebase Hosting.

### Step 1: Initialize Firebase (First Time Only)
Navigate to the `frontend/` directory and associate it with your Firebase project:
```bash
cd frontend
firebase init hosting
```
*   Select **Use an existing project** and choose your project.
*   For "What do you want to use as your public directory?", type `out`.
*   For "Configure as a single-page app?", type `y`.
*   For "Set up automatic builds and deploys with GitHub?", type `n`.
*   For "File out/index.html already exists. Overwrite?", type `n`.

This will ensure the `firebase.json` and `.firebaserc` are configured correctly.

### Step 2: Build the Static Site
Build and export the Next.js static site:
```bash
npm run build
```
This compiles the pages and outputs them into the `frontend/out/` directory.

### Step 3: Deploy to Firebase Hosting
Deploy the static files to Firebase Hosting:
```bash
firebase deploy --only hosting
```
Once deployed, Firebase will output your hosting URL (e.g., `https://YOUR_PROJECT_ID.web.app`).

---

## 4. Troubleshooting

*   **CORS Blocked Errors**: Ensure that the `FIREBASE_HOSTING_DOMAIN` environment variable is set on your Cloud Run backend to allow requests from your Firebase URL.
*   **Leaflet Map Tiles Failing to Load**: Leaflet requires internet access to fetch CartoDB tiles. Verify client network connection.
*   **Missing Elevation Profiles**: Make sure the `OPENTOPOGRAPHY_API_KEY` environment variable is correctly configured on your Cloud Run backend.
