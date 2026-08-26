"""
api.py — Minimal Flask endpoint so the Android app can POST a captured
finger photo and get enroll/match results back, instead of running the
Python pipeline locally on-device.

Run:
    python api.py
    # listens on 0.0.0.0:5000

Endpoints:
    POST /enroll   multipart form: image=<file>, person_id=<str>
    POST /match    multipart form: image=<file>

NOTE: no auth, no TLS here — this is for local network live-testing only.
Add auth (API key/JWT) and HTTPS before this touches anything but a lab bench.
"""

import tempfile
import os
from flask import Flask, request, jsonify

from enroll import enroll
from match import match

app = Flask(__name__)


@app.post("/enroll")
def api_enroll():
    if "image" not in request.files or "person_id" not in request.form:
        return jsonify({"error": "need 'image' file and 'person_id' field"}), 400

    image = request.files["image"]
    person_id = request.form["person_id"]

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        image.save(tmp.name)
        tmp_path = tmp.name

    try:
        enroll(tmp_path, person_id)
        return jsonify({"status": "enrolled", "person_id": person_id})
    finally:
        os.unlink(tmp_path)


@app.post("/match")
def api_match():
    if "image" not in request.files:
        return jsonify({"error": "need 'image' file"}), 400

    image = request.files["image"]
    threshold = float(request.form.get("threshold", 40.0))

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        image.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = match(tmp_path, threshold)
        return jsonify({"matched_id": result})
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
