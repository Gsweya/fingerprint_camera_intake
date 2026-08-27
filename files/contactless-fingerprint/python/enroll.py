"""
enroll.py — Preprocess a finger photo, extract a fingerprint template,
and store it in the local template DB.

Usage:
    python enroll.py --image sample_finger_1.jpg --id person_001 --name "Alice"
"""

import argparse
from sourceafis import FingerprintTemplate, FingerprintImage

from preprocess import preprocess
from db import save_template, save_registry_entry


def enroll(
    image_path: str,
    person_id: str,
    *,
    name: str | None = None,
    notes: str = "",
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

    # The compatibility layer extracts minutiae from the ridge-skeleton PNG
    # and stores a pickled template payload in the local DB.
    fp_image = FingerprintImage(ridge_image.tobytes(),
                                 width=ridge_image.shape[1],
                                 height=ridge_image.shape[0])
    template = FingerprintTemplate(fp_image)

    save_template(person_id, template.to_bytes())
    save_registry_entry(person_id, name or person_id, notes=notes)
    print(f"Enrolled '{name or person_id}' (id={person_id}) from {image_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to finger photo")
    parser.add_argument("--id", required=True, help="Unique person/ID to store under")
    parser.add_argument("--name", default=None, help="Human-readable name for registry.csv")
    parser.add_argument("--notes", default="", help="Optional notes for the registry")
    parser.add_argument("--no-auto-crop", action="store_true", help="Disable automatic skin-region crop")
    parser.add_argument("--test-mode", action="store_true", help="Use faster smaller working sizes")
    parser.add_argument("--max-dim", type=int, default=None, help="Force a maximum working dimension")
    args = parser.parse_args()
    enroll(
        args.image,
        args.id,
        name=args.name,
        notes=args.notes,
        auto_crop=not args.no_auto_crop,
        test_mode=args.test_mode,
        max_dim=args.max_dim,
    )
