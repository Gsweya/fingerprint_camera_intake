"""
live_demo.py — Webcam preview with on-demand fingerprint register / verify /
match actions.

Controls:
    c = capture current frame and run the selected mode
    q = quit

Examples:
    python live_demo.py --mode register --id person_001 --name "Alice"
    python live_demo.py --mode verify --id person_001
    python live_demo.py --mode match
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import cv2

from db import load_registry_map
from enroll import enroll
from match import match
from verify import verify


def _label_for(person_id: str) -> str:
    row = load_registry_map().get(person_id)
    if not row:
        return person_id
    name = row.get("name") or person_id
    return name if name == person_id else f"{name} ({person_id})"


def run_live_demo(
    *,
    mode: str,
    person_id: str | None,
    name: str | None,
    threshold: float,
    camera_index: int,
    auto_crop: bool,
    test_mode: bool,
    max_dim: int | None,
):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}")

    window = "FingerCap Live Demo"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    status = "press c to capture, q to quit"
    last_result = ""

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                status = "camera frame read failed"
                frame = None

            if frame is not None:
                preview = frame.copy()
                lines = [
                    f"mode: {mode}",
                    f"status: {status}",
                    f"last: {last_result}",
                    "keys: c=capture  q=quit",
                ]
                if mode in {"register", "verify"} and person_id:
                    lines.insert(1, f"id: {_label_for(person_id)}")
                y = 30
                for line in lines:
                    cv2.putText(
                        preview,
                        line,
                        (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        (0, 255, 0),
                        2,
                        cv2.LINE_AA,
                    )
                    y += 30
                cv2.imshow(window, preview)

            key = cv2.waitKey(30) & 0xFF
            if key == ord("q"):
                break
            if key != ord("c") or frame is None:
                continue

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                cv2.imwrite(str(tmp_path), frame)

            try:
                status = f"captured {tmp_path.name}"
                if mode == "register":
                    if not person_id:
                        raise ValueError("--id is required for register mode")
                    enroll(
                        str(tmp_path),
                        person_id,
                        name=name,
                        auto_crop=auto_crop,
                        test_mode=test_mode,
                        max_dim=max_dim,
                    )
                    last_result = f"registered {_label_for(person_id)}"
                    status = "register complete"
                elif mode == "verify":
                    if not person_id:
                        raise ValueError("--id is required for verify mode")
                    result = verify(
                        str(tmp_path),
                        person_id,
                        threshold,
                        auto_crop=auto_crop,
                        test_mode=test_mode,
                        max_dim=max_dim,
                    )
                    last_result = f"verify result: {result}"
                    status = "verify complete"
                elif mode == "match":
                    result = match(
                        str(tmp_path),
                        threshold,
                        auto_crop=auto_crop,
                        test_mode=test_mode,
                        max_dim=max_dim,
                    )
                    last_result = f"match result: {result}"
                    status = "match complete"
                else:
                    raise ValueError("mode must be register, verify, or match")
            except Exception as exc:
                last_result = f"error: {exc}"
                status = "action failed"
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["register", "verify", "match"], default="match")
    parser.add_argument("--id", default=None, help="Claimed person ID for register/verify")
    parser.add_argument("--name", default=None, help="Human-readable name for register mode")
    parser.add_argument("--threshold", type=float, default=40.0)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--no-auto-crop", action="store_true")
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--max-dim", type=int, default=None)
    args = parser.parse_args()

    run_live_demo(
        mode=args.mode,
        person_id=args.id,
        name=args.name,
        threshold=args.threshold,
        camera_index=args.camera_index,
        auto_crop=not args.no_auto_crop,
        test_mode=args.test_mode,
        max_dim=args.max_dim,
    )
