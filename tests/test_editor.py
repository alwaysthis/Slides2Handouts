import os
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import pymupdf as pdf
from PyQt6.QtWidgets import QApplication,QDoubleSpinBox,QScrollArea,QPlainTextEdit,QCheckBox,QDialog
from PyQt6.QtCore import Qt,QPointF,QPoint,QTimer
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest
from src.gui.editor import Editor
from src.gui.theme import stylesheet
from src.core.model import DEFAULT,TEXT,group,move,regroup,footer_box,object_box,paper,title_object,content_box,boxes
from src.configuration.store import write,read
from src.rendering.pdfout import render,footer_issue,draw
APP=QApplication.instance() or QApplication([])
APP.setStyle("Fusion");APP.setStyleSheet(stylesheet())

class Editing(unittest.TestCase):
    def make_editor(self):
        editor=Editor();editor.show()
        self.addCleanup(editor.close)
        self.addCleanup(editor.hide)
        APP.processEvents()
        return editor
    def test_grouping(self):
        pages=group(range(6),3);move(pages,0,2,1,0)
        self.assertEqual([[s["source"] for s in p["slides"]] for p in pages],[[0,1],[2,3,4,5]])
        regroup(pages,1,1,2)
        self.assertEqual([s["source"] for p in pages for s in p["slides"]],list(range(6)))
    def test_export(self):
        with pdf.open() as source,pdf.open() as output:
            original=source.new_page();original.insert_text((30,40),"VECTOR");original.draw_line((20,50),(90,70))
            state=dict(settings=deepcopy(DEFAULT),pages=group([0,0],1))
            state["settings"]["number"]["text"]="{chapter}{sep}{sub}"
            state["pages"][1]["numbering"]=dict(chapter=2,sub=1)
            for i in range(2):render(output,source,state,i)
            with pdf.open(stream=output.tobytes()) as result:
                self.assertIn("VECTOR",result[1].get_text());self.assertIn("2.1",result[1].get_text())
                self.assertFalse(result[1].get_images());self.assertTrue(any(d["items"][0][0]=="l" for d in result[1].get_drawings()))
    def test_footer_clearance(self):
        with pdf.open() as source:
            source.new_page();state=deepcopy(DEFAULT);pg=group([0],1)[0]
            for size in ("A3","A4","Letter","Custom"):
                for horizontal in (True,False):
                    state.update(paper=size,landscape=horizontal);x,y,w,h=footer_box(state)
                    self.assertAlmostEqual(paper(state)[1]-y-h,16)
                    note=object_box(state,state["objects"][0]);self.assertGreaterEqual(y-note[1]-note[3],9.99)
                    self.assertEqual(footer_issue(state,pg,source),"")
    def test_immediate_properties_and_title_inheritance(self):
        e=self.make_editor();e.add_page();e.goto(0);e.edit_title()
        e.edit_property("text","第一章");e.goto(1);e.select(("title",0))
        self.assertIsNone(e.pg.get("title"));self.assertTrue(e.inspector.inherit.isChecked())
        self.assertEqual(e.obj()["text"],"第一章")
        e.inspector.text_field.setPlainText("第二章")
        self.assertEqual(e.pg["title"]["text"],"第二章");self.assertFalse(e.inspector.inherit.isChecked())
        e.set_title_inheritance(True)
        self.assertIsNone(e.pg["title"]);self.assertEqual(e.obj()["text"],"第一章")
        e.goto(0);e.select(("title",0));e.edit_property("text","绪论")
        self.assertEqual(title_object(e.state,1)["text"],"绪论")
        e.add_object("text");e.edit_property("valign","center")
        self.assertEqual(e.obj()["valign"],"center")
        e.copy();e.paste();e.history(False);self.assertEqual(len(e.pg["objects"]),1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"state.json";write(path,"project",e.state)
            self.assertEqual(read(path,"project"),e.state)
            e.export_to(Path(tmp)/"out.pdf")
            with pdf.open(Path(tmp)/"out.pdf") as result:self.assertIn("绪论",result[1].get_text())
    def test_wheel_and_navigation(self):
        e=self.make_editor();e.add_page();e.page_entry.setText("1");e.jump()
        self.assertEqual(e.pi,0);e.next.click();self.assertEqual(e.pi,1)
        e.resize(960,600);APP.processEvents()
        spin=e.inspector.findChild(QDoubleSpinBox);before=spin.value()
        scroll=e.inspector.parentWidget().parentWidget()
        previous_scroll=scroll.verticalScrollBar().value()
        wheel=QWheelEvent(QPointF(5,5),QPointF(5,5),QPoint(0,0),QPoint(0,-120),
                          Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False)
        APP.sendEvent(spin,wheel);self.assertEqual(spin.value(),before)
        if scroll.verticalScrollBar().maximum()>0:self.assertGreater(scroll.verticalScrollBar().value(),previous_scroll)
        e.canvas.geometry_for_page();old=e.canvas.zoom
        APP.sendEvent(e.canvas,QWheelEvent(QPointF(120,120),QPointF(120,120),QPoint(),QPoint(0,120),
                          Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False))
        self.assertGreater(e.canvas.zoom,old)
        self.assertIsInstance(e.inspector.parentWidget().parentWidget(),QScrollArea)
    def test_vertical_alignment_and_actual_gap(self):
        ys=[]
        for align in ("top","center","bottom"):
            with pdf.open() as output:
                page=output.new_page(width=300,height=300)
                draw(page,dict(TEXT,text="Alignment",box=[20,20,200,150],valign=align,font="Arial"))
                ys.append(page.search_for("Alignment")[0].y0)
        self.assertLess(ys[0],ys[1]);self.assertLess(ys[1],ys[2])
        with pdf.open() as source:
            source.new_page(width=720,height=405)
            s=deepcopy(DEFAULT);pg=group([0,0,0],3)[0]
            for gap in (8,24):
                s["gap"]=gap;rects=boxes(s,pg,source)
                self.assertAlmostEqual(rects[1][1]-rects[0][1]-rects[0][3],gap)
    def test_shift_constraint(self):
        e=self.make_editor();e.add_object("text");e.canvas.geometry_for_page();e.canvas.update_hits()
        initial=list(e.obj()["box"]);rect=e.canvas.canvas_rect(initial)
        start=rect.center().toPoint();end=start+QPoint(60,15)
        QTest.mousePress(e.canvas,Qt.MouseButton.LeftButton,pos=start)
        from PyQt6.QtGui import QMouseEvent
        APP.sendEvent(e.canvas,QMouseEvent(QMouseEvent.Type.MouseMove,QPointF(end),QPointF(end),Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ShiftModifier))
        QTest.mouseRelease(e.canvas,Qt.MouseButton.LeftButton,pos=end)
        self.assertAlmostEqual(e.obj()["box"][1],initial[1]);self.assertGreater(e.obj()["box"][0],initial[0])

    def test_async_preview_and_source_location(self):
        e=self.make_editor()
        e.source.new_page(width=720,height=405).insert_text((40,60),"SLIDE 1")
        e.source.new_page(width=720,height=405).insert_text((40,60),"SLIDE 2")
        path=Path(e.temp.name)/"sample.pdf";e.source.save(path);e.preview_source=str(path)
        e.source_revision+=1;e.state["pages"]=group([0,1],1);e.refresh()
        from PyQt6.QtWidgets import QListWidgetItem
        item=QListWidgetItem("2");item.setData(Qt.ItemDataRole.UserRole,1);e.library.addItem(item)
        e.locate_source(item);self.assertEqual(e.pi,1);self.assertEqual(e.sel,("slides",0))
        e.add_object("text");e.edit_property("text","中文预览")
        ticks=[]
        timer=QTimer();timer.setInterval(15);timer.timeout.connect(lambda:ticks.append(1));timer.start()
        for _ in range(160):
            QTest.qWait(50)
            if not e.canvas.image.isNull():break
        timer.stop()
        self.assertFalse(e.canvas.image.isNull(),e.status.text())
        self.assertGreater(len(ticks),5)
        e.select(("title",0))
        e.canvas.schedule()

    def test_hex_color_dialog(self):
        e=self.make_editor()
        from src.gui.widgets import ColorButton
        from PyQt6.QtWidgets import QColorDialog,QLineEdit
        button=e.inspector.findChild(ColorButton)
        captured=[]
        def accept():
            dialog=APP.activeModalWidget()
            picker=dialog.findChild(QColorDialog)
            field=picker.findChild(QLineEdit,"qt_colorname_lineedit")
            field.setText("#123456")
            from PyQt6.QtGui import QColor
            picker.setCurrentColor(QColor(field.text()))
            captured.append(field.text());dialog.accept()
        QTimer.singleShot(150,accept);button.click()
        self.assertEqual(captured,["#123456"])
        self.assertEqual(e.settings["background"],"#123456")
