#!/usr/bin/env python3
"""
Sparse3D Native Test Runner (using unittest).

Executes unit and integration checks for validation, pipeline processing, and backend API.
"""

import sys
import unittest
import tempfile
import numpy as np
import cv2
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reconstruction.pipeline import ReconstructionPipeline


class TestImageValidation(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

        # Create 3 valid synthetic images
        self.img1_path = self.tmp_path / "img1.png"
        self.img2_path = self.tmp_path / "img2.png"
        self.img3_path = self.tmp_path / "img3.png"

        cv2.imwrite(str(self.img1_path), np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))
        cv2.imwrite(str(self.img2_path), np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))
        cv2.imwrite(str(self.img3_path), np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_validation_success(self):
        """Test preprocessing 3 valid images."""
        workspace = self.tmp_path / "workspace"
        output = self.tmp_path / "output"

        pipeline = ReconstructionPipeline(
            job_id="unittest_val_ok",
            input_image_paths=[self.img1_path, self.img2_path, self.img3_path],
            workspace_dir=workspace,
            output_dir=output
        )

        ok = pipeline.validate_and_preprocess_images()
        self.assertTrue(ok)
        self.assertEqual(len(list(pipeline.images_dir.glob("*.png"))), 3)

    def test_validation_insufficient_images(self):
        """Test preprocessing fails when fewer than 3 images provided."""
        workspace = self.tmp_path / "workspace"
        output = self.tmp_path / "output"

        pipeline = ReconstructionPipeline(
            job_id="unittest_val_short",
            input_image_paths=[self.img1_path, self.img2_path],
            workspace_dir=workspace,
            output_dir=output
        )

        ok = pipeline.validate_and_preprocess_images()
        self.assertFalse(ok)


class TestPipelineRegistration(unittest.TestCase):

    def test_registration_parsing(self):
        """Test parsing registration statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            sparse_dir = tmp_path / "sparse_model"
            sparse_dir.mkdir(parents=True, exist_ok=True)

            images_txt = sparse_dir / "images.txt"
            with open(images_txt, "w", encoding="utf-8") as f:
                f.write("# Image list\n")
                f.write("1 0.1 0.2 0.3 0.4 1.0 2.0 3.0 1 image_001.png\n\n")
                f.write("2 0.1 0.2 0.3 0.4 1.0 2.0 3.0 2 image_002.png\n\n")

            pipeline = ReconstructionPipeline(
                job_id="unittest_reg_stats",
                input_image_paths=[tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"],
                workspace_dir=tmp_path / "ws",
                output_dir=tmp_path / "out"
            )
            pipeline.sparse_model_dir = sparse_dir

            stats = pipeline.parse_registration_stats()
            self.assertEqual(stats["total_input_images"], 3)
            self.assertEqual(stats["registered_image_count"], 2)
            self.assertAlmostEqual(stats["registration_ratio_pct"], 66.67, places=2)


if __name__ == "__main__":
    unittest.main()
