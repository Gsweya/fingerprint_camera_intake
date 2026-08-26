"""
enroll.py — Preprocess a finger photo, extract a SourceAFIS template,
and store it in the local template DB.

Usage:
    python enroll.py --image sample_finger_1.jpg --id person_001
"""

import argparse
from sourceafis import FingerprintTemplate, FingerprintImage

from preprocess import preprocess
from db import save_template


def enroll(image_path: str, person_id: str):
    ridge_image = preprocess(image_path)

    # SourceAFIS wants raw grayscale/binary image bytes; it does its own
    # minutiae extraction internally from the ridge-skeleton PNG we pass in.
    fp_image = FingerprintImage(ridge_image.tobytes(),
                                 width=ridge_image.shape[1],
                                 height=ridge_image.shape[0])
    template = FingerprintTemplate(fp_image)

    save_template(person_id, template.to_bytes())
    print(f"Enrolled '{person_id}' from {image_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to finger photo")
    parser.add_argument("--id", required=True, help="Unique person/ID to store under")
    args = parser.parse_args()
    enroll(args.image, args.id)
