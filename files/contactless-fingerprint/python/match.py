"""
match.py — Preprocess a new finger photo, extract its template, and
match (1:N) against every template in the local DB.

Usage:
    python match.py --image sample_finger_1_retake.jpg --threshold 40

SourceAFIS match scores: roughly 0-100+, no fixed scale. As a starting
point, ~40 is often used as a false-accept-rate-conscious threshold for
sensor-captured prints; for camera-based captures you should calibrate
your OWN threshold using a labeled test set (matching photo pairs vs.
non-matching pairs) rather than trusting this default.
"""

import argparse
from sourceafis import FingerprintTemplate, FingerprintImage, FingerprintMatcher

from preprocess import preprocess
from db import load_all_templates


def match(image_path: str, threshold: float = 40.0):
    ridge_image = preprocess(image_path)
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
        print(f"MATCH: {best_id} (score={best_score:.1f}, threshold={threshold})")
        return best_id
    else:
        print(f"NO MATCH (best candidate {best_id}, score={best_score:.1f} < threshold={threshold})")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to finger photo to verify")
    parser.add_argument("--threshold", type=float, default=40.0)
    args = parser.parse_args()
    match(args.image, args.threshold)
