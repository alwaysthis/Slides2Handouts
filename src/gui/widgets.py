from pathlib import Path
from PyQt6.QtCore import Qt, QEvent, QObject, QPointF, QRectF, QSize, QSignalBlocker
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QIcon, QPixmap, QWheelEvent, QFontDatabase
from PyQt6.QtWidgets import (QWidget,QHBoxLayout,QVBoxLayout,QToolButton,QLabel,
    QDialog,QDialogButtonBox,QColorDialog,QLineEdit,QFormLayout,QPushButton,
    QMenuBar,QMessageBox,QInputDialog,QApplication,QAbstractSpinBox,QComboBox,QScrollArea,QSizePolicy)

from .theme import paint_rounded_surface

ROOT=Path(__file__).resolve().parents[2]

def line_icon(kind):
    pix=QPixmap(36,36)
    pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#476653"),2))
    if kind in ("previous","next"):
        x=14 if kind=="previous" else 22
        other=36-x
        painter.drawLine(other,10,x,18)
        painter.drawLine(x,18,other,26)
    elif kind.startswith("align_"):
        alignment=kind.removeprefix("align_")
        if alignment in ("left","center","right"):
            for y,width in ((9,22),(15,13),(21,22),(27,13)):
                x={"left":7,"center":(36-width)//2,"right":29-width}[alignment]
                painter.drawLine(x,y,x+width,y)
        else:
            y={"top":7,"middle":18,"bottom":29}[alignment]
            painter.drawLine(6,y,30,y)
            start={"top":12,"middle":11,"bottom":10}[alignment]
            rows=(start,start+6,start+12) if alignment!="middle" else (11,25)
            for line in rows:
                painter.drawLine(11,line,25,line)
    elif kind in ("zoom_in","zoom_out"):
        painter.drawEllipse(5,5,18,18);painter.drawLine(20,20,30,30);painter.drawLine(9,14,19,14)
        if kind=="zoom_in":painter.drawLine(14,9,14,19)
    elif kind in ("undo","redo"):
        if kind=="redo":
            painter.translate(36,0)
            painter.scale(-1,1)
        path=QPainterPath(QPointF(7,15))
        path.lineTo(20,15)
        path.cubicTo(26,15,30,19,30,26)
        painter.drawPath(path)
        painter.drawLine(7,15,14,8)
        painter.drawLine(7,15,14,22)
    elif kind=="close":
        painter.drawLine(11,11,25,25);painter.drawLine(25,11,11,25)
    elif kind=="min":
        painter.drawLine(10,21,26,21)
    elif kind=="max":
        painter.drawRect(10,10,16,16)
    elif kind=="restore":
        painter.drawRect(10,14,13,13);painter.drawLine(14,10,27,10)
        painter.drawLine(27,10,27,23)
    painter.end()
    return QIcon(pix)

class TitleBar(QWidget):
    def __init__(self,window,menus=None,history=None):
        super().__init__(window)
        self.host=window
        self.setObjectName("titleStrip")
        self.setFixedHeight(32)
        row=QHBoxLayout(self);row.setContentsMargins(8,0,0,0);row.setSpacing(0)
        if menus is not None:
            logo=QLabel();logo.setPixmap(QIcon(str(ROOT/"assets/handouts.ico")).pixmap(20,20))
            row.addWidget(logo);row.addSpacing(5)
            if history is not None:
                self.undo_button=self.button("undo","撤销 (Ctrl+Z)",lambda:history(False))
                self.redo_button=self.button("redo","重做 (Ctrl+Y)",lambda:history(True))
                for button in (self.undo_button,self.redo_button):
                    button.setFixedWidth(28)
                    row.addWidget(button)
                row.addSpacing(3)
            bar=QMenuBar()
            for title,commands in menus.items():
                if callable(commands):
                    bar.addAction(title,commands)
                    continue
                menu=bar.addMenu(title)
                for text,fn,*children in commands:
                    if children:
                        sub=menu.addMenu(text)
                        for label,callback in children[0]:sub.addAction(label,callback)
                        default=sub.menuAction()
                        menu.installEventFilter(self)
                        if not hasattr(self,"submenu_defaults"):self.submenu_defaults={}
                        self.submenu_defaults[default]=fn
                        continue
                    action=menu.addAction(text)
                    action.triggered.connect(lambda checked=False,fn=fn:fn())
            row.addWidget(bar)
        else:row.addWidget(QLabel(window.windowTitle()))
        row.addStretch()
        if menus is not None:
            for key,label,fn in [("min","最小化",window.showMinimized),("max","最大化 / 还原",self.toggle)]:
                row.addWidget(self.button(key,label,fn))
        row.addWidget(self.button("close","关闭",window.close))
        window.installEventFilter(self)

    def set_history_enabled(self,undo,redo):
        self.undo_button.setEnabled(undo)
        self.redo_button.setEnabled(redo)

    def button(self,key,label,fn):
        button=QToolButton()
        button.setIcon(line_icon(key));button.setIconSize(QSize(18,18))
        button.setToolTip(label);button.setAccessibleName(label);button.setFixedSize(42,32)
        hover="#e95c58" if key=="close" else "#e8eeeb"
        button.setStyleSheet("QToolButton {background:transparent;border:0;border-radius:5px;padding:0;} QToolButton:hover {background:"+hover+";}")
        button.clicked.connect(fn)
        if key=="max":self.max_button=button
        return button

    def toggle(self):
        if self.host.isMaximized():self.host.showNormal()
        else:self.host.showMaximized()
        self.max_button.setIcon(line_icon("restore" if self.host.isMaximized() else "max"))

    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.MouseButtonRelease and hasattr(obj,"actionAt"):
            action=obj.actionAt(event.position().toPoint())
            callback=getattr(self,"submenu_defaults",{}).get(action)
            if callback and event.button()==Qt.MouseButton.LeftButton:
                if action.menu():action.menu().hide()
                obj.close()
                callback()
                return True
        if obj is self.host and event.type()==QEvent.Type.WindowStateChange and hasattr(self,"max_button"):
            self.max_button.setIcon(line_icon("restore" if self.host.isMaximized() else "max"))
        return super().eventFilter(obj,event)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.host.windowHandle():
            self.host.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self,event):
        if hasattr(self,"max_button"):self.toggle()

