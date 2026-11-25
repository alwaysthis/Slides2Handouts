import unittest
import tempfile
from pathlib import Path
from pptx import Presentation
from src.rendering.importer import convert

class ImportTest(unittest.TestCase):
    def test_real_presentation(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            deck = Presentation()
            slide = deck.slides.add_slide(deck.slide_layouts[5])
            slide.shapes.title.text = "Vector title"
            deck.save(folder / "sample.pptx")
            with convert(folder / "sample.pptx", folder / "sample.pdf") as document:
                self.assertIn("Vector title", document[0].get_text())
                self.assertGreater(document[0].get_pixmap().width, 0)
    def test_pptx_to_edited_handout(self):
        from test_editor import APP
        from PyQt6.QtWidgets import QFileDialog
        from unittest.mock import patch
        import pymupdf
        from src.gui.editor import Editor
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            deck=Presentation()
            for i in range(6):
                slide=deck.slides.add_slide(deck.slide_layouts[5])
                slide.shapes.title.text=f"Original {i+1}"
            path=folder/"lesson.pptx"
            deck.save(path)
            editor=Editor()
            editor.show()
            try:
                editor.load_source(path)
                self.assertEqual(len(editor.images),6)
                editor.select(("slides",2))
                editor.shift(1)
                self.assertEqual([len(p["slides"]) for p in editor.pages],[2,3,1])
                editor.add_object("text")
                editor.obj()["text"]="课堂笔记"
                editor.settings["number"]["text"]="{chapter}{sep}{sub}"
                editor.pg["numbering"]=dict(chapter=2,sub=1)
                project=folder/"lesson.json"
                from src.configuration.store import write,read
                write(project,"project",editor.state)
                with patch.object(QFileDialog,"getOpenFileName",return_value=(str(project),"")):
                    editor.open_project()
                editor.save()
                self.assertIn("embedded_pptx",read(project,"project")["source"])
                path.unlink()
                with patch.object(QFileDialog,"getOpenFileName",return_value=(str(project),"")):
                    editor.open_project()
                output=folder/"handout.pdf"
                with patch.object(QFileDialog,"getSaveFileName",return_value=(str(output),"")):
                    editor.export()
                with pymupdf.open(output) as result:
                    self.assertEqual(len(result),3)
                    self.assertIn("Original 6",result[2].get_text())
                    text=result[1].get_text()
                    for expected in ["Original 3","Original 5","课堂笔记","2.1"]:
                        self.assertIn(expected,text)
            finally:
                editor.hide()
                editor.close()
