"""Pipeline stage 1: image analysis, view selection and preprocessing (needs no COLMAP)."""

import cv2

from src.reconstruction.pipeline import ReconstructionPipeline
from tests.conftest import textured_image


def make_pipeline(tmp_path, paths, **opts):
    return ReconstructionPipeline("t1", paths, tmp_path / "ws", tmp_path / "out", options=opts)


def test_stage1_selects_subset_and_resizes(tmp_path):
    paths = []
    for i in range(5):
        p = tmp_path / f"in_{i}.png"
        cv2.imwrite(str(p), textured_image(i, (1800, 1200)))
        paths.append(p)
    pipe = make_pipeline(tmp_path, paths, num_views=3, view_arrangement="uniform", quality="fast")
    assert pipe.stage_image_analysis()
    assert len(pipe.selected) == 3
    processed = sorted((tmp_path / "ws" / "t1" / "images").glob("*.png"))
    assert len(processed) == 3
    for f in processed:
        h, w = cv2.imread(str(f)).shape[:2]
        assert max(h, w) <= 1024  # 'fast' preset
    assert set(pipe.name_map.values()) == set(pipe.selected)


def test_stage1_fails_with_too_few_usable_images(tmp_path):
    good = tmp_path / "ok.png"
    cv2.imwrite(str(good), textured_image(1))
    bad1, bad2 = tmp_path / "b1.png", tmp_path / "b2.png"
    bad1.write_bytes(b"junk")
    bad2.write_bytes(b"junk")
    pipe = make_pipeline(tmp_path, [good, bad1, bad2])
    assert not pipe.stage_image_analysis()


def test_invalid_options_are_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        make_pipeline(tmp_path, [], recon_method="magic")
    with pytest.raises(ValueError):
        make_pipeline(tmp_path, [], quality="ultra")
