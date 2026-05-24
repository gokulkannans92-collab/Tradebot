# Backend

This folder contains a self-contained backend package copied from the existing TradeBot source.
It can be uploaded to Oracle Cloud as a standalone backend deployment root without requiring the original repository root.

## What is included

- `src/` — full application source copied from the root project
- `Dockerfile` — local backend Docker build file
- `docker-compose.yml` — launches the backend using the current backend folder
- `requirements.txt` — dependency manifest copied from the root project
- `.dockerignore` — copied from the root Docker ignore rules
- `data/.env.example` — application runtime config template
- `.env.example` — Docker/backend runtime environment template
- `.gitignore` — ignores local secrets and logs
- `run_backend.ps1` — Windows helper to start the backend
- `run_backend.sh` — Unix helper to start the backend

## Usage

1. Copy the example env file:
   ```powershell
   Copy-Item .env.example .env
   ```
   or on Bash:
   ```bash
   cp .env.example .env
   ```

2. Edit `backend/.env` and set at least:
   - `JWT_SECRET_KEY`
   - `API_ALLOWED_ORIGINS`
   - `ENVIRONMENT=production`

3. Ensure the `data/` and `logs/` folders exist:
   ```powershell
   New-Item -ItemType Directory -Force data,logs
   ```
   or
   ```bash
   mkdir -p data logs
   ```

4. Start the backend locally:
   ```powershell
   .\run_backend.ps1
   ```
   or
   ```bash
   ./run_backend.sh
   ```

5. Or start with Docker Compose:
   ```bash
   docker compose up --build
   ```

## Oracle Cloud Deployment Guide

This folder is self-contained and can be uploaded as the backend root for Oracle Cloud deployment.

1. Upload the `backend/` folder to your Oracle Cloud environment.
2. Copy `backend/.env.example` to `backend/.env` and populate it with production values.
3. Confirm `backend/data` and `backend/logs` exist inside the upload target.
4. Build the container in Oracle Cloud:
   ```bash
   docker build -t tradebot-backend .
   ```
5. Run the backend container:
   ```bash
   docker run -d --name tradebot-backend \
     -p 8000:8000 \
     --env-file .env \
     -v "$PWD/data:/app/data" \
     -v "$PWD/logs:/app/logs" \
     tradebot-backend:latest
   ```

If you prefer Docker Compose on Oracle Cloud, use:
```bash
docker compose up --build -d
```

## Notes

- The backend is now self-contained inside `backend/`.
- `Dockerfile` and `docker-compose.yml` are both configured to use the local `backend/` folder.
- `.gitignore` already excludes `.env`, `data/.env`, and `logs/` so secrets and runtime files stay local.
