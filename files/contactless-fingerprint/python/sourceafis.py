"""
Compatibility layer for the old SourceAFIS-style imports used by this
prototype.

The original repo pinned an unavailable `sourceafis` package. This module
keeps the existing `from sourceafis import ...` imports working while routing
the implementation through the installed `afis` package.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from afis import SafisExtractor, match_templates, FingerprintTemplate as AfisFingerprintTemplate
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise ImportError(
        "The `afis` package is required. Install it with `pip install -r "
        "requirements.txt`."
    ) from exc


@dataclass
class FingerprintImage:
    data: bytes
    width: int
    height: int

    def to_array(self) -> np.ndarray:
        array = np.frombuffer(self.data, dtype=np.uint8)
        return array.reshape((self.height, self.width))


class FingerprintTemplate:
    """
    Minimal wrapper that preserves the old SourceAFIS-style API.
    """

    def __init__(self, image: FingerprintImage):
        if not isinstance(image, FingerprintImage):
            raise TypeError("FingerprintTemplate expects a FingerprintImage")

        ridge = image.to_array()
        if ridge.ndim != 2:
            raise ValueError("FingerprintImage data must be grayscale")

        template = SafisExtractor().extract_minutiae(ridge)
        self._template = template
        self.minutiae = template.minutiae
        self.header = template.header
        self.report = template.report

    def to_bytes(self) -> bytes:
        return self._template.to_json().encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes):
        template = AfisFingerprintTemplate.from_json(data.decode("utf-8"))
        instance = cls.__new__(cls)
        instance._template = template
        instance.minutiae = template.minutiae
        instance.header = template.header
        instance.report = template.report
        return instance


class FingerprintMatcher:
    def __init__(self, probe_template: FingerprintTemplate):
        self.probe_template = probe_template

    def match(self, candidate: FingerprintTemplate) -> float:
        result = match_templates(
            self.probe_template.minutiae,
            candidate.minutiae,
            method="safis",
        )
        raw_score = getattr(result, "raw_score", None)
        if raw_score is not None:
            return float(raw_score)
        return float(getattr(result, "score", result)) * 100.0
