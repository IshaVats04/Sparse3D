# 3D RECON LAB — REST API contract

Base URL: `http://127.0.0.1:8000` (configurable in the UI, so the same frontend can talk to a Colab-hosted backend).
All responses are JSON unless a file is noted. Errors: `{"detail": "message"}` with a 4xx/5xx status.

Nothing in this API returns invented numbers. A metric that cannot be measured (for example Chamfer
distance without a ground-truth model) is `null` and the UI must show "n/a" with the `metrics_note`.

## Health

`GET /api/health`
```json
{
  "status": "healthy", "app_name": "3D RECON LAB", "version": "3.0.0",
  "environment": {
    "python_version": "3.14.7", "platform": "win32",
    "colmap_available": true, "colmap_path": "…", "colmap_cuda": true,
    "torch_available": false, "neural_available": false, "neural_reason": "PyTorch is not installed",
    "cuda_available": false, "device": "cpu",
    "active_jobs_count": 0
  }
}
```

## Execution target (local machine or a remote GPU worker such as Google Colab)

Experiments run on this machine, or on a remote worker (the same backend started in a Colab notebook). The user connects
a worker by pasting the single **connection code** printed by the notebook (`S3D1.` followed by base64 text). The backend
then forwards jobs to the worker, mirrors progress and logs into the local job, and downloads the finished files, so the
rest of the UI works unchanged on local job ids.

`GET /api/execution`
```json
{
  "mode": "auto",                       // "auto" | "local" | "remote"
  "effective": "remote",                // where a new experiment would run right now
  "reason": "This machine has no GPU; using the connected remote worker",
  "local":  {"gpu": false, "colmap_available": true, "colmap_gpu_usable": false,
             "neural_available": false, "neural_backend": null, "neural_reason": "weights not reachable"},
  "remote": {"configured": true, "connected": true, "host": "abc-def.trycloudflare.com",
             "gpu": true, "gpu_name": "Tesla T4", "colmap_available": true, "colmap_gpu_usable": true,
             "neural_available": true, "neural_backend": "vggt", "neural_reason": null,
             "error": null, "checked_at": "2026-10-11 10:00:00"},   // remote is null when nothing is connected
  "capabilities": {"gpu": true, "colmap_available": true, "colmap_gpu_usable": true,
                   "neural_available": true, "neural_backend": "vggt", "neural_reason": null},   // of the effective target
  "colab": {
    "notebook_open_url": "https://colab.research.google.com/github/IshaVats04/Sparse3D/blob/main/notebooks/02_colab_backend.ipynb",
    "notebook_download_url": "/api/colab/notebook",
    "steps": ["Open the notebook in Colab", "Runtime > Change runtime type > T4 GPU", "Runtime > Run all",
              "Wait for the last cell to print a connection code (starts with S3D1.)", "Paste the code below and press Connect"]
  }
}
```
`mode`: `local` always runs here; `remote` always uses the worker (experiment creation fails with 409 if none is
connected); `auto` uses the worker when one is connected and this machine has no GPU, otherwise runs here.

`PUT /api/execution` with JSON `{"mode": "auto", "connection_code": "S3D1.…"}` (`connection_code` optional; omit to keep the
current worker). The worker is contacted before the code is accepted: `400` for a malformed code, `502` with a readable
`detail` if the worker cannot be reached or rejects the token. Returns the same body as `GET`.

`DELETE /api/execution/remote` disconnects the worker and returns the same body.

`GET /api/colab/notebook` returns the notebook file (`.ipynb`) for users who prefer uploading it to Colab.

Jobs gain `"execution": {"target": "local" | "remote", "remote_job_id": "EXP-…" | null}`. While a remote job runs, its
`logs`, `stage`, `stages` and `progress` mirror the worker's; finished jobs behave like local ones.

`GET /api/health` `environment` gains `neural_backend` (`"vggt"`, `"depth_fusion"` or `null`).
`POST /api/jobs` gains optional `gt_projections` (JSON object: image name to 3x4 matrix) used by remote workers.

