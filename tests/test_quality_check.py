import cv2
import numpy as np

from src.reconstruction.quality_check import analyze_images
from tests.conftest import textured_image


def test_good_images_pass_and_overlap_is_measured(tmp_path):
    base = textured_image(1, (480, 360))
    paths = []
    for i, shift in enumerate((0, 12, 24)):  # same scene, small translations => strong overlap
        M = np.float32([[1, 0, shift], [0, 1, 0]])
        p = tmp_path / f"s{i}.png"
        cv2.imwrite(str(p), cv2.warpAffine(base, M, (480, 360), borderValue=(90, 90, 90)))
        paths.append(p)
    rep = analyze_images(paths)
    assert rep["image_count"] == 3 and rep["can_proceed"]
    assert all(i["keypoints"] > 100 for i in rep["images"])
    assert all(p["matches"] > 20 and not p["warning"] for p in rep["pairs"])


def test_unrelated_images_warn_about_overlap(tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"u{i}.png"
        cv2.imwrite(str(p), textured_image(100 + i, (480, 360)))
        paths.append(p)
    rep = analyze_images(paths)
    assert any(p["warning"] for p in rep["pairs"])
    assert any(m["level"] == "warn" and "overlap" in m["text"].lower() for m in rep["messages"])


def test_blurry_dark_and_corrupt_images_are_flagged(tmp_path):
    flat = tmp_path / "flat.png"
    cv2.imwrite(str(flat), np.full((300, 300, 3), 10, np.uint8))
    corrupt = tmp_path / "bad.png"
    corrupt.write_bytes(b"not an image")
    good = tmp_path / "good.png"
    cv2.imwrite(str(good), textured_image(5, (480, 360)))
    rep = analyze_images([flat, corrupt, good])
    by = {i["name"]: i for i in rep["images"]}
    assert by["bad.png"]["status"] == "error"
    assert by["flat.png"]["status"] == "warn" and any("dark" in s or "blurry" in s for s in by["flat.png"]["issues"])
    assert not rep["can_proceed"]  # a corrupt file is an error


def test_too_few_images_cannot_proceed(tmp_path):
    p = tmp_path / "a.png"
    cv2.imwrite(str(p), textured_image(1))
    assert not analyze_images([p])["can_proceed"]
