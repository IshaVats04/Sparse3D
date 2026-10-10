#!/usr/bin/env python3
"""
Visualize COLMAP TXT model output.

Reads cameras.txt, images.txt, and points3D.txt from COLMAP export.
Displays 3D point cloud and camera positions using Matplotlib.
Saves visualization to output directory.
"""

import sys
from pathlib import Path
from typing import Tuple, List
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def parse_cameras_txt(filepath: Path) -> dict:
    """Parse COLMAP cameras.txt file."""
    cameras = {}
    
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            
            camera_id = int(parts[0])
            model = parts[1]
            width = int(parts[2])
            height = int(parts[3])
            params = list(map(float, parts[4:]))
            
            cameras[camera_id] = {
                'model': model,
                'width': width,
                'height': height,
                'params': params
            }
    
    return cameras


def parse_images_txt(filepath: Path) -> dict:
    """Parse COLMAP images.txt file."""
    images = {}
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('#'):
            i += 1
            continue
        
        # Check if this is a metadata line (starts with an integer ID)
        parts = line.strip().split()
        if not parts or not parts[0].isdigit() or len(parts) < 10:
            i += 1
            continue
        
        # First line: IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
        image_id = int(parts[0])
        qw, qx, qy, qz = map(float, parts[1:5])
        tx, ty, tz = map(float, parts[5:8])
        camera_id = int(parts[8])
        name = parts[9]
        
        # Convert quaternion to rotation matrix and extract camera position
        # Camera position = -R^T * t
        q = np.array([qw, qx, qy, qz])
        q = q / np.linalg.norm(q)  # Normalize quaternion
        
        # Quaternion to rotation matrix
        w, x, y, z = q
        R = np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
            [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
            [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y]
        ])
        
        # Camera position
        t = np.array([tx, ty, tz])
        camera_position = -R.T @ t
        
        images[image_id] = {
            'camera_id': camera_id,
            'name': name,
            'quaternion': q,
            'translation': t,
            'rotation': R,
            'position': camera_position
        }
        
        i += 2  # Skip the second line (POINTS2D data)
    
    return images


def parse_points3D_txt(filepath: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Parse COLMAP points3D.txt file."""
    points = []
    colors = []
    errors = []
    
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue
            
            parts = line.strip().split()
            if len(parts) < 8:
                continue
            
            # POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]
            x, y, z = map(float, parts[1:4])
            r, g, b = map(int, parts[4:7])
            error = float(parts[7])
            
            points.append([x, y, z])
            colors.append([r, g, b])
            errors.append(error)
    
    return np.array(points), np.array(colors), np.array(errors)


def visualize_colmap_model(
    model_dir: Path,
    output_path: Path,
    show_cameras: bool = True
) -> dict:
    """Visualize COLMAP TXT model."""
    
    print("\n" + "="*60)
    print("COLMAP MODEL VISUALIZATION")
    print("="*60)
    print(f"Model directory: {model_dir}")
    print(f"Output path: {output_path}")
    print("="*60 + "\n")
    
    # Read files
    cameras_file = model_dir / "cameras.txt"
    images_file = model_dir / "images.txt"
    points_file = model_dir / "points3D.txt"
    
    if not cameras_file.exists():
        print(f"Error: cameras.txt not found")
        return {"status": "error", "message": "cameras.txt not found"}
    
    if not images_file.exists():
        print(f"Error: images.txt not found")
        return {"status": "error", "message": "images.txt not found"}
    
    if not points_file.exists():
        print(f"Error: points3D.txt not found")
        return {"status": "error", "message": "points3D.txt not found"}
    
    print("Reading COLMAP model files...")
    cameras = parse_cameras_txt(cameras_file)
    images = parse_images_txt(images_file)
    points, colors, errors = parse_points3D_txt(points_file)
    
    print(f"Cameras: {len(cameras)}")
    print(f"Registered images: {len(images)}")
    print(f"3D points: {len(points)}")
    print(f"Mean reprojection error: {np.mean(errors):.4f} pixels")
    print()
    
    # Create figure
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot points
    if len(points) > 0:
        # Normalize colors to [0, 1]
        colors_normalized = colors / 255.0
        ax.scatter(points[:, 0], points[:, 1], points[:, 2],
                  c=colors_normalized, s=1, alpha=0.6, label='3D Points')
        print(f"Plotted {len(points)} 3D points")
    
    # Plot camera positions
    if show_cameras and len(images) > 0:
        camera_positions = []
        camera_names = []
        
        for img_id, img_data in images.items():
            camera_positions.append(img_data['position'])
            camera_names.append(img_data['name'])
        
        camera_positions = np.array(camera_positions)
        ax.scatter(camera_positions[:, 0], camera_positions[:, 1], camera_positions[:, 2],
                  c='red', s=100, marker='^', label='Camera Positions', edgecolors='black')
        
        # Annotate cameras
        for i, (pos, name) in enumerate(zip(camera_positions, camera_names)):
            ax.text(pos[0], pos[1], pos[2], name, fontsize=8)
        
        print(f"Plotted {len(camera_positions)} camera positions")
    
    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title(f'COLMAP Sparse Reconstruction\n{len(points)} points, {len(images)} registered images')
    
    # Set equal aspect ratio
    if len(points) > 0:
        max_range = np.array([
            points[:, 0].max() - points[:, 0].min(),
            points[:, 1].max() - points[:, 1].min(),
            points[:, 2].max() - points[:, 2].min()
        ]).max() / 2.0
        
        mid_x = (points[:, 0].max() + points[:, 0].min()) * 0.5
        mid_y = (points[:, 1].max() + points[:, 1].min()) * 0.5
        mid_z = (points[:, 2].max() + points[:, 2].min()) * 0.5
        
        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)
    
    ax.legend()
    
    # Save figure
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nVisualization saved to: {output_path}")
    
    # Show plot (comment out for non-interactive environments)
    # plt.show()
    
    print("\n" + "="*60)
    print("VISUALIZATION COMPLETE")
    print("="*60 + "\n")
    
    return {
        "status": "success",
        "num_cameras": len(cameras),
        "num_registered_images": len(images),
        "num_points": len(points),
        "mean_reprojection_error": float(np.mean(errors)),
        "output_path": str(output_path),
        "registered_image_names": [img['name'] for img in images.values()]
    }


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python visualize_colmap_txt.py <model_dir> <output_path> [--no-cameras]")
        print("\nArguments:")
        print("  model_dir  : Directory containing COLMAP TXT files (cameras.txt, images.txt, points3D.txt)")
        print("  output_path: Path to save visualization image")
        print("  --no-cameras: Skip camera positions (optional)")
        print("\nExample:")
        print("  python visualize_colmap_txt.py outputs/dtu_scan1_6views_lighting0/sparse_reconstruction_retry outputs/dtu_scan1_6views_lighting0/visualization.png")
        print("  python visualize_colmap_txt.py outputs/dtu_scan1_6views_lighting0/sparse_reconstruction_retry outputs/dtu_scan1_6views_lighting0/visualization.png --no-cameras")
        sys.exit(1)
    
    model_dir = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    show_cameras = "--no-cameras" not in sys.argv
    
    result = visualize_colmap_model(model_dir, output_path, show_cameras)
    
    print("\nSummary:")
    print(f"  Cameras: {result.get('num_cameras', 0)}")
    print(f"  Registered images: {result.get('num_registered_images', 0)}")
    print(f"  3D points: {result.get('num_points', 0)}")
    print(f"  Mean reprojection error: {result.get('mean_reprojection_error', 0):.4f} pixels")
    
    if result["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
