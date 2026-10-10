# Methodology

## Problem statement

3D reconstruction normally needs many overlapping views to estimate camera poses, depth and geometry. With only 3 to 6
ordinary photographs, insufficient coverage and overlap cause ambiguous geometry, inaccurate depth and pose estimates,
incomplete surfaces, floating artifacts and distortions. Existing sparse-view methods use geometric constraints, learned
priors, semantic information or generative models, and their performance depends on the number and arrangement of views.
This framework reconstructs from 3 to 6 photographs and measures how view count and viewpoint arrangement affect quality,
completeness, accuracy and cost.

Research questions: RQ1 (3 to 6 views), RQ2 (arrangement / overlap), RQ3 (classical vs learned), RQ4 (quality vs compute).

## Pipeline

1. **Image analysis**: resolution, blur (variance of the Laplacian), brightness, SIFT keypoints, near-duplicates, and pairwise
   overlap (ratio-test SIFT matches verified with a RANSAC fundamental matrix; overlap % = inliers / smaller keypoint set).
2. **View selection**: choose k of the n supplied images by arrangement (uniform, non-uniform, high/low overlap, random).
3. **Features and matching**: COLMAP SIFT + exhaustive matching, single shared camera.
4. **Camera poses**: COLMAP incremental mapper with relaxed thresholds for sparse input; the model with the most registered views is kept.
5. **Reconstruction**
   * Classical: dense MVS (PatchMatch + fusion) when COLMAP has CUDA and an NVIDIA GPU is present, otherwise the sparse SfM cloud; statistical outlier removal; optional Poisson / ball-pivoting meshing.
   * Neural (preferred, VGGT): one feed-forward pass over all views predicts camera poses, depth and confidence without SfM; depth is unprojected with the predicted cameras, low-confidence pixels (below the 30th percentile) are dropped, and the cloud is thinned to 400k points. Works when COLMAP cannot register the views.
   * Neural (fallback, depth fusion): pretrained monocular depth (Depth Anything V2 Small) -> per-view affine fit of inverse depth to the SfM points (robust least squares) -> back-projection with the SfM poses inside the region covered by SfM points -> fusion -> outlier removal.
6. **Evaluation** (below).

The classical method and the depth-fusion fallback share steps 1 to 4 (each method's runtime is the shared time plus its own); the VGGT backend needs only step 1.

## Metrics

With a ground-truth model the reconstruction is aligned to it (RMS-radius scale normalisation, FPFH + RANSAC, ICP) and all
distances are expressed in units of the ground-truth bounding-box diagonal.

* **Chamfer distance**: (mean accuracy distance + mean completeness distance) / 2.
* **Accuracy / precision**: fraction of reconstructed points within tau = 0.02 of the reference.
* **Completeness / recall**: percent of reference points within tau of the reconstruction.
* **F-score**: harmonic mean of precision and recall at tau.
* **Floating artifacts**: percent of points with fewer than 3 neighbours within 6x the median nearest-neighbour distance (no ground truth needed).
* **Registration ratio, reprojection error**: from the SfM model.
* **Pose error**: requires known camera poses; not computed yet.

Metrics that cannot be measured are reported as null, never estimated.

## Experiments

* **A: number of views**. Same object and pipeline, 3, 4, 5, 6 views (`POST /api/experiments/sweep`).
* **B: view arrangement**. Good vs poor arrangements for the same k.
* **C: classical vs neural**. Table of Chamfer, F-score, completeness, artifacts, runtime for 3 to 6 views.

For credible numbers use a controlled setup: objects with known geometry (rendered or scanned) plus a smartphone capture study.
