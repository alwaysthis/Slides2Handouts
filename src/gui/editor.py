import json
import logging
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path
import pymupdf as pdf
from PyQt6.QtCore import Qt,QTimer,QProcess,QSize,QSignalBlocker,QEvent
from PyQt6.QtGui import QAction,QIcon,QImage,QPixmap,QKeySequence,QShortcut
from PyQt6.QtWidgets import (QMainWindow,QApplication,QWidget,QFrame,QSplitter,QVBoxLayout,QHBoxLayout,
    QLabel,QToolButton,QPushButton,QLineEdit,QScrollArea,QListWidget,QListWidgetItem,QTreeWidget,
    QTreeWidgetItem,QAbstractItemView,QFileDialog,QProgressBar,QDialog,QPlainTextEdit)
from src.core.model import (DEFAULT,TEXT,group,page,paper,boxes,move,regroup,title_object,content_box)
from src.configuration.store import read,write,identity
from src.rendering.pdfout import render,footer_issue
from .widgets import TitleBar,Dialog,message,prompt,WheelGuard
from .inspector import Inspector
from .canvas import PageCanvas

ROOT=Path(__file__).resolve().parents[2]

class PageTree(QTreeWidget):
    def __init__(self,editor):
        super().__init__()
        self.editor=editor;self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
    def dropEvent(self,event):
        selected=self.currentItem();target=self.itemAt(event.position().toPoint())
        if not selected or not target:return
        first=selected.data(0,Qt.ItemDataRole.UserRole)
        last=target.data(0,Qt.ItemDataRole.UserRole)
        e=self.editor
        def action():
            if len(first)==1 and len(last)==1:
                e.pages.insert(last[0],e.pages.pop(first[0]))
            elif len(first)==2:
                slot=last[1] if len(last)==2 else len(e.pages[last[0]]["slides"])
                move(e.pages,first[0],first[1],last[0],slot)
            e.pi=last[0];e.sel=None
        e.change(action)
        event.acceptProposedAction()

