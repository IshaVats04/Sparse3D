"""Input image quality and pairwise-overlap analysis (Feature 2 of the project spec).

Per image: resolution, blur (variance of the Laplacian), brightness, SIFT keypoint count.
Per image pair: ratio-test SIFT matches, geometrically verified with a RANSAC fundamental matrix, and an
approximate overlap percentage (inlier matches relative to the smaller keypoint set).
"""

import itertools
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

MIN_SIDE_PX = 256
BLUR_WARN = 60.0           # variance of Laplacian below this looks blurry
DARK_WARN, BRIGHT_WARN = 40.0, 220.0
MIN_KEYPOINTS_WARN = 150
MIN_PAIR_INLIERS = 20
ANALYSIS_SIDE = 800        # images are downscaled to this long side for analysis only


try:  # optional: iPhone HEIC/HEIF photos
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:
    HEIF_SUPPORTED = False


def read_image(path: Path) -> Optional[np.ndarray]:
    """Read any common photo as a BGR array, honouring EXIF orientation, with Unicode-safe I/O.

    OpenCV decodes the usual formats (and applies EXIF rotation). Anything it cannot read (16-bit or palette
    variants, HEIC when pillow-heif is installed) goes through Pillow.
    """
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is not None:
            return img
    except Exception:
        pass
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def write_image(path: Path, img: np.ndarray, ext: str = ".png") -> bool:
    """Write an image with Unicode-safe I/O."""
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    buf.tofile(str(path))
    return True


