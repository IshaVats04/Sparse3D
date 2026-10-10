# 3D Object Reconstruction from 2D Images

A research project for sparse-view 3D reconstruction using classical Structure-from-Motion (SfM) as a baseline.

## Research Goal

Build a system that can reconstruct a 3D object from a sparse set of ordinary 2D images (target: approximately 3–6 input images). This baseline uses COLMAP for Structure-from-Motion / Multi-View Stereo reconstruction and will inform future research into sparse-view reconstruction methods (SpaRP, UFORecon, SparseRecon).

## Baseline Methodology

**Baseline: Classical Structure-from-Motion / Multi-View Stereo reconstruction using COLMAP.**

### What is Structure-from-Motion (SfM)?

Structure-from-Motion is a computer vision technique that estimates 3D structure from a set of 2D images taken from different viewpoints. It simultaneously recovers:

- **Camera poses**: The position and orientation of each camera in 3D space
- **3D point cloud**: The 3D coordinates of feature points visible across multiple images

### Why Multiple Views are Needed

Multiple viewpoints are essential because:

1. **Triangulation**: A single 2D image cannot determine depth. Multiple views allow triangulation of 3D points.
2. **Feature matching**: Features must be visible in at least 2-3 images to be reconstructed.
3. **Coverage**: Different angles capture different parts of the object.

### What is Camera Pose Estimation?

Camera pose estimation determines:
- **Position**: Where the camera was in 3D space (X, Y, Z coordinates)
- **Orientation**: Which direction the camera was facing (rotation matrix or quaternion)

This is essential for knowing how all images relate to each other in 3D space.

### What is Feature Matching?

Feature matching identifies the same visual features (corners, edges, distinctive patterns) across multiple images. COLMAP uses SIFT (Scale-Invariant Feature Transform) features, which are robust to:
- Scale changes
- Rotation
- Illumination variations

### What is a Sparse Point Cloud?

A sparse point cloud is a set of 3D points representing the reconstructed geometry. "Sparse" means it contains only the key feature points used for reconstruction, not a dense surface. This is the first step before more advanced techniques (like Multi-View Stereo) can create dense reconstructions.

### Limitations with 3–6 Images

When only 3–6 images are available:

1. **Insufficient overlap**: Features may not be visible in enough images for reliable triangulation
2. **Poor coverage**: Some object parts may not be visible from any viewpoint
3. **Ambiguity**: Fewer constraints make the reconstruction problem more ill-posed
4. **Registration failure**: COLMAP may fail to register all cameras if features don't match well

This is the core challenge that sparse-view reconstruction research aims to address.

## System Architecture

```
                                  Sparse3D Architecture
                                  
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                                Modern Web UI                                     │
  │   - Image Uploader & Thumbnail Previews (Drag & Drop, format/count validation)   │
  │   - Reconstruction Configuration Panel (Mode, Resizing, BPA/Poisson Meshing)    │
  │   - Real-time Stage Progress Tracker & Live Execution Console                    │
  │   - Interactive Three.js WebGL 3D Point Cloud & Mesh Viewports                   │
  │   - Research Evaluation Metrics Dashboard & File Downloads                       │
  └────────────────────────────────────────┬─────────────────────────────────────────┘
                                           │  REST API (HTTP / JSON / Multipart)
                                           ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                            FastAPI Backend Application                           │
  │   - Health & Hardware Capabilities Endpoint (/api/health)                         │
  │   - Job Creation & Multipart Image Ingestion (/api/jobs)                         │
  │   - Asynchronous Job Execution (ThreadPoolExecutor Worker)                      │
  │   - Status Polling & Live Logs Endpoint (/api/jobs/{id})                         │
  │   - Secure File Serving Guard with Directory Traversal Prevention               │
  └────────────────────────────────────────┬─────────────────────────────────────────┘
                                           │  Job Isolation & Service Call
                                           ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                        Unified Reconstruction Service Engine                     │
  │                                                                                  │
  │  [Stage 1] Image Validation & Preprocessing (OpenCV / Aspect-Preserving Resize)  │
  │  [Stage 2] COLMAP SIFT Feature Extraction & Matching (Exhaustive/Sequential)     │
  │  [Stage 3] COLMAP Structure-from-Motion Mapping & TXT Model Export               │
  │  [Stage 4] COLMAP Dense MVS (PatchMatch Stereo & Fusion, CUDA GPU dependent)     │
  │  [Stage 5] Point Cloud Processing & Outlier Filtering (Open3D)                   │
  │  [Stage 6] Surface Mesh Generation (Ball Pivoting & Poisson Algorithms)          │
  │  [Stage 7] Research Evaluation Report Compilation (JSON Metadata & Metrics)     │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start: Running the Web Application

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the FastAPI Server & Web UI
```bash
python src/backend/app.py
```
Open your browser to: **`http://localhost:8000`**

