"""
match.py — Preprocess a new finger photo, extract its template, and
match (1:N) against every template in the local DB.

Usage:
    python match.py --image sample_finger_1_retake.jpg --threshold 40

Match scores are roughly 0-100+, no fixed scale. As a starting point,
~40 is often used as a false-accept-rate-conscious threshold for
sensor-captured prints; for camera-based captures you should calibrate
your OWN threshold using a labeled test set (matching photo pairs vs.
non-matching pairs) rather than trusting this default.
"""

import argparse
from sourceafis import FingerprintTemplate, FingerprintImage, FingerprintMatcher

from preprocess import preprocess
from db import load_all_templates, lookup_registry


def _label_for(person_id: str) -> str:
    row = lookup_registry(person_id)
    if not row:
        return person_id
    name = row.get("name") or person_id
    if name == person_id:
        return person_id
    return f"{name} ({person_id})"


def match(
    image_path: str,
    threshold: float = 40.0,
    *,
    auto_crop: bool = True,
    test_mode: bool = False,
    max_dim: int | None = None,
):
    ridge_image = preprocess(
        image_path,
        auto_crop=auto_crop,
        test_mode=test_mode,
        max_dim=max_dim,
    )
    fp_image = FingerprintImage(ridge_image.tobytes(),
                                 width=ridge_image.shape[1],
                                 height=ridge_image.shape[0])
    probe_template = FingerprintTemplate(fp_image)
    matcher = FingerprintMatcher(probe_template)

    best_id, best_score = None, -1.0
    for person_id, template_bytes in load_all_templates():
        candidate = FingerprintTemplate.from_bytes(template_bytes)
        score = matcher.match(candidate)
        if score > best_score:
            best_id, best_score = person_id, score

    if best_id is None:
        print("No enrolled templates in DB — run enroll.py first.")
        return None

    if best_score >= threshold:
        print(
            f"MATCH: {_label_for(best_id)} "
            f"(score={best_score:.1f}, threshold={threshold})"
        )
        return best_id
    else:
        print(
            "NO MATCH "
            f"(best candidate {_label_for(best_id)}, "
            f"score={best_score:.1f} < threshold={threshold})"
        )
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to finger photo to verify")
    parser.add_argument("--threshold", type=float, default=40.0)
    parser.add_argument("--no-auto-crop", action="store_true", help="Disable automatic skin-region crop")
    parser.add_argument("--test-mode", action="store_true", help="Use faster smaller working sizes")
    parser.add_argument("--max-dim", type=int, default=None, help="Force a maximum working dimension")
    args = parser.parse_args()
    match(
        args.image,
        args.threshold,
        auto_crop=not args.no_auto_crop,
        test_mode=args.test_mode,
        max_dim=args.max_dim,
    )
