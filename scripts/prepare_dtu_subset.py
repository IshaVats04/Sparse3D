#!/usr/bin/env python3
"""
Prepare a subset of DTU dataset for testing.

Analyzes DTU dataset structure and selects images from distinct camera positions.
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple
import json
import shutil
import re


def parse_dtu_filename(filename: str) -> Dict:
    """
    Parse DTU filename: clean_XXX_Y_r5000.png
    Returns: {'camera': int, 'lighting': int}
    """
    match = re.match(r'clean_(\d+)_(\d+)_r5000\.png', filename)
    if match:
        return {
            'camera': int(match.group(1)),
            'lighting': int(match.group(2))
        }
    return None


def analyze_dtu_dataset(data_dir: Path) -> Dict:
    """Analyze DTU dataset structure."""
    images = []
    
    for img_file in data_dir.glob('clean_*_r5000.png'):
        parsed = parse_dtu_filename(img_file.name)
        if parsed:
            images.append({
                'path': str(img_file),
                'camera': parsed['camera'],
                'lighting': parsed['lighting']
            })
    
    # Group by camera position
    cameras = {}
    for img in images:
        cam_id = img['camera']
        if cam_id not in cameras:
            cameras[cam_id] = []
        cameras[cam_id].append(img)
    
    # Sort cameras
    sorted_cameras = sorted(cameras.keys())
    
    print(f"\n{'='*60}")
    print("DTU DATASET ANALYSIS")
    print(f"{'='*60}")
    print(f"Total images: {len(images)}")
    print(f"Camera positions: {len(cameras)}")
    print(f"Lighting conditions per camera: {len(list(cameras.values())[0]) if cameras else 0}")
    print(f"Camera IDs: {sorted_cameras[:10]}...{sorted_cameras[-10:] if len(sorted_cameras) > 10 else sorted_cameras}")
    print(f"{'='*60}\n")
    
    return {
        'total_images': len(images),
        'num_cameras': len(cameras),
        'lighting_per_camera': len(list(cameras.values())[0]) if cameras else 0,
        'camera_ids': sorted_cameras,
        'cameras': cameras
    }


def select_images(cameras: Dict, num_views: int = 6, lighting: int = 0) -> List[Dict]:
    """
    Select images from distinct camera positions with consistent lighting.
    
    Args:
        cameras: Dictionary of camera_id -> list of images
        num_views: Number of camera positions to select
        lighting: Lighting condition to use (0-6)
    
    Returns:
        List of selected image dictionaries
    """
    sorted_cameras = sorted(cameras.keys())
    
    # Select evenly spaced camera positions
    if len(sorted_cameras) >= num_views:
        step = len(sorted_cameras) // num_views
        selected_cameras = [sorted_cameras[i * step] for i in range(num_views)]
    else:
        selected_cameras = sorted_cameras
    
    print(f"\nSelecting {len(selected_cameras)} camera positions: {selected_cameras}")
    print(f"Using lighting condition: {lighting}")
    
    selected_images = []
    for cam_id in selected_cameras:
        # Find image with specified lighting
        for img in cameras[cam_id]:
            if img['lighting'] == lighting:
                selected_images.append(img)
                print(f"  - Camera {cam_id:03d}, Lighting {lighting}: {Path(img['path']).name}")
                break
    
    return selected_images


def prepare_test_subset(
    source_dir: Path,
    output_dir: Path,
    selected_images: List[Dict],
    experiment_name: str
) -> Dict:
    """
    Copy selected images to test directory with COLMAP-compatible names.
    
    Args:
        source_dir: Source DTU directory
        output_dir: Output experiment directory
        selected_images: List of selected image dictionaries
        experiment_name: Name of the experiment
    
    Returns:
        Manifest dictionary
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        'experiment_name': experiment_name,
        'source_directory': str(source_dir),
        'output_directory': str(output_dir),
        'num_images': len(selected_images),
        'images': []
    }
    
    print(f"\n{'='*60}")
    print(f"COPYING IMAGES TO: {output_dir}")
    print(f"{'='*60}\n")
    
    for i, img in enumerate(selected_images, 1):
        # Use simple sequential naming for COLMAP
        new_name = f"image_{i:03d}.png"
        new_path = output_dir / new_name

        source_path = Path(img['path'])
        shutil.copy2(source_path, new_path)

        print(f"[OK] Copied: {source_path.name} -> {new_name}")

        manifest['images'].append({
            'original_filename': source_path.name,
            'colmap_filename': new_name,
            'camera_position': img['camera'],
            'lighting_condition': img['lighting'],
            'index': i
        })
    
    # Save manifest
    manifest_path = output_dir / 'manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n[OK] Manifest saved to: {manifest_path}")
    
    return manifest