def emphasis_buttons(parent,values,commit):
    host=QWidget(parent)
    row=QHBoxLayout(host);row.setContentsMargins(0,0,0,0);row.setSpacing(4)
    for letter,key,label,rule in (
        ("B","bold","加粗","font-weight:bold"),
        ("I","italic","斜体","font-style:italic"),
        ("U","underline","下划线","text-decoration:underline"),
    ):
        button=QToolButton()
        button.setText(letter);button.setToolTip(label);button.setAccessibleName(label)
        button.setCheckable(True);button.setChecked(values.get(key,False))
        button.setStyleSheet('QToolButton {font-family:"Times New Roman";font-size:16px;min-width:22px;'+rule+';}')
        button.toggled.connect(lambda checked,field=key:commit(field,checked))
        row.addWidget(button)
    row.addStretch()
    return host


class FontPicker(QComboBox):
    """Compact font list with local names and stable values for PDF rendering."""
    def __init__(self,value):
        super().__init__()
        from src.rendering.fonts import ALIASES
        localized={family:label for label,family in ALIASES.items()}
        families={}
        for family in QFontDatabase.families():
            label=localized.get(family.casefold(),family)
            canonical=ALIASES.get(label,family)
            families.setdefault(canonical.casefold(),(label,canonical))
        canonical=ALIASES.get(value,value)
        label=localized.get(canonical.casefold(),value)
        families.setdefault(canonical.casefold(),(label,canonical))
        ordered=sorted(families.values(),key=lambda pair:(pair[0]!="宋体",pair[0].casefold()))
        for label,family in ordered:self.addItem(label,family)
        self.setCurrentIndex(next(i for i,(_,family) in enumerate(ordered) if family.casefold()==canonical.casefold()))
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(7)
        self.setMaxVisibleItems(9)

    def showPopup(self):
        super().showPopup()
        popup=self.view().window()
        if popup is not self.window():
            popup.resize(min(popup.width(),250),popup.height())


class WheelGuard(QObject):
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Wheel and isinstance(obj,(QAbstractSpinBox,QComboBox)):
            parent=obj.parentWidget()
            while parent and not isinstance(parent,QScrollArea):parent=parent.parentWidget()
            if parent:
                position=QPointF(parent.viewport().mapFromGlobal(event.globalPosition().toPoint()))
                forwarded=QWheelEvent(position,event.globalPosition(),event.pixelDelta(),event.angleDelta(),
                                      event.buttons(),event.modifiers(),event.phase(),event.inverted())
                QApplication.sendEvent(parent.viewport(),forwarded)
            event.accept()
            return True
        return False