## Examples (bundled sample image sets)

`GET /api/examples` → `[{"id": "dtu_scan1_6views", "name": "DTU scan1 (6 views)", "images": [{"name": "image_001.png", "url": "/api/examples/dtu_scan1_6views/image_001.png"}]}]`

`GET /api/examples/{id}/{name}` → image file.

## Local datasets (large collections such as the DTU MVS dataset)

The server scans `SPARSE3D_DATASET_DIR` (one or more folders, separated by `;` on Windows / `:` elsewhere), `data/datasets`
and `data/samples`. Datasets are read in place; only the images chosen for an experiment are copied.

`GET /api/datasets` →
```json
[{"id": "dtu-3fa9c1d2", "kind": "dtu", "name": "DTU MVS (MVS Data/Cleaned)",
  "scans": [{"id": "scan1", "name": "Scan 1", "image_count": 343, "cameras": [1, 2, 3], "lightings": [0, 1, 2],
             "has_ground_truth": true, "has_camera_poses": true, "default_cameras": [1, 10, 20, 30, 40, 49]}]},
 {"id": "folder-91ab33c0", "kind": "folder", "name": "my_mug",
  "scans": [{"id": "all", "name": "my_mug", "image_count": 8, "cameras": [], "lightings": [],
             "has_ground_truth": false, "has_camera_poses": false, "default_cameras": []}]}]
```
`kind: "dtu"` scans have camera ids and lightings; `kind: "folder"` is any directory of photos (it may hold a
`ground_truth.ply|obj|stl`).

`GET /api/datasets/{dataset_id}/{scan_id}/images?lighting=0&limit=200` →
`[{"name": "clean_001_0_r5000.png", "camera": 1, "lighting": 0, "url": "/api/datasets/…/image/clean_001_0_r5000.png?thumb=1"}]`
(`url` is a 320 px JPEG thumbnail; drop `?thumb=1` for the original).

`POST /api/validate`, `POST /api/jobs` and `POST /api/experiments/sweep` accept, instead of `images`/`example_id`:

| field | type | notes |
|---|---|---|
| `dataset_id` | string | from `/api/datasets` |
| `scan_id` | string | scan id (`all` for folders) |
| `cameras` | string | comma-separated camera ids, in capture order (DTU). Empty → `default_cameras` |
| `lighting` | int | DTU lighting condition, default 0 |
| `use_dataset_ground_truth` | bool | default true; attaches the scan's reference cloud |

When the dataset has ground truth, Chamfer / F-score / completeness / accuracy are computed automatically; when it has
camera poses, `camera_pose_error_deg` is computed and the reconstruction is aligned to the reference with the known
cameras. The job JSON gains `dataset` (`{id, kind, name, scan, cameras, lighting}` or `null`),
`ground_truth_source` (file name or `null`) and `known_camera_poses` (count).

## Image validation (before reconstruction)

`POST /api/validate` — multipart, field `images` (repeated), optional form `example_id` instead of files.
```json
{
  "image_count": 4, "can_proceed": true,
  "images": [{
    "name": "front.jpg", "width": 1600, "height": 1200,
    "blur_score": 182.4, "brightness": 121.0, "keypoints": 2310,
    "status": "ok",                         // "ok" | "warn" | "error"
    "issues": ["Image looks blurry"]        // empty when ok
  }],
  "pairs": [{"a": "front.jpg", "b": "back.jpg", "matches": 14, "overlap_pct": 6.2, "warning": true}],
  "messages": [{"level": "ok|warn|error", "text": "Feature points detected in all images"}]
}
```

## Jobs

`POST /api/jobs` — multipart form. `202 Accepted` → `{"job_id": "EXP-AB12CD", "status": "queued", "message": "…"}`

