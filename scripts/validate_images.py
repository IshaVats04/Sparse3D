#!/usr/bin/env python3
"""
Image validation script for 3D reconstruction pipeline.

Checks:
- Supported image formats
- Image dimensions
- Corrupted/unreadable images
- Duplicate images (based on hash)
- Number of input images
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import hashlib
import json

import cv2
import numpy as np
from PIL import Image


class ImageValidator:
    """Validates images for 3D reconstruction pipeline."""

    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    MIN_RESOLUTION = (64, 64)  # Minimum acceptable resolution
    MAX_RESOLUTION = (8192, 8192)  # Maximum acceptable resolution

    def __init__(self, image_dir: str):
        self.image_dir = Path(image_dir)
        self.valid_images: List[Path] = []
        self.invalid_images: List[Tuple[Path, str]] = []
        self.image_hashes: Dict[str, Path] = {}
        self.duplicates: List[Tuple[Path, Path]] = []

    def is_supported_format(self, filepath: Path) -> bool:
        """Check if file has supported image format."""
        return filepath.suffix.lower() in self.SUPPORTED_FORMATS

    def check_image_readable(self, filepath: Path) -> bool:
        """Check if image can be read without errors."""
        try:
            # Try with OpenCV
            img = cv2.imread(str(filepath))
            if img is None:
                return False

            # Try with PIL as backup
            with Image.open(filepath) as pil_img:
                pil_img.verify()

            return True
        except Exception:
            return False

    def get_image_resolution(self, filepath: Path) -> Tuple[int, int]:
        """Get image resolution (height, width)."""
        try:
            img = cv2.imread(str(filepath))
            if img is None:
                return (0, 0)
            h, w = img.shape[:2]
            return (h, w)
        except Exception:
            return (0, 0)

    def check_resolution(self, resolution: Tuple[int, int]) -> bool:
        """Check if resolution is within acceptable bounds."""
        h, w = resolution
        min_h, min_w = self.MIN_RESOLUTION
        max_h, max_w = self.MAX_RESOLUTION
        return (h >= min_h and w >= min_w and h <= max_h and w <= max_w)

    def compute_image_hash(self, filepath: Path) -> str:
        """Compute MD5 hash of image file."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def detect_duplicates(self, filepath: Path, img_hash: str) -> None:
        """Detect duplicate images based on hash."""
        if img_hash in self.image_hashes:
            self.duplicates.append((filepath, self.image_hashes[img_hash]))
        else:
            self.image_hashes[img_hash] = filepath

    def validate(self) -> Dict:
        """Run full validation on all images in directory."""
        if not self.image_dir.exists():
            print(f"Error: Directory {self.image_dir} does not exist.")
            return {"status": "error", "message": "Directory not found"}

        # Find all image files
        image_files = []
        for f in self.image_dir.iterdir():
            if f.is_file() and self.is_supported_format(f):
                image_files.append(f)

        print(f"\n{'='*60}")
        print("IMAGE VALIDATION REPORT")
        print(f"{'='*60}")
        print(f"Directory: {self.image_dir}")
        print(f"Images found: {len(image_files)}")
        print(f"{'-'*60}\n")

        # Validate each image
        resolutions = []
        for img_path in image_files:
            issues = []

            # Check if readable
            if not self.check_image_readable(img_path):
                issues.append("corrupted or unreadable")
                self.invalid_images.append((img_path, "; ".join(issues)))
                print(f"[X] {img_path.name}: {', '.join(issues)}")
                continue

            # Check resolution
            resolution = self.get_image_resolution(img_path)
            if not self.check_resolution(resolution):
                issues.append(f"invalid resolution {resolution}")
                self.invalid_images.append((img_path, "; ".join(issues)))
                print(f"[X] {img_path.name}: {', '.join(issues)}")
                continue

            # Check for duplicates
            img_hash = self.compute_image_hash(img_path)
            self.detect_duplicates(img_path, img_hash)

            # If no issues, add to valid images
            if not issues:
                self.valid_images.append(img_path)
                resolutions.append(resolution)
                print(f"[OK] {img_path.name}: {resolution[1]}x{resolution[0]}")

        # Print summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Valid images: {len(self.valid_images)}")
        print(f"Invalid images: {len(self.invalid_images)}")

        if self.valid_images:
            # Calculate average resolution
            avg_h = sum(r[0] for r in resolutions) // len(resolutions)
            avg_w = sum(r[1] for r in resolutions) // len(resolutions)
            print(f"Average resolution: {avg_w}x{avg_h}")

            # Resolution range
            min_h = min(r[0] for r in resolutions)
            max_h = max(r[0] for r in resolutions)
            min_w = min(r[1] for r in resolutions)
            max_w = max(r[1] for r in resolutions)
            print(f"Resolution range: {min_w}x{min_h} to {max_w}x{max_h}")

        if self.duplicates:
            print(f"Duplicate images found: {len(self.duplicates)}")
            for dup, original in self.duplicates:
                print(f"  - {dup.name} (duplicate of {original.name})")

        print(f"{'='*60}\n")

        # Determine status
        if len(self.valid_images) < 3:
            print("Status: INSUFFICIENT IMAGES (need at least 3)")
            status = "insufficient"
        elif len(self.invalid_images) > 0:
            print("Status: READY FOR RECONSTRUCTION (with warnings)")
            status = "ready_with_warnings"
        else:
            print("Status: READY FOR RECONSTRUCTION")
            status = "ready"

        print(f"{'='*60}\n")

        # Prepare result dictionary
        result = {
            "status": status,
            "total_images": len(image_files),
            "valid_images": len(self.valid_images),
            "invalid_images": len(self.invalid_images),
            "duplicate_images": len(self.duplicates),
            "valid_image_paths": [str(p) for p in self.valid_images],
            "invalid_image_details": [(str(p), reason) for p, reason in self.invalid_images],
            "duplicate_details": [(str(d), str(o)) for d, o in self.duplicates],
        }

        if self.valid_images:
            result["average_resolution"] = {
                "width": avg_w,
                "height": avg_h
            }
            result["resolution_range"] = {
                "min_width": min_w,
                "max_width": max_w,
                "min_height": min_h,
                "max_height": max_h
            }

        return result

    def save_report(self, result: Dict, output_path: str) -> None:
        """Save validation report to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Validation report saved to: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python validate_images.py <image_directory> [output_json]")
        print("\nExample:")
        print("  python validate_images.py data/raw")
        print("  python validate_images.py data/raw outputs/validation_report.json")
        sys.exit(1)

    image_dir = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) > 2 else None

    validator = ImageValidator(image_dir)
    result = validator.validate()

    if output_json:
        validator.save_report(result, output_json)

    # Exit with error code if not ready
    if result["status"] in ["error", "insufficient"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
