"""Control and popup rules adapted from the local CrystalX theme. Qt draws rounded surfaces directly."""
from pathlib import Path
CONTROLS = """
QPushButton,QToolButton {background:#fff;color:#252525;border:1px solid #e0e0e0;border-radius:4px;padding:4px 8px;}
QToolButton {padding:2px;}
QPushButton:hover,QToolButton:hover {background:#f3f3f3;border-color:#b8b8b8;}
QPushButton:pressed,QToolButton:pressed,QToolButton:checked {background:#e3e8e6;border-color:#8fa69b;}
QPushButton:disabled,QToolButton:disabled {color:#aaa;border-color:#eee;}
QAbstractSpinBox,QComboBox {background:#fff;color:#252525;border:1px solid #ddd;border-radius:4px;padding:3px 8px;min-height:22px;}
QAbstractSpinBox:hover,QComboBox:hover,QAbstractSpinBox:focus,QComboBox:focus {border-color:#91aa9c;background:#fcfcfc;}
QComboBox::drop-down {border:0;width:22px;}
QMenu {background:white;border:1px solid #ddd;padding:4px;}
QMenu::item {padding:3px 16px 3px 8px;min-width:90px;}
QMenu::item:selected {background:#ecefed;border-radius:3px;}
QMenuBar {border:0;background:transparent;}
QMenuBar::item {padding:6px 14px;background:transparent;}
QMenuBar::item:selected {background:#ecefed;}
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
QMenu {background-color:#ffffff;color:#29352f;border:1px solid #d5ddd8;padding:4px;}
QMenu::item {background:transparent;color:#29352f;padding:3px 16px 3px 8px;min-width:90px;}
QMenu::item:selected {background:#e8eeeb;color:#29352f;border-radius:3px;}
QMenu::item:disabled {color:#9aa39e;}
QMenu::separator {height:1px;background:#dfe5e1;margin:4px 6px;}
"""
ASSETS=Path(__file__).resolve().parents[2]/"assets"
def stylesheet():
    return BASE_STYLE+CONTROLS+MENU_STYLE+"""
QMainWindow {background:#f1f3f2;}
QWidget#central,QWidget#titleStrip {background:transparent;}
QFrame#panel {background:#fdfefd;border:1px solid #bdcbc2;border-radius:9px;}
QLabel {background:transparent;}
QLineEdit {background:#fff;border:1px solid #dce3dd;border-radius:5px;padding:3px 6px;min-height:20px;}
QAbstractSpinBox,QComboBox {padding:2px 7px;min-height:22px;border-radius:5px;}
QAbstractSpinBox QLineEdit {border:0;background:transparent;padding:0;min-height:0;}
QPushButton {padding:4px 8px;border-radius:5px;min-height:20px;}
QToolButton {padding:2px;border-radius:5px;}
QCheckBox {background:transparent;spacing:5px;}
QScrollArea,QTreeWidget,QListWidget {border:0;background:transparent;}
QTreeWidget::item {padding:2px;min-height:22px;}
QListWidget::item {padding:4px;}
QSplitter {background:#f1f3f2;}
QSplitter::handle {background:#f1f3f2;width:5px;}
QWidget#inspector {background:#fdfefd;}
QLabel#section {color:#42654f;font-weight:600;padding-top:6px;}
QPlainTextEdit {background:white;border:1px solid #dce3dd;border-radius:5px;padding:3px;}
QWidget[inherit="true"] QPlainTextEdit,QWidget[inherit="true"] QLineEdit,
QWidget[inherit="true"] QAbstractSpinBox {color:#929c96;}
QDialog {background:#f1f3f2;}
QProgressBar {border:1px solid #dce3dd;border-radius:4px;background:white;text-align:center;}
QProgressBar::chunk {background:#8aa995;}
""" + stepper_css()

def stepper_css():
    css=""
    for direction,position in (("up","top right"),("down","bottom right")):
        selectors=",".join(f"{kind}::{direction}-button" for kind in ("QSpinBox","QDoubleSpinBox"))
        css+=selectors+"{subcontrol-origin:border;subcontrol-position:"+position+";width:20px;border:0;border-left:1px solid #ddd;background:transparent;margin:1px;}"
        css+=",".join(f"{kind}::{direction}-arrow" for kind in ("QSpinBox","QDoubleSpinBox"))+'{image:url("'+(ASSETS/f"spin-{direction}.svg").as_posix()+'");width:8px;height:5px;}'
    css+='QComboBox {padding-right:25px;} QComboBox::drop-down {subcontrol-origin:border;subcontrol-position:top right;width:23px;border:0;background:transparent;} QComboBox::down-arrow {image:url("'+(ASSETS/"combo-arrow.svg").as_posix()+'");width:12px;height:8px;}'
    css+='QCheckBox::indicator {width:16px;height:16px;border:1px solid #87998d;border-radius:3px;background:#fff;} QCheckBox::indicator:checked {image:url("'+(ASSETS/"check.svg").as_posix()+'");background:#e0ebe4;}'
    return css
