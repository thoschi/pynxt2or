from __future__ import annotations

import sys
import threading
import webbrowser
from urllib.parse import urlencode

from PySide6.QtCore import QObject, QSettings, Signal, Slot, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .connector import Connector, State
from .discovery import AutoRobot
from .server import OpenRobertaServer
from .sim import SimNXT

PUBLIC_OR = "https://lab.open-roberta.org"
DEFAULT_LOCAL_OR = "https://cora.corvi.schule"


class Bridge(QObject):
    changed = Signal(object, str)


class Window(QMainWindow):
    def __init__(self, address=DEFAULT_LOCAL_OR, fake_nxt=False):
        super().__init__()
        self.fake_nxt = fake_nxt
        self.connected = False
        self.connector_state = State.DISCOVER
        self.browser_opened_for_token = ""
        self.settings = QSettings("pynxt2ors", "pynxt2ors")

        saved_local = self.settings.value("local_server", address or DEFAULT_LOCAL_OR, type=str)

        self.setWindowTitle("pynxt2ors – Open Roberta Connector")
        self.setMinimumWidth(570)
        self.setFixedHeight(500 if fake_nxt else 445)

        self.bridge = Bridge()
        self.bridge.changed.connect(self.state_changed)

        factory = SimNXT if fake_nxt else AutoRobot
        self.connector = Connector(
            lambda s, m: self.bridge.changed.emit(s, m),
            address=saved_local,
            robot_factory=factory,
            server=OpenRobertaServer(saved_local),
        )

        box = QVBoxLayout()
        box.setContentsMargins(28, 24, 28, 24)
        box.setSpacing(12)

        title = QLabel("Open Roberta Connector")
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        box.addWidget(title)

        if fake_nxt:
            mode = QLabel("SIMULATION – echter Open-Roberta-Server, kein echter NXT")
            mf = QFont()
            mf.setBold(True)
            mode.setFont(mf)
            mode.setAlignment(Qt.AlignCenter)
            mode.setWordWrap(True)
            box.addWidget(mode)

        self.status = QLabel("Starte …")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        box.addWidget(self.status)

        self.token = QLabel("")
        tf = QFont("Monospace")
        tf.setPointSize(20)
        tf.setBold(True)
        self.token.setFont(tf)
        self.token.setAlignment(Qt.AlignCenter)
        box.addWidget(self.token)

        server_label = QLabel("Open-Roberta-Server")
        sf = QFont()
        sf.setBold(True)
        server_label.setFont(sf)
        box.addWidget(server_label)

        server_row = QHBoxLayout()
        self.local_radio = QRadioButton("Eigener Server")
        self.online_radio = QRadioButton("Online Open Roberta")
        self.server_group = QButtonGroup(self)
        self.server_group.addButton(self.local_radio)
        self.server_group.addButton(self.online_radio)
        self.local_radio.setChecked(True)
        server_row.addWidget(self.local_radio)
        server_row.addWidget(self.online_radio)
        server_row.addStretch(1)
        box.addLayout(server_row)

        self.local_address = QLineEdit(saved_local)
        self.local_address.setPlaceholderText(DEFAULT_LOCAL_OR)
        self.local_address.editingFinished.connect(self.save_local_address)
        box.addWidget(self.local_address)

        self.local_radio.toggled.connect(self.server_selection_changed)
        self.online_radio.toggled.connect(self.server_selection_changed)

        self.open_button = QPushButton("Open Roberta öffnen")
        self.open_button.clicked.connect(self.open_roberta_manual)
        self.open_button.setEnabled(False)
        box.addWidget(self.open_button)

        self.button = QPushButton("Verbinden")
        self.button.setEnabled(False)
        self.button.clicked.connect(self.toggle)
        box.addWidget(self.button)

        self.quit_button = QPushButton("Beenden")
        self.quit_button.clicked.connect(self.quit_application)
        box.addWidget(self.quit_button)

        root = QWidget()
        root.setLayout(box)
        self.setCentralWidget(root)
        self.server_selection_changed()
        threading.Thread(target=self.connector.run, daemon=True).start()

    def selected_server(self) -> str:
        if self.online_radio.isChecked():
            return PUBLIC_OR
        value = self.local_address.text().strip() or DEFAULT_LOCAL_OR
        if "://" not in value:
            value = "https://" + value
        return value.rstrip("/")

    def robot_system(self) -> str:
        kind = (self.connector.robot_kind or "NXT").upper()
        # Current pynxt2ors EV3 transport implements the Open-Roberta/leJOS v1 path.
        return "ev3lejosv1" if kind == "EV3" else "nxt"

    def roberta_url(self, include_token=False) -> str:
        params = {"loadSystem": self.robot_system()}
        if include_token and self.connector.token and self.local_radio.isChecked():
            params["connectorToken"] = self.connector.token
        return self.selected_server() + "/?" + urlencode(params)

    def save_local_address(self):
        value = self.local_address.text().strip() or DEFAULT_LOCAL_OR
        self.local_address.setText(value)
        self.settings.setValue("local_server", value)
        if self.local_radio.isChecked() and self.connector_state in (State.DISCOVER, State.READY):
            try:
                self.connector.server.set_address(self.selected_server())
            except ValueError as exc:
                QMessageBox.warning(self, "pynxt2ors", str(exc))

    @Slot()
    def server_selection_changed(self):
        self.local_address.setEnabled(self.local_radio.isChecked() and not self.connected)
        if self.connector_state in (State.DISCOVER, State.READY):
            try:
                self.connector.server.set_address(self.selected_server())
            except ValueError:
                pass

    def open_roberta_manual(self):
        try:
            webbrowser.open(self.roberta_url(include_token=False), new=2)
        except Exception as exc:
            QMessageBox.warning(self, "pynxt2ors", f"Open Roberta konnte nicht geöffnet werden:\n{exc}")

    @Slot(object, str)
    def state_changed(self, state, msg):
        self.connector_state = state
        self.status.setText(msg or state.value)
        self.quit_button.setEnabled(state not in (State.CONNECTED, State.RUNNING, State.WAIT_SERVER))
        self.open_button.setEnabled(bool(self.connector.robot_kind))

        locked = state in (State.WAIT_SERVER, State.CONNECTED, State.RUNNING)
        self.local_radio.setEnabled(not locked)
        self.online_radio.setEnabled(not locked)
        self.local_address.setEnabled(not locked and self.local_radio.isChecked())

        if state == State.READY:
            self.token.clear()
            self.connected = False
            self.browser_opened_for_token = ""
            self.button.setText("Verbinden")
            self.button.setEnabled(True)
        elif state == State.WAIT_SERVER:
            self.token.setText(self.connector.token)
            QApplication.clipboard().setText(self.connector.token)
            self.button.setEnabled(False)
            # The patched self-hosted Lab consumes connectorToken itself.
            if self.local_radio.isChecked() and self.browser_opened_for_token != self.connector.token:
                self.browser_opened_for_token = self.connector.token
                webbrowser.open(self.roberta_url(include_token=True), new=2)
        elif state in (State.CONNECTED, State.RUNNING):
            self.connected = True
            self.button.setText("Trennen")
            self.button.setEnabled(True)
        elif state == State.DISCOVER:
            self.token.clear()
            self.connected = False
            self.button.setText("Verbinden")
            self.button.setEnabled(False)
        elif state == State.TOKEN_TIMEOUT:
            self.button.setEnabled(False)
        elif state == State.ERROR:
            self.connected = False
            self.button.setText("Erneut versuchen")
            self.button.setEnabled(True)
            self.quit_button.setEnabled(True)
            QMessageBox.warning(self, "pynxt2ors", msg)

    def toggle(self):
        if self.connected:
            self.connector.request_disconnect()
            return
        try:
            self.save_local_address()
            self.connector.server.set_address(self.selected_server())
        except ValueError as exc:
            QMessageBox.warning(self, "pynxt2ors", str(exc))
            return
        self.connector.request_connect()

    def quit_application(self):
        if self.connector_state in (State.WAIT_SERVER, State.CONNECTED, State.RUNNING):
            return
        self.connector.stop()
        QApplication.quit()

    def closeEvent(self, event):
        self.connector.stop()
        event.accept()


def main(address=DEFAULT_LOCAL_OR, fake_nxt=False):
    app = QApplication.instance() or QApplication(sys.argv)
    w = Window(address, fake_nxt=fake_nxt)
    w.show()
    return app.exec()
