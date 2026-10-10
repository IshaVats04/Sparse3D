#!/usr/bin/env python3
"""
Point cloud generation script using Open3D.

This script:
- Loads COLMAP reconstruction output
- Converts to Open3D point cloud
- Removes outliers
- Estimates statistics
- Exports to PLY format
"""

import sys
from pathlib import Path
from typing import Optional, Dict
import json
import numpy as np

try:
    import open3d as o3d
except ImportError:
    print("Error: Open3D not installed. Install with: pip install open3d")
    sys.exit(1)


class PointCloudGenerator:
    """Generates and processes point clouds from COLMAP output."""

    def __init__(self, colmap_output_dir: str, output_dir: str):
        self.colmap_output_dir = Path(colmap_output_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_colmap_points(self) -> Optional[o3d.geometry.PointCloud]:
        """Load 3D points from COLMAP reconstruction."""
        # COLMAP exports points.txt with format:
        # POINT_ID X Y Z R G B ERROR N_OBS [...]
        points_file = self.colmap_output_dir / "points3D.txt"

        if not points_file.exists():
            print(f"Error: COLMAP points file not found: {points_file}")
            return None

        print(f"Loading points from: {points_file}")

        points = []
        colors = []

        with open(points_file, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue

                parts = line.strip().split()
                if len(parts) < 8:
                    continue

                # Format: POINT_ID X Y Z R G B ERROR N_OBS
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                r, g, b = float(parts[4]), float(parts[5]), float(parts[6])

                points.append([x, y, z])
                colors.append([r/255.0, g/255.0, b/255.0])

        if not points:
            print("Error: No valid points found in COLMAP output")
            return None

        points = np.array(points)
        colors = np.array(colors)

        print(f"Loaded {len(points)} points")

        # Create Open3D point cloud
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)

        return pcd

    def remove_outliers(
        self,
        pcd: o3d.geometry.PointCloud,
        nb_neighbors: int = 20,
        std_ratio: float = 2.0
    ) -> o3d.geometry.PointCloud:
        """Remove statistical outliers from point cloud."""
        print(f"\nRemoving outliers (nb_neighbors={nb_neighbors}, std_ratio={std_ratio})")

        pcd_clean, ind = pcd.remove_statistical_outlier(
            nb_neighbors=nb_neighbors,
            std_ratio=std_ratio
        )

        removed = len(pcd.points) - len(pcd_clean.points)
        print(f"Removed {removed} outliers ({removed/len(pcd.points)*100:.1f}%)")
        print(f"Remaining points: {len(pcd_clean.points)}")

        return pcd_clean

    def estimate_normals(
        self,
        pcd: o3d.geometry.PointCloud,
        search_param: Optional[o3d.geometry.KDTreeSearchParamHybrid] = None
    ) -> o3d.geometry.PointCloud:
        """Estimate normals for point cloud."""
        print("\nEstimating normals")

        if search_param is None:
            search_param = o3d.geometry.KDTreeSearchParamHybrid(
                radius=0.1,
                max_nn=30
            )

        pcd.estimate_normals(search_param=search_param)
        print("Normals estimated")

        return pcd

    def compute_statistics(self, pcd: o3d.geometry.PointCloud) -> Dict:
        """Compute point cloud statistics."""
        points = np.asarray(pcd.points)

        stats = {
            "num_points": len(points),
            "has_colors": pcd.has_colors(),
            "has_normals": pcd.has_normals(),
        }

        if len(points) > 0:
            # Bounding box
            min_bound = points.min(axis=0)
            max_bound = points.max(axis=0)
            dimensions = max_bound - min_bound

            stats["bounding_box"] = {
                "min": min_bound.tolist(),
                "max": max_bound.tolist(),
                "dimensions": dimensions.tolist()
            }

            # Centroid
            centroid = points.mean(axis=0)
            stats["centroid"] = centroid.tolist()

            # Point density (points per unit volume)
            volume = np.prod(dimensions)
            if volume > 0:
                stats["point_density"] = len(points) / volume

        return stats

    def export_point_cloud(
        self,
        pcd: o3d.geometry.PointCloud,
        output_path: str,
        write_normals: bool = True
    ) -> bool:
        """Export point cloud to PLY file."""
        try:
            o3d.io.write_point_cloud(
                output_path,
                pcd,
                write_ascii=False,
                compressed=False,
                write_normals=write_normals
            )
            print(f"\nPoint cloud exported to: {output_path}")
            return True
        except Exception as e:
            print(f"\nError exporting point cloud: {e}")
            return False

    def process(
        self,
        remove_outliers_flag: bool = True,
        estimate_normals_flag: bool = False,
        nb_neighbors: int = 20,
        std_ratio: float = 2.0
    ) -> Dict:
        """Process COLMAP output to generate point cloud."""
        print("\n" + "="*60)
        print("POINT CLOUD GENERATION")
        print("="*60)
        print(f"COLMAP output directory: {self.colmap_output_dir}")
        print(f"Output directory: {self.output_dir}")
        print("="*60 + "\n")

        # Load points
        pcd = self.load_colmap_points()
        if pcd is None:
            return {
                "status": "error",
                "message": "Failed to load COLMAP points"
            }

        print(f"\nInitial point cloud: {len(pcd.points)} points")

        # Remove outliers
        if remove_outliers_flag:
            pcd = self.remove_outliers(pcd, nb_neighbors, std_ratio)

        # Estimate normals
        if estimate_normals_flag:
            pcd = self.estimate_normals(pcd)

        # Compute statistics
        stats = self.compute_statistics(pcd)

        print("\n" + "-"*60)
        print("POINT CLOUD STATISTICS")
        print("-"*60)
        print(f"Number of points: {stats['num_points']}")
        print(f"Has colors: {stats['has_colors']}")
        print(f"Has normals: {stats['has_normals']}")

        if "bounding_box" in stats:
            bbox = stats["bounding_box"]
            print(f"\nBounding box:")
            print(f"  Min: [{bbox['min'][0]:.3f}, {bbox['min'][1]:.3f}, {bbox['min'][2]:.3f}]")
            print(f"  Max: [{bbox['max'][0]:.3f}, {bbox['max'][1]:.3f}, {bbox['max'][2]:.3f}]")
            print(f"  Dimensions: [{bbox['dimensions'][0]:.3f}, {bbox['dimensions'][1]:.3f}, {bbox['dimensions'][2]:.3f}]")

        if "centroid" in stats:
            print(f"\nCentroid: [{stats['centroid'][0]:.3f}, {stats['centroid'][1]:.3f}, {stats['centroid'][2]:.3f}]")

        if "point_density" in stats:
            print(f"Point density: {stats['point_density']:.3f} points/unit³")

        print("-"*60 + "\n")

        # Export point cloud
        output_path = self.output_dir / "reconstruction.ply"
        success = self.export_point_cloud(pcd, str(output_path))

        if not success:
            return {
                "status": "error",
                "message": "Failed to export point cloud"
            }

        print("\n" + "="*60)
        print("POINT CLOUD GENERATION COMPLETED")
        print("="*60 + "\n")

        return {
            "status": "success",
            "message": "Point cloud generated successfully",
            "output_path": str(output_path),
            "statistics": stats,
            "num_points_original": len(pcd.points) if not remove_outliers_flag else "N/A",
            "num_points_final": stats["num_points"],
            "remove_outliers": remove_outliers_flag,
            "estimate_normals": estimate_normals_flag
        }

    def save_report(self, result: Dict, output_path: str) -> None:
        """Save processing report to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Point cloud report saved to: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python generate_point_cloud.py <colmap_output_dir> <output_dir> [--no-outliers] [--normals]")
        print("\nArguments:")
        print("  colmap_output_dir: Directory containing COLMAP reconstruction output")
        print("  output_dir        : Directory to save point cloud")
        print("  --no-outliers     : Skip outlier removal (optional)")
        print("  --normals         : Estimate normals (optional)")
        print("\nExample:")
        print("  python generate_point_cloud.py outputs/sparse/sparse_reconstruction outputs/point_clouds")
        print("  python generate_point_cloud.py outputs/sparse/sparse_reconstruction outputs/point_clouds --normals")
        sys.exit(1)

    colmap_output_dir = sys.argv[1]
    output_dir = sys.argv[2]
    remove_outliers_flag = "--no-outliers" not in sys.argv
    estimate_normals_flag = "--normals" in sys.argv

    generator = PointCloudGenerator(
        colmap_output_dir=colmap_output_dir,
        output_dir=output_dir
    )

    result = generator.process(
        remove_outliers_flag=remove_outliers_flag,
        estimate_normals_flag=estimate_normals_flag
    )

    # Save report
    report_path = Path(output_dir) / "point_cloud_report.json"
    generator.save_report(result, str(report_path))

    # Exit with error code if failed
    if result["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
