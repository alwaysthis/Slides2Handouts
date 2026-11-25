"""Keep one editor per Windows session and forward subsequent launches."""
import ctypes
from ctypes import wintypes
from time import monotonic, sleep

from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance:
    name="Slides2Handouts.Editor"

    def __init__(self):
        self.kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        self.kernel.CreateMutexW.argtypes=(ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR)
        self.kernel.CreateMutexW.restype=wintypes.HANDLE
        self.kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
        self.handle=self.kernel.CreateMutexW(None,False,"Local\\"+self.name)
        error=ctypes.get_last_error()
        if not self.handle:
            raise ctypes.WinError(error)
        self.primary=error!=183

    def listen(self,activate):
        self.server=QLocalServer()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        def receive():
            while self.server.hasPendingConnections():
                connection=self.server.nextPendingConnection()
                activate()
                connection.disconnectFromServer()
                connection.deleteLater()
        self.server.newConnection.connect(receive)
        if not self.server.listen(self.name):
            raise RuntimeError(self.server.errorString())

    def notify(self):
        socket=QLocalSocket()
        deadline=monotonic()+5
        while monotonic()<deadline:
            socket.connectToServer(self.name)
            if socket.waitForConnected(150):
                socket.disconnectFromServer()
                return
            socket.abort()
            sleep(.08)

    def close(self):
        if hasattr(self,"server"):
            self.server.close()
        self.kernel.CloseHandle(self.handle)
