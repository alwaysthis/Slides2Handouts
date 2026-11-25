from copy import deepcopy
import unittest
import pymupdf as pdf
from src.core.model import DEFAULT,TEXT,group,boxes
from src.core.structure import regions,contents,section_band
from src.rendering.pdfout import render

class StructureTests(unittest.TestCase):
    def test_mirrored_regions_and_void_export(self):
        settings=dict(deepcopy(DEFAULT),division="horizontal",alternate=True,odd_side="left",even_side="right")
        self.assertLess(regions(settings,0)[0][0],regions(settings,0)[1][0])
        self.assertGreater(regions(settings,1)[0][0],regions(settings,1)[1][0])
        with pdf.open() as source,pdf.open() as output:
            for label in ("One","Two","Three"):
                source.new_page(width=720,height=405).insert_text((20,40),label)
            pages=group([0,1,2],3)
            original=boxes(settings,pages[0],source)
            pages[0]["slides"][1]["source"]=None
            self.assertEqual(original,boxes(settings,pages[0],source))
            result=render(output,source,dict(settings=settings,pages=pages),0)
            self.assertIn("Three",result.get_text())
            self.assertNotIn("Two",result.get_text())

    def test_sections_and_contents(self):
        pages=group([0,0,0],1)
        pages[0]["header"]=dict(TEXT,text="Header")
        pages[1].update(section=True,header_inherit=True)
        pages[2].update(section=True,header_inherit=True)
        pages[2]["objects"].append(dict(TEXT,text="Chapter",level=1))
        self.assertEqual(section_band(pages,2,"header")["text"],"Header")
        self.assertIn("Chapter    3",contents(dict(settings=DEFAULT,pages=pages)))