class Editor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slides2Handouts · 讲义编辑器")
        self.setWindowIcon(QIcon(str(ROOT/"assets/handouts.ico")))
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        available=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1280,available.width()-20),min(820,available.height()-20));self.setMinimumSize(960,600)
        self.temp=tempfile.TemporaryDirectory()
        self.source=pdf.open();self.source_revision=0;self.preview_source=None
        self.state={"settings":read(ROOT/"configs/default.json","template"),"pages":[page()],"source":None}
        self.pi=0;self.sel=None;self.saved=None;self.clip=None
        self.undo=[];self.redo=[];self.last_edit=None;self.dirty=False
        self.process=None;self.images=[]
        self._build()
        self.refresh()
    @property
    def settings(self):return self.state["settings"]
    @property
    def pages(self):return self.state["pages"]
    @property
    def pg(self):return self.pages[self.pi]
    def _build(self):
        central=QWidget();central.setObjectName("central");self.setCentralWidget(central)
        outer=QVBoxLayout(central);outer.setContentsMargins(6,0,6,4);outer.setSpacing(5)
        menus={
            "文件":[("导入 PPTX",self.import_file),("打开工程",self.open_project),("保存工程",self.save),("工程另存为",lambda:self.save(True)),("导出 PDF",self.export)],
            "编辑":[("撤销",lambda:self.history(False)),("重做",lambda:self.history(True)),("复制",self.copy),("粘贴",self.paste),("删除",self.delete)],
            "页面":[("新增页面",self.add_page),("插入选中原稿",self.insert),("移到下一页并顺延",lambda:self.shift(1)),("移到上一页",lambda:self.shift(-1)),("移至指定页与位置",self.destination),("从选中原稿重新分页",self.reflow)],
            "布局":[("页面 / Slides 区域",lambda:self.select(None)),("恢复本页自动布局",self.auto),("对齐与统一尺寸",self.align),
                    ("添加批注区",lambda:self.add_object("notes")),("页码样式",lambda:self.select(("number",0))),("本页编号",lambda:self.select(("numbering",0)))],
            "文字":[("添加文字",lambda:self.add_object("text")),("本页标题",self.edit_title),("文字复制到页面范围",self.scope)],
            "配置":[("加载模板",self.template),("保存模板",self.save_template),("设为默认",lambda:write(ROOT/"configs/default.json","template",self.settings)),("删除模板",self.remove_template)]
        }
        self.titlebar=TitleBar(self,menus);outer.addWidget(self.titlebar)
        self.split=QSplitter();outer.addWidget(self.split,1)
        panels=[]
        for _ in range(3):
            frame=QFrame();frame.setObjectName("panel");frame.setMinimumWidth(180)
            layout=QVBoxLayout(frame);layout.setContentsMargins(9,8,9,8);layout.setSpacing(5)
            self.split.addWidget(frame);panels.append(layout)
        left,middle,right=panels
        left.addWidget(QLabel("原始幻灯片"))
        self.library=QListWidget();self.library.setIconSize(QSize(120,76))
        self.library.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.library.itemClicked.connect(self.locate_source)
        self.library.itemDoubleClicked.connect(self.preview_original)
        left.addWidget(self.library,3)
        insert=QPushButton("插入选中原稿");insert.clicked.connect(self.insert);left.addWidget(insert)
        left.addWidget(QLabel("输出页面"))
        self.tree=PageTree(self);self.tree.itemClicked.connect(self.tree_selected);left.addWidget(self.tree,2)
        nav=QHBoxLayout();nav.setContentsMargins(0,0,0,0);nav.setSpacing(5);nav.addStretch()
        self.previous=QToolButton();self.previous.setText("‹");self.previous.setToolTip("上一页")
        self.previous.clicked.connect(lambda:self.goto(self.pi-1));nav.addWidget(self.previous)
        self.page_entry=QLineEdit("1");self.page_entry.setFixedWidth(38);self.page_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_entry.returnPressed.connect(self.jump);nav.addWidget(self.page_entry)
        self.page_total=QLabel("/ 1");nav.addWidget(self.page_total)
        self.next=QToolButton();self.next.setText("›");self.next.clicked.connect(lambda:self.goto(self.pi+1));nav.addWidget(self.next)
        nav.addSpacing(8)
        minus=QToolButton();minus.setText("−");minus.clicked.connect(lambda:self.canvas.set_zoom(self.canvas.zoom/1.2));nav.addWidget(minus)
        self.zoom_label=QLabel("100%");self.zoom_label.setFixedWidth(42);self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter);nav.addWidget(self.zoom_label)
        plus=QToolButton();plus.setText("＋");plus.clicked.connect(lambda:self.canvas.set_zoom(self.canvas.zoom*1.2));nav.addWidget(plus)
        fit=QPushButton("适应窗口");fit.clicked.connect(lambda:self.canvas.fit());nav.addWidget(fit);nav.addStretch()
        middle.addLayout(nav)
        self.canvas=PageCanvas(self);middle.addWidget(self.canvas,1)
        self.property_title=QLabel("页面设置");self.property_title.setStyleSheet("font-weight:600;");right.addWidget(self.property_title)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inspector=Inspector(self);scroll.setWidget(self.inspector);right.addWidget(scroll)
        self.status=QLabel();self.status.setStyleSheet("background:#e0e6e2;color:#4f6258;padding:2px 5px;");outer.addWidget(self.status)
        self.split.setSizes([210,710,350])
        for key,fn in [("Ctrl+S",self.save),("Ctrl+Z",lambda:self.history(False)),("Ctrl+Y",lambda:self.history(True)),("Ctrl+C",self.copy),("Ctrl+V",self.paste),("Delete",self.delete),("PgUp",lambda:self.goto(self.pi-1)),("PgDown",lambda:self.goto(self.pi+1))]:
            shortcut=QShortcut(QKeySequence(key),self)
            shortcut.activated.connect(lambda fn=fn,key=key:self.shortcut(fn,key))
        self.wheel_guard=WheelGuard(self)
        QApplication.instance().installEventFilter(self.wheel_guard)
        QApplication.instance().installEventFilter(self)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.MouseButtonPress and isinstance(obj,QWidget) and obj.window() is self and not self.isMaximized():
            pos=self.mapFromGlobal(event.globalPosition().toPoint());edges=Qt.Edge(0);margin=5
            if pos.x()<margin:edges|=Qt.Edge.LeftEdge
            if pos.x()>self.width()-margin:edges|=Qt.Edge.RightEdge
            if pos.y()<margin:edges|=Qt.Edge.TopEdge
            if pos.y()>self.height()-margin:edges|=Qt.Edge.BottomEdge
            if edges and self.windowHandle():return self.windowHandle().startSystemResize(edges)
        return super().eventFilter(obj,event)
    def shortcut(self,fn,key):
        if key!="Ctrl+S" and isinstance(QApplication.focusWidget(),(QLineEdit,QPlainTextEdit)):return
        fn()
    def report_error(self,error):
        logging.error("Editor operation failed",exc_info=error)
        self.status.setText(str(error))
    def change(self,operation,rebuild=True):
        before=deepcopy(self.state);old_page=self.pi
        try:
            operation()
            self.validate()
        except Exception:
            self.state=before;self.pi=old_page;raise
        self.undo.append(before);self.undo=self.undo[-60:];self.redo.clear()
        self.last_edit=None;self.dirty=True
        if rebuild:self.refresh()
        else:self.canvas.schedule()
    def validate(self):
        if self.settings["count"]<1:raise ValueError("每页数量必须大于零")
        if min(content_box(self.settings)[2:])<=0:raise ValueError("Slides 区域宽高必须大于零")
        for obj in self.settings["objects"]+self.pg["objects"]:
            if obj["box"][2]<=0 or obj["box"][3]<=0:raise ValueError("对象宽高必须大于零")
    def history(self,forward):
        a,b=(self.redo,self.undo) if forward else (self.undo,self.redo)
        if a:
            b.append(self.state);self.state=a.pop();self.pi=min(self.pi,len(self.pages)-1)
            self.sel=None;self.last_edit=None;self.dirty=True;self.refresh()
    def refresh(self):
        self.pi=max(0,min(self.pi,len(self.pages)-1))
        with QSignalBlocker(self.tree):
            self.tree.clear()
            for p,pg in enumerate(self.pages):
                parent=QTreeWidgetItem([f"第 {p+1} 页"]);parent.setData(0,Qt.ItemDataRole.UserRole,(p,));self.tree.addTopLevelItem(parent)
                for i,slide in enumerate(pg["slides"]):
                    child=QTreeWidgetItem([f"幻灯片 {slide['source']+1}"]);child.setData(0,Qt.ItemDataRole.UserRole,(p,i));parent.addChild(child)
                parent.setExpanded(p==self.pi)
        self.sync_navigation();self.select(self.sel)
    def sync_navigation(self):
        self.page_entry.setText(str(self.pi+1));self.page_total.setText(f"/ {len(self.pages)}")
        self.previous.setEnabled(self.pi>0);self.next.setEnabled(self.pi+1<len(self.pages))
        issue=footer_issue(self.settings,self.pg,self.source,title_object(self.state,self.pi))
        self.status.setText(issue or f"原稿 {len(self.source)} 张 · 讲义 {len(self.pages)} 页")
    def goto(self,index):
        self.pi=max(0,min(index,len(self.pages)-1));self.sel=None;self.last_edit=None
        self.sync_navigation();self.select(None)
        item=self.tree.topLevelItem(self.pi)
        if item:
            item.setExpanded(True);self.tree.setCurrentItem(item);self.tree.scrollToItem(item)
    def jump(self):
        value=self.page_entry.text()
        if value.isdecimal() and 1<=int(value)<=len(self.pages):self.goto(int(value)-1)
        else:
            self.page_entry.setText(str(self.pi+1));self.status.setText(f"页码范围为 1–{len(self.pages)}")
    def obj(self):
        kind,i=self.sel or ("settings",0)
        if kind=="settings":return self.settings
        if kind=="number":return self.settings["number"]
        if kind=="numbering":return self.pg["numbering"]
        if kind=="title":return self.pg.get("title") or title_object(self.state,self.pi) or dict(TEXT,kind="title",text="")
        if kind=="slides":return self.pg["slides"][i]
        return (self.settings if kind=="global" else self.pg)["objects"][i]
    def select(self,selection):
        self.sel=selection;self.last_edit=None
        names={"settings":"页面设置","number":"页码样式","numbering":"本页编号","slides":"幻灯片","title":"本页标题","global":"模板对象","objects":"页面对象"}
        self.property_title.setText(names[(selection or ("settings",0))[0]])
        self.inspector.build();self.canvas.update_hits();self.canvas.schedule()
    def edit_property(self,key,value,rebuild=False):
        before=deepcopy(self.state)
        target=self.obj()
        old=target.get(key)
        if self.sel==("number",0) and key in ("start","chapter","substart","separator"):
            target=self.settings;old=target[key]
        if old==value:return
        if self.sel==("title",0) and self.pg.get("title") is None:
            self.pg["title"]=deepcopy(target);target=self.pg["title"]
        if self.sel==("numbering",0) and (value is None or value==""):target.pop(key,None)
        else:target[key]=value
        try:self.validate()
        except Exception:
            self.state=before;raise
        now=time.monotonic();edit=(self.pi,self.sel,key)
        if not self.last_edit or self.last_edit[0]!=edit or now-self.last_edit[1]>1:
            self.undo.append(before);self.undo=self.undo[-60:];self.redo.clear()
        self.last_edit=(edit,now);self.dirty=True
        if self.sel==("title",0):
            if self.inspector.inherit:
                with QSignalBlocker(self.inspector.inherit):self.inspector.inherit.setChecked(False)
            self.inspector.setProperty("inherit",False)
            self.inspector.style().unpolish(self.inspector);self.inspector.style().polish(self.inspector)
            for widget in self.inspector.findChildren(QWidget):widget.style().unpolish(widget);widget.style().polish(widget)
        self.sync_navigation()
        if rebuild:self.inspector.build()
        elif key in ("paper","landscape","margins") and not self.sel:QTimer.singleShot(0,self.inspector.build)
        self.canvas.update_hits();self.canvas.schedule()
    def edit_title(self):
        if title_object(self.state,self.pi) is None:
            self.change(lambda:self.settings.update(title=dict(TEXT,kind="title",text="标题",box=[28,4,539,22],size=12)))
        self.select(("title",0))
    def set_title_inheritance(self,inherit):
        current=self.obj()
        def action():self.pg["title"]=None if inherit else deepcopy(current)
        self.change(action);self.select(("title",0))
    def focus_text(self):
        if self.inspector.text_field:self.inspector.text_field.setFocus();self.inspector.text_field.selectAll()
    def locate_source(self,item):
        index=item.data(Qt.ItemDataRole.UserRole)
        matches=[(p,i) for p,pg in enumerate(self.pages) for i,s in enumerate(pg["slides"]) if s["source"]==index]
        if matches:
            p,i=next((entry for entry in matches if entry[0]==self.pi),matches[0])
            self.goto(p);self.select(("slides",i))
        else:self.status.setText("此原稿尚未放入讲义，可点击插入选中原稿")
    def tree_selected(self,item,column):
        entry=item.data(0,Qt.ItemDataRole.UserRole);self.pi=entry[0]
        self.sync_navigation();self.select(("slides",entry[1]) if len(entry)==2 else None)
    def add_page(self):
        self.change(lambda:self.pages.append(page()));self.goto(len(self.pages)-1)
    def insert(self):
        indices=[item.data(Qt.ItemDataRole.UserRole) for item in self.library.selectedItems()]
        pos=self.sel[1] if self.sel and self.sel[0]=="slides" else len(self.pg["slides"])
        self.change(lambda:self.pg["slides"].__setitem__(slice(pos,pos),page(indices)["slides"]))
    def shift(self,d):
        if not self.sel or self.sel[0]!="slides" or self.pi+d<0:return
        i=self.sel[1];p=self.pi
        def action():
            if p+d==len(self.pages):self.pages.append(page())
            move(self.pages,p,i,p+d,0 if d>0 else len(self.pages[p+d]["slides"]))
            if d>0:
                capacity=self.settings["count"];dest=p+1
                while dest<len(self.pages):
                    if len(self.pages[dest]["slides"])<=capacity:break
                    if dest+1==len(self.pages):self.pages.append(page())
                    excess=self.pages[dest]["slides"][capacity:];del self.pages[dest]["slides"][capacity:]
                    for slide in excess:slide["box"]=None
                    self.pages[dest+1]["slides"][0:0]=excess;dest+=1
            self.pi=p+d;self.sel=None
        self.change(action)
    def destination(self):
        if not self.sel or self.sel[0]!="slides":return
        value=prompt(self,"移动原稿","目标页, 插入位置（从 1 开始）","1,1")
        if value:
            p,i=[int(v.strip())-1 for v in value.split(",")]
            if not 0<=p<len(self.pages) or not 0<=i<=len(self.pages[p]["slides"]):raise ValueError("目标超出范围")
            source=self.pi;index=self.sel[1]
            def action():
                move(self.pages,source,index,p,i);self.pi=p;self.sel=None
            self.change(action)
    def reflow(self):
        i=self.sel[1] if self.sel and self.sel[0]=="slides" else 0
        self.sel=None;self.change(lambda:regroup(self.pages,self.pi,i,self.settings["count"]))
    def auto(self):
        self.change(lambda:[s.update(box=None) for s in self.pg["slides"]])
    def align(self):
        indices=[]
        for item in self.tree.selectedItems():
            data=item.data(0,Qt.ItemDataRole.UserRole)
            if len(data)==2 and data[0]==self.pi:indices.append(data[1])
        if len(indices)<2:
            self.status.setText("按 Ctrl 选择本页多张幻灯片后对齐");return
        positions=boxes(self.settings,self.pg,self.source);x,_,w,_=positions[min(indices)]
        def action():
            for i in indices:
                _,y,ow,oh=positions[i];self.pg["slides"][i]["box"]=[x,y,w,w*oh/ow]
        self.change(action)
    def add_object(self,kind):
        if kind=="title":self.edit_title();return
        obj=deepcopy(DEFAULT["objects"][0] if kind=="notes" else TEXT)
        self.change(lambda:self.pg["objects"].append(obj))
        self.select(("objects",len(self.pg["objects"])-1))
    def copy(self):
        if self.sel:self.clip=deepcopy(self.obj())
    def paste(self):
        if not self.clip:return
        key="slides" if "source" in self.clip else "objects"
        if key=="objects" and "kind" not in self.clip:return
        obj=deepcopy(self.clip)
        if obj.get("kind")=="title":obj["kind"]="text"
        self.change(lambda:self.pg[key].append(obj))
    def delete(self):
        if not self.sel:return
        kind,i=self.sel
        if kind=="title":self.edit_property("enabled",False,rebuild=True);return
        if kind not in ("global","slides","objects"):return
        target=self.settings["objects"] if kind=="global" else self.pg[kind]
        self.sel=None;self.change(lambda:target.pop(i))
    def scope(self):
        if not self.sel or self.sel[0] not in ("objects","title"):return
        value=prompt(self,"复制文字","页面范围，例如 1,3-5；全部输入 *","*")
        if value is None:return
        targets=set()
        for part in value.split(","):
            bounds=[1,len(self.pages)] if part=="*" else list(map(int,part.split("-")))
            if not 1<=bounds[0]<=bounds[-1]<=len(self.pages):raise ValueError("页面范围不正确")
            targets.update(range(bounds[0]-1,bounds[-1]))
        obj=deepcopy(self.obj())
        def action():
            for p in targets:
                if self.sel[0]=="title":self.pages[p]["title"]=deepcopy(obj)
                elif p!=self.pi:self.pages[p]["objects"].append(deepcopy(obj))
        self.change(action)
    def preview_original(self,item):
        index=item.data(Qt.ItemDataRole.UserRole);pg=self.source[index]
        pix=pg.get_pixmap(matrix=pdf.Matrix(1.4,1.4))
        image=QImage(pix.samples,pix.width,pix.height,pix.stride,QImage.Format.Format_RGB888).copy()
        dialog=Dialog(self,f"原始幻灯片 {index+1}")
        label=QLabel();label.setPixmap(QPixmap.fromImage(image).scaled(900,650,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        dialog.body.addWidget(label);dialog.exec()
    def load_source(self,path,state=None):
        path=Path(path).resolve();folder=Path(tempfile.mkdtemp(dir=self.temp.name))
        dialog=Dialog(self,"导入课件");dialog.setFixedWidth(380)
        label=QLabel(f"正在转换 {path.name}");label.setWordWrap(True);dialog.body.addWidget(label)
        bar=QProgressBar();bar.setRange(0,0);dialog.body.addWidget(bar)
        process=QProcess(dialog);self.process=process
        process.setWorkingDirectory(str(ROOT))
        result={}
        def done(code,status):
            result["code"]=code;dialog.accept()
        process.finished.connect(done)
        process.errorOccurred.connect(lambda error:(result.update(code=-1),dialog.accept()))
        process.start(sys.executable,["-m","src.rendering.worker",str(path),str(folder),str(self.devicePixelRatioF())])
        dialog.exec()
        if process.state()!=QProcess.ProcessState.NotRunning:
            # Close is explicit cancellation. Terminate the process tree, including PowerPoint export helper.
            import subprocess
            subprocess.run(["taskkill","/PID",str(process.processId()),"/T","/F"],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
            process.waitForFinished(3000);self.process=None;return False
        self.process=None
        if result.get("code",1)!=0:
            error=folder/"error.txt";raise ValueError(error.read_text(encoding="utf8") if error.exists() else process.errorString())
        digest=json.loads((folder/"result.json").read_text(encoding="utf8"))
        if state and digest!=state["source"]["sha256"]:raise ValueError("原稿文件指纹不匹配")
        doc=pdf.open(folder/"source.pdf")
        new=state or dict(settings=deepcopy(self.settings),pages=group(list(range(len(doc))),self.settings["count"]),source=dict(path=str(path),sha256=digest))
        self.canvas.clear();self.source.close();self.source=doc;self.source_revision+=1;self.preview_source=str(folder/"source.pdf");self.state=new
        self.library.clear();self.images=[]
        for i in range(len(doc)):
            pix=QPixmap(str(folder/f"{i}.png"));self.images.append(pix)
            item=QListWidgetItem(QIcon(pix),str(i+1));item.setData(Qt.ItemDataRole.UserRole,i);self.library.addItem(item)
        self.undo.clear();self.redo.clear();self.clip=None;self.saved=None;self.pi=0;self.sel=None;self.dirty=False
        self.refresh();return True
    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,"导入 PPTX","","PowerPoint (*.pptx)")
        if path:self.load_source(path)
    def save(self,another=False):
        path=None if another else self.saved
        if not path:path=QFileDialog.getSaveFileName(self,"保存工程","","讲义工程 (*.json)")[0]
        if path:
            if not path.lower().endswith(".json"):path+=".json"
            write(path,"project",self.state);self.saved=path;self.dirty=False;self.status.setText("工程已保存")
    def open_project(self):
        path=QFileDialog.getOpenFileName(self,"打开工程","","讲义工程 (*.json)")[0]
        if not path:return
        state=read(path,"project")
        if state["source"]:
            source=Path(state["source"]["path"])
            if not source.exists():
                chosen=QFileDialog.getOpenFileName(self,"定位原始 PPTX","","PowerPoint (*.pptx)")[0]
                if not chosen:return
                source=Path(chosen)
            state["source"]["path"]=str(source)
            if not self.load_source(source,state):return
        else:
            self.canvas.clear();self.source.close();self.source=pdf.open();self.source_revision+=1;self.preview_source=None
            self.library.clear();self.images=[];self.state=state;self.pi=0;self.sel=None;self.undo.clear();self.redo.clear();self.refresh()
        self.saved=path;self.dirty=False
    def template(self):
        path=QFileDialog.getOpenFileName(self,"加载模板",str(ROOT/"configs"),"模板 (*.json)")[0]
        if path:
            settings=read(path,"template");self.sel=None;self.change(lambda:self.state.update(settings=settings))
    def save_template(self):
        path=QFileDialog.getSaveFileName(self,"保存模板",str(ROOT/"configs"),"模板 (*.json)")[0]
        if path:write(path if path.endswith(".json") else path+".json","template",self.settings)
    def remove_template(self):
        path=QFileDialog.getOpenFileName(self,"删除模板",str(ROOT/"configs"),"模板 (*.json)")[0]
        if path and Path(path).resolve()!=(ROOT/"configs/default.json").resolve():
            read(path,"template")
            if message(self,"删除模板",path,True):Path(path).unlink()
    def export_to(self,path):
        with pdf.open() as doc:
            for i in range(len(self.pages)):render(doc,self.source,self.state,i)
            doc.subset_fonts();doc.save(path,garbage=4,deflate=True)
    def export(self):
        path=QFileDialog.getSaveFileName(self,"导出 PDF",str(ROOT/"output"),"PDF (*.pdf)")[0]
        if not path:return
        issues=[f"第 {i+1} 页：{issue}" for i,pg in enumerate(self.pages) if (issue:=footer_issue(self.settings,pg,self.source,title_object(self.state,i)))]
        if issues and not message(self,"检查页码","\n".join(issues[:10])+"\n继续导出？",True):return
        self.export_to(path if path.endswith(".pdf") else path+".pdf");self.status.setText("已导出 "+path)
    def closeEvent(self,event):
        self.canvas.shutdown();self.source.close();self.temp.cleanup()
        QApplication.instance().removeEventFilter(self.wheel_guard)
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)
