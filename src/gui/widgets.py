from pathlib import Path
from PyQt6.QtCore import Qt, QEvent, QObject, QPointF, QRectF, QSize, QSignalBlocker
from PyQt6.QtGui import QColor, QPainter, QPen, QIcon, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (QWidget,QHBoxLayout,QVBoxLayout,QToolButton,QLabel,
    QDialog,QDialogButtonBox,QColorDialog,QLineEdit,QFormLayout,QPushButton,
    QMenuBar,QMessageBox,QInputDialog,QApplication,QAbstractSpinBox,QComboBox,QScrollArea)
from .theme import MENU_STYLE

ROOT=Path(__file__).resolve().parents[2]

def line_icon(kind):
    pix=QPixmap(36,36)
    pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#476653"),2))
    if kind=="close":
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
    def __init__(self,window,menus=None):
        super().__init__(window)
        self.host=window
        self.setObjectName("titleStrip")
        self.setFixedHeight(32)
        row=QHBoxLayout(self);row.setContentsMargins(8,0,0,0);row.setSpacing(0)
        if menus is not None:
            logo=QLabel();logo.setPixmap(QIcon(str(ROOT/"assets/handouts.ico")).pixmap(20,20))
            row.addWidget(logo);row.addSpacing(5)
            bar=QMenuBar()
            for title,commands in menus.items():
                menu=bar.addMenu(title);menu.setStyleSheet(MENU_STYLE)
                for text,fn in commands:
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

    def button(self,key,label,fn):
        button=QToolButton()
        button.setIcon(line_icon(key));button.setIconSize(QSize(18,18))
        button.setToolTip(label);button.setFixedSize(42,32)
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
        if obj is self.host and event.type()==QEvent.Type.WindowStateChange and hasattr(self,"max_button"):
            self.max_button.setIcon(line_icon("restore" if self.host.isMaximized() else "max"))
        return super().eventFilter(obj,event)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.host.windowHandle():
            self.host.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self,event):
        if hasattr(self,"max_button"):self.toggle()

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
        self.setWindowTitle(title)
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(1,1,1,1);self.outer.setSpacing(0)
        self.outer.addWidget(TitleBar(self))
        self.body=QVBoxLayout();self.body.setContentsMargins(14,10,14,12);self.body.setSpacing(8)
        self.outer.addLayout(self.body)
    def showEvent(self,event):
        super().showEvent(event);center(self,self.parentWidget())

def message(parent,title,text,question=False):
    dialog=Dialog(parent,title)
    label=QLabel(text);label.setWordWrap(True);label.setMinimumWidth(320)
    dialog.body.addWidget(label)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Yes|QDialogButtonBox.StandardButton.No if question else QDialogButtonBox.StandardButton.Ok)
    for role,label in [(QDialogButtonBox.StandardButton.Yes,"继续"),(QDialogButtonBox.StandardButton.No,"取消"),(QDialogButtonBox.StandardButton.Ok,"确定")]:
        if buttons.button(role):buttons.button(role).setText(label)
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
    if question:buttons.button(QDialogButtonBox.StandardButton.Yes).clicked.connect(dialog.accept)
    dialog.body.addWidget(buttons)
    return dialog.exec()==QDialog.DialogCode.Accepted

def prompt(parent,title,label,value=""):
    dialog=Dialog(parent,title);dialog.body.addWidget(QLabel(label))
    field=QLineEdit(str(value));dialog.body.addWidget(field)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);dialog.body.addWidget(buttons)
    return field.text() if dialog.exec()==QDialog.DialogCode.Accepted else None

class ColorButton(QPushButton):
    def __init__(self,color,parent=None,allow_empty=False):
        super().__init__(parent)
        self.value=color;self.allow_empty=allow_empty
        self.setFixedSize(28,28)
        self.setToolTip("选择颜色")
        self.clicked.connect(self.pick)
        self.refresh()
    def refresh(self):
        self.setStyleSheet(f"QPushButton {{background:{self.value or '#f1f3f2'};border:1px solid #87998d;border-radius:5px;padding:0;min-height:0;}} QPushButton:hover {{border:2px solid #354f3e;}}")
        self.setText("" if self.value else "∅")
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
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        def accept():
            from_hex()
            if QColor(field.text()).isValid():dialog.accept()
        buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
        dialog.body.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.value=picker.currentColor().name()
            self.refresh()
            self.changed(self.value)
    def changed(self,value):pass
