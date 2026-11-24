"""PDF preview service. All MuPDF work runs outside the Qt UI process."""
import sys
import json
from pathlib import Path
from collections import OrderedDict
import pymupdf as pdf
from src.rendering.pdfout import render

def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    source=None
    source_path=None
    cache=OrderedDict()
    for line in sys.stdin:
        request=json.loads(line)
        try:
            if request["source"]!=source_path:
                if source:source.close()
                for doc in cache.values():doc.close()
                cache.clear()
                source=pdf.open(request["source"]) if request["source"] else pdf.open()
                source_path=request["source"]
            state=request["state"];index=request["index"]
            from src.core.model import title_object
            key=json.dumps([state["settings"],state["pages"][index],title_object(state,index),
                            [p["numbering"] for p in state["pages"][:index]]],ensure_ascii=False)
            if key not in cache:
                doc=pdf.open()
                try:render(doc,source,state,index)
                except Exception:doc.close();raise
                cache[key]=doc
                while len(cache)>3:cache.popitem(last=False)[1].close()
            cache.move_to_end(key)
            pix=cache[key][0].get_pixmap(matrix=pdf.Matrix(request["scale"],request["scale"]),
                                       clip=pdf.Rect(request["clip"]),alpha=False)
            path=Path(request["output"])
            pix.save(path)
            print(json.dumps({"id":request["id"],"path":str(path)}),flush=True)
        except Exception as error:
            print(json.dumps({"id":request["id"],"error":str(error)}),flush=True)
    if source:source.close()
    for doc in cache.values():doc.close()

if __name__=="__main__":main()
