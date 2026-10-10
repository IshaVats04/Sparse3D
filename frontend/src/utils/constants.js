// Static UI constants. No metric values live here.

export const STORAGE_KEYS = {
  apiBase: 'sparse3d.apiBase',
  jobId: 'sparse3d.jobId',
  mock: 'sparse3d.mock',
};

export const MAX_IMAGES = 6;
export const MIN_IMAGES = 3;
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
// The backend decodes these formats with OpenCV; camera RAW files are not supported (convert to JPG/PNG first).
export const IMAGE_ACCEPT = 'image/jpeg,image/png,image/bmp,image/webp,image/tiff,.jpg,.jpeg,.png,.bmp,.webp,.tif,.tiff';
export const RAW_EXTENSIONS = [];
export const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'tif', 'tiff'];
export const GT_ACCEPT = '.ply,.obj,.stl';

export const TERMINAL_STATUSES = ['completed', 'partial_success', 'failed', 'cancelled'];
export const SUCCESS_STATUSES = ['completed', 'partial_success'];

export const VIEW_COUNT_OPTIONS = [3, 4, 5, 6];

export const ARRANGEMENTS = [
  { value: 'auto', label: 'Auto Detect', help: 'Uses every uploaded image as given.' },
  { value: 'uniform', label: 'Uniform', help: 'Views evenly spread around the object.' },
  { value: 'non_uniform', label: 'Non-uniform', help: 'Views clustered unevenly around the object.' },
  { value: 'high_overlap', label: 'High overlap', help: 'Neighbouring views share much of the scene.' },
  { value: 'low_overlap', label: 'Low overlap', help: 'Wide baselines between views; harder to match.' },
  { value: 'random', label: 'Random', help: 'A random subset of the uploaded images.' },
];

export const OBJECT_CATEGORIES = [
  'General Object', 'Vase', 'Chair', 'Mug', 'Shoe', 'Toy', 'Bottle', 'Electronic device',
];

export const QUALITIES = [
  { value: 'fast', label: 'Fast' },
  { value: 'standard', label: 'Standard' },
  { value: 'high', label: 'High' },
];

export const MESH_METHODS = [
  { value: 'poisson', label: 'Poisson' },
  { value: 'ball_pivoting', label: 'Ball pivoting' },
  { value: 'none', label: 'None' },
];

export const METHODS = [
  {
    value: 'classical',
    title: 'Classical (COLMAP + Open3D)',
    desc: 'Feature matching, SfM, MVS',
  },
  {
    value: 'neural',
    title: 'Neural (PyTorch)',
    desc: 'Sparse-view neural reconstruction',
  },
  {
    value: 'both',
    title: 'Both (Compare)',
    desc: 'Run both methods and compare results',
  },
];

export const METHOD_LABELS = {
  classical: 'Classical (COLMAP + Open3D)',
  neural: 'Neural (PyTorch)',
  both: 'Both',
};
export const METHOD_SHORT = { classical: 'Classical', neural: 'Neural', both: 'Both' };
export const METHOD_COLORS = { classical: '#3b82f6', neural: '#8b5cf6' };

export const DEFAULT_CONFIG = {
  project_name: 'Experiment',
  num_views: 5,
  view_arrangement: 'auto',
  object_category: 'General Object',
  quality: 'standard',
  recon_method: 'both',
  estimate_poses: true,
  run_evaluation: true,
  generate_mesh: false,
  save_intermediate: false,
  mesh_method: 'poisson',
};

export const STAGE_ORDER = [
  { key: 'image_analysis', label: 'Image Analysis' },
  { key: 'feature_extraction', label: 'Feature Extraction' },
  { key: 'camera_pose', label: 'Camera Pose Estimation' },
  { key: 'reconstruction', label: '3D Reconstruction' },
  { key: 'evaluation', label: 'Evaluation' },
];

export const STAGE_DESCRIPTIONS = {
  image_analysis: 'Checking image sharpness, brightness and resolution, and detecting keypoints in each view.',
  feature_extraction: 'Extracting local features from every view and matching them between image pairs.',
  camera_pose: 'Estimating the camera position and orientation for each view (structure from motion).',
  reconstruction: 'Building the 3D point cloud and, when requested, a surface mesh from the registered views.',
  evaluation: 'Computing quantitative metrics for each reconstruction.',
  complete: 'All stages finished.',
  failed: 'The pipeline stopped before completing.',
};

export const STATUS_META = {
  queued: { label: 'Queued', tone: 'slate' },
  processing: { label: 'Processing', tone: 'blue' },
  completed: { label: 'Completed', tone: 'green' },
  partial_success: { label: 'Partial', tone: 'amber' },
  failed: { label: 'Failed', tone: 'red' },
  cancelled: { label: 'Cancelled', tone: 'slate' },
};

export const FILE_TYPES = [
  { id: 'mesh', label: '3D Mesh (.ply)', neuralType: 'neural_mesh', ext: 'ply', resultKey: 'mesh' },
  { id: 'point_cloud', label: 'Point Cloud (PLY)', neuralType: 'neural_point_cloud', ext: 'ply', resultKey: 'point_cloud' },
  { id: 'metrics_csv', label: 'Evaluation Metrics (CSV)', ext: 'csv' },
  { id: 'camera_poses', label: 'Camera Poses (TXT)', ext: 'txt', resultKey: 'camera_poses' },
  { id: 'report', label: 'Report (JSON)', ext: 'json' },
];

export const ANALYSIS_METRICS = [
  { key: 'f_score', label: 'F-score', better: 'higher' },
  { key: 'chamfer_distance', label: 'Chamfer', better: 'lower' },
  { key: 'completeness_pct', label: 'Completeness', better: 'higher' },
  { key: 'runtime_sec', label: 'Runtime', better: 'lower' },
  { key: 'registration_ratio_pct', label: 'Registration ratio', better: 'higher' },
];

export const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', to: '/dashboard' },
  { id: 'experiments', label: 'Experiments', icon: 'FlaskConical', to: '/history' },
  { id: 'upload', label: 'Upload Images', icon: 'ImagePlus', to: '/upload' },
  { id: 'configuration', label: 'Configuration', icon: 'SlidersHorizontal', to: '/configuration' },
  { id: 'processing', label: 'Reconstruction', icon: 'Cpu', to: '/processing', job: true },
  { id: 'viewer', label: '3D Viewer', icon: 'Box', to: '/viewer', job: true },
  { id: 'evaluation', label: 'Evaluation', icon: 'BarChart3', to: '/evaluation', job: true },
  { id: 'comparison', label: 'Comparison', icon: 'GitCompare', to: '/comparison', job: true },
  { id: 'analysis', label: 'Analysis', icon: 'LineChart', to: '/analysis' },
  { id: 'history', label: 'History', icon: 'History', to: '/history#downloads' },
  { id: 'settings', label: 'Settings', icon: 'Settings', to: '/settings' },
];
