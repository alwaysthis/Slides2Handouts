from pathlib import Path
import sys
import logging
import faulthandler
import traceback

if __name__=="__main__":
    root=Path(__file__).resolve().parent
    stream=(root/"runtime.log").open("a",encoding="utf8")
    faulthandler.enable(file=stream)
    logging.basicConfig(stream=stream,level=logging.INFO,format="%(asctime)s %(message)s")
    logging.info("Starting Slides2Handouts Qt")
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Slides2Handouts.Editor")
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QLibraryInfo,QTranslator
        from src.gui.theme import stylesheet
        from src.gui.editor import Editor
        from src.gui.widgets import message
        app=QApplication(sys.argv)
        translation=QTranslator()
        translation.load("qtbase_zh_CN",QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
        app.installTranslator(translation)
        app.setStyle("Fusion");app.setStyleSheet(stylesheet())
        editor=Editor()
        def exception_hook(kind,error,tb):
            logging.error("UI callback",exc_info=(kind,error,tb))
            editor.status.setText(str(error))
            message(editor,"操作失败",str(error))
        sys.excepthook=exception_hook
        editor.show()
        code=app.exec()
        logging.info("Normal exit")
        sys.exit(code)
    except Exception:
        details=traceback.format_exc()
        (root/"startup.log").write_text(details,encoding="utf8")
        ctypes.windll.user32.MessageBoxW(None,details,"Slides2Handouts",16)
        raise
