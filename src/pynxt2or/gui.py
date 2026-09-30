from __future__ import annotations
import sys, threading
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget
from .connector import Connector, State
from .discovery import AutoRobot
from .server import OpenRobertaServer
from .sim import SimNXT

class Bridge(QObject): changed = Signal(object, str)

class Window(QMainWindow):
    def __init__(self, address="https://lab.open-roberta.org:443", fake_nxt=False):
        super().__init__(); self.fake_nxt=fake_nxt; self.connected=False; self.connector_state=State.DISCOVER
        self.setWindowTitle("pynxt2or – Open Roberta Connector"); self.setFixedSize(520, 410 if fake_nxt else 350)
        self.bridge=Bridge(); self.bridge.changed.connect(self.state_changed)
        factory = SimNXT if fake_nxt else AutoRobot
        self.connector=Connector(lambda s,m:self.bridge.changed.emit(s,m), address=address, robot_factory=factory, server=OpenRobertaServer(address))
        box=QVBoxLayout(); box.setContentsMargins(28,24,28,24); box.setSpacing(14)
        title=QLabel("Open Roberta Connector"); f=QFont(); f.setPointSize(20); f.setBold(True); title.setFont(f); title.setAlignment(Qt.AlignCenter); box.addWidget(title)
        if fake_nxt:
            mode=QLabel("SIMULATION – echter Open-Roberta-Server, kein echter NXT"); mf=QFont(); mf.setBold(True); mode.setFont(mf); mode.setAlignment(Qt.AlignCenter); mode.setWordWrap(True); box.addWidget(mode)
        self.status=QLabel("Starte …"); self.status.setAlignment(Qt.AlignCenter); self.status.setWordWrap(True); box.addWidget(self.status)
        self.token=QLabel(""); tf=QFont("Monospace"); tf.setPointSize(20); tf.setBold(True); self.token.setFont(tf); self.token.setAlignment(Qt.AlignCenter); box.addWidget(self.token)
        self.button=QPushButton("Verbinden"); self.button.setEnabled(False); self.button.clicked.connect(self.toggle); box.addWidget(self.button)
        self.quit_button=QPushButton("Beenden"); self.quit_button.clicked.connect(self.quit_application); box.addWidget(self.quit_button)
        root=QWidget(); root.setLayout(box); self.setCentralWidget(root)
        threading.Thread(target=self.connector.run,daemon=True).start()

    @Slot(object,str)
    def state_changed(self,state,msg):
        self.connector_state=state; self.status.setText(msg or state.value)
        self.quit_button.setEnabled(state not in (State.CONNECTED,State.RUNNING))
        if state==State.READY:
            self.token.clear(); self.connected=False; self.button.setText("Verbinden"); self.button.setEnabled(True)
        elif state==State.WAIT_SERVER:
            self.token.setText(self.connector.token); QApplication.clipboard().setText(self.connector.token); self.button.setEnabled(False)
        elif state in (State.CONNECTED,State.RUNNING):
            self.connected=True; self.button.setText("Trennen"); self.button.setEnabled(True)
        elif state==State.DISCOVER:
            self.token.clear(); self.connected=False; self.button.setText("Verbinden"); self.button.setEnabled(False)
        elif state==State.TOKEN_TIMEOUT: self.button.setEnabled(False)
        elif state==State.ERROR:
            self.button.setEnabled(False); QMessageBox.warning(self,"pynxt2or",msg)

    def toggle(self): self.connector.request_disconnect() if self.connected else self.connector.request_connect()
    def quit_application(self):
        if self.connector_state in (State.CONNECTED,State.RUNNING): return
        self.connector.stop(); QApplication.quit()
    def closeEvent(self,event): self.connector.stop(); event.accept()

def main(address="https://lab.open-roberta.org:443",fake_nxt=False):
    app=QApplication.instance() or QApplication(sys.argv); w=Window(address,fake_nxt=fake_nxt); w.show(); return app.exec()
