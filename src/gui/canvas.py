import json
import sys
from pathlib import Path
import pymupdf as pdf
from PyQt6.QtCore import Qt,QPointF,QRectF,QTimer,QProcess
from PyQt6.QtGui import QColor,QPainter,QPen,QImage,QLinearGradient,QRadialGradient
from PyQt6.QtWidgets import QWidget
from src.core.structure import boundaries,section_start
from src.core.model import boxes,paper,object_box,footer_box,title_object

class PageCanvas(QWidget):
    def __init__(self,editor):
        super().__init__()
        self.editor=editor
        self.setMinimumSize(240,240)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.slide_menu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.zoom=1.0
        self.offset=QPointF()
        self.image=QImage()
        self.image_index=-1
        self.drag=None
        self.preview_box=None
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(100)
        self.timer.timeout.connect(self.render_page)
        self.scale=1;self.origin=QPointF()
        self.hits=[]
        self.request_id=0
        self.pending=None
        self.active=None
        self.worker=QProcess(self)
        self.worker.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        self.worker.readyReadStandardOutput.connect(self.receive_preview)
        self.worker.finished.connect(self.worker_finished)

    def clear(self):
        self.timer.stop()
        self.request_id+=1
        self.pending=None
        self.image=QImage()
    def shutdown(self):
        self.clear()
        self.worker.closeWriteChannel()
        if not self.worker.waitForFinished(1500):
            self.worker.kill();self.worker.waitForFinished(1500)
    def worker_finished(self,*args):
        self.active=None
    def dispatch(self):
        if self.active is not None or self.pending is None:return
        if self.worker.state()==QProcess.ProcessState.NotRunning:
            self.worker.start(str(Path(sys.executable).with_name("python.exe")),["-m","src.rendering.preview_worker"])
        self.active=self.pending;self.pending=None
        self.worker.write((json.dumps(self.active,ensure_ascii=False)+"\n").encode("utf8"))
    def receive_preview(self):
        while self.worker.canReadLine():
            result=json.loads(bytes(self.worker.readLine()).decode("utf8"))
            request=self.active
            self.active=None
            if request and result["id"]==self.request_id:
                if "error" in result:self.editor.report_error(ValueError(result["error"]))
                else:
                    self.image=QImage(result["path"])
                    self.image_index=request["index"]
                    self.image_box=[value/request["scale"] for value in result["pixel_box"]]
                    self.update()
            self.dispatch()
    def schedule(self):
        self.geometry_for_page()
        self.timer.start();self.update()
    def geometry_for_page(self):
        w,h=paper(self.editor.effective_settings())
        fit=max(.05,min((self.width()-24)/w,(self.height()-24)/h))
        self.scale=fit*self.zoom
        self.origin=QPointF((self.width()-w*self.scale)/2,(self.height()-h*self.scale)/2)+self.offset
        return w,h
    def render_page(self):
        e=self.editor
        if not e.pages or (e.preview_source is None and not e.pg["objects"]):return
        w,h=self.geometry_for_page()
        dpr=self.devicePixelRatioF()
        clip=pdf.Rect(max(0,-self.origin.x()/self.scale),max(0,-self.origin.y()/self.scale),
                      min(w,(self.width()-self.origin.x())/self.scale),min(h,(self.height()-self.origin.y())/self.scale))
        self.update_hits()
        if clip.is_empty:
            self.image=QImage();self.update();return
        self.request_id+=1
        self.pending=dict(id=self.request_id,source=e.preview_source,state=e.state,index=e.pi,
                          scale=self.scale*dpr,clip=list(clip),
                          output=str(Path(e.temp.name)/"preview.png"))
        # Snapshot before queued edits can mutate the document.
        self.pending=json.loads(json.dumps(self.pending))
        self.dispatch()
        self.update()
    def update_hits(self):
        e=self.editor
        self.hits=[]
        if e.preview_source is not None:
            for name,area in zip(("slides_region","notes_region"),boundaries(e.effective_settings(),e.pi)):
                if area:self.hits.append(((name,0),area,-1))
        for k,objects in (("global",e.settings["objects"]),("objects",e.pg["objects"]),("section_object",e.pages[section_start(e.pages,e.pi)].get("section_objects",[]))):
            for i,obj in enumerate(objects):
                if obj["kind"]!="title" and obj.get("enabled",True):
                    self.hits.append(((k,i),object_box(e.effective_settings(),obj),0 if obj["kind"]=="notes" else 2))
        for i,box in enumerate(boxes(e.effective_settings(),e.pg,e.source)):
            self.hits.append((("slides" if e.pg["slides"][i]["source"] is not None else "void",i),box,1))
        from src.core.structure import section_band
        for band in ("header","footer"):
            obj=section_band(e.pages,e.pi,band)
            if obj and obj.get("enabled",True):self.hits.append(((band,0),obj["box"],3))
        if not e.pg["numbering"].get("hidden") and e.settings["number"].get("enabled",True):
            self.hits.append((("number",0),footer_box(e.settings),3))
        self.hits.sort(key=lambda hit:hit[2])
    def canvas_rect(self,box):
        x,y,w,h=box
        return QRectF(self.origin.x()+x*self.scale,self.origin.y()+y*self.scale,w*self.scale,h*self.scale)
    def paintEvent(self,event):
        painter=QPainter(self)
        gradient=QLinearGradient(0,0,0,self.height())
        gradient.setColorAt(0,QColor("#454545"))
        gradient.setColorAt(.30,QColor("#929292"))
        gradient.setColorAt(.58,QColor("#f5f5f5"))
        gradient.setColorAt(.72,QColor("#dadada"))
        gradient.setColorAt(1,QColor("#646464"))
        painter.fillRect(self.rect(),gradient)
        light=QRadialGradient(QPointF(self.width()*.44,self.height()*.34),
                              max(self.width(),self.height())*.8)
        light.setColorAt(0,QColor(255,255,255,174))
        light.setColorAt(.53,QColor(255,255,255,54))
        light.setColorAt(1,QColor(255,255,255,0))
        painter.fillRect(self.rect(),light)
        edge=QLinearGradient(0,0,self.width(),0)
        edge.setColorAt(0,QColor(24,24,24,82))
        edge.setColorAt(.35,QColor(24,24,24,0))
        edge.setColorAt(.68,QColor(24,24,24,0))
        edge.setColorAt(1,QColor(24,24,24,92))
        painter.fillRect(self.rect(),edge)
        if self.editor.preview_source is None and not self.editor.pg["objects"]:
            painter.setPen(QColor("#52675c"))
            painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"从「文件」导入 PPTX")
            return
        if not self.image.isNull() and self.image_index==self.editor.pi:
            width,height=paper(self.editor.effective_settings())
            sheet=self.canvas_rect((0,0,width,height))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor("#a8a8a8"))
            painter.drawRect(sheet.adjusted(-.5,-.5,.5,.5))
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(self.canvas_rect(self.image_box),self.image)
        else:
            painter.setPen(QColor("#819087"))
            painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"正在生成预览…")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for key,box,_ in self.hits:
            selected=key in self.editor.selected_objects
            if selected or key[0] in ("slides_region","notes_region","void"):
                area=self.canvas_rect(self.preview_box if key==self.editor.sel and self.preview_box else box)
                pen=QPen(QColor("#4c8770" if selected else "#738a7e"),1)
                if not selected:pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen);painter.drawRect(area)
                if selected:
                    for _,point in self.handles(area):
                        painter.fillRect(QRectF(point.x()-3,point.y()-3,6,6),QColor("#4c8770"))

    def handles(self,area):
        return [((x,y),QPointF(area.left()+area.width()*(x+1)/2,area.top()+area.height()*(y+1)/2))
                for x in (-1,0,1) for y in (-1,0,1) if x or y]

    def hit(self,position):
        for key,box,_ in reversed(self.hits):
            if key not in self.editor.selected_objects:continue
            area=self.canvas_rect(box)
            for handle,point in self.handles(area):
                if (point-position).manhattanLength()<9:return key,box,handle
        edges=[]
        for key,box,_ in self.hits:
            if key[0] not in ("slides_region","notes_region"):continue
            area=self.canvas_rect(box)
            if area.adjusted(-4,-4,4,4).contains(position) and not area.adjusted(5,5,-5,-5).contains(position):
                distance=min(abs(position.x()-area.left()),abs(position.x()-area.right()),
                             abs(position.y()-area.top()),abs(position.y()-area.bottom()))
                edges.append((distance,key,box))
        if edges:
            _,key,box=min(edges,key=lambda edge:edge[0])
            return key,box,None
        for key,box,_ in reversed(self.hits):
            if key[0]!="void" and self.canvas_rect(box).contains(position):return key,box,None
        return None,None,None
    def resizeEvent(self,event):
        self.schedule()
    def set_zoom(self,value):
        self.zoom=max(.2,min(5,value));self.editor.zoom_label.setText(f"{self.zoom:.0%}")
        self.schedule()
    def fit(self):
        self.offset=QPointF();self.set_zoom(1)
    def wheelEvent(self,event):
        before=(event.position()-self.origin)/self.scale
        self.set_zoom(self.zoom*(1.12 if event.angleDelta().y()>0 else 1/1.12))
        self.offset+=event.position()-(self.origin+before*self.scale)
        self.schedule();event.accept()
    def mousePressEvent(self,event):
        self.setFocus()
        if event.button()==Qt.MouseButton.MiddleButton:
            self.drag=("pan",event.position(),QPointF(self.offset));return
        if event.button()!=Qt.MouseButton.LeftButton:return
        key,box,handle=self.hit(event.position())
        e=self.editor
        if key is None:
            e.select(None);return
        if key not in e.selected_objects:
            previous=list(e.selected_objects)
            e.select(key)
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier and previous and e.obj().get("kind")=="text":
                e.selected_objects=[*previous,key]
                e.scope_box.setEnabled(False)
            return
        self.drag=("object",event.position(),list(box),handle)
    def mouseMoveEvent(self,event):
        if not self.drag:
            key,_,handle=self.hit(event.position())
            cursor=Qt.CursorShape.ArrowCursor
            if key in self.editor.selected_objects:
                if handle:
                    x,y=handle
                    cursor=(Qt.CursorShape.SizeFDiagCursor if x==y else Qt.CursorShape.SizeBDiagCursor) if x and y else Qt.CursorShape.SizeHorCursor if x else Qt.CursorShape.SizeVerCursor
                else:cursor=Qt.CursorShape.SizeAllCursor
            self.setCursor(cursor)
            return
        mode,start,original,*rest=self.drag
        delta=event.position()-start
        if mode=="pan":
            self.offset=original+delta;self.schedule();return
        dx,dy=delta.x()/self.scale,delta.y()/self.scale
        x,y,w,h=original
        locked=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        centered=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if rest[0]:
            hx,hy=rest[0]
            width=max(4,w+hx*dx*(2 if centered else 1))
            height=max(4,h+hy*dy*(2 if centered else 1))
            if self.editor.sel[0]=="slides" or locked:
                ratio=width/w if hx and (not hy or abs(dx/w)>=abs(dy/h)) else height/h
                width,height=w*ratio,h*ratio
            x+=(w-width)*(.5 if centered or not hx else int(hx<0))
            y+=(h-height)*(.5 if centered or not hy else int(hy<0))
            self.preview_box=[x,y,width,height]
        else:
            if locked:
                if abs(dx)>=abs(dy):dy=0
                else:dx=0
            self.preview_box=[x+dx,y+dy,w,h]
        self.update()
    def mouseReleaseEvent(self,event):
        if self.preview_box is not None:
            self.editor.edit_property("box",self.preview_box,rebuild=True,proportional=bool(self.drag[-1]))
        self.preview_box=None;self.drag=None;self.update()
    def slide_menu(self,pos):
        key,_,_=self.hit(QPointF(pos))
        if key and key[0]=="slides":
            from PyQt6.QtWidgets import QMenu
            self.editor.select(key)
            menu=QMenu(self)
            menu.addAction("移到下一页",lambda:self.editor.shift(1,True))
            menu.exec(self.mapToGlobal(pos))
    def mouseDoubleClickEvent(self,event):
        if self.editor.obj().get("kind") in ("text","title"):
            self.editor.focus_text()
