# 3D RECON LAB - frontend

React 18 + Vite + Tailwind CSS 3, react-router-dom, Three.js (`@react-three/fiber`, `@react-three/drei`), Chart.js (`react-chartjs-2`).
It codes against `docs/API_CONTRACT.md` and talks to the FastAPI backend.

## Commands

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
npm run build     # production build into frontend/dist
npm run preview   # serve dist (also proxies /api)
```

Set `VITE_BACKEND_URL` to proxy the dev server to a different backend (default `http://127.0.0.1:8000`).

## Pointing the UI at another backend (e.g. Colab)

Open **Settings**, enter the API base URL (for example a tunnel URL), press **Test connection** (calls `GET /api/health`) and **Save**.
The value is stored in `localStorage` under `sparse3d.apiBase`; empty means same origin (the dev proxy). The remote server must allow CORS.

## Mock mode (no backend needed)

Add `?mock=1` to any URL (for example `http://localhost:5173/?mock=1`) or start with `VITE_MOCK=1 npm run dev`.
The flag is remembered for the browser session; `?mock=0` turns it off. All mock data lives in `src/services/mock.js` and is
illustrative only: real pages never contain sample numbers. Handy mock checks: `EXP-MOCK01` (full metrics), `EXP-MOCK02` (no ground
truth, neural failed), `EXP-MOCK03` (failed), and a filename containing `bad` makes `/api/validate` return an error.

## Local datasets

On **Upload**, the source switch "Local dataset" lists `GET /api/datasets`. Pick a scan (and a lighting condition for DTU scans), then click
3 to 6 camera thumbnails (the badge number is the capture order) or use "Pick evenly spaced" (the scan's `default_cameras`). Only the 320 px
thumbnails from `GET /api/datasets/{id}/{scan}/images` are loaded in the browser. The selection feeds `/api/validate`, `/api/jobs`
(`dataset_id`, `scan_id`, `cameras`, `lighting`, `use_dataset_ground_truth`) and the sweep panel on the Analysis page. A ground-truth file chosen
on the Configuration page overrides the dataset's reference model (the UI then sends `use_dataset_ground_truth=false`).
The mock layer has a fake DTU dataset ("DTU MVS (mock)", scans 1 and 4) and a plain folder ("my_mug"); `EXP-MOCK01` is a DTU job with measured pose error.

Image uploads accept JPG, PNG, BMP, WebP and TIFF only (no RAW, no HEIC/HEIF).

## Execution target (Colab GPU worker)

**Settings > Execution** binds to `GET/PUT /api/execution` (polled every 5 s while the page is open): "This computer", "Colab GPU worker"
or "Automatic" (default), live status chips for this computer and the worker, and the `reason` line. When the worker is selected (or Automatic)
and not connected, a numbered panel built from `colab.steps` offers "Open notebook in Colab", "Download notebook" (`/api/colab/notebook` via the
API base) and a "Connection code" field (`S3D1.…`, Paste / Connect). The server's `detail` is shown if connecting fails; a Disconnect button
(`DELETE /api/execution/remote`) appears once connected. **Configuration** shows a "Runs on" banner and uses `capabilities` from
`/api/execution` to enable the Neural / Both cards. Jobs whose `execution.target` is `remote` get a "Colab GPU" badge.
In mock mode: any code starting with `S3D1.` connects a fake "Tesla T4" worker (a code containing "unreachable" returns a 502-style error), and
this computer is mocked as having no GPU and no neural backend, so the whole flow can be tried with `?mock=1`.

## Layout

```
src/
  App.jsx, main.jsx, index.css
  components/{layout,upload,experiment,viewer,charts,ui}
  pages/        Landing, Dashboard, Upload, Configuration, Processing, Viewer3D, Evaluation, Comparison, Analysis, History, Settings
  services/     api.js (all fetch, base URL), experimentService.js, reconstructionService.js, evaluationService.js, mock.js
  hooks/        useExperiment (1.5s job polling), useUpload (wizard context), useHealth, useAnalysis, useAsync
  utils/        constants.js, formatters.js, metrics.js
```

Routes: `/`, `/dashboard`, `/upload`, `/configuration`, `/processing/:jobId?`, `/viewer/:jobId?`, `/evaluation/:jobId?`,
`/comparison/:jobId?`, `/analysis` (optional `?group=GRP-...`), `/history`, `/settings`.

The wizard state (files or example set, configuration, current job id) lives in a React context; the current job id is also kept in
`sessionStorage` (`sparse3d.jobId`) so a refresh keeps it. Selected files cannot survive a refresh.
