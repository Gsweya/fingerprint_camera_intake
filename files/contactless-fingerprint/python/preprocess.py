"""
preprocess.py — Turn a raw finger photo into a clean ridge image
suitable for minutiae extraction.

Pipeline:
  1. Load image, convert to grayscale
  2. CLAHE contrast enhancement (brings out faint ridges from skin photos)
  3. Adaptive threshold -> binary ridge/valley image
  4. Morphological thinning -> 1px-wide ridge skeleton (what SourceAFIS expects)

This is the part that differs most from "real" fingerprint sensor pipelines,
since a camera photo has uneven lighting, skin tone variance, and no direct
contact pressure info. Tune CLAHE clip limit / threshold block size per your
capture rig (lighting setup, distance) — defaults below are a reasonable start.
"""

import cv2
import numpy as np
from skimage.morphology import skeletonize


def load_and_crop_finger(image_path: str) -> np.ndarray:
    """Load image and convert to grayscale. Assumes the finger roughly
    fills the frame — for a real app, add finger-region detection
    (e.g. skin-color segmentation) before this step."""
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return gray


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    """CLAHE — brings out ridge/valley contrast that's normally very faint
    in a plain camera photo (unlike a capacitive sensor which measures
    ridges directly)."""
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def binarize(enhanced: np.ndarray) -> np.ndarray:
    """Adaptive threshold — local, so it copes with uneven lighting
    across the finger surface (a major failure mode vs. sensor capture)."""
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=25,
        C=8,
    )
    return binary


def thin_ridges(binary: np.ndarray) -> np.ndarray:
    """Skeletonize to 1px ridge lines — minutiae extractors expect this."""
    bool_img = binary > 0
    skeleton = skeletonize(bool_img)
    return (skeleton * 255).astype(np.uint8)


def preprocess(image_path: str, save_debug: bool = False) -> np.ndarray:
    gray = load_and_crop_finger(image_path)
    enhanced = enhance_contrast(gray)
    binary = binarize(enhanced)
    skeleton = thin_ridges(binary)

    if save_debug:
        cv2.imwrite("_debug_gray.png", gray)
        cv2.imwrite("_debug_enhanced.png", enhanced)
        cv2.imwrite("_debug_binary.png", binary)
        cv2.imwrite("_debug_skeleton.png", skeleton)

    return skeleton


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python preprocess.py <finger_photo.jpg>")
        sys.exit(1)
    result = preprocess(sys.argv[1], save_debug=True)
    cv2.imwrite("output_ridge_image.png", result)
    print("Wrote output_ridge_image.png and _debug_*.png for inspection")