### 3. Run Automated Unit & Integration Tests
```bash
# Run unit test suite
python tests/run_tests.py

# Run real dataset integration test
python scripts/test_integration.py
```

### 4. GPU-Accelerated Dense Reconstruction (Google Colab)
For CUDA Dense PatchMatch Stereo reconstruction, open **`notebooks/02_dense_reconstruction_colab.ipynb`** in Google Colab with an NVIDIA T4 GPU runtime.

---

## API Reference

- `GET /api/health`: Health status & environment capabilities.
- `POST /api/jobs`: Create asynchronous reconstruction job with uploaded images.
- `GET /api/jobs`: List all past and active reconstruction jobs.
- `GET /api/jobs/{job_id}`: Retrieve status, progress stage, logs, and warnings.
- `GET /api/jobs/{job_id}/report`: Structured research evaluation report JSON.
- `GET /api/jobs/{job_id}/files/{file_type}`: Securely download output file (`point_cloud`, `mesh`, `report`).

---

## Project Structure

```
Sparse3D/
├── src/
│   ├── backend/
│   │   └── app.py                # FastAPI web server & REST API
│   ├── frontend/
│   │   ├── index.html            # Web UI HTML dashboard
│   │   ├── css/style.css         # Dark mode glassmorphism UI style system
│   │   └── js/app.js             # Client application & Three.js 3D WebGL renderer
│   └── reconstruction/
│       └── pipeline.py           # Unified reconstruction service engine
├── scripts/
│   ├── test_integration.py       # Integration test runner
│   ├── run_dense_reconstruction.py # Dense MVS script
│   ├── run_colmap.py             # Sparse SfM script
│   ├── validate_images.py        # Image validation
│   ├── generate_point_cloud.py   # PLY point cloud generator
│   └── visualize_point_cloud.py  # 3D visualizer
├── tests/
│   ├── run_tests.py              # Native unittest runner
│   ├── test_validation.py        # Image validation unit tests
│   └── test_backend.py           # FastAPI backend integration tests
├── notebooks/
│   ├── 01_baseline_reconstruction.ipynb
│   └── 02_dense_reconstruction_colab.ipynb
├── data/                         # Datasets & DTU scan subsets
├── outputs/                      # Job outputs & point cloud PLYs
├── workspace/                    # Isolated COLMAP workspace jobs
├── requirements.txt              # Dependencies
├── CLAUDE_REVIEW.md              # Architecture & peer review package
└── README.md
```
│
├── outputs/
│   ├── sparse/           # COLMAP sparse reconstruction
│   ├── dense/            # Dense reconstruction (future)
│   ├── point_clouds/     # Generated point clouds (PLY)
│   └── visualizations/   # Visualization screenshots
│
├── workspace/            # COLMAP temporary workspace
│
├── requirements.txt
├── README.md
└── .gitignore
```

## Requirements

### Software Dependencies

- Python 3.10+
- COLMAP (must be installed separately, see Installation section)

### Python Packages

See `requirements.txt`:
- numpy >= 1.21.0
- opencv-python >= 4.5.0
- open3d >= 0.16.0
- matplotlib >= 3.4.0
- Pillow >= 8.0.0
- jupyter >= 1.0.0
- ipykernel >= 6.0.0
- pandas >= 1.3.0

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install COLMAP

COLMAP must be installed separately. Choose your platform:

#### Windows

1. Download from: https://github.com/colmap/colmap/releases
2. Install the executable
3. Add COLMAP to your system PATH

To verify installation:
```bash
colmap --help
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install colmap
```

#### macOS

```bash
brew install colmap
```

#### Build from Source (Any Platform)

If pre-built packages are not available:

```bash
git clone https://github.com/colmap/colmap.git
cd colmap
mkdir build && cd build
cmake ..
make -j8
sudo make install
```

### 3. Verify Installation

```bash
# Check Python
python --version

