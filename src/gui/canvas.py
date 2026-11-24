import json
import sys
from pathlib import Path
import pymupdf as pdf
from PyQt6.QtCore import Qt,QPointF,QRectF,QTimer,QProcess
from PyQt6.QtGui import QColor,QPainter,QPen,QImage
from PyQt6.QtWidgets import QWidget
from src.core.model import boxes,paper,object_box,footer_box,title_object

class PageCanvas(QWidget):
    def __init__(self,editor):
        super().__init__()
        self.editor=editor
        self.setMinimumSize(240,240)
        self.setMouseTracking(True)
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
                    self.image.setDevicePixelRatio(request["dpr"])
                    self.image_index=request["index"]
                    self.image_origin=QPointF(*request["origin"])
                    self.update()
            self.dispatch()
    def schedule(self):
        self.timer.start();self.update()
    def geometry_for_page(self):
        w,h=paper(self.editor.settings)
        fit=max(.05,min((self.width()-24)/w,(self.height()-24)/h))
        self.scale=fit*self.zoom
        self.origin=QPointF((self.width()-w*self.scale)/2,(self.height()-h*self.scale)/2)+self.offset
        return w,h
    def render_page(self):
        e=self.editor
        if not e.pages:return
        w,h=self.geometry_for_page()
        dpr=self.devicePixelRatioF()
        clip=pdf.Rect(max(0,-self.origin.x()/self.scale),max(0,-self.origin.y()/self.scale),
                      min(w,(self.width()-self.origin.x())/self.scale),min(h,(self.height()-self.origin.y())/self.scale))
        self.update_hits()
        if clip.is_empty:
            self.image=QImage();self.update();return
        self.request_id+=1
        origin=self.origin+QPointF(clip.x0*self.scale,clip.y0*self.scale)
        self.pending=dict(id=self.request_id,source=e.preview_source,state=e.state,index=e.pi,
                          scale=self.scale*dpr,clip=list(clip),dpr=dpr,origin=[origin.x(),origin.y()],
                          output=str(Path(e.temp.name)/"preview.png"))
        # Snapshot before queued edits can mutate the document.
        self.pending=json.loads(json.dumps(self.pending))
        self.dispatch()
        self.update()
    def update_hits(self):
        e=self.editor
        self.hits=[]
        for k,objects in (("global",e.settings["objects"]),("objects",e.pg["objects"])):
            for i,obj in enumerate(objects):
                if obj["kind"]!="title" and obj.get("enabled",True):
                    self.hits.append(((k,i),object_box(e.settings,obj),0 if obj["kind"]=="notes" else 2))
        for i,box in enumerate(boxes(e.settings,e.pg,e.source)):
            self.hits.append((("slides",i),box,1))
        title=title_object(e.state,e.pi)
        if title and title.get("enabled",True):self.hits.append((("title",0),title["box"],3))
        if not e.pg["numbering"].get("hidden") and e.settings["number"].get("enabled",True):
            self.hits.append((("number",0),footer_box(e.settings),3))
        self.hits.sort(key=lambda hit:hit[2])
    def canvas_rect(self,box):
        x,y,w,h=box
        return QRectF(self.origin.x()+x*self.scale,self.origin.y()+y*self.scale,w*self.scale,h*self.scale)
    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor("#fdfefd"))
        if not self.image.isNull() and self.image_index==self.editor.pi:
            painter.drawImage(self.image_origin,self.image)
        else:
            painter.setPen(QColor("#819087"))
            painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"正在生成预览…")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for key,box,_ in self.hits:
            if key==self.editor.sel:
                box=self.preview_box or box
                area=self.canvas_rect(box)
                painter.setPen(QPen(QColor("#4c8770"),1))
                painter.drawRect(area)
                painter.fillRect(QRectF(area.right()-4,area.bottom()-4,8,8),QColor("#4c8770"))
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
        self.geometry_for_page()
        self.offset+=event.position()-(self.origin+before*self.scale)
        self.schedule();event.accept()
    def mousePressEvent(self,event):
        self.setFocus()
        if event.button()==Qt.MouseButton.MiddleButton:
            self.drag=("pan",event.position(),QPointF(self.offset));return
        if event.button()!=Qt.MouseButton.LeftButton:return
        for key,box,_ in reversed(self.hits):
            area=self.canvas_rect(box)
            if area.adjusted(-4,-4,4,4).contains(event.position()):
                self.editor.select(key)
                size=(event.position()-area.bottomRight()).manhattanLength()<14
                self.drag=("object",event.position(),list(box),size)
                return
        self.editor.select(None)
    def mouseMoveEvent(self,event):
        if not self.drag:return
        mode,start,original,*rest=self.drag
        delta=event.position()-start
        if mode=="pan":
            self.offset=original+delta;self.schedule();return
        dx,dy=delta.x()/self.scale,delta.y()/self.scale
        x,y,w,h=original
        locked=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if rest[0]:
            width=max(4,w+dx)
            height=h*width/w if self.editor.sel[0]=="slides" or locked else max(4,h+dy)
            self.preview_box=[x,y,width,height]
        else:
            if locked:
                if abs(dx)>=abs(dy):dy=0
                else:dx=0
            self.preview_box=[x+dx,y+dy,w,h]
        self.update()
    def mouseReleaseEvent(self,event):
        if self.preview_box is not None:
            self.editor.edit_property("box",self.preview_box,rebuild=True)
        self.preview_box=None;self.drag=None;self.update()
    def mouseDoubleClickEvent(self,event):
        if self.editor.obj().get("kind") in ("text","title"):
            self.editor.focus_text()
