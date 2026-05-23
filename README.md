# TradeBot Frontend

This folder contains a self-contained web frontend for the TradeBot backend.
It mimics the native app GUI style using a dark card-based layout and connects to the backend API.

## Features

- Dark theme with TradeBot-style cards
- Login screen matching the desktop app aesthetic
- Dashboard skeleton with bot status and quick actions
- JWT authentication against `/api/auth/login`
- Fetches status from `/api/v1/status`

## Run locally

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Start the development server:

```bash
npm run dev
```

3. Open the local URL shown by Vite.

## Configuration

The app uses the environment variable `VITE_API_BASE_URL` to target the backend API.
By default it falls back to `http://localhost:8000`.

Example:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Deploy

This frontend is ready for static deployment on Vercel, Netlify, or any static host.
Build production assets with:

```bash
npm run build
```

Copy the contents of `dist/` to your hosting provider.
