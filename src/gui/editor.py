import json
import logging
import sys
import tempfile
import time
from copy import deepcopy
from shutil import copyfile
from collections import Counter,deque
from pathlib import Path
import pymupdf as pdf
from PyQt6.QtCore import Qt,QTimer,QProcess,QSize,QSignalBlocker,QEvent,QSettings,QItemSelectionModel,QPointF
from PyQt6.QtGui import QColor,QPainter,QAction,QIcon,QImage,QPixmap,QKeySequence,QShortcut
from PyQt6.QtWidgets import (QMainWindow,QApplication,QWidget,QFrame,QSplitter,QSplitterHandle,QVBoxLayout,QHBoxLayout,
    QLabel,QMenu,QComboBox,QToolButton,QPushButton,QLineEdit,QScrollArea,QListWidget,QListWidgetItem,QTreeWidget,
    QTreeWidgetItem,QTabBar,QStackedWidget,QAbstractItemView,QFileDialog,QProgressBar,QDialog,QPlainTextEdit)
from src.core.model import (DEFAULT,TEXT,group,page,paper,boxes,move,regroup,title_object,content_box)
from src.configuration.store import read,write,identity,write_project,unpack_project_source
from src.rendering.pdfout import render,footer_issue
from .theme import paint_rounded_surface
from .widgets import line_icon,TitleBar,Dialog,message,prompt,WheelGuard
from .inspector import Inspector
from .canvas import PageCanvas
from .style_dialog import style_dialog,numbering_dialog
from src.core.structure import boundaries,section_start,section_objects,section_band,band_owner,contents,migrate_titles
from src.core.model import page_objects

ROOT=Path(__file__).resolve().parents[2]

class SidebarSplitter(QSplitter):
    def createHandle(self):
        return SidebarHandle(self.orientation(),self)


class SidebarHandle(QSplitterHandle):
    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#526e5d" if self.underMouse() else "#90a497"))
        center=QPointF(self.rect().center())
        for offset in (-5,0,5):
            painter.drawEllipse(center+QPointF(offset,0),1.2,1.2)


class SourceList(QListWidget):
    def __init__(self,editor):
        super().__init__()
        self.editor=editor
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_menu)

    def selected_rows(self):
        return sorted(self.row(item) for item in self.selectedItems())

    def dropEvent(self,event):
        if event.source() is not self:return
        position=event.position().toPoint()
        target=self.itemAt(position)
        slot=self.row(target)+(position.y()>=self.visualItemRect(target).center().y()) if target else self.count()
        self.editor.move_sources(self.selected_rows(),slot)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def show_menu(self,pos):
        item=self.itemAt(pos)
        if item and not item.isSelected():
            self.setCurrentItem(item)
        elif item:
            self.setCurrentItem(item,QItemSelectionModel.SelectionFlag.NoUpdate)
        menu=QMenu(self)
        menu.addAction("剪切",self.editor.cut_sources).setEnabled(bool(self.selectedItems()))
        menu.addAction("复制",self.editor.copy_sources).setEnabled(bool(self.selectedItems()))
        menu.addAction("粘贴到此处",self.editor.paste_sources).setEnabled(bool(self.editor.source_clip))
        menu.exec(self.viewport().mapToGlobal(pos))