def check_calibration(calibration_dir: Path) -> Dict:
    """Check if calibration files exist and document format."""
    calibration_info = {
        'exists': calibration_dir.exists(),
        'directory': str(calibration_dir),
        'files': []
    }

    if calibration_info['exists']:
        for cal_file in calibration_dir.iterdir():
            if cal_file.is_file():
                calibration_info['files'].append(cal_file.name)
    
    print(f"\n{'='*60}")
    print("CALIBRATION CHECK")
    print(f"{'='*60}")
    print(f"Calibration directory: {calibration_dir}")
    print(f"Exists: {calibration_info['exists']}")
    if calibration_info['files']:
        print(f"Files: {calibration_info['files'][:5]}...")
    print(f"{'='*60}\n")
    
    return calibration_info


def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print("Usage: python prepare_dtu_subset.py <dtu_cleaned_dir> <output_dir> <num_views> [lighting]")
        print("\nArguments:")
        print("  dtu_cleaned_dir: DTU Cleaned directory (e.g., data/dtu/SampleSet/MVS Data/Cleaned/scan1)")
        print("  output_dir      : Output experiment directory (e.g., data/experiments/dtu_scan1_6views)")
        print("  num_views       : Number of views to select (e.g., 6)")
        print("  lighting        : Lighting condition to use (0-6, default: 0)")
        print("\nExample:")
        print("  python prepare_dtu_subset.py 'data/dtu/SampleSet/MVS Data/Cleaned/scan1' data/experiments/dtu_scan1_6views 6")
        print("  python prepare_dtu_subset.py 'data/dtu/SampleSet/MVS Data/Cleaned/scan1' data/experiments/dtu_scan1_6views 6 0")
        sys.exit(1)
    
    dtu_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    num_views = int(sys.argv[3])
    lighting = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    
    if not dtu_dir.exists():
        print(f"Error: DTU directory not found: {dtu_dir}")
        sys.exit(1)
    
    # Analyze dataset
    analysis = analyze_dtu_dataset(dtu_dir)
    
    # Select images
    selected_images = select_images(analysis['cameras'], num_views, lighting)
    
    if len(selected_images) < num_views:
        print(f"\nWarning: Only selected {len(selected_images)} images (requested {num_views})")
    
    # Prepare test subset
    experiment_name = f"dtu_scan1_{num_views}views_lighting{lighting}"
    manifest = prepare_test_subset(dtu_dir, output_dir, selected_images, experiment_name)
    
    # Check calibration
    calibration_dir = dtu_dir.parent.parent / "Calibration"
    calibration_info = check_calibration(calibration_dir)
    
    # Save full report
    report = {
        'experiment': experiment_name,
        'analysis': analysis,
        'selection': {
            'num_views_requested': num_views,
            'num_views_selected': len(selected_images),
            'lighting_condition': lighting
        },
        'manifest': manifest,
        'calibration': calibration_info
    }
    
    report_path = output_dir / 'preparation_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{'='*60}")
    print("PREPARATION COMPLETE")
    print(f"{'='*60}")
    print(f"Experiment: {experiment_name}")
    print(f"Images selected: {len(selected_images)}")
    print(f"Output directory: {output_dir}")
    print(f"Report saved to: {report_path}")
    print(f"{'='*60}\n")
    
    print("\nNext steps:")
    print(f"1. Validate images: python scripts\\validate_images.py {output_dir}")
    print(f"2. Run COLMAP: python scripts\\run_colmap.py {output_dir} workspace\\{experiment_name} outputs\\{experiment_name}")


if __name__ == "__main__":
    main()