# Check COLMAP
colmap --help

# Check Python packages
python -c "import cv2, open3d, numpy; print('All packages OK')"
```

## Dataset Preparation

### Image Requirements

For successful reconstruction, images should:

1. **Show the same object** from different viewpoints
2. **Have sufficient overlap** (60-80% overlap between consecutive images)
3. **Be well-lit** with consistent lighting
4. **Avoid motion blur** - use fast shutter speed
5. **Cover the object** from multiple angles (ideally 360° around)
6. **Be in supported formats**: JPG, PNG, BMP, TIFF, WebP

### Recommended Capture Strategy

1. **Orbit the object**: Move around the object in a circle
2. **Maintain distance**: Keep a consistent distance from the object
3. **Overlap views**: Ensure each image overlaps with the previous one
4. **Multiple heights**: Capture from different elevations if possible
5. **Avoid rotation-only**: Move the camera, don't just rotate in place

### Example Dataset Sizes

- **Minimum**: 3 images (will have poor quality)
- **Recommended for baseline**: 10-20 images
- **Ideal for sparse-view research**: 3-6 images (challenging)

### Public Datasets

If you don't have your own images, consider:

1. **DTU Dataset**: https://virtual.vtt.fi/vtt-ops/dtu/
   - Multi-view light field dataset
   - Ground truth available
   - Requires registration

2. **ETH3D**: https://www.eth3d.net/
   - High-quality multi-view stereo benchmark
   - Ground truth available

3. **Tanks and Temples**: http://tanksandtemples.org/
   - Large-scale outdoor scenes
   - Benchmark dataset

For simple testing, you can photograph any object (a mug, toy, sculpture) with your phone.

### Organizing Your Dataset

Place your images in `data/raw/`:

```
data/raw/
├── image001.jpg
├── image002.jpg
├── image003.jpg
└── ...
```

## How to Run the Pipeline

### Option 1: Using Scripts (Command Line)

#### Step 1: Validate Images

```bash
python scripts/validate_images.py data/raw
```

This checks:
- Supported formats
- Image dimensions
- Corrupted files
- Duplicates
- Minimum image count

#### Step 2: Preprocess Images (Optional)

```bash
# Basic preprocessing (no changes)
python scripts/preprocess_images.py data/raw data/processed

# Resize to max 1920px
python scripts/preprocess_images.py data/raw data/processed 1920

# Resize and normalize
python scripts/preprocess_images.py data/raw data/processed 1920 true
```

#### Step 3: Run COLMAP SfM

```bash
# With GPU (default)
python scripts/run_colmap.py data/processed workspace outputs/sparse

# With CPU only
python scripts/run_colmap.py data/processed workspace outputs/sparse --cpu
```

This performs:
- Feature extraction
- Feature matching
- Sparse reconstruction
- Model export

#### Step 4: Generate Point Cloud

```bash
# Basic (with outlier removal)
python scripts/generate_point_cloud.py outputs/sparse/sparse_reconstruction outputs/point_clouds

# With normal estimation
python scripts/generate_point_cloud.py outputs/sparse/sparse_reconstruction outputs/point_clouds --normals

# Without outlier removal
python scripts/generate_point_cloud.py outputs/sparse/sparse_reconstruction outputs/point_clouds --no-outliers
```

#### Step 5: Visualize

```bash
# Interactive visualization (opens window)
python scripts/visualize_point_cloud.py outputs/point_clouds/reconstruction.ply outputs/visualizations

