"""
preprocess.py — Turn a raw finger photo into a clean ridge image
suitable for minutiae extraction.

Pipeline:
  1. Load image
  2. Optionally auto-crop the skin region / finger region
  3. Downscale for faster debug/test runs
  4. Convert to grayscale
  5. CLAHE contrast enhancement
  6. Adaptive threshold -> binary ridge/valley image
  7. Morphological thinning -> 1px-wide ridge skeleton

This is the part that differs most from "real" fingerprint sensor pipelines,
since a camera photo has uneven lighting, skin tone variance, and no direct
contact pressure info. The auto-crop is a pragmatic heuristic for phone photos
where the finger occupies only part of the frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize


@dataclass
class PreprocessResult:
    skeleton: np.ndarray
    gray: np.ndarray
    enhanced: np.ndarray
    binary: np.ndarray
    crop_box: tuple[int, int, int, int] | None


def load_image(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    return img


def resize_max_dim(image: np.ndarray, max_dim: int | None) -> np.ndarray:
    if not max_dim:
        return image
    h, w = image.shape[:2]
    largest = max(h, w)
    if largest <= max_dim:
        return image
    scale = max_dim / float(largest)
    new_size = (int(round(w * scale)), int(round(h * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def skin_mask(bgr: np.ndarray) -> np.ndarray:
    """Heuristic skin detector for warm-lit phone photos."""
    b, g, r = cv2.split(bgr)
    max_rgb = np.maximum(np.maximum(r, g), b)
    min_rgb = np.minimum(np.minimum(r, g), b)
    mask = (
        (r > 95) &
        (g > 40) &
        (b > 20) &
        ((max_rgb - min_rgb) > 15) &
        (np.abs(r - g) > 15) &
        (r > g) &
        (r > b)
    )
    return (mask.astype(np.uint8) * 255)


def largest_skin_crop(
    image: np.ndarray,
    *,
    max_dim: int = 1400,
    padding_ratio: float = 0.08,
    min_area_ratio: float = 0.02,
) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    """Return a cropped version of the image around the largest skin region."""
    small = resize_max_dim(image, max_dim)
    mask = skin_mask(small)
    kernel = np.ones((11, 11), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image, None

    img_area = small.shape[0] * small.shape[1]
    best = None
    best_area = 0.0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > best_area:
            best = contour
            best_area = area

    if best is None or best_area < img_area * min_area_ratio:
        return image, None

    x, y, w, h = cv2.boundingRect(best)
    pad_x = int(round(w * padding_ratio))
    pad_y = int(round(h * padding_ratio))
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(small.shape[1], x + w + pad_x)
    y1 = min(small.shape[0], y + h + pad_y)

    # Map the crop back to the original image coordinates.
    scale_x = image.shape[1] / float(small.shape[1])
    scale_y = image.shape[0] / float(small.shape[0])
    ox0 = int(round(x0 * scale_x))
    oy0 = int(round(y0 * scale_y))
    ox1 = int(round(x1 * scale_x))
    oy1 = int(round(y1 * scale_y))
    ox0 = max(0, ox0)
    oy0 = max(0, oy0)
    ox1 = min(image.shape[1], ox1)
    oy1 = min(image.shape[0], oy1)

    if ox1 <= ox0 or oy1 <= oy0:
        return image, None

    return image[oy0:oy1, ox0:ox1], (ox0, oy0, ox1, oy1)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def binarize(enhanced: np.ndarray) -> np.ndarray:
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
    bool_img = binary > 0
    skeleton = skeletonize(bool_img)
    return (skeleton * 255).astype(np.uint8)


def preprocess(
    image_path: str,
    save_debug: bool = False,
    *,
    auto_crop: bool = True,
    test_mode: bool = False,
    max_dim: int | None = None,
) -> np.ndarray:
    """
    Return a ridge skeleton image.

    test_mode uses a smaller working size so the AFIS extractor can finish more
    quickly on large phone photos.
    """
    color = load_image(image_path)
    crop_box = None

    if auto_crop:
        crop_max_dim = 1000 if test_mode else 1600
        color, crop_box = largest_skin_crop(color, max_dim=crop_max_dim)

    work_max_dim = max_dim
    if work_max_dim is None:
        work_max_dim = 512 if test_mode else 1400
    color = resize_max_dim(color, work_max_dim)
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    enhanced = enhance_contrast(gray)
    binary = binarize(enhanced)
    skeleton = thin_ridges(binary)

    if test_mode:
        # Keep the debug path intentionally small so template extraction does
        # not spend most of its time on a giant phone image.
        skeleton = resize_max_dim(skeleton, 256)

    if save_debug:
        cv2.imwrite("_debug_crop.png", color)
        cv2.imwrite("_debug_gray.png", gray)
        cv2.imwrite("_debug_enhanced.png", enhanced)
        cv2.imwrite("_debug_binary.png", binary)
        cv2.imwrite("_debug_skeleton.png", skeleton)
        if crop_box is not None:
            Path("_debug_crop_box.txt").write_text(
                f"{crop_box[0]},{crop_box[1]},{crop_box[2]},{crop_box[3]}\n",
                encoding="utf-8",
            )

    return skeleton


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to finger photo")
    parser.add_argument("--no-auto-crop", action="store_true")
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--max-dim", type=int, default=None)
    args = parser.parse_args()

    result = preprocess(
        args.image,
        save_debug=True,
        auto_crop=not args.no_auto_crop,
        test_mode=args.test_mode,
        max_dim=args.max_dim,
    )
    cv2.imwrite("output_ridge_image.png", result)
    print("Wrote output_ridge_image.png and _debug_*.png for inspection")
