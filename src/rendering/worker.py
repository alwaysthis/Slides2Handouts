"""Isolated PowerPoint and PDF worker. Tk remains in the parent process."""
import sys
import json
from pathlib import Path
import traceback
from src.configuration.store import identity
from src.rendering.importer import convert

def prepare(path, folder, density):
    digest=identity(path)
    with convert(path,folder/"source.pdf") as doc:
        for n,page in enumerate(doc):
            import pymupdf
            scale=density*min(110/page.rect.width,72/page.rect.height)
            page.get_pixmap(matrix=pymupdf.Matrix(scale,scale)).save(folder/f"{n}.png")
    (folder/"result.json").write_text(json.dumps(digest),encoding="utf8")

if __name__=="__main__":
    folder=Path(sys.argv[2])
    try:
        prepare(Path(sys.argv[1]),folder,float(sys.argv[3]))
    except Exception:
        (folder/"error.txt").write_text(traceback.format_exc(),encoding="utf8")
        sys.exit(1)
