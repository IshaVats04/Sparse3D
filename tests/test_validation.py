"""Unit tests for Image Validation and Preprocessing."""

import os
import tempfile
import numpy as np
import cv2
import pytest
from pathlib import Path

from src.reconstruction.pipeline import ReconstructionPipeline


@pytest.fixture
def temp_images_dir():
    """Create a temporary directory with valid and invalid sample images."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Create 3 valid synthetic images
        img1_path = tmp_path / "img1.png"
        img2_path = tmp_path / "img2.png"
        img3_path = tmp_path / "img3.png"
        
        cv2.imwrite(str(img1_path), np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))
        cv2.imwrite(str(img2_path), np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))
        cv2.imwrite(str(img3_path), np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))

        # Create a corrupt file
        corrupt_path = tmp_path / "corrupt.png"
        with open(corrupt_path, "w") as f:
            f.write("NOT_AN_IMAGE_FILE")

        yield {
            "root": tmp_path,
            "valid": [img1_path, img2_path, img3_path],
            "corrupt": corrupt_path
        }


def test_image_validation_success(temp_images_dir):
    """Test validation with 3 valid synthetic images."""
    valid_paths = temp_images_dir["valid"]
    workspace = temp_images_dir["root"] / "workspace"
    output = temp_images_dir["root"] / "output"

    pipeline = ReconstructionPipeline(
        job_id="test_job_val",
        input_image_paths=valid_paths,
        workspace_dir=workspace,
        output_dir=output,
        max_image_dim=1000
    )

    success = pipeline.validate_and_preprocess_images()
    assert success is True
    assert len(list(pipeline.images_dir.glob("*.png"))) == 3


def test_image_validation_insufficient_images(temp_images_dir):
    """Test validation fails when fewer than 3 images are provided."""
    only_two_paths = temp_images_dir["valid"][:2]
    workspace = temp_images_dir["root"] / "workspace"
    output = temp_images_dir["root"] / "output"

    pipeline = ReconstructionPipeline(
        job_id="test_job_insufficient",
        input_image_paths=only_two_paths,
        workspace_dir=workspace,
        output_dir=output
    )

    success = pipeline.validate_and_preprocess_images()
    assert success is False