def _small_gray(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    scale = ANALYSIS_SIDE / max(h, w)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def compute_features(paths: Sequence[Path], max_features: int = 2000) -> Dict[str, Any]:
    """SIFT keypoints/descriptors per image (analysis resolution)."""
    sift = cv2.SIFT_create(nfeatures=max_features)
    out: Dict[str, Any] = {}
    for p in paths:
        img = read_image(p)
        if img is None:
            out[p.name] = None
            continue
        gray = _small_gray(img)
        kps, desc = sift.detectAndCompute(gray, None)
        out[p.name] = {"img": img, "gray": gray, "kps": kps, "desc": desc}
    return out


def match_pair(fa: Dict[str, Any], fb: Dict[str, Any]) -> Tuple[int, float]:
    """Return (verified matches, overlap percent) for two feature sets."""
    if not fa or not fb or fa["desc"] is None or fb["desc"] is None:
        return 0, 0.0
    if len(fa["kps"]) < 8 or len(fb["kps"]) < 8:
        return 0, 0.0
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    raw = matcher.knnMatch(fa["desc"], fb["desc"], k=2)
    good = [m for m, n in (r for r in raw if len(r) == 2) if m.distance < 0.8 * n.distance]
    if len(good) < 8:
        return len(good), 0.0
    pa = np.float32([fa["kps"][m.queryIdx].pt for m in good])
    pb = np.float32([fb["kps"][m.trainIdx].pt for m in good])
    _, mask = cv2.findFundamentalMat(pa, pb, cv2.FM_RANSAC, 3.0, 0.99)
    inliers = int(mask.sum()) if mask is not None else 0
    denom = max(1, min(len(fa["kps"]), len(fb["kps"])))
    return inliers, round(100.0 * inliers / denom, 1)


def analyze_images(paths: Sequence[Path]) -> Dict[str, Any]:
    """Build the validation report described in docs/API_CONTRACT.md."""
    feats = compute_features(paths)
    images: List[Dict[str, Any]] = []
    messages: List[Dict[str, str]] = []

    for p in paths:
        f = feats.get(p.name)
        if f is None:
            images.append({"name": p.name, "width": 0, "height": 0, "blur_score": 0.0, "brightness": 0.0,
                           "keypoints": 0, "status": "error", "issues": ["File is corrupt or not a readable image"]})
            continue
        h, w = f["img"].shape[:2]
        blur = float(cv2.Laplacian(f["gray"], cv2.CV_64F).var())
        bright = float(f["gray"].mean())
        n_kp = len(f["kps"])
        issues: List[str] = []
        status = "ok"
        if min(h, w) < MIN_SIDE_PX:
            issues.append(f"Resolution too low ({w}x{h}); at least {MIN_SIDE_PX}px on the short side")
            status = "error"
        if blur < BLUR_WARN:
            issues.append("Image looks blurry")
            status = "warn" if status == "ok" else status
        if bright < DARK_WARN:
            issues.append("Image is very dark")
            status = "warn" if status == "ok" else status
        elif bright > BRIGHT_WARN:
            issues.append("Image is over-exposed")
            status = "warn" if status == "ok" else status
        if n_kp < MIN_KEYPOINTS_WARN:
            issues.append(f"Few feature points ({n_kp}); the object may lack texture")
            status = "warn" if status == "ok" else status
        images.append({"name": p.name, "width": int(w), "height": int(h), "blur_score": round(blur, 1),
                       "brightness": round(bright, 1), "keypoints": int(n_kp), "status": status, "issues": issues})

    # Duplicate / near-identical detection and pairwise overlap
    pairs: List[Dict[str, Any]] = []
    valid = [p for p in paths if feats.get(p.name) is not None]
    for a, b in itertools.combinations(valid, 2):
        matches, overlap = match_pair(feats[a.name], feats[b.name])
        pairs.append({"a": a.name, "b": b.name, "matches": matches, "overlap_pct": overlap,
                      "warning": matches < MIN_PAIR_INLIERS})

    dup_names = set()
    for a, b in itertools.combinations(valid, 2):
        ga, gb = feats[a.name]["gray"], feats[b.name]["gray"]
        sa = cv2.resize(ga, (32, 32)).astype(np.float32)
        sb = cv2.resize(gb, (32, 32)).astype(np.float32)
        if float(np.abs(sa - sb).mean()) < 1.5:
            dup_names.add(b.name)
            for img in images:
                if img["name"] == b.name:
                    img["issues"].append(f"Near-duplicate of {a.name}")
                    img["status"] = "warn" if img["status"] == "ok" else img["status"]

    # Summary messages
    n = len(paths)
    if n < 3:
        messages.append({"level": "error", "text": f"{n} image(s) provided; at least 3 are required"})
    if n > 6:
        messages.append({"level": "error", "text": f"{n} images provided; at most 6 are supported in sparse-view mode"})
    if any(i["status"] == "error" for i in images):
        messages.append({"level": "error", "text": "One or more images cannot be used (see details)"})
    else:
        messages.append({"level": "ok", "text": f"Images uploaded: {n}"})
    if images and all(i["status"] != "error" and i["width"] >= MIN_SIDE_PX for i in images):
        messages.append({"level": "ok", "text": "Resolution acceptable"})
    low_kp = [i["name"] for i in images if i["keypoints"] < MIN_KEYPOINTS_WARN and i["keypoints"] > 0]
    if images and not low_kp and all(i["keypoints"] > 0 for i in images):
        messages.append({"level": "ok", "text": "Feature points detected in all images"})
    for i in images:
        for issue in i["issues"]:
            if i["status"] != "error":
                messages.append({"level": "warn", "text": f"{i['name']}: {issue}"})
    # one low-overlap warning per image that connects to no other image well
    for pr in pairs:
        if pr["warning"]:
            messages.append({"level": "warn",
                             "text": f"Low overlap between {pr['a']} and {pr['b']} ({pr['matches']} verified matches)"})
    # connectivity: every image should match at least one other image
    for img in images:
        if img["status"] == "error":
            continue
        best = max((pr["matches"] for pr in pairs if img["name"] in (pr["a"], pr["b"])), default=0)
        if len(valid) > 1 and best < MIN_PAIR_INLIERS:
            # Deliberately poor arrangements are a valid experiment, so this warns rather than blocks.
            messages.append({"level": "warn",
                             "text": f"{img['name']} barely overlaps with any other image; "
                                     "it will likely fail to register"})

    can_proceed = 3 <= n <= 6 and not any(m["level"] == "error" for m in messages)
    return {"image_count": n, "can_proceed": can_proceed, "images": images, "pairs": pairs,
            "messages": messages, "_duplicates": sorted(dup_names)}


def public_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal keys before sending a report to clients."""
    return {k: v for k, v in report.items() if not k.startswith("_")}

