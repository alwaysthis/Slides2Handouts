"""Control and popup rules adapted from the local CrystalX theme. Qt draws rounded surfaces directly."""
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QMenu, QWidget
CONTROLS = """
QPushButton,QToolButton {background:#fff;color:#252525;border:1px solid #e0e0e0;border-radius:4px;padding:4px 8px;}
QToolButton {padding:2px;}
QPushButton:hover,QToolButton:hover {background:#f3f3f3;border-color:#b8b8b8;}
QPushButton:pressed,QToolButton:pressed,QToolButton:checked {background:#e3e8e6;border-color:#8fa69b;}
QPushButton:disabled,QToolButton:disabled {color:#aaa;border-color:#eee;}
QAbstractSpinBox,QComboBox {background:#fff;color:#252525;border:1px solid #ddd;border-radius:4px;padding:3px 8px;min-height:22px;}
QAbstractSpinBox:hover,QComboBox:hover,QAbstractSpinBox:focus,QComboBox:focus {border-color:#91aa9c;background:#fcfcfc;}
QComboBox::drop-down {border:0;width:22px;}
QScrollBar:vertical {background:transparent;width:10px;margin:0;}
QScrollBar::handle:vertical {background:#cbd0cd;min-height:28px;border-radius:4px;margin:1px;}
QScrollBar::handle:vertical:hover {background:#aab5af;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
QScrollArea {border:0;}
"""

BASE_STYLE = """
QWidget { background:#fdfefd; color:#29352f; font-family:'Segoe UI','Microsoft YaHei'; font-size:13px; }
QMainWindow,QMenuBar,QToolBar { background:#fafcfb; }
QToolBar { border-bottom:1px solid #dce3dd; spacing:12px; padding:12px; }
QPushButton { border:1px solid #dce3dd; border-radius:5px; padding:9px 14px; background:#fff; }
QPushButton:disabled { color:#a4ada7; background:#f1f4f0; }
QPushButton:hover { background:#e3eee7; border-color:#94b49f; }
QPushButton:checked { background:#dbece1; color:#286345; }
QTreeWidget,QTableWidget { border:0; background:transparent; alternate-background-color:#f7faf8; }
QTreeWidget::item { padding:9px; }
QTreeWidget::item:selected { background:#deece2; color:#286345; }
QGroupBox { border:0; margin-top:18px; padding-top:22px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; top:4px; font-weight:bold; }
QDoubleSpinBox,QComboBox { background:white; border:1px solid #dce3dd; border-radius:4px; padding:6px; }
QHeaderView::section { background:transparent; padding:6px; border:0; }
QStatusBar { border:0; color:#4f6258; background:#e0e6e2; }
QStatusBar QWidget {background:#e0e6e2;}
QSplitter::handle { background:#e0e6e0; width:1px; height:1px; }
"""

MENU_STYLE = """
QMenuBar {border:0;background:transparent;}
QMenuBar::item {padding:5px 12px;border-radius:5px;background:transparent;}
QMenuBar::item:selected,QMenuBar::item:pressed {background:#e0e8e3;}
QMenu,QWidget#comboPopup {
    background:#ffffff;color:#29352f;border:1px solid #d5ddd8;border-radius:8px;padding:4px;
}
QComboBox {combobox-popup:0;}
QWidget#comboPopup QAbstractItemView {
    background:transparent;border:0;outline:none;
    selection-background-color:transparent;selection-color:#29352f;
}
QWidget#comboPopup QAbstractItemView::item {padding:4px 8px;border-radius:5px;}
QWidget#comboPopup QAbstractItemView::item:hover,QWidget#comboPopup QAbstractItemView::item:selected {
    background:#e8eeeb;color:#29352f;border-radius:5px;
}
QMenu::item {background:transparent;color:#29352f;padding:3px 16px 3px 8px;min-width:90px;}
QMenu::item:selected {background:#e8eeeb;color:#29352f;border-radius:5px;}
QMenu::item:disabled {color:#9aa39e;}
QMenu::separator {height:1px;background:#dfe5e1;margin:4px 6px;}
"""
ASSETS=Path(__file__).resolve().parents[2]/"assets"
def stylesheet():
    return BASE_STYLE+CONTROLS+MENU_STYLE+"""
QMainWindow#handoutWindow {background:transparent;}
QWidget#central,QWidget#titleStrip {background:transparent;}
QFrame#panel {background:#fdfefd;border:1px solid #bdcbc2;border-radius:9px;}
QLabel {background:transparent;}
QLineEdit {background:#fff;border:1px solid #dce3dd;border-radius:5px;padding:3px 6px;min-height:20px;}
QAbstractSpinBox,QComboBox {padding:2px 7px;min-height:22px;border-radius:5px;}
QAbstractSpinBox QLineEdit {border:0;background:transparent;padding:0;min-height:0;}
QPushButton {padding:4px 8px;border-radius:5px;min-height:20px;}
QPushButton#colorSwatch {padding:0;min-height:26px;max-height:26px;min-width:26px;max-width:26px;
    border:0;background:transparent;}
QToolButton {padding:2px;border-radius:5px;}
QCheckBox {background:transparent;spacing:5px;}
QScrollArea,QTreeWidget,QListWidget {border:0;background:transparent;}
QTreeWidget::item {padding:2px;min-height:22px;}
QListWidget::item {padding:4px;}
QListWidget#slideLibrary {background:#eef2ef;outline:none;
    selection-background-color:rgba(255,255,255,205);selection-color:#29352f;}
QListWidget#slideLibrary::item {margin:2px;border-radius:5px;}
QListWidget#slideLibrary::item:selected {background:rgba(255,255,255,205);color:#29352f;}
QListWidget#slideLibrary::item:hover:!selected {background:rgba(255,255,255,105);}
QListWidget#presetList {background:#eef2ef;border-radius:6px;padding:3px;outline:none;
    selection-background-color:rgba(255,255,255,205);selection-color:#29352f;}
QListWidget#presetList::item {padding:5px 7px;margin:2px;border-radius:5px;}
QListWidget#presetList::item:selected {background:rgba(255,255,255,205);color:#29352f;}
QListWidget#presetList::item:hover:!selected {background:rgba(255,255,255,105);color:#29352f;}
QTabBar#outputModes {background:transparent;}
QTabBar#outputModes::tab {background:transparent;color:#53665b;padding:4px 12px;
    border:0;border-radius:6px;margin-right:4px;}
QTabBar#outputModes::tab:selected {background:#e5ece7;color:#29352f;}
QTabBar#outputModes::tab:hover:!selected {background:#f5f7f5;}
QFrame#settingsDivider {background:#d5ddd8;border:0;}
QWidget#settingsPage,QStackedWidget#settingsStack {background:transparent;}
QFrame#settingsContent {background:#ffffff;border:1px solid #e0e7e2;border-radius:8px;}
QLabel#stylePreview {background:#f5f8f6;border:1px solid #dce5df;border-radius:6px;padding:9px;}
QSplitter {background:#f1f3f2;}
QSplitter::handle {background:#f1f3f2;width:5px;}
QFrame#leftRail {background:transparent;border:0;}
QSplitter#pageSidebarSplit::handle:vertical {height:5px;background:transparent;border:0;}
QWidget#inspector {background:#fdfefd;}
QLabel#section {color:#42654f;font-weight:600;padding-top:6px;}
QPlainTextEdit {background:white;border:1px solid #dce3dd;border-radius:5px;padding:3px;}
QWidget[inherit="true"] QPlainTextEdit,QWidget[inherit="true"] QLineEdit,
QWidget[inherit="true"] QAbstractSpinBox {color:#929c96;}
QDialog {background:#f1f3f2;}
QDialog#roundedDialog {background:transparent;}
QProgressBar {border:1px solid #dce3dd;border-radius:4px;background:white;text-align:center;}
QProgressBar::chunk {background:#8aa995;}
""" + stepper_css()

