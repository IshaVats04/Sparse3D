#!/usr/bin/env python3
"""
Point cloud visualization script using Open3D.

This script:
- Loads a point cloud file
- Visualizes it interactively
- Saves a screenshot
- Optionally visualizes camera positions
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


class PointCloudVisualizer:
    """Visualizes point clouds with Open3D."""

    def __init__(self, point_cloud_path: str, output_dir: str):
        self.point_cloud_path = Path(point_cloud_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_point_cloud(self) -> Optional[o3d.geometry.PointCloud]:
        """Load point cloud from file."""
        if not self.point_cloud_path.exists():
            print(f"Error: Point cloud file not found: {self.point_cloud_path}")
            return None

        print(f"Loading point cloud from: {self.point_cloud_path}")

        try:
            pcd = o3d.io.read_point_cloud(str(self.point_cloud_path))
            print(f"Loaded {len(pcd.points)} points")
            return pcd
        except Exception as e:
            print(f"Error loading point cloud: {e}")
            return None

    def create_coordinate_frame(self, size: float = 1.0) -> o3d.geometry.TriangleMesh:
        """Create a coordinate frame for reference."""
        return o3d.geometry.TriangleMesh.create_coordinate_frame(size=size)

    def load_cameras(self, cameras_txt: str) -> Optional[o3d.geometry.PointCloud]:
        """
        Load camera positions from COLMAP cameras.txt file.

        Returns a point cloud with camera positions.
        """
        cameras_file = Path(cameras_txt)
        if not cameras_file.exists():
            print(f"Camera file not found: {cameras_file}")
            return None

        print(f"Loading cameras from: {cameras_file}")

        camera_positions = []

        with open(cameras_file, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    continue

                parts = line.strip().split()
                if len(parts) < 10:
                    continue

                # Format: CAMERA_ID MODEL WIDTH HEIGHT PARAMS...
                # We need images.txt for positions, not cameras.txt
                # This is a placeholder - actual camera positions are in images.txt
                pass

        if not camera_positions:
            print("No camera positions found")
            return None

        # Create point cloud for camera positions
        camera_pcd = o3d.geometry.PointCloud()
        camera_pcd.points = o3d.utility.Vector3dVector(camera_positions)

        return camera_pcd

    def visualize(
        self,
        show_coordinates: bool = True,
        show_cameras: bool = False,
        cameras_txt: Optional[str] = None,
        point_size: float = 1.0,
        background_color: list = [0.1, 0.1, 0.1]
    ) -> Dict:
        """Visualize point cloud and save screenshot."""
        print("\n" + "="*60)
        print("POINT CLOUD VISUALIZATION")
        print("="*60)
        print(f"Point cloud path: {self.point_cloud_path}")
        print(f"Output directory: {self.output_dir}")
        print("="*60 + "\n")

        # Load point cloud
        pcd = self.load_point_cloud()
        if pcd is None:
            return {
                "status": "error",
                "message": "Failed to load point cloud"
            }

        # Create visualization objects
        geometries = [pcd]

        if show_coordinates:
            coord_frame = self.create_coordinate_frame(size=1.0)
            geometries.append(coord_frame)
            print("Added coordinate frame")

        if show_cameras and cameras_txt:
            cameras = self.load_cameras(cameras_txt)
            if cameras:
                geometries.append(cameras)
                print("Added camera positions")

        # Set up visualizer
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name="3D Reconstruction", width=1920, height=1080)
        vis.get_render_option().background_color = background_color
        vis.get_render_option().point_size = point_size

        for geom in geometries:
            vis.add_geometry(geom)

        # Capture screenshot
        screenshot_path = self.output_dir / "visualization.png"
        print(f"\nCapturing screenshot to: {screenshot_path}")
        vis.capture_screen_image(str(screenshot_path))

        # Run interactive visualization
        print("\nLaunching interactive visualization...")
        print("Controls:")
        print("  - Mouse drag: Rotate")
        print("  - Shift + drag: Pan")
        print("  - Scroll: Zoom")
        print("  - Press 'Q' or close window to exit")

        vis.run()
        vis.destroy_window()

        print("\n" + "="*60)
        print("VISUALIZATION COMPLETED")
        print("="*60)
        print(f"Screenshot saved to: {screenshot_path}")
        print("="*60 + "\n")

        return {
            "status": "success",
            "message": "Visualization completed",
            "screenshot_path": str(screenshot_path),
            "num_points": len(pcd.points),
            "has_colors": pcd.has_colors(),
            "has_normals": pcd.has_normals()
        }

    def visualize_offscreen(
        self,
        show_coordinates: bool = True,
        point_size: float = 1.0,
        background_color: list = [0.1, 0.1, 0.1],
        rotate: bool = True
    ) -> Dict:
        """
        Create offscreen visualization without interactive window.

        Useful for automated pipelines.
        """
        print("\n" + "="*60)
        print("OFFSCREEN VISUALIZATION")
        print("="*60)

        # Load point cloud
        pcd = self.load_point_cloud()
        if pcd is None:
            return {
                "status": "error",
                "message": "Failed to load point cloud"
            }

        # Create visualization objects
        geometries = [pcd]

        if show_coordinates:
            coord_frame = self.create_coordinate_frame(size=1.0)
            geometries.append(coord_frame)

        # Set up offscreen visualizer
        vis = o3d.visualization.Visualizer()
        vis.create_window(visible=False, width=1920, height=1080)
        vis.get_render_option().background_color = background_color
        vis.get_render_option().point_size = point_size

        for geom in geometries:
            vis.add_geometry(geom)

        # Compute view control
        view_ctl = vis.get_view_control()
        view_ctl.set_front([0, 0, -1])
        view_ctl.set_up([0, 1, 0])
        view_ctl.set_zoom(0.8)

        if rotate:
            # Rotate for multiple views
            for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
                view_ctl.rotate(angle * np.pi / 180, 0)
                vis.poll_events()
                vis.update_renderer()
                screenshot_path = self.output_dir / f"visualization_{angle:03d}.png"
                vis.capture_screen_image(str(screenshot_path))
                print(f"Saved view at {angle}°")
        else:
            # Single view
            vis.poll_events()
            vis.update_renderer()
            screenshot_path = self.output_dir / "visualization.png"
            vis.capture_screen_image(str(screenshot_path))
            print(f"Saved screenshot")

        vis.destroy_window()

        print("\n" + "="*60)
        print("OFFSCREEN VISUALIZATION COMPLETED")
        print("="*60 + "\n")

        return {
            "status": "success",
            "message": "Offscreen visualization completed",
            "screenshot_path": str(screenshot_path),
            "num_points": len(pcd.points)
        }

    def save_report(self, result: Dict, output_path: str) -> None:
        """Save visualization report to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Visualization report saved to: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python visualize_point_cloud.py <point_cloud_path> <output_dir> [--offscreen] [--rotate]")
        print("\nArguments:")
        print("  point_cloud_path: Path to point cloud file (.ply)")
        print("  output_dir       : Directory to save screenshots")
        print("  --offscreen     : Use offscreen rendering (no interactive window)")
        print("  --rotate         : Generate multiple rotated views (with --offscreen)")
        print("\nExample:")
        print("  python visualize_point_cloud.py outputs/point_clouds/reconstruction.ply outputs/visualizations")
        print("  python visualize_point_cloud.py outputs/point_clouds/reconstruction.ply outputs/visualizations --offscreen")
        print("  python visualize_point_cloud.py outputs/point_clouds/reconstruction.ply outputs/visualizations --offscreen --rotate")
        sys.exit(1)

    point_cloud_path = sys.argv[1]
    output_dir = sys.argv[2]
    offscreen = "--offscreen" in sys.argv
    rotate = "--rotate" in sys.argv

    visualizer = PointCloudVisualizer(
        point_cloud_path=point_cloud_path,
        output_dir=output_dir
    )

    if offscreen:
        result = visualizer.visualize_offscreen(rotate=rotate)
    else:
        result = visualizer.visualize()

    # Save report
    report_path = Path(output_dir) / "visualization_report.json"
    visualizer.save_report(result, str(report_path))

    # Exit with error code if failed
    if result["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