| field | type | default | notes |
|---|---|---|---|
| `images` | file[] | – | 3–6 files; or use `example_id` |
| `example_id` | string | – | use a bundled sample set instead of uploads |
| `project_name` | string | `Experiment` | |
| `object_category` | string | `General Object` | |
| `recon_method` | `classical` \| `neural` \| `both` | `both` | |
| `num_views` | int 3–6 | number of images | if fewer than the number of images uploaded, a subset is chosen using `view_arrangement` |
| `view_arrangement` | `auto` \| `uniform` \| `non_uniform` \| `high_overlap` \| `low_overlap` \| `random` | `auto` | `auto` uses every image given |
| `quality` | `fast` \| `standard` \| `high` | `standard` | maps to max image size and feature count |
| `estimate_poses` | bool | `true` | export camera poses |
| `run_evaluation` | bool | `true` | compute metrics |
| `generate_mesh` | bool | `false` | textured/coloured mesh output |
| `save_intermediate` | bool | `false` | keep COLMAP database / sparse model |
| `mesh_method` | `ball_pivoting` \| `poisson` \| `none` | `poisson` | used when `generate_mesh` is true |
| `ground_truth` | file (.ply/.obj/.stl) | – | optional reference model; enables Chamfer / F-score / completeness / accuracy |
| `group_id` | string | – | set by the sweep endpoint |

`GET /api/jobs/{job_id}` → **Job**

```json
{
  "job_id": "EXP-AB12CD", "project_name": "Vase_Experiment_01", "object_category": "Vase",
  "status": "queued|processing|completed|partial_success|failed|cancelled",
  "stage": "image_analysis|feature_extraction|camera_pose|reconstruction|evaluation|complete|failed",
  "progress": 60,
  "stages": [
    {"key": "image_analysis",     "label": "Image Analysis",        "status": "complete"},
    {"key": "feature_extraction", "label": "Feature Extraction",    "status": "complete"},
    {"key": "camera_pose",        "label": "Camera Pose Estimation","status": "running"},
    {"key": "reconstruction",     "label": "3D Reconstruction",     "status": "pending"},
    {"key": "evaluation",         "label": "Evaluation",            "status": "pending"}
  ],
  "created_at": "2026-10-10 12:14:21", "start_time": "…|null", "end_time": "…|null",
  "elapsed_sec": 134.2, "eta_sec": 250.0,
  "image_count": 5,
  "images": [{"name": "front.jpg", "url": "/api/jobs/EXP-AB12CD/images/front.jpg"}],
  "configuration": {"recon_method": "both", "num_views": 5, "view_arrangement": "auto", "quality": "standard",
                    "estimate_poses": true, "run_evaluation": true, "generate_mesh": false, "save_intermediate": false,
                    "mesh_method": "poisson", "object_category": "Vase", "selected_images": ["front.jpg"]},
  "logs": ["[12:14:21] [INFO] Loading images…"],
  "warnings": [],
  "error_message": null,
  "validation": { "…": "same shape as POST /api/validate" },
  "group_id": null,
  "has_ground_truth": false,
  "results": {"classical": MethodResult | null, "neural": MethodResult | null},
  "comparison": {"chamfer_pct": -32.1, "f_score_pct": 10.0, "…": "…"} | null
}
```

