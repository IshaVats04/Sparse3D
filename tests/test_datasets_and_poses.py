import cv2
import numpy as np

from src.reconstruction import datasets
from src.reconstruction.metrics import align_by_cameras, decompose_projection, umeyama


def build_fake_dtu(root, scan=1, cams=(1, 9, 17, 25, 33, 41), lightings=(0, 3)):
    mvs = root / "SampleSet" / "MVS Data"
    (mvs / "Cleaned" / f"scan{scan}").mkdir(parents=True)
    (mvs / "Calibration" / "cal18").mkdir(parents=True)
    (mvs / "Points" / "stl").mkdir(parents=True)
    for c in cams:
        for light in lightings:
            cv2.imwrite(str(mvs / "Cleaned" / f"scan{scan}" / f"clean_{c:03d}_{light}_r5000.png"),
                        np.full((60, 80, 3), 100, np.uint8))
        K = np.array([[100.0, 0, 40], [0, 100, 30], [0, 0, 1]])
        Rt = np.hstack([np.eye(3), np.array([[0.0], [0.0], [c * 1.0]])])
        np.savetxt(mvs / "Calibration" / "cal18" / f"pos_{c:03d}.txt", K @ Rt)
    (mvs / "Points" / "stl" / f"stl{scan:03d}_total.ply").write_text("ply\nformat ascii 1.0\nend_header\n")
    return mvs


def test_discovers_dtu_layout_with_ground_truth_and_poses(tmp_path, monkeypatch):
    build_fake_dtu(tmp_path)
    monkeypatch.setenv("SPARSE3D_DATASET_DIR", str(tmp_path))
    dtu = [d for d in datasets.discover() if d.kind == "dtu"]
    assert len(dtu) == 1
    scan = dtu[0].scans["scan1"]
    assert scan.cameras == [1, 9, 17, 25, 33, 41] and scan.lightings == [0, 3]
    assert scan.ground_truth is not None and scan.projection(9).shape == (3, 4)
    assert scan.projection(2) is None


def test_select_images_defaults_and_errors(tmp_path, monkeypatch):
    build_fake_dtu(tmp_path)
    monkeypatch.setenv("SPARSE3D_DATASET_DIR", str(tmp_path))
    scan = next(d for d in datasets.discover() if d.kind == "dtu").scans["scan1"]
    refs = datasets.select_images(scan, [9, 25], lighting=3)
    assert [r.camera for r in refs] == [9, 25] and all(r.lighting == 3 for r in refs)
    assert len(datasets.select_images(scan)) == 6
    try:
        datasets.select_images(scan, [2])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_plain_folder_is_a_dataset(tmp_path, monkeypatch):
    d = tmp_path / "my_mug"
    d.mkdir()
    for i in range(4):
        cv2.imwrite(str(d / f"p{i}.jpg"), np.zeros((40, 40, 3), np.uint8))
    monkeypatch.setenv("SPARSE3D_DATASET_DIR", str(tmp_path))
    folders = [x for x in datasets.discover() if x.kind == "folder"]
    assert any(f.name == "my_mug" and len(f.scans["all"].images) == 4 for f in folders)


def test_umeyama_recovers_similarity():
    rng = np.random.default_rng(0)
    src = rng.normal(size=(20, 3))
    ang = 0.8
    R = np.array([[np.cos(ang), -np.sin(ang), 0], [np.sin(ang), np.cos(ang), 0], [0, 0, 1]])
    dst = 2.5 * (R @ src.T).T + np.array([1.0, -2.0, 3.0])
    s, R2, t, resid = umeyama(src, dst)
    assert abs(s - 2.5) < 1e-6 and np.allclose(R2, R, atol=1e-6) and resid < 1e-6


def test_pose_error_is_zero_for_a_similarity_transformed_camera_set():
    gt, pred = {}, {}
    # ground-truth cameras on an arc, each looking at the origin
    q = np.sqrt(0.5)
    S = np.array([[q, -q, 0], [q, q, 0], [0, 0, 1.0]])  # arbitrary reconstruction-frame rotation (45 deg about z)
    for i in range(5):
        a = i * 0.4
        c = np.array([5 * np.cos(a), 5 * np.sin(a), 1.0 + 0.2 * i])
        z = -c / np.linalg.norm(c)
        x = np.cross([0, 0, 1.0], z)
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        R = np.stack([x, y, z])           # world-to-camera
        gt[f"i{i}"] = (R, c)
        c_pred = 0.5 * S @ c + 3.0        # similarity: scale 0.5, rotate, shift
        pred[f"i{i}"] = (R @ S.T, c_pred)
    res = align_by_cameras(pred, gt)
    assert res["pose_error_deg"] < 1e-3 and res["relative_residual"] < 1e-6
    assert abs(res["scale"] - 2.0) < 1e-6
    assert align_by_cameras({"a": pred["i0"]}, gt) is None


def test_decompose_projection_roundtrip():
    K = np.array([[100.0, 0, 40], [0, 100, 30], [0, 0, 1]])
    R = np.eye(3)
    t = np.array([[1.0], [2.0], [3.0]])
    P = K @ np.hstack([R, t])
    R2, c = decompose_projection(P)
    assert np.allclose(R2, R, atol=1e-6) and np.allclose(c, -R.T @ t.ravel(), atol=1e-6)
