#!/usr/bin/env python3
"""
Image preprocessing script for 3D reconstruction pipeline.

Performs lightweight preprocessing:
- Optional resizing (maintaining aspect ratio)
- Optional normalization
- Preserves original images
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import json

import cv2
import numpy as np
from PIL import Image


class ImagePreprocessor:
    """Preprocesses images for 3D reconstruction pipeline."""

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        max_dimension: Optional[int] = None,
        normalize: bool = False
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.max_dimension = max_dimension
        self.normalize = normalize

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def resize_with_aspect_ratio(
        self,
        image: np.ndarray,
        max_dim: int
    ) -> Tuple[np.ndarray, float]:
        """
        Resize image while maintaining aspect ratio.

        Returns:
            Resized image and scale factor
        """
        h, w = image.shape[:2]

        # If image is already smaller than max_dim, don't upscale
        if max(h, w) <= max_dim:
            return image, 1.0

        # Calculate new dimensions
        if h > w:
            new_h = max_dim
            new_w = int(w * (max_dim / h))
        else:
            new_w = max_dim
            new_h = int(h * (max_dim / w))

        # Resize
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        scale_factor = max_dim / max(h, w)

        return resized, scale_factor

    def normalize_image(self, image: np.ndarray) -> np.ndarray:
        """
        Normalize image to [0, 255] range.

        This is a simple intensity normalization that doesn't affect features significantly.
        """
        # Convert to float
        img_float = image.astype(np.float32)

        # Simple min-max normalization
        img_min = img_float.min()
        img_max = img_float.max()

        if img_max > img_min:
            img_normalized = (img_float - img_min) / (img_max - img_min) * 255
        else:
            img_normalized = img_float

        return img_normalized.astype(np.uint8)

    def process_image(self, input_path: Path) -> Optional[dict]:
        """
        Process a single image.

        Returns:
            Dictionary with processing info, or None if failed
        """
        try:
            # Read image
            img = cv2.imread(str(input_path))
            if img is None:
                print(f"[X] Failed to read: {input_path.name}")
                return None

            original_h, original_w = img.shape[:2]

            # Resize if max_dimension is specified
            if self.max_dimension:
                img, scale_factor = self.resize_with_aspect_ratio(img, self.max_dimension)
            else:
                scale_factor = 1.0

            # Normalize if requested
            if self.normalize:
                img = self.normalize_image(img)

            # Save processed image
            output_path = self.output_dir / input_path.name
            cv2.imwrite(str(output_path), img)

            processed_h, processed_w = img.shape[:2]

            print(f"[OK] Processed: {input_path.name}")
            print(f"  Original: {original_w}x{original_h}")
            print(f"  Processed: {processed_w}x{processed_h}")
            print(f"  Scale factor: {scale_factor:.3f}")

            return {
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_resolution": {"width": original_w, "height": original_h},
                "processed_resolution": {"width": processed_w, "height": processed_h},
                "scale_factor": scale_factor,
                "normalized": self.normalize
            }

        except Exception as e:
            print(f"[X] Error processing {input_path.name}: {e}")
            return None

    def process_all(self) -> dict:
        """Process all images in input directory."""
        if not self.input_dir.exists():
            print(f"Error: Input directory {self.input_dir} does not exist.")
            return {"status": "error", "message": "Input directory not found"}

        supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        image_files = [f for f in self.input_dir.iterdir()
                      if f.is_file() and f.suffix.lower() in supported_formats]

        print(f"\n{'='*60}")
        print("IMAGE PREPROCESSING")
        print(f"{'='*60}")
        print(f"Input directory: {self.input_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Images to process: {len(image_files)}")
        print(f"Max dimension: {self.max_dimension if self.max_dimension else 'None (no resizing)'}")
        print(f"Normalize: {self.normalize}")
        print(f"{'-'*60}\n")

        results = []
        successful = 0
        failed = 0

        for img_path in image_files:
            result = self.process_image(img_path)
            if result:
                results.append(result)
                successful += 1
            else:
                failed += 1

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Successfully processed: {successful}")
        print(f"Failed: {failed}")
        print(f"{'='*60}\n")

        return {
            "status": "success" if failed == 0 else "partial_success",
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "max_dimension": self.max_dimension,
            "normalize": self.normalize,
            "total_images": len(image_files),
            "successful": successful,
            "failed": failed,
            "results": results
        }

    def save_report(self, result: dict, output_path: str) -> None:
        """Save preprocessing report to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Preprocessing report saved to: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python preprocess_images.py <input_dir> <output_dir> [max_dimension] [normalize]")
        print("\nArguments:")
        print("  input_dir    : Directory containing input images")
        print("  output_dir   : Directory to save processed images")
        print("  max_dimension: Optional maximum dimension (e.g., 1920)")
        print("  normalize    : Optional - set to 'true' to normalize images")
        print("\nExample:")
        print("  python preprocess_images.py data/raw data/processed")
        print("  python preprocess_images.py data/raw data/processed 1920")
        print("  python preprocess_images.py data/raw data/processed 1920 true")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    max_dimension = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else None
    normalize = len(sys.argv) > 4 and sys.argv[4].lower() in ['true', '1', 'yes']

    preprocessor = ImagePreprocessor(
        input_dir=input_dir,
        output_dir=output_dir,
        max_dimension=max_dimension,
        normalize=normalize
    )

    result = preprocessor.process_all()

    # Save report
    report_path = Path(output_dir) / "preprocessing_report.json"
    preprocessor.save_report(result, str(report_path))

    # Exit with error code if all failed
    if result["status"] == "error" or result["successful"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
