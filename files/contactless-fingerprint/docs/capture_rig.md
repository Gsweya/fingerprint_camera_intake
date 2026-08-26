# Capture Rig Notes

Camera-based fingerprint capture lives or dies on the physical setup, not the
software. Rough guidance for anything beyond a toy test:

## Lighting
- Use **raking light** — light source at a low angle (~20-30°) to the finger
  surface, not straight-on flash. This casts shadows in the ridge valleys and
  is what makes ridges visible at all in a photo.
- Two small LEDs at opposing low angles reduces single-direction shadow bias.
- Avoid the phone's built-in flash alone — it's axial (same direction as the
  lens), which flattens ridge contrast rather than enhancing it.

## Distance / focus
- Macro range: ~5-8cm from lens, depending on the phone's macro capability.
- Lock focus (tap-to-focus) rather than relying on continuous autofocus —
  finger movement during continuous AF causes blur.
- A basic 3D-printed or cardboard stand-off cone helps keep distance
  consistent across captures.

## Resolution / DPI equivalent
- Dedicated sensors: ~500 DPI over a small area (~1.6cm x 1.6cm) = quite
  dense ridge detail.
- Phone camera: 12MP+ at 5-8cm gets you into a comparable *pixel* density,
  but real detail is limited by lens sharpness, motion blur, and skin
  reflectance — expect meaningfully lower effective resolution than a sensor.

## Background / contamination
- Plain, matte, non-reflective background behind/under the finger.
- Skin oil/moisture causes specular highlights that block ridge detail —
  matte surface + slightly angled light minimizes this.

## Validation before trusting any threshold
Don't guess a match/no-match threshold. Build a small labeled test set:
- Multiple captures of the *same* finger (different sessions) → genuine pairs
- Captures from *different* people's same-position finger → impostor pairs
Run both through `match.py`, plot score distributions, and pick a threshold
that separates them for your specific rig — thresholds are not portable
across capture setups.
