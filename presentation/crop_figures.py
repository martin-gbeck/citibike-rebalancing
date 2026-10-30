"""Copies the report figures into img/ without their title and subtitle, which the slide carries instead."""

from pathlib import Path

import numpy as np
from PIL import Image

FIGURES = Path(__file__).parent.parent / "figures"
OUT = Path(__file__).parent / "img"


def text_bands(ink: np.ndarray) -> list[tuple[int, int]]:
    """Runs of rows that hold any ink, top to bottom."""
    bands, start = [], None
    for y, has_ink in enumerate(ink):
        if has_ink and start is None:
            start = y
        elif not has_ink and start is not None:
            bands.append((start, y))
            start = None
    return bands


for path in sorted(FIGURES.glob("fig*.png")):
    image = Image.open(path).convert("RGB")
    pixels = np.asarray(image).astype(int)
    ink = (pixels.min(axis=2) < 200).any(axis=1)
    # the title and the subtitle are the first two bands of ink; everything below them is the chart
    _, subtitle_end = text_bands(ink)[1]
    image.crop((0, subtitle_end + 12, image.width, image.height)).save(OUT / path.name)
    print(path.name, image.size, "->", subtitle_end)