class PageTree(QTreeWidget):
    def __init__(self,editor):
        super().__init__()
        self.editor=editor;self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
    def dropEvent(self,event):
        target=self.itemAt(event.position().toPoint())
        if event.source() is self.editor.library and target:
            entry=target.data(0,Qt.ItemDataRole.UserRole)
            indices=[item.data(Qt.ItemDataRole.UserRole) for item in self.editor.library.selectedItems()]
            self.editor.insert_sources(indices,entry[0],entry[1] if len(entry)==2 else None)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return
        selected=self.currentItem()
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
        self.setObjectName("handoutWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        available=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1280,available.width()-20),min(820,available.height()-20));self.setMinimumSize(960,600)
        self.move(available.center()-self.rect().center())
        self.temp=tempfile.TemporaryDirectory()
        self.source=pdf.open();self.source_revision=0;self.preview_source=None;self.source_snapshot=None
        self.state={"settings":read(ROOT/"configs/default.json","template"),"pages":[page()],"source":None}
        self.apply_scope="object"
        self.selected_objects=[]
        self.pi=0;self.sel=None;self.saved=None;self.clip=None
        self.undo=[];self.redo=[];self.last_edit=None;self.dirty=False
        self.process=None;self.images=[];self.source_clip=[];self.preview_mode=False
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
        outer=QVBoxLayout(central);outer.setContentsMargins(6,2,6,5);outer.setSpacing(5)
        menus={
            "文件":[("导入 PPTX",self.import_file),("打开工程",self.open_project),("保存工程",self.save),("工程另存为",lambda:self.save(True)),("导出 PDF",self.export),("导出目录",self.export_contents)],
            "插入":[("页",self.add_page),("文本框",lambda:self.add_object("text"),
                     self.scope_commands("text")),("目录",self.insert_toc),
                    ("批注区",lambda:self.add_object("notes"),self.scope_commands("notes")),
                    ("页码",self.insert_number),("分节符",self.insert_section),
                    ("页眉",lambda:self.edit_band("header")),("页脚",lambda:self.edit_band("footer"))],
            "页面":[("移到下一页并顺延",lambda:self.shift(1)),("移到上一页",lambda:self.shift(-1)),("移至指定页与位置",self.destination),("从选中原稿重新分页",self.reflow)],
            "布局":[("页面 / Slides 区域",lambda:self.select(None)),("恢复本页自动布局",self.auto),("对齐与统一尺寸",self.align),
                    ("页码样式",lambda:self.select(("number",0))),("本页编号",lambda:self.select(("numbering",0)))],
            "样式":lambda:style_dialog(self),
            "编号器":lambda:numbering_dialog(self),
            "配置":[("加载模板",self.template),("保存模板",self.save_template),("设为默认",lambda:write(ROOT/"configs/default.json","template",self.settings)),("删除模板",self.remove_template)]
        }
        self.titlebar=TitleBar(self,menus,history=self.history);outer.addWidget(self.titlebar)
        self.split=QSplitter();outer.addWidget(self.split,1)
        panels=[]
        for name in ("leftRail","panel","panel"):
            frame=QFrame();frame.setObjectName(name);frame.setMinimumWidth(180)
            layout=QVBoxLayout(frame);layout.setContentsMargins(9,8,9,8);layout.setSpacing(5)
            self.split.addWidget(frame);panels.append(layout)
        left,middle,right=panels
        self.property_panel=right.parentWidget()
        left.setContentsMargins(0,0,0,0)
        self.left_split=SidebarSplitter(Qt.Orientation.Vertical)
        self.left_split.setObjectName("pageSidebarSplit")
        self.left_split.setChildrenCollapsible(False)
        self.left_split.setHandleWidth(5)
        left.addWidget(self.left_split)
        sidebar_panes=[]
        for label in ("原始幻灯片","输出页面"):
            pane=QFrame()
            pane.setObjectName("panel")
            pane.setMinimumHeight(105)
            layout=QVBoxLayout(pane)
            layout.setContentsMargins(9,8,9,8)
            layout.setSpacing(5)
            layout.addWidget(QLabel(label))
            self.left_split.addWidget(pane)
            sidebar_panes.append(layout)
        sources,output=sidebar_panes
        self.left_split.setStretchFactor(0,3)
        self.left_split.setStretchFactor(1,2)
        self.left_split.handle(1).setToolTip("拖动分隔线调整上下窗口高度")
        self.library=SourceList(self);self.library.setObjectName("slideLibrary");self.library.setIconSize(QSize(120,76))
        self.library.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.library.itemClicked.connect(self.locate_source)
        self.library.itemDoubleClicked.connect(self.preview_original)
        sources.addWidget(self.library,1)
        self.output_tabs=QTabBar()
        self.output_tabs.setObjectName("outputModes")
        self.output_tabs.setExpanding(False)
        self.output_tabs.setDrawBase(False)
        self.output_tabs.addTab("页面结构");self.output_tabs.addTab("缩略图")
        output.addWidget(self.output_tabs)
        self.output_tabs.currentChanged.connect(self.set_preview_mode)
        self.tree=PageTree(self);self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.tree.customContextMenuRequested.connect(self.slide_menu);self.tree.itemClicked.connect(self.tree_selected)
        self.output_stack=QStackedWidget()
        self.output_stack.addWidget(self.tree)
        self.output_thumbnails=QListWidget()
        self.output_thumbnails.setObjectName("slideLibrary")
        self.output_thumbnails.setIconSize(QSize(125,168))
        self.output_thumbnails.itemClicked.connect(lambda item:self.goto(self.output_thumbnails.row(item)))
        self.output_stack.addWidget(self.output_thumbnails)
        output.addWidget(self.output_stack,1)
        self.thumbnail_process=QProcess(self)
        self.thumbnail_process.setWorkingDirectory(str(ROOT))
        self.thumbnail_process.readyReadStandardOutput.connect(self.receive_thumbnails)
        self.thumbnail_timer=QTimer(self)
        self.thumbnail_timer.setSingleShot(True)
        self.thumbnail_timer.setInterval(180)
        self.thumbnail_timer.timeout.connect(self.render_thumbnails)
        nav=QHBoxLayout();nav.setContentsMargins(0,0,0,0);nav.setSpacing(5);nav.addStretch()
        self.previous=QToolButton();self.previous.setIcon(line_icon("previous"));self.previous.setFixedSize(26,26);self.previous.setToolTip("上一页")
        self.previous.clicked.connect(lambda:self.goto(self.pi-1));nav.addWidget(self.previous)
        self.page_entry=QLineEdit("1");self.page_entry.setFixedWidth(38);self.page_entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_entry.returnPressed.connect(self.jump);nav.addWidget(self.page_entry)
        self.page_total=QLabel("/ 1");nav.addWidget(self.page_total)
        self.next=QToolButton();self.next.setIcon(line_icon("next"));self.next.setFixedSize(26,26);self.next.clicked.connect(lambda:self.goto(self.pi+1));nav.addWidget(self.next)
        nav.addSpacing(8)
        minus=QToolButton();minus.setIcon(line_icon("zoom_out"));minus.setToolTip("缩小");minus.clicked.connect(lambda:self.canvas.set_zoom(self.canvas.zoom/1.2));nav.addWidget(minus)
        self.zoom_label=QLabel("100%");self.zoom_label.setFixedWidth(42);self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus=QToolButton();plus.setIcon(line_icon("zoom_in"));plus.setToolTip("放大");plus.clicked.connect(lambda:self.canvas.set_zoom(self.canvas.zoom*1.2));nav.addWidget(plus);nav.addWidget(self.zoom_label)
        fit=QPushButton("适应窗口");fit.clicked.connect(lambda:self.canvas.fit());nav.addWidget(fit);nav.addStretch()
        middle.addLayout(nav)
        self.canvas=PageCanvas(self);middle.addWidget(self.canvas,1)
        self.property_title=QLabel("页面设置");self.property_title.setStyleSheet("font-weight:600;");right.addWidget(self.property_title)
        self.scope_widget=QWidget()
        scope_row=QHBoxLayout(self.scope_widget)
        scope_row.setContentsMargins(0,0,0,0)
        scope_row.addWidget(QLabel("当前设置应用于"))
        self.scope_box=QComboBox()
        scope_row.addWidget(self.scope_box,1)
        self.scope_box.currentIndexChanged.connect(lambda _:setattr(self,"apply_scope",self.scope_box.currentData()))
        right.addWidget(self.scope_widget)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.property_scroll=scroll
        self.inspector=Inspector(self);scroll.setWidget(self.inspector);right.addWidget(scroll)
        status_rule=QFrame();status_rule.setFixedHeight(1)
        status_rule.setStyleSheet("background:#d1dcd5;border:0;")
        outer.addWidget(status_rule)
        self.status=QLabel()
        self.status.setStyleSheet("background:transparent;color:#4f6258;padding:0 6px 2px;")
        status_row=QHBoxLayout()
        status_row.addWidget(self.status,1)
        self.export_progress=QProgressBar()
        self.export_progress.setFixedWidth(180)
        self.export_progress.setFixedHeight(16)
        self.export_progress.hide()
        status_row.addWidget(self.export_progress)
        outer.addLayout(status_row)
        self.split.setSizes([210,710,350])
        for key,fn in [("Ctrl+S",self.save),("Ctrl+Z",lambda:self.history(False)),("Ctrl+Y",lambda:self.history(True)),("Ctrl+X",self.cut),("Ctrl+C",self.copy),("Ctrl+V",self.paste),("Delete",self.delete),("PgUp",lambda:self.goto(self.pi-1)),("PgDown",lambda:self.goto(self.pi+1))]:
            shortcut=QShortcut(QKeySequence(key),self)
            shortcut.activated.connect(lambda fn=fn,key=key:self.shortcut(fn,key))
        self.wheel_guard=WheelGuard(self)
        QApplication.instance().installEventFilter(self.wheel_guard)
        QApplication.instance().installEventFilter(self)
    def paintEvent(self,event):
        painter=QPainter(self)
        # Clear pixels from the maximized backing surface before restoring corners.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(),Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if self.isMaximized() or self.isFullScreen():
            painter.fillRect(self.rect(),QColor("#f1f3f2"))
        else:
            paint_rounded_surface(painter,self.rect(),"#f1f3f2","#bdcbc2",10)

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.WindowStateChange:
            self.update()

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
        focus=QApplication.focusWidget()
        if focus and (focus is self.library or self.library.isAncestorOf(focus)):
            source_action={"Ctrl+X":self.cut_sources,"Ctrl+C":self.copy_sources,"Ctrl+V":self.paste_sources}.get(key)
            if source_action:
                source_action()
                return
        if key=="Ctrl+V" and self.source_clip and not self.clip and not isinstance(focus,(QLineEdit,QPlainTextEdit)):
            slot=self.sel[1] if self.sel and self.sel[0]=="slides" else None
            self.insert_sources(self.source_clip,self.pi,slot)
            return
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
        self.titlebar.set_history_enabled(bool(self.undo),bool(self.redo))
        if rebuild:self.refresh()
        else:
            self.canvas.schedule()
            if self.preview_mode:self.thumbnail_timer.start()
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
        self.sync_sources()
        with QSignalBlocker(self.tree):
            self.tree.clear()
            for p,pg in enumerate(self.pages):
                parent=QTreeWidgetItem([f"第 {p+1} 页"]);parent.setData(0,Qt.ItemDataRole.UserRole,(p,));self.tree.addTopLevelItem(parent)
                for i,slide in enumerate(pg["slides"]):
                    child=QTreeWidgetItem([f"幻灯片 {slide['source']+1}" if slide["source"] is not None else "空槽位"]);child.setData(0,Qt.ItemDataRole.UserRole,(p,i));parent.addChild(child)
                parent.setExpanded(p==self.pi)
        self.sync_navigation();self.select(self.sel)
        if self.preview_mode:self.thumbnail_timer.start()
    def sync_navigation(self):
        self.titlebar.set_history_enabled(bool(self.undo),bool(self.redo))
        self.page_entry.setText(str(self.pi+1));self.page_total.setText(f"/ {len(self.pages)}")
        self.previous.setEnabled(self.pi>0);self.next.setEnabled(self.pi+1<len(self.pages))
        issue=footer_issue(self.effective_settings(),self.pg,self.source,title_object(self.state,self.pi))
        self.status.setText(issue or f"原稿 {len(self.source)} 张 · 讲义 {len(self.pages)} 页")
    def goto(self,index):
        self.pi=max(0,min(index,len(self.pages)-1));self.sel=None;self.last_edit=None
        self.sync_navigation();self.select(None)
        if self.preview_mode:self.output_thumbnails.setCurrentRow(self.pi)
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
        if kind in ("slides_region","notes_region"):
            area=boundaries(self.effective_settings(),self.pi)[kind=="notes_region"]
            if kind=="notes_region":
                notes=next((o for o in reversed(page_objects(self.state,self.pi)) if o["kind"]=="notes"),None)
                return dict(notes or DEFAULT["objects"][0],box=area)
            settings=self.effective_settings()
            return dict(box=area,count=settings["count"],direction=settings["direction"],
                        columns=settings.get("columns",0),gap=settings["gap"],align=settings["align"],
                        slide_border=settings.get("slide_border",False))
        if kind=="section_object":return self.pages[section_start(self.pages,self.pi)]["section_objects"][i]
        if kind in ("header","footer"):return section_band(self.pages,self.pi,kind) or self.pages[section_start(self.pages,self.pi)][kind]
        if kind=="number":return self.settings["number"]
        if kind=="numbering":return self.pg["numbering"]
        if kind=="title":return self.pg.get("title") or title_object(self.state,self.pi) or dict(TEXT,kind="title",text="")
        if kind=="slides":return self.pg["slides"][i]
        return (self.settings if kind=="global" else self.pg)["objects"][i]
    def select(self,selection):
        if selection and selection[0]=="slides" and self.pg["slides"][selection[1]]["source"] is None:selection=None
        preserve_scroll=selection==self.sel
        self.sel=selection;self.last_edit=None
        self.selected_objects=[] if selection is None else [selection]
        self.apply_scope="object"
        with QSignalBlocker(self.scope_box):
            self.scope_box.setEnabled(True)
            self.scope_box.clear()
            band=selection and selection[0] in ("header","footer")
            self.scope_box.addItem("当前节" if band else "当前对象","section" if band else "object")
            if band:self.apply_scope="section"
            else:
                self.scope_box.addItem("当前节","section")
                self.scope_box.addItem("全局","global")
            self.scope_widget.setVisible(bool(band) or self.obj().get("kind")!="text")
        names={"settings":"页面设置","number":"页码样式","numbering":"本页编号","slides":"幻灯片","title":"本页标题","slides_region":"Slides 边界","notes_region":"批注边界","section_object":"节对象","header":"页眉","footer":"页脚","global":"全局对象","objects":"页面对象"}
        title=names[(selection or ("settings",0))[0]]
        if selection and selection[0] in ("global","objects","section_object"):
            kind=self.obj().get("kind")
            title={"notes":"批注区","text":"文本框"}.get(kind,title)
        self.property_title.setText(title)
        self.property_panel.setVisible(self.preview_source is not None or selection is not None)
        self.inspector.build(preserve_scroll=preserve_scroll)
        self.canvas.update_hits();self.canvas.schedule()
    def edit_property(self,key,value,rebuild=False,proportional=False):
        before=deepcopy(self.state)
        selection=self.sel
        if selection and selection[0] in ("slides_region","notes_region"):
            if selection[0]=="notes_region" and key!="box":
                notes=next((o for o in reversed(page_objects(self.state,self.pi)) if o["kind"]=="notes"),None)
                if notes is None:
                    self.add_object("notes")
                    notes=self.obj()
                self.change(lambda:notes.update({key:value}),False)
                return
            if key=="box":
                key="content_box" if selection[0]=="slides_region" else "notes_box"
            self.layout_edit(key,value)
            return
        if not selection and (self.apply_scope!="object" or key in self.pg.get("page_layout",{})):
            self.layout_edit(key,value)
            return
        target=self.obj()
        if selection and selection[0] in ("header","footer"):
            kind=selection[0]
            owner=self.pages[section_start(self.pages,self.pi)]
            if key=="band_inherit":
                self.change(lambda:owner.update({kind+"_inherit":value}))
                return
            if key=="header_alternate":
                def change_parity():
                    if owner.get("header_inherit"):
                        self.detach_header(owner)
                    owner["header_alternate"]=value
                    if value and "header_even" not in owner:
                        owner["header_even"]=deepcopy(owner["header"])
                self.change(change_parity)
                return
            if owner.get(kind+"_inherit"):
                if kind=="header":
                    self.detach_header(owner)
                else:
                    owner.update({kind:deepcopy(target),kind+"_inherit":False})
            if kind=="header" and self.pi%2 and owner.get("header_alternate"):
                if "header_even" not in owner:
                    owner["header_even"]=deepcopy(owner["header"])
                target=owner["header_even"]
            else:
                target=owner[kind]
        if key=="text_style":
            def set_style():
                for obj in self.property_targets() or [target]:
                    obj["text_style"]=value
                    obj.pop("text_overrides",None)
            self.change(set_style)
            return
        targets=self.property_targets()
        if targets:
            if key=="box":
                original=object_box(self.effective_settings(),target)
                delta=[new-old for new,old in zip(value,original)]
                for obj in targets:
                    box=object_box(self.effective_settings(),obj)
                    obj["box"]=[
                        max(1,v*value[i]/original[i]) if proportional and i>=2 else
                        v+d if i<2 else max(1,v+d)
                        for i,(v,d) in enumerate(zip(box,delta))
                    ]
                    obj.pop("auto_box",None)
            else:
                for obj in targets:
                    if obj.get("text_style") and key in ("font","latin_font","size","bold","italic","underline"):
                        obj.setdefault("text_overrides",{})[key]=value
                    else:obj[key]=value
            self.undo.append(before);self.redo.clear();self.sync_navigation();self.canvas.schedule()
            if rebuild:self.inspector.build()
            return
        from src.core.textstyles import styled
        old=styled(self.settings,target).get(key)
        if self.sel==("number",0) and key in ("start","chapter","substart","separator","page_style","section_style"):
            target=self.settings;old=target.get(key)
        if old==value:return
        if self.sel==("title",0) and self.pg.get("title") is None:
            self.pg["title"]=deepcopy(target);target=self.pg["title"]
        if self.sel==("numbering",0) and (value is None or value==""):target.pop(key,None)
        else:
            if key=="box":target.pop("auto_box",None)
            if target.get("text_style") and key in ("font","latin_font","size","bold","italic","underline"):
                target.setdefault("text_overrides",{})[key]=value
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
        elif key in ("paper","landscape","margins","division","alternate") and not self.sel:QTimer.singleShot(0,self.inspector.build)
        self.canvas.update_hits();self.canvas.schedule()
        if self.preview_mode:self.thumbnail_timer.start()
    def effective_settings(self):
        start=section_start(self.pages,self.pi)
        return self.settings | self.pages[start].get("layout",{}) | self.pg.get("page_layout",{}) | {"_page_index":self.pi}

    def layout_edit(self,key,value):
        def apply():
            owners={"object":self.pg,"section":self.pages[section_start(self.pages,self.pi)]}
            target=owners[self.apply_scope].setdefault("layout" if self.apply_scope=="section" else "page_layout",{}) if self.apply_scope in owners else self.settings
            if key=="box":key_name="content_box"
            else:key_name=key
            target[key_name]=value
        self.change(apply,False)
        self.sync_navigation()
        self.canvas.update_hits()
        self.canvas.schedule()

    def property_targets(self):
        if not self.sel:return []
        selected=self.obj()
        if selected.get("kind")!="text":
            if self.apply_scope=="object" or selected.get("kind")!="notes":return []
            start=section_start(self.pages,self.pi)
            pages=self.pages if self.apply_scope=="global" else [p for i,p in enumerate(self.pages) if section_start(self.pages,i)==start]
            return [o for o in [selected]+[o for p in pages for o in p["objects"]+p.get("section_objects",[])] if o.get("kind")=="notes" and (o is selected or o not in self.settings["objects"])]
        if len(self.selected_objects)>1:
            active=self.sel
            targets=[]
            for key in self.selected_objects:
                self.sel=key
                if self.obj().get("kind")=="text":targets.append(self.obj())
            self.sel=active
            return targets
        if self.apply_scope=="object":return []
        start=section_start(self.pages,self.pi)
        pages=self.pages if self.apply_scope in ("global","level") else [p for i,p in enumerate(self.pages) if section_start(self.pages,i)==start]
        level=self.obj().get("level",0)
        pool=self.settings["objects"]+[o for p in pages for o in p["objects"]+p.get("section_objects",[])]
        return [o for o in pool if o.get("kind")=="text" and (self.apply_scope!="level" or o.get("level",0)==level)]

    def scope_commands(self,kind):
        return [(label,lambda scope=scope:self.add_object(kind,scope)) for label,scope in
                [("当前页","page"),("当前节","section"),("全局","global")]]

    def choose_file(self,title,file_filter,*,save=False,default=""):
        preferences=QSettings("Slides2Handouts","Slides2Handouts")
        folder=preferences.value("files/lastDirectory",default,type=str)
        if folder and not Path(folder).is_dir():folder=default
        picker=QFileDialog.getSaveFileName if save else QFileDialog.getOpenFileName
        path,_=picker(self,title,folder,file_filter)
        if path:
            preferences.setValue("files/lastDirectory",str(Path(path).absolute().parent))
        return path

    def export_contents(self):
        path=self.choose_file("导出目录","文本 (*.txt)",save=True)
        if path:Path(path).write_text(contents(self.state),encoding="utf-8-sig")

    def insert_toc(self):
        self.add_object("text",toc=True)

    def insert_number(self):
        self.change(lambda:(self.settings.update(number_enabled=True),self.pg["numbering"].pop("hidden",None)))
        self.select(("number",0))

    def insert_section(self):
        self.change(lambda:self.pg.update(section=True))

    def detach_header(self,owner):
        inherited=band_owner(self.pages,self.pi,"header")
        odd=inherited.get("header") or owner["header"]
        even=inherited.get("header_even",odd)
        owner.update(header=deepcopy(odd),header_even=deepcopy(even),
                     header_alternate=inherited.get("header_alternate",False),header_inherit=False)

    def edit_band(self,kind):
        settings=self.effective_settings()
        owner=self.pages[section_start(self.pages,self.pi)]
        width,height=paper(settings)
        if kind not in owner:
            left,top,right,bottom=settings["margins"]
            if kind=="header":
                label="页眉"
                y=6
                box_height=18
                size=11
            else:
                label="页脚"
                box_height=13
                y=height-box_height-2
                size=9
            band=dict(TEXT,text=label,box=[left,y,width-left-right,box_height],
                      text_style="body",text_overrides={"size":size})
            self.change(lambda:owner.update({kind:band,kind+"_inherit":False}))
            margin=top if kind=="header" else bottom
            required=y+box_height if kind=="header" else height-y
            if margin<required:
                self.status.setText(f"{label}超出页边距，请调整位置、字号或页边距")
        self.select((kind,0))

    def slide_menu(self,pos):
        item=self.tree.itemAt(pos)
        if not item:return
        self.tree_selected(item,0)
        if not self.sel:return
        menu=QMenu(self)
        menu.addAction("移到下一页",lambda:self.shift(1,True))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

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
        else:self.status.setText("此原稿尚未放入讲义，可拖到输出页面或使用复制、粘贴")
    def tree_selected(self,item,column):
        entry=item.data(0,Qt.ItemDataRole.UserRole);self.pi=entry[0]
        self.sync_navigation();self.select(("slides",entry[1]) if len(entry)==2 else None)
    def add_page(self):
        self.change(lambda:self.pages.append(page()));self.goto(len(self.pages)-1)
    def set_preview_mode(self,index):
        self.preview_mode=bool(index)
        self.sel=None
        self.output_stack.setCurrentIndex(index)
        self.refresh()

    def render_thumbnails(self):
        if not self.preview_mode:return
        process=self.thumbnail_process
        if process.state()!=QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(250)
        self.output_thumbnails.clear()
        for index in range(len(self.pages)):
            self.output_thumbnails.addItem(f"第 {index+1} 页")
        self.output_thumbnails.setCurrentRow(self.pi)
        folder=Path(self.temp.name)/"thumbnails"
        folder.mkdir(exist_ok=True)
        request={"state":self.state,"source":self.preview_source,"thumbnail_dir":str(folder)}
        process.start(str(Path(sys.executable).with_name("python.exe")),["-m","src.rendering.preview_worker"])
        process.write((json.dumps(request)+"\n").encode("utf8"))
        process.closeWriteChannel()

    def receive_thumbnails(self):
        process=self.thumbnail_process
        while process.canReadLine():
            reply=json.loads(bytes(process.readLine()).decode("utf8"))
            item=self.output_thumbnails.item(reply["index"])
            if item and "path" in reply:item.setIcon(QIcon(QPixmap(reply["path"])))

    def source_order(self):
        return list(self.state.get("library_order",range(len(self.images))))

    def sync_sources(self):
        order=self.source_order()
        current=[self.library.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.library.count())]
        if order==current:return
        scroll=self.library.verticalScrollBar().value()
        self.library.setUpdatesEnabled(False)
        try:
            with QSignalBlocker(self.library):
                reusable={}
                while self.library.count():
                    item=self.library.takeItem(0)
                    reusable.setdefault(item.data(Qt.ItemDataRole.UserRole),[]).append(item)
                for source in order:
                    items=reusable.get(source)
                    if items:
                        item=items.pop()
                    else:
                        item=QListWidgetItem(QIcon(self.images[source]),str(source+1))
                        item.setData(Qt.ItemDataRole.UserRole,source)
                    self.library.addItem(item)
        finally:
            self.library.setUpdatesEnabled(True)
        self.library.verticalScrollBar().setValue(scroll)

    def move_sources(self,rows,slot):
        order=self.source_order()
        moved=[order[i] for i in rows]
        rest=[value for i,value in enumerate(order) if i not in rows]
        slot-=sum(i<slot for i in rows)
        result=rest[:slot]+moved+rest[slot:]
        if result!=order:self.set_source_order(result)
        for i in range(slot,slot+len(moved)):self.library.item(i).setSelected(True)

    def set_source_order(self,order):
        previous=Counter(self.source_order())
        updated=Counter(order)
        def apply():
            self.state["library_order"]=order
            removed=previous-updated
            positions=[]
            slots=[]
            for pg in self.pages:
                kept=[]
                for slide in pg["slides"]:
                    source=slide["source"]
                    if removed[source]:
                        removed[source]-=1
                        continue
                    if source is not None and source in updated:
                        positions.append((pg,len(kept)))
                        slots.append(slide)
                    kept.append(slide)
                pg["slides"]=kept
            by_source={}
            for slide in slots:
                by_source.setdefault(slide["source"],deque()).append(slide)
            for source,count in (updated-previous).items():
                by_source.setdefault(source,deque()).extend(page([source]*count)["slides"])
            arranged=[]
            for source in order:
                if by_source.get(source):arranged.append(by_source[source].popleft())
            for queue in by_source.values():arranged.extend(queue)
            for (pg,index),slide in zip(positions,arranged):
                if pg["slides"][index] is not slide:slide["box"]=None
                pg["slides"][index]=slide
            if len(arranged)>len(positions):
                pg,index=positions[-1] if positions else (self.pg,-1)
                pg["slides"][index+1:index+1]=arranged[len(positions):]
            self.sel=None
        self.change(apply)

    def copy_sources(self):
        self.clip=None
        order=self.source_order()
        self.source_clip=[order[i] for i in self.library.selected_rows()]

    def cut_sources(self):
        self.copy_sources()
        rows=set(self.library.selected_rows())
        if rows:
            remaining=[source for i,source in enumerate(self.source_order()) if i not in rows]
            self.set_source_order(remaining)

    def paste_sources(self):
        if not self.source_clip:return
        order=self.source_order()
        slot=self.library.currentRow()
        if slot<0:slot=len(order)
        order[slot:slot]=self.source_clip
        self.set_source_order(order)
        for row in range(slot,slot+len(self.source_clip)):self.library.item(row).setSelected(True)

    def insert_sources(self,indices,page_index,slot=None):
        if not indices:return
        slides=self.pages[page_index]["slides"]
        slot=len(slides) if slot is None else slot
        def insert():
            slides[slot:slot]=page(indices)["slides"]
            self.pi=page_index
            self.sel=None
        self.change(insert)

    def cut(self):
        self.copy()
        self.delete()

    def shift(self,d,void=False):
        if not self.sel or self.sel[0]!="slides" or self.pi+d<0:return
        i=self.sel[1];p=self.pi
        def action():
            if p+d==len(self.pages):self.pages.append(page())
            move(self.pages,p,i,p+d,0 if d>0 else len(self.pages[p+d]["slides"]))
            if void:
                self.pages[p]["slides"].insert(i,dict(source=None,box=None))
                destination=self.pages[p+d]["slides"]
                vacancy=next((j for j,item in enumerate(destination) if item["source"] is None),None)
                if vacancy is not None:destination.pop(vacancy)
            if d>0:
                capacity=self.effective_settings()["count"];dest=p+1
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
    def add_object(self,kind,scope="page",toc=False):
        if kind=="notes" and not boundaries(self.effective_settings(),self.pi)[1]:
            raise ValueError("请先在布局中划分批注区")
        obj=deepcopy(DEFAULT["objects"][0] if kind=="notes" else TEXT)
        if kind=="notes":obj["auto_box"]=True
        else:
            from src.core.textstyles import text_styles
            styles=text_styles(self.settings)
            obj["text_style"]="body" if "body" in styles else next(iter(styles),"body")
        if toc:obj.update(toc=True,text="目录",box=[28,28,360,520])
        target={"page":self.pg["objects"],"global":self.settings["objects"]}
        def add():
            objects=section_objects(self.state,self.pi) if scope=="section" else target[scope]
            objects.append(obj)
        self.change(add)
        objects=section_objects(self.state,self.pi) if scope=="section" else target[scope]
        self.select(({"page":"objects","global":"global","section":"section_object"}[scope],len(objects)-1))
    def copy(self):
        if self.sel:
            self.source_clip=[]
            self.clip=deepcopy(self.obj())
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
        if kind not in ("global","slides","objects","section_object"):return
        target=self.settings["objects"] if kind=="global" else section_objects(self.state,self.pi) if kind=="section_object" else self.pg[kind]
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
        snapshot=folder/"original.pptx"
        copyfile(path,snapshot)
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
        process.start(sys.executable,["-m","src.rendering.worker",str(snapshot),str(folder),str(self.devicePixelRatioF())])
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
        self.source_snapshot=snapshot
        if state is None:self.settings.setdefault("division","horizontal")
        self.library.clear();self.images=[];self.source_clip=[]
        for i in range(len(doc)):
            pix=QPixmap(str(folder/f"{i}.png"));self.images.append(pix)
        self.undo.clear();self.redo.clear();self.clip=None;self.saved=None;self.pi=0;self.sel=None;self.dirty=False
        self.refresh();return True
    def import_file(self):
        path=self.choose_file("导入 PPTX","PowerPoint (*.pptx)")
        if path:self.load_source(path)
    def save(self,another=False):
        path=None if another else self.saved
        if not path:path=self.choose_file("保存工程","讲义工程 (*.json)",save=True)
        if path:
            if not path.lower().endswith(".json"):path+=".json"
            write_project(path,self.state,self.source_snapshot)
            self.saved=path;self.dirty=False
            self.status.setText("工程已保存 · 已内嵌 PPTX" if self.state["source"] else "工程已保存")
    def open_project(self):
        path=self.choose_file("打开工程","讲义工程 (*.json)")
        if not path:return
        state=read(path,"project")
        migrate_titles(state)
        used_embedded_source=False
        if state["source"]:
            metadata=state["source"]
            if "embedded_pptx" in metadata:
                with tempfile.TemporaryDirectory(dir=self.temp.name) as staging:
                    source=unpack_project_source(metadata,Path(staging)/"original.pptx")
                    if not self.load_source(source,state):return
                    used_embedded_source=True
            else:
                source=Path(metadata["path"])
                if not source.is_file() or identity(source)!=metadata["sha256"]:
                    chosen=self.choose_file("定位原始 PPTX","PowerPoint (*.pptx)")
                    if not chosen:return
                    source=Path(chosen)
                metadata["path"]=str(source)
                if not self.load_source(source,state):return
        else:
            self.canvas.clear();self.source.close();self.source=pdf.open();self.source_revision+=1;self.preview_source=None;self.source_snapshot=None
            self.library.clear();self.images=[];self.source_clip=[];self.state=state;self.pi=0;self.sel=None;self.undo.clear();self.redo.clear();self.refresh()
        self.saved=path;self.dirty=False
        if used_embedded_source:
            self.status.setText("工程已打开 · 已读取内嵌 PPTX")
    def template(self):
        path=self.choose_file("加载模板","模板 (*.json)",default=str(ROOT/"configs"))
        if path:
            settings=read(path,"template");self.sel=None;self.change(lambda:self.state.update(settings=settings))
    def save_template(self):
        path=self.choose_file("保存模板","模板 (*.json)",save=True,default=str(ROOT/"configs"))
        if path:write(path if path.endswith(".json") else path+".json","template",self.settings)
    def remove_template(self):
        path=self.choose_file("删除模板","模板 (*.json)",default=str(ROOT/"configs"))
        if path and Path(path).resolve()!=(ROOT/"configs/default.json").resolve():
            read(path,"template")
            if message(self,"删除模板",path,True):Path(path).unlink()
    def export_to(self,path):
        total=len(self.pages)
        self.export_progress.setRange(0,total)
        self.export_progress.setFormat("导出 PDF  %v / %m")
        self.export_progress.setValue(0)
        self.export_progress.show()
        self.export_progress.parentWidget().layout().activate()
        self.export_progress.repaint()
        try:
            self.write_pdf(path,total)
        finally:
            self.export_progress.hide()

    def write_pdf(self,path,total):
        with pdf.open() as doc:
            for i in range(total):
                render(doc,self.source,self.state,i)
                self.export_progress.setValue(i+1)
                self.export_progress.repaint()
            self.export_progress.setFormat("正在保存 PDF…")
            self.export_progress.repaint()
            doc.subset_fonts();doc.save(path,garbage=4,deflate=True)
    def export(self):
        path=self.choose_file("导出 PDF","PDF (*.pdf)",save=True,default=str(ROOT/"output"))
        if not path:return
        issues=[f"第 {i+1} 页：{issue}" for i,pg in enumerate(self.pages) if (issue:=footer_issue(self.settings,pg,self.source,title_object(self.state,i)))]
        if issues and not message(self,"检查页码","\n".join(issues[:10])+"\n继续导出？",True):return
        self.export_to(path if path.endswith(".pdf") else path+".pdf");self.status.setText("已导出 "+path)
    def closeEvent(self,event):
        if self.isVisible():
            confirmation=Dialog(self,"退出 Slides2Handouts")
            warning="当前工程有未保存的修改。确定退出吗？" if self.dirty else "确定退出 Slides2Handouts 吗？"
            confirmation.body.addWidget(QLabel(warning))
            buttons=confirmation.add_buttons()
            cancel=buttons.button(buttons.StandardButton.Cancel)
            confirm=buttons.button(buttons.StandardButton.Ok)
            confirm.setText("退出")
            cancel.setDefault(True)
            cancel.setFocus()
            if confirmation.exec()!=QDialog.DialogCode.Accepted:
                event.ignore()
                return
        self.thumbnail_timer.stop()
        if self.thumbnail_process.state()!=QProcess.ProcessState.NotRunning:
            self.thumbnail_process.kill()
            self.thumbnail_process.waitForFinished(500)
        self.canvas.shutdown();self.source.close();self.temp.cleanup()
        QApplication.instance().removeEventFilter(self.wheel_guard)
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)