# Offscreen (saves screenshots only)
python scripts/visualize_point_cloud.py outputs/point_clouds/reconstruction.ply outputs/visualizations --offscreen

# Offscreen with multiple rotated views
python scripts/visualize_point_cloud.py outputs/point_clouds/reconstruction.ply outputs/visualizations --offscreen --rotate
```

### Option 2: Using Jupyter Notebook

```bash
# Start Jupyter
jupyter notebook notebooks/01_baseline_reconstruction.ipynb
```

Run the cells in the notebook to execute the complete pipeline.

## Expected Outputs

After running the pipeline, you will find:

### In `outputs/sparse/`:
- `sparse_reconstruction/` - COLMAP reconstruction output
  - `cameras.txt` - Camera parameters
  - `images.txt` - Camera poses
  - `points3D.txt` - 3D points
- `colmap_report.json` - Pipeline execution report
- `validation_report.json` - Image validation report

### In `outputs/point_clouds/`:
- `reconstruction.ply` - Final point cloud (PLY format)
- `point_cloud_report.json` - Point cloud statistics

### In `outputs/visualizations/`:
- `visualization.png` - Main visualization screenshot
- `visualization_045.png`, etc. - Multiple rotated views (if using --rotate)
- `visualization_report.json` - Visualization report

### In `workspace/`:
- `database.db` - COLMAP feature database
- `sparse/0/` - COLMAP sparse reconstruction

## Troubleshooting

### COLMAP Not Found

**Error**: `COLMAP not found in PATH`

**Solution**:
1. Verify COLMAP is installed: `colmap --help`
2. Add COLMAP to your system PATH
3. On Windows, add the COLMAP installation directory to PATH
4. Restart your terminal after modifying PATH

### Insufficient Images

**Error**: `INSUFFICIENT IMAGES (need at least 3)`

**Solution**:
- Ensure at least 3 images are in your input directory
- Check that images are in supported formats
- Verify the correct directory path

### Feature Matching Fails

**Error**: Feature matching fails or reconstruction fails

**Possible causes**:
1. **Poor overlap**: Images don't share enough features
   - Solution: Capture images with more overlap (60-80%)

2. **Low texture**: Object lacks distinctive features
   - Solution: Use objects with more texture/variation

3. **Lighting changes**: Dramatic lighting differences between images
   - Solution: Use consistent lighting

4. **Motion blur**: Camera movement during capture
   - Solution: Use faster shutter, stabilize camera

### Poor Reconstruction Quality

**Symptoms**: Point cloud is sparse, distorted, or incomplete

**Solutions**:
1. **Add more images**: 10-20 images work better than 3-6
2. **Improve overlap**: Ensure consecutive images overlap significantly
3. **Better angles**: Capture from more diverse viewpoints
4. **Better lighting**: Uniform, diffuse lighting works best
5. **Sharper images**: Avoid motion blur and focus issues

### Out of Memory

**Error**: Memory error during COLMAP processing

**Solutions**:
1. **Resize images**: Use preprocessing to reduce resolution
2. **Use CPU**: COLMAP CPU mode uses less memory: `--cpu` flag
3. **Process fewer images**: Start with a subset

### Open3D Import Error

**Error**: `ImportError: No module named 'open3d'`

**Solution**:
```bash
pip install open3d
```

## Experiment: Varying Number of Views

To investigate how reconstruction quality changes with the number of input images:

### Setup

Create subdirectories with different numbers of images:

```
data/
├── 3_images/
│   ├── img1.jpg
│   ├── img2.jpg
│   └── img3.jpg
├── 4_images/
│   ├── img1.jpg
│   ├── img2.jpg
│   ├── img3.jpg
│   └── img4.jpg
├── 5_images/
├── 6_images/
└── 10_images/
```

### Run Experiments

For each directory, run the complete pipeline:

```bash
# Example for 3 images
python scripts/validate_images.py data/3_images outputs/3_images/validation_report.json
python scripts/run_colmap.py data/3_images workspace/3_images outputs/3_images/sparse
python scripts/generate_point_cloud.py outputs/3_images/sparse/sparse_reconstruction outputs/3_images/point_clouds
python scripts/visualize_point_cloud.py outputs/3_images/point_clouds/reconstruction.ply outputs/3_images/visualizations --offscreen
```

### Record Results

For each experiment, record:

| # Images | Registered | Points | Success | Quality Notes |
|---------|------------|--------|---------|---------------|
| 3       | ?          | ?      | ?       | ?             |
| 4       | ?          | ?      | ?       | ?             |
| 5       | ?          | ?      | ?       | ?             |
| 6       | ?          | ?      | ?       | ?             |
| 10+     | ?          | ?      | ?       | ?             |

**Metrics to track**:
- Number of input images
- Number of registered images (successfully positioned)
- Number of reconstructed 3D points
- Reconstruction success/failure
- Qualitative observations (completeness, accuracy, noise)

### Expected Results

- **3 images**: Likely to fail or produce very sparse, incomplete reconstruction
- **4-6 images**: May succeed but with limited coverage and accuracy
- **10+ images**: Should produce reasonable quality reconstruction

This experiment demonstrates the challenge of sparse-view reconstruction.

## Limitations

### Current Baseline Limitations

1. **Sparse views**: COLMAP performs poorly with <10 images
2. **No learning**: This is a classical method, not deep learning
3. **Texture dependence**: Requires distinctive features for matching
4. **No priors**: Doesn't use learned shape priors or object knowledge
5. **No completion**: Cannot hallucinate missing geometry
6. **Manual capture**: Requires careful image capture

### Research Challenges for Sparse-View Reconstruction

1. **Feature matching**: Fewer images mean fewer feature correspondences
2. **Ambiguity**: Ill-posed problem with insufficient constraints
3. **Coverage**: Object parts may be completely unobserved
4. **Accuracy**: Limited views reduce triangulation accuracy

### Why This is Not a Complete Solution

This baseline establishes what classical SfM can achieve. It does **not** solve sparse-view reconstruction because:

- It fails or produces poor results with 3-6 images
- It cannot reconstruct unseen parts of the object
- It has no learned knowledge about object shapes
- It cannot complete missing geometry

The actual research contribution (future work) will involve deep learning methods that can:

- Learn shape priors from large datasets
- Infer unseen geometry
- Work with very few views (3-6 images)
- Handle ambiguous configurations

## Next Steps Toward Deep-Learning Sparse-View Method

### Step 2: Investigate Sparse-View Reconstruction Methods

Research and implement state-of-the-art sparse-view methods:

1. **SpaRP** (Sparse-View Reconstruction with Priors)
   - Uses learned shape priors
   - Handles sparse inputs

2. **UFORecon** (Ultra-Fast One-step Reconstruction)
   - Fast single-stage reconstruction
   - Good for sparse views

3. **SparseRecon**
   - Specialized for sparse inputs
   - Uses neural networks for completion

### Step 3: Implement and Compare

1. Implement one or more sparse-view methods
2. Compare against this COLMAP baseline
3. Evaluate on 3/4/5/6 image experiments
4. Quantify improvements

### Step 4: Develop Novel Method (Optional)

Based on research findings, develop improvements:

- Better shape priors
- Improved feature learning
- Novel network architectures
- Better handling of ambiguity

## Citation

If you use this baseline in your research, please cite COLMAP:

```bibtex
@article{schoenberger2016sfm,
  title={Structure-from-Motion Revisited},
  author={Sch{\"o}nberger, Johannes L and Frahm, Jan-Michael},
  journal={Conference on Computer Vision and Pattern Recognition (CVPR)},
  year={2016}
}
```

## License

This project is for research purposes. COLMAP has its own license (BSD).

## Contact

For questions about this research project, please contact the repository maintainers.

---

**Note**: This is a research baseline, not a production-ready system. It is designed to establish a foundation for investigating sparse-view 3D reconstruction methods.
