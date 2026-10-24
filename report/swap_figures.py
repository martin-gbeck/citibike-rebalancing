"""Put the redrawn figures into the docx in place of the old ones, keeping each image's width
and fixing its height to the new aspect ratio. Nothing else in the document changes."""

import re
import shutil
import sys
import zipfile
from pathlib import Path

from PIL import Image

docx = Path(sys.argv[1])
figures = Path(sys.argv[2])
# the figures appear in the document in number order, and pandoc numbered the media the same way
order = [
    "fig1-daily-rhythm", "fig2-rush-map", "fig3-neighbourhood-clock", "fig4-habit",
    "fig5-single-day", "fig6-demand-model", "fig7-demand-effects", "fig8-one-day",
    "fig9-tradeoff", "fig10-where-vans-go", "fig11-shortages-left",
    "fig12-shortages-by-hour", "fig13-moves-vs-reported",
]
media = {f"word/media/image{i}.png": figures / f"{name}.png" for i, name in enumerate(order, 1)}

with zipfile.ZipFile(docx) as source:
    rels = source.read("word/_rels/document.xml.rels").decode()
    target_of = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(media/[^"]+)"', rels))
    document = source.read("word/document.xml").decode()

    def resize(drawing: re.Match[str]) -> str:
        block = drawing.group(0)
        rel = re.search(r'r:embed="(rId\d+)"', block)
        extent = re.search(r'<wp:extent cx="(\d+)"', block)
        if rel is None or extent is None:
            return block
        width, height = Image.open(media["word/" + target_of[rel.group(1)]]).size
        cy = round(int(extent.group(1)) * height / width)
        block = re.sub(r'(<wp:extent cx="\d+" cy=")\d+', rf"\g<1>{cy}", block)
        return re.sub(r'(<a:ext cx="\d+" cy=")\d+', rf"\g<1>{cy}", block)

    document = re.sub(r"<w:drawing>.*?</w:drawing>", resize, document, flags=re.S)

    updated = docx.with_suffix(".tmp")
    with zipfile.ZipFile(updated, "w", zipfile.ZIP_DEFLATED) as out:
        for item in source.infolist():
            if item.filename in media:
                out.writestr(item, media[item.filename].read_bytes())
            elif item.filename == "word/document.xml":
                out.writestr(item, document)
            else:
                out.writestr(item, source.read(item.filename))
shutil.move(updated, docx)
print(f"swapped {len(media)} figures into {docx.name}")