**MethodResult**
```json
{
  "status": "completed|failed|unavailable|skipped",
  "message": "human readable reason when not completed",
  "label": "Classical (COLMAP + Open3D)",
  "runtime_sec": 98.3,
  "files": {"point_cloud": "/api/jobs/ID/files/point_cloud|null", "mesh": "…|null", "camera_poses": "…|null"},
  "point_count": 15420,
  "mesh": {"vertex_count": 590, "triangle_count": 715},
  "registration": {"total_input": 5, "registered": 5, "ratio_pct": 100.0, "names": ["front.jpg"], "mean_reprojection_error_px": 0.82},
  "cameras": [{"name": "front.jpg", "position": [0.1, -3.6, 1.5], "rotation": [0.99, 0.01, 0.05, 0.0]}],
  "metrics": {
    "chamfer_distance": 0.0128, "f_score": 0.874, "completeness_pct": 89.2, "accuracy": 0.861,
    "camera_pose_error_deg": 2.4, "runtime_sec": 98.3, "point_count": 15420,
    "reprojection_error_px": 0.82, "registration_ratio_pct": 100.0, "floating_artifact_pct": 3.1
  },
  "metrics_note": "Chamfer distance, F-score, completeness and accuracy need a ground-truth model. Upload one to enable them.",
  "error_histogram": {"bins": [0.0, 0.03, 0.06], "counts": [12, 35]} | null
}
```
`cameras[].position` is the camera centre in the reconstruction's world frame; `cameras[].rotation` is the camera-to-world
quaternion `[w, x, y, z]` in COLMAP convention (camera looks along +z, +y points down). The reconstruction frame is arbitrary
(SfM is only defined up to a similarity transform), so clouds from COLMAP usually appear Y-down.

`chamfer_distance`, `f_score`, `completeness_pct`, `accuracy` are `null` unless `has_ground_truth`.
`camera_pose_error_deg` is `null` unless ground-truth poses are known. `floating_artifact_pct`, `reprojection_error_px`,
`registration_ratio_pct`, `runtime_sec`, `point_count` are always measured (when the stage ran).

`GET /api/jobs` → `[{job_id, project_name, object_category, status, stage, created_at, image_count, num_views, view_arrangement, recon_method, group_id, dataset, f_score, chamfer, runtime_sec}]`
(`dataset` is `{id, kind, name, scan, cameras, lighting}` or `null`; `scan` is the scan id such as `"scan1"`, `name` is the dataset's display name.)
If both an uploaded `ground_truth` file and a dataset reference model are available, the uploaded file is used.
(`f_score`/`chamfer` come from the best available method, `null` when no ground truth).

`GET /api/jobs/{job_id}/report` → full report JSON. `DELETE /api/jobs/{job_id}`. `POST /api/jobs/{job_id}/cancel`.

`GET /api/jobs/{job_id}/images/{name}` → input image file.

`GET /api/jobs/{job_id}/files/{file_type}` → file download. `file_type` ∈
`point_cloud`, `mesh`, `neural_point_cloud`, `neural_mesh`, `report`, `metrics_csv`, `camera_poses`.
PLY files are served as `application/octet-stream` and can be loaded with three.js `PLYLoader`.

## Sweep (the paper's central experiment)

`POST /api/experiments/sweep` — multipart, same fields as `POST /api/jobs` plus `view_counts` (default `3,4,5,6`)
and `arrangements` (comma list, default the single `view_arrangement`). Needs at least `max(view_counts)` images.
Returns `{"group_id": "GRP-1A2B3C", "job_ids": ["EXP-…", …]}`; each child is an ordinary job with `group_id` set.

## Analysis (aggregated from real finished jobs)

`GET /api/analysis?group_id=GRP-…` (group_id optional → all completed jobs)
```json
{
  "has_data": true,
  "view_count": [{"views": 3, "classical": {"chamfer_distance": null, "f_score": null, "completeness_pct": null, "runtime_sec": 42.1,
                   "registration_ratio_pct": 66.7, "point_count": 301, "reprojection_error_px": 1.1, "floating_artifact_pct": 4.0, "runs": 1},
                  "neural": {"…": "…"} | null}],
  "arrangement": [{"arrangement": "uniform", "classical": {"…": "…"}, "neural": {"…": "…"} | null}],
  "failures": [{"job_id": "EXP-…", "num_views": 3, "view_arrangement": "low_overlap", "method": "classical", "reason": "Only 2 of 3 views registered"}],
  "insights": ["Registration ratio rises from 66.7% at 3 views to 100% at 6 views."]
}
```
Values are averages over runs with that setting; `null` when not measurable. `insights` are generated from the data only.

## Settings

The frontend stores the API base URL in `localStorage` (`sparse3d.apiBase`) so it can point at a Colab-hosted backend.
