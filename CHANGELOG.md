# Changelog

## 0.3.0

### Added
- React + Vite + Tailwind web UI (upload, configuration, live processing, Three.js viewer, metrics, comparison, analysis, history).
- Image quality and pairwise-overlap analysis before reconstruction.
- View-count and view-arrangement experiments, including a sweep endpoint.
- Neural method: pretrained monocular depth fused with the SfM poses.
- Evaluation: Chamfer distance, F-score, completeness, accuracy, floating-artifact estimate, camera pose error.
- Local dataset support (DTU MVS and plain image folders) with automatic ground-truth cloud and camera poses.
- SQLite experiment history and aggregated analysis.
- Google Colab notebook that runs the backend on a GPU.
- Retry strategy for structure-from-motion so a wider range of photo sets reconstructs.
- Remote GPU worker: Settings > Execution, a one-paste connection code, automatic routing when this machine has no GPU,
  live progress mirroring and result download. The Colab notebook is fully prewritten.
- VGGT feed-forward neural backend: reconstructs from 3-6 unposed photos without COLMAP (neural-only runs need no COLMAP).

### Changed
- Metrics are measured, never estimated; anything that needs a reference is `null` without one.
- COLMAP is located through `SPARSE3D_COLMAP`, `tools/colmap` or `PATH` (no machine-specific paths).
- Sparse-friendly COLMAP mapper settings (6 of 6 DTU views register, previously 5 of 6).
- Job data lives outside OneDrive-synced folders by default.

### Removed
- Hard-coded benchmark numbers and placeholder camera poses.
- Superseded standalone scripts, the vanilla JS frontend and generated review reports.
