from __future__ import annotations

import sys
import threading
import webbrowser
from urllib.parse import urlencode

from PySide6.QtCore import QObject, QSettings, Signal, Slot, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from .connector import Connector, State
from .discovery import AutoRobot
from .server import OpenRobertaServer

PUBLIC_OR = "https://lab.open-roberta.org"
DEFAULT_LOCAL_OR = "https://cora.corvi.schule"


class Bridge(QObject):
    changed = Signal(object, str)


class Window(QMainWindow):
    def __init__(self, address=DEFAULT_LOCAL_OR, robot_factory=AutoRobot,
                 system_override="", connector_enabled=True):
        super().__init__()
        self.settings = QSettings("pynxt2ors", "pynxt2ors")
        self.local_server = self.settings.value(
            "local_server", address or DEFAULT_LOCAL_OR, type=str
        )
        self.robot_factory = robot_factory
        self.system_override = system_override
        self.connector_enabled = connector_enabled
        self.connector = None
        self.thread = None
        self.connector_state = State.DISCOVER
        self.pending_open = False
        self.last_error = ""

        self.setWindowTitle("pynxt2ors – Open Roberta Connector")
        self.setFixedSize(590, 335)
        self.bridge = Bridge()
        self.bridge.changed.connect(self.state_changed)

        box = QVBoxLayout()
        box.setContentsMargins(28, 24, 28, 24)
        box.setSpacing(13)

        title = QLabel("Open Roberta Connector")
        f = QFont(); f.setPointSize(20); f.setBold(True)
        title.setFont(f); title.setAlignment(Qt.AlignCenter)
        box.addWidget(title)

        self.status = QLabel("Suche Roboter …" if connector_enabled else "Bereit")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        box.addWidget(self.status)

        self.token_label = QLabel("")
        self.token_label.setAlignment(Qt.AlignCenter)
        self.token_label.setTextFormat(Qt.RichText)
        self.token_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.token_label.setOpenExternalLinks(False)
        self.token_label.linkActivated.connect(self.copy_token)
        self.token_label.hide()
        box.addWidget(self.token_label)

        sl = QLabel("Open-Roberta-Server")
        sf = QFont(); sf.setBold(True); sl.setFont(sf)
        box.addWidget(sl)

        row = QHBoxLayout()
        self.local_radio = QRadioButton("Eigener Server")
        self.online_radio = QRadioButton("Offizielles Open Roberta")
        group = QButtonGroup(self)
        group.addButton(self.local_radio); group.addButton(self.online_radio)
        self.local_radio.setChecked(True)
        row.addWidget(self.local_radio); row.addWidget(self.online_radio); row.addStretch(1)
        box.addLayout(row)

        self.address = QLineEdit(self.local_server)
        self.address.editingFinished.connect(self.save_local_address)
        box.addWidget(self.address)
        self.local_radio.toggled.connect(self.server_selection_changed)
        self.online_radio.toggled.connect(self.server_selection_changed)

        button_row = QHBoxLayout()

        self.open_button = QPushButton("Open Roberta Lab öffnen")
        self.open_button.setMinimumHeight(42)
        self.open_button.clicked.connect(self.open_roberta)
        self.open_button.setEnabled(not self.connector_enabled)
        button_row.addWidget(self.open_button, 1)

        self.quit_button = QPushButton("Beenden")
        self.quit_button.setMinimumHeight(42)
        self.quit_button.clicked.connect(self.close)
        button_row.addWidget(self.quit_button)

        box.addLayout(button_row)

        root = QWidget(); root.setLayout(box); self.setCentralWidget(root)
        self.server_selection_changed()

        if self.connector_enabled:
            self.start_connector()
        else:
            self.status.setText(f"Modus: {self.system_override}")

    def selected_server(self):
        if self.online_radio.isChecked():
            return PUBLIC_OR
        value = self.address.text().strip() or DEFAULT_LOCAL_OR
        if "://" not in value:
            value = "https://" + value
        return value.rstrip("/")

    def save_local_address(self):
        if not self.local_radio.isChecked():
            return
        value = self.address.text().strip() or DEFAULT_LOCAL_OR
        self.local_server = value
        self.address.setText(value)
        self.settings.setValue("local_server", value)

    @Slot()
    def server_selection_changed(self):
        if self.online_radio.isChecked():
            if self.address.isEnabled():
                self.save_local_address()
            self.address.setText(PUBLIC_OR)
            self.address.setEnabled(False)
        else:
            self.address.setText(self.local_server)
            self.address.setEnabled(True)

        # A connector already waiting on one server cannot simply move its
        # long-poll session to another server. Restart it cleanly.
        if self.connector_enabled and self.connector is not None:
            self.restart_connector()

    @Slot(str)
    def copy_token(self, _link=""):
        if not self.connector or not self.connector.token:
            return
        QApplication.clipboard().setText(self.connector.token)
        self.status.setText("Token in die Zwischenablage kopiert")

    def update_token_label(self):
        token = self.connector.token if self.connector else ""
        if token:
            self.token_label.setText(
                f'<a href="copy"><b>Token: {token}</b></a>'
                ' &nbsp; <span style="color:#777;">(anklicken zum Kopieren)</span>'
            )
            self.token_label.show()
        else:
            self.token_label.clear()
            self.token_label.hide()

    def robot_system(self):
        if self.system_override:
            return self.system_override
        if self.connector and self.connector.robot_system:
            return self.connector.robot_system
        return ""

    def roberta_url(self, include_token=False):
        system = self.robot_system()
        if not system:
            raise RuntimeError("Noch kein Roboter erkannt")
        params = {"loadSystem": system}
        if (include_token and self.local_radio.isChecked() and self.connector
                and self.connector.token):
            params["connectorToken"] = self.connector.token
        return self.selected_server() + "/?" + urlencode(params)

    def start_connector(self):
        self.connector = Connector(
            lambda s, m: self.bridge.changed.emit(s, m),
            address=self.selected_server(),
            robot_factory=self.robot_factory,
            server=OpenRobertaServer(self.selected_server()),
            auto_connect=True,
        )
        self.thread = threading.Thread(target=self.connector.run, daemon=True)
        self.thread.start()

    def stop_connector(self):
        if self.connector:
            self.connector.stop()
        self.connector = None
        self.thread = None

    def restart_connector(self):
        self.stop_connector()
        self.connector_state = State.DISCOVER
        self.status.setText("Suche Roboter …")
        self.pending_open = False
        self.open_button.setEnabled(False)
        self.token_label.clear()
        self.token_label.hide()
        self.start_connector()

    def _open_browser(self):
        include_token = self.local_radio.isChecked() and self.connector_enabled
        webbrowser.open(self.roberta_url(include_token), new=2)
        self.pending_open = False

    @Slot()
    def open_roberta(self):
        self.save_local_address()
        try:
            if not self.connector_enabled:
                self._open_browser()
                return

            if not self.robot_system():
                QMessageBox.information(self, "pynxt2ors", "Noch kein Roboter erkannt.")
                return

            # Private patched Lab needs the current connector token. If the
            # previous registration timed out/failed, trigger one fresh attempt
            # and open as soon as WAIT_SERVER supplies the new token.
            if self.local_radio.isChecked() and not self.connector.token:
                self.pending_open = True
                self.connector.server.set_address(self.selected_server())
                self.connector.request_connect()
                self.status.setText("Stelle Verbindung zu Open Roberta her …")
                return

            self._open_browser()
        except Exception as exc:
            QMessageBox.warning(self, "pynxt2ors", f"Open Roberta konnte nicht geöffnet werden:\n{exc}")

    @Slot(object, str)
    def state_changed(self, state, msg):
        self.connector_state = state
        self.status.setText(msg or state.value)
        self.update_token_label()

        # The button is also the readiness indicator: it is usable only when
        # exactly one robot has been identified and therefore loadSystem is
        # known. CLI system overrides are handled without the connector.
        ready_states = (State.READY, State.WAIT_SERVER, State.CONNECTED, State.RUNNING)
        self.open_button.setEnabled(bool(self.robot_system()) and state in ready_states)

        if state == State.WAIT_SERVER:
            # The public Lab still needs manual token entry. Keeping the token
            # in the clipboard makes that a paste operation; the private Lab
            # receives it automatically in the URL.
            if self.connector and self.connector.token:
                QApplication.clipboard().setText(self.connector.token)
            if self.pending_open:
                try:
                    self._open_browser()
                except Exception as exc:
                    self.pending_open = False
                    QMessageBox.warning(self, "pynxt2ors", str(exc))
        elif state == State.ERROR:
            # ERROR is reserved for actual robot/protocol failures. A temporary
            # HTTP/proxy problem is handled by Connector without discarding the
            # detected robot.
            self.open_button.setEnabled(bool(self.robot_system()))
            if msg != self.last_error:
                self.last_error = msg
                QMessageBox.warning(self, "pynxt2ors", msg)
        elif state == State.MULTIPLE:
            # This condition is shown in the status line and is re-checked
            # automatically, so unplugging the extra robot recovers by itself.
            self.open_button.setEnabled(False)
        elif state in (State.DISCOVER, State.TOKEN_TIMEOUT):
            self.open_button.setEnabled(False)
        elif state in (State.READY, State.CONNECTED, State.RUNNING):
            self.last_error = ""

    def closeEvent(self, event):
        self.stop_connector()
        event.accept()


def main(address=DEFAULT_LOCAL_OR, robot_factory=AutoRobot,
         system_override="", connector_enabled=True):
    app = QApplication.instance() or QApplication(sys.argv)
    w = Window(address, robot_factory=robot_factory,
               system_override=system_override,
               connector_enabled=connector_enabled)
    w.show()
    return app.exec()
