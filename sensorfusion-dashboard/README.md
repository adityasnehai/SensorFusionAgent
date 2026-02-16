# SensorFusion Dashboard (Frontend)

This is the Next.js frontend for SensorFusionAgent.

## Run

```bash
cd /home/aditya/projects/SensorFusionAgent/sensorfusion-dashboard
npm install
npm run dev
```

Open `http://localhost:3000`.

Backend should run at `http://localhost:8000` (see root README).

## Environment (optional)

Create from template:

```bash
cp .env.local.example .env.local
```

Then edit `.env.local` in this folder:

```env
NEXT_PUBLIC_FUSE_API_URL=http://localhost:8000/fuse
NEXT_PUBLIC_FUSE_API_BASE=http://localhost:8000
```

## Build

```bash
npm run build
npm run start
```

## Main UI Flow

- `/`: upload datasets and start async fusion job
- `/results`: poll job progress and render analytics panels

For full project setup, backend APIs, dataset structures, and metrics, read:
- `/home/aditya/projects/SensorFusionAgent/README.md`