def center(dialog,parent):
    dialog.adjustSize()
    if parent:
        dialog.move(parent.frameGeometry().center()-dialog.rect().center())

class Dialog(QDialog):
    def __init__(self,parent,title):
        super().__init__(parent,Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.setObjectName("roundedDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(title)
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(6,4,6,6);self.outer.setSpacing(0)
        self.outer.addWidget(TitleBar(self))
        self.body=QVBoxLayout();self.body.setContentsMargins(14,10,14,12);self.body.setSpacing(8)
        self.outer.addLayout(self.body)
    def showEvent(self,event):
        super().showEvent(event);center(self,self.parentWidget())

    def paintEvent(self,event):
        painter=QPainter(self)
        paint_rounded_surface(painter,self.rect(),"#f1f3f2","#bdcbc2",10)

    def add_buttons(self,standard=None,*,accept=None):
        roles=QDialogButtonBox.StandardButton
        if standard is None:
            standard=roles.Ok|roles.Cancel
        buttons=QDialogButtonBox(standard,self)
        for role,label in ((roles.Ok,"确定"),(roles.Cancel,"取消"),(roles.Yes,"继续"),(roles.No,"取消")):
            button=buttons.button(role)
            if button:button.setText(label)
        buttons.accepted.connect(self.accept if accept is None else accept)
        buttons.rejected.connect(self.reject)
        self.body.addWidget(buttons)
        return buttons

def message(parent,title,text,question=False):
    dialog=Dialog(parent,title)
    label=QLabel(text);label.setWordWrap(True);label.setMinimumWidth(320)
    dialog.body.addWidget(label)
    roles=QDialogButtonBox.StandardButton
    dialog.add_buttons(roles.Yes|roles.No if question else roles.Ok)
    return dialog.exec()==QDialog.DialogCode.Accepted

def prompt(parent,title,label,value=""):
    dialog=Dialog(parent,title);dialog.body.addWidget(QLabel(label))
    field=QLineEdit(str(value));dialog.body.addWidget(field)
    dialog.add_buttons()
    return field.text() if dialog.exec()==QDialog.DialogCode.Accepted else None

class ColorButton(QPushButton):
    def __init__(self,color,parent=None,allow_empty=False):
        super().__init__(parent)
        self.setObjectName("colorSwatch")
        self.value=color;self.allow_empty=allow_empty
        self.setFixedSize(26,26)
        self.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
        self.setToolTip("选择颜色")
        self.clicked.connect(self.pick)
        self.refresh()
    def refresh(self):
        self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        side=min(self.width(),self.height())
        square=QRectF((self.width()-side)/2,(self.height()-side)/2,side,side)
        paint_rounded_surface(painter,square,self.value or "#f1f3f2",
                              "#354f3e" if self.underMouse() or self.hasFocus() else "#87998d",6)
        if not self.value:
            painter.setPen(QColor("#53665b"))
            painter.drawText(square,Qt.AlignmentFlag.AlignCenter,"∅")

    def pick(self):
        dialog=Dialog(self.window(),"选择颜色")
        picker=QColorDialog(QColor(self.value or "#ffffff"))
        picker.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        picker.setOption(QColorDialog.ColorDialogOption.NoButtons)
        picker.setWindowFlags(Qt.WindowType.Widget)
        dialog.body.addWidget(picker)
        field=picker.findChild(QLineEdit,"qt_colorname_lineedit")
        translations={"Basic colors":"预设颜色","Custom colors":"自定义颜色","Hue:":"色相","Sat:":"饱和度","Val:":"明度",
                      "Red:":"红","Green:":"绿","Blue:":"蓝","Alpha channel:":"透明度","HTML:":"十六进制"}
        for label in picker.findChildren(QLabel):
            text=label.text().replace("&","")
            if text in translations:label.setText(translations[text])
        for button in picker.findChildren(QPushButton):
            text=button.text().replace("&","")
            if text=="Pick Screen Color":button.setText("屏幕取色")
            if text=="Add to Custom Colors":button.setText("添加到自定义颜色")
        def from_hex():
            color=QColor(field.text())
            if color.isValid():picker.setCurrentColor(color)
        def accept():
            from_hex()
            if QColor(field.text()).isValid():dialog.accept()
        dialog.add_buttons(accept=accept)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.value=picker.currentColor().name()
            self.refresh()
            self.changed(self.value)
    def changed(self,value):pass