def stepper_css():
    css=""
    for direction,position in (("up","top right"),("down","bottom right")):
        selectors=",".join(f"{kind}::{direction}-button" for kind in ("QSpinBox","QDoubleSpinBox"))
        css+=selectors+"{subcontrol-origin:border;subcontrol-position:"+position+";width:20px;border:0;border-left:1px solid #ddd;background:transparent;margin:1px;}"
        css+=",".join(f"{kind}::{direction}-arrow" for kind in ("QSpinBox","QDoubleSpinBox"))+'{image:url("'+(ASSETS/f"spin-{direction}.svg").as_posix()+'");width:8px;height:5px;}'
    css+='QSpinBox::up-button,QDoubleSpinBox::up-button {border-bottom:1px solid #ddd;margin-bottom:0;}'
    css+='QComboBox {padding-right:25px;} QComboBox::drop-down {subcontrol-origin:border;subcontrol-position:top right;width:23px;border:0;background:transparent;} QComboBox::down-arrow {image:url("'+(ASSETS/"combo-arrow.svg").as_posix()+'");width:12px;height:8px;}'
    css+='QCheckBox::indicator {width:16px;height:16px;border:1px solid #87998d;border-radius:3px;background:#fff;} QCheckBox::indicator:checked {image:url("'+(ASSETS/"check.svg").as_posix()+'");background:#e0ebe4;}'
    return css


def paint_rounded_surface(painter,rect,fill,border,radius):
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(border),1))
    painter.setBrush(QColor(fill))
    painter.drawRoundedRect(QRectF(rect).adjusted(.5,.5,-.5,-.5),radius,radius)
    painter.restore()


class PopupSurfaces(QObject):
    def eventFilter(self, widget, event):
        kind=event.type()
        if kind not in (QEvent.Type.Polish,QEvent.Type.Paint,QEvent.Type.Show):
            return False
        combo=widget.inherits("QComboBoxPrivateContainer")
        if kind==QEvent.Type.Polish and (isinstance(widget,QMenu) or combo):
            if combo:
                widget.setObjectName("comboPopup")
            widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            widget.setWindowFlags(widget.windowFlags() | Qt.WindowType.FramelessWindowHint
                                  | Qt.WindowType.NoDropShadowWindowHint)
        if combo and kind==QEvent.Type.Show and widget.layout():
            widget.layout().setContentsMargins(4,4,4,4)
        if combo and kind==QEvent.Type.Paint:
            painter=QPainter(widget)
            paint_rounded_surface(painter,widget.rect(),"#ffffff","#d5ddd8",8)
            painter.end()
            return True
        return False


def install_theme(app):
    app.setStyle("Fusion")
    app.setEffectEnabled(Qt.UIEffect.UI_AnimateCombo,False)
    popup_surfaces=PopupSurfaces(app)
    app.installEventFilter(popup_surfaces)
    app.popup_surfaces=popup_surfaces
    app.setStyleSheet(stylesheet())
