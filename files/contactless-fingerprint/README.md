# Contactless Fingerprint Capture & Matching — Reference Pipeline

Research/prototype pipeline for **camera-based (contactless) fingerprint capture**,
preprocessing, minutiae extraction, and 1:N matching. This does **not** use any
phone's built-in capacitive fingerprint sensor (that data path is hardware-sealed
on all consumer Android devices) — it uses the regular camera, so accuracy depends
entirely on your capture rig (macro lens, lighting, distance).

## Architecture

```
[Android CameraX capture] --finger photo--> [upload/local file]
        |
        v
[Python: OpenCV preprocessing]  -- enhance, binarize, thin -->
        |
        v
[Python: AFIS compatibility layer] -- extract minutiae + template -->
        |
        v
[AFIS matcher] -- 1:1 or 1:N match against stored templates (SQLite/DB)
```

## Repo layout

```
contactless-fingerprint/
├── android/          # Kotlin CameraX capture app (finger photo -> file/API)
├── python/           # Preprocessing + enrollment + matching pipeline
│   ├── preprocess.py
│   ├── enroll.py
│   ├── match.py
│   ├── db.py
│   └── requirements.txt
└── docs/
    └── capture_rig.md
```

## Quick start (Python side — do this first to live-test on a laptop)

```bash
git clone <this-repo>
cd contactless-fingerprint/python
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Enroll a reference finger photo
python enroll.py --image sample_finger_1.jpg --id person_001

# Try to match a new photo against the enrolled DB
python match.py --image sample_finger_1_retake.jpg

# Verify a claimed identity against the DB
python verify.py --image sample_finger_1_retake.jpg --id person_001

# Live webcam demo
python live_demo.py --mode register --id person_001 --name "Alice"
python live_demo.py --mode verify --id person_001
python live_demo.py --mode match
```

No Android device needed to test the core pipeline — just feed it finger photos
taken with any phone camera (macro mode, good raking light, ~5-8cm distance).

### Registry and matching

- `enroll.py` stores the template in SQLite and also writes `registry.csv`
  with a human-readable name.
- `match.py` does 1:N identification and prints the name from the registry if
  it exists.
- `verify.py` does 1:1 verification against a claimed `person_id`.
- `live_demo.py` opens the webcam and lets you capture/register/verify/match
  with keyboard controls.
- `preprocess.py --test-mode` enables faster downscaled processing for large
  phone images.
- `preprocess.py` now auto-crops the skin region by default.

## Android app

Minimal CameraX app that:
1. Opens camera in macro-assisted mode
2. Captures a finger photo on tap
3. Saves it locally and/or POSTs it to a Flask endpoint running `python/api.py`

Build with Android Studio (`android/` as project root) or `./gradlew assembleDebug`.
Requires `minSdk 26+`. No special permissions beyond `CAMERA` and `INTERNET`.

## Accuracy expectations (be realistic)

- Dedicated capacitive sensors: ~500 DPI equivalent, controlled contact → low FAR/FRR
- Camera-based capture: highly variable — lighting, focus, finger curvature, motion
  blur all degrade minutiae quality. Expect noticeably higher false accept/reject
  rates unless you tightly control the capture rig (see `docs/capture_rig.md`).
- This is a **research/prototyping pipeline**, not a production-grade biometric
  system. Don't deploy for access control / identity verification without proper
  accuracy validation (FAR/FRR testing on a real dataset) and legal review — see
  note below.

## Legal / compliance note

Biometric data (fingerprints included) is regulated in most jurisdictions —
GDPR (EU) classifies it as "special category" data, several US states (Illinois
BIPA, Texas, Washington) have dedicated biometric privacy statutes with steep
per-violation penalties, and Tanzania's Personal Data Protection Act (2022)
also covers biometric identifiers as sensitive personal data requiring explicit
consent and a registered data-protection basis before collection. Before
collecting real fingerprints from real people (even for a pilot), get informed
consent, a lawful basis, and ideally legal sign-off — this applies regardless of
whether you use a dedicated sensor or a camera-based method.
