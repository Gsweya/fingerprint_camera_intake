"""
verify.py — Preprocess a finger photo, extract its template, and verify a
claimed identity against the local DB.

Usage:
    python verify.py --image sample_finger_1.jpg --id person_001 --threshold 40
"""

import argparse
from sourceafis import FingerprintTemplate, FingerprintImage, FingerprintMatcher

from preprocess import preprocess
from db import load_template, lookup_registry


def _label_for(person_id: str) -> str:
    row = lookup_registry(person_id)
    if not row:
        return person_id
    name = row.get("name") or person_id
    if name == person_id:
        return person_id
    return f"{name} ({person_id})"


def verify(
    image_path: str,
    person_id: str,
    threshold: float = 40.0,
    *,
    auto_crop: bool = True,
    test_mode: bool = False,
    max_dim: int | None = None,
):
    template_bytes = load_template(person_id)
    if template_bytes is None:
        print(f"NO SUCH PERSON: {_label_for(person_id)}")
        return None

    ridge_image = preprocess(
        image_path,
        auto_crop=auto_crop,
        test_mode=test_mode,
        max_dim=max_dim,
    )
    fp_image = FingerprintImage(
        ridge_image.tobytes(),
        width=ridge_image.shape[1],
        height=ridge_image.shape[0],
    )
    probe_template = FingerprintTemplate(fp_image)
    claimed_template = FingerprintTemplate.from_bytes(template_bytes)
    matcher = FingerprintMatcher(probe_template)
    score = matcher.match(claimed_template)

    if score >= threshold:
        print(
            f"VERIFIED: {_label_for(person_id)} "
            f"(score={score:.1f}, threshold={threshold})"
        )
        return person_id

    print(
        f"REJECTED: {_label_for(person_id)} "
        f"(score={score:.1f} < threshold={threshold})"
    )
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to finger photo to verify")
    parser.add_argument("--id", required=True, help="Claimed person ID to verify against")
    parser.add_argument("--threshold", type=float, default=40.0)
    parser.add_argument("--no-auto-crop", action="store_true", help="Disable automatic skin-region crop")
    parser.add_argument("--test-mode", action="store_true", help="Use faster smaller working sizes")
    parser.add_argument("--max-dim", type=int, default=None, help="Force a maximum working dimension")
    args = parser.parse_args()
    verify(
        args.image,
        args.id,
        args.threshold,
        auto_crop=not args.no_auto_crop,
        test_mode=args.test_mode,
        max_dim=args.max_dim,
    )
