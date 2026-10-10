# Datasets and ground truth

Sparse3D works with any photos you provide and, for large collections already on disk, reads them in place.
Only the images chosen for an experiment are copied into its workspace, so a multi-gigabyte dataset is never duplicated.

## Where datasets are found

| Location | Purpose |
|---|---|
| `SPARSE3D_DATASET_DIR` | one or more folders (separated by `;` on Windows, `:` elsewhere), scanned recursively to a depth of six levels |
| `data/datasets/` | convenient place inside a checkout (git-ignored) |
| `data/samples/` | small samples shipped with the repository |

```powershell
# Windows
$env:SPARSE3D_DATASET_DIR = "D:\datasets"
python src/backend/app.py
```

Datasets show up in the web UI under **Upload images > Local dataset** and in `GET /api/datasets`.

## DTU MVS

Download the "SampleSet" or the full set from the [DTU Robot Image Data Sets](https://roboimagedata.compute.dtu.dk/?page_id=36)
page and unzip it anywhere below a dataset root. The following layout is recognised:

```
<anywhere>/MVS Data/
  Cleaned/scan1/clean_001_0_r5000.png   images: camera 001, lighting 0   (Rectified/scanN[_train]/rect_*.png also works)
  Calibration/cal18/pos_001.txt         3x4 projection matrix per camera  -> known camera poses
  Points/stl/stl001_total.ply           reference point cloud (millimetres) -> ground truth
```

For a DTU scan the server automatically

* offers its cameras and lighting conditions for selection,
* uses `stlNNN_total.ply` as ground truth (read in place, thinned to 400k points for evaluation),
* uses the calibration matrices as known camera poses: the reconstruction is aligned to the reference with the cameras,
  `camera_pose_error_deg` is measured, and Chamfer distance, F-score, completeness and accuracy are reported without any manual step.

Evaluation distances are expressed in units of the reference bounding-box diagonal and the F-score threshold is 2 % of it.
The reconstruction is cropped to the reference bounding box (plus 15 %) so background clutter is not counted as error.
This is not the official DTU benchmark protocol (which uses observation masks and a 0.2 mm resolution); it is a consistent
way to compare view counts, arrangements and methods against each other.

Command line:

```bash
python scripts/run_experiment.py --dataset-root D:/datasets --scan 1 --cameras 1,9,17,25 --views 4 --method both
```

Typical views for sparse-view studies: pick cameras that span the object (the UI's "evenly spaced" button) for a good
arrangement, and neighbouring cameras for a poor one.

## Your own photos

Upload 3 to 6 photos in the UI, or point the CLI at a folder. Any common format works (JPEG, PNG, BMP, WebP, TIFF; HEIC
with `pip install pillow-heif`). EXIF orientation is honoured, photos of different sizes are handled, and COLMAP uses
the EXIF focal length when present.

Tips: 60 to 80 % overlap between neighbouring views, a textured object, even lighting, no motion blur, and avoid pure
rotation of the camera in place. The validation step reports blur, brightness, feature counts and pairwise overlap
before you start.

To get quantitative metrics for your own object, put a reference model next to the photos as
`ground_truth.ply` (or `.obj` / `.stl`), or upload it with the experiment. Without a reference, only the
measurements that need none are reported (registration ratio, reprojection error, point count, runtime, floating artifacts).
