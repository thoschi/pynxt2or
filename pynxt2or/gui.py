from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Signal, Slot, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .connector import Connector, State
from .lcp import NXTUSB
from .server import OpenRobertaServer
from .sim import SimNXT


OPEN_ROBERTA_URL = "https://lab.open-roberta.org/"


class Bridge(QObject):
    changed = Signal(object, str)


class Window(QMainWindow):
    def __init__(
        self,
        address="https://lab.open-roberta.org:443",
        fake_nxt=False,
    ):
        super().__init__()

        self.fake_nxt = fake_nxt
        self.setWindowTitle("pynxt2or – Open Roberta NXT")
        self.setFixedSize(520, 450 if fake_nxt else 390)

        self.bridge = Bridge()
        self.bridge.changed.connect(self.state_changed)

        self.connector_state = State.DISCOVER

        nxt_factory = SimNXT if fake_nxt else NXTUSB

        self.connector = Connector(
            lambda s, m: self.bridge.changed.emit(s, m),
            address=address,
            nxt_factory=nxt_factory,
            server=OpenRobertaServer(address),
        )

        box = QVBoxLayout()
        box.setContentsMargins(28, 24, 28, 24)
        box.setSpacing(14)

        # Titel

        title = QLabel("Open Roberta NXT")

        font = QFont()
        font.setPointSize(20)
        font.setBold(True)

        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)

        box.addWidget(title)

        # Simulationshinweis

        if fake_nxt:
            mode = QLabel(
                "SIMULATION – echter Open-Roberta-Server, "
                "kein echter NXT"
            )

            font = QFont()
            font.setBold(True)

            mode.setFont(font)
            mode.setAlignment(Qt.AlignCenter)
            mode.setWordWrap(True)

            box.addWidget(mode)

            details = QLabel(
                "Simulierter NXT: PYNXT2OR-SIM · Firmware 1.31\n"
                "Heruntergeladene Programme: "
                "~/pynxt2or-fake-downloads/"
            )

            details.setAlignment(Qt.AlignCenter)
            details.setWordWrap(True)

            box.addWidget(details)

        # Status

        self.status = QLabel("Starte …")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)

        box.addWidget(self.status)

        # Token

        self.token = QLabel("")

        token_font = QFont("Monospace")
        token_font.setPointSize(20)
        token_font.setBold(True)

        self.token.setFont(token_font)
        self.token.setAlignment(Qt.AlignCenter)
        self.token.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        box.addWidget(self.token)

        # Clipboard-Status

        self.clipboard_info = QLabel("")
        self.clipboard_info.setAlignment(Qt.AlignCenter)
        self.clipboard_info.setWordWrap(True)

        box.addWidget(self.clipboard_info)

        # Hauptbutton

        self.button = QPushButton("Verbinden")
        self.button.setEnabled(False)
        self.button.clicked.connect(self.toggle)

        box.addWidget(self.button)

        # Open-Roberta-Button

        self.open_roberta_button = QPushButton(
            "Open Roberta Lab öffnen"
        )

        self.open_roberta_button.setEnabled(False)
        self.open_roberta_button.clicked.connect(
            self.open_roberta
        )

        box.addWidget(self.open_roberta_button)

        root = QWidget()
        root.setLayout(box)

        self.setCentralWidget(root)

        # Connector starten

        threading.Thread(
            target=self.connector.run,
            daemon=True,
        ).start()

    def copy_token(self):
        token = self.connector.token

        if not token:
            return

        QApplication.clipboard().setText(token)

        self.clipboard_info.setText(
            "Token wurde in die Zwischenablage kopiert."
        )

    @Slot()
    def open_roberta(self):
        ok = QDesktopServices.openUrl(
            QUrl(OPEN_ROBERTA_URL)
        )

        if not ok:
            QMessageBox.warning(
                self,
                "pynxt2or",
                "Open Roberta Lab konnte nicht "
                "im Browser geöffnet werden.",
            )

    @Slot(object, str)
    def state_changed(self, state, msg):
        self.connector_state = state
        self.status.setText(msg or state.value)

        if state == State.DISCOVER:
            self.token.clear()
            self.clipboard_info.clear()

            self.button.setText("Verbinden")
            self.button.setEnabled(False)

            self.open_roberta_button.setEnabled(False)

        elif state == State.READY:
            self.token.clear()
            self.clipboard_info.clear()

            self.button.setText("Verbinden")
            self.button.setEnabled(True)

            self.open_roberta_button.setEnabled(False)

        elif state == State.WAIT_SERVER:
            self.token.setText(self.connector.token)

            # Token automatisch in die Zwischenablage.
            self.copy_token()

            # Während Open Roberta auf den Token wartet,
            # kann der Vorgang abgebrochen werden.
            self.button.setText("Abbrechen")
            self.button.setEnabled(True)

            self.open_roberta_button.setEnabled(True)

        elif state == State.CONNECTED:
            self.button.setText("Trennen")
            self.button.setEnabled(True)

            self.open_roberta_button.setEnabled(True)

        elif state == State.RUNNING:
            self.button.setText("Trennen")
            self.button.setEnabled(True)

            self.open_roberta_button.setEnabled(True)

        elif state == State.TOKEN_TIMEOUT:
            self.button.setText("Verbinden")
            self.button.setEnabled(False)

            self.open_roberta_button.setEnabled(False)

        elif state == State.ERROR:
            self.button.setText("Verbinden")
            self.button.setEnabled(False)

            self.open_roberta_button.setEnabled(False)

            QMessageBox.warning(
                self,
                "pynxt2or",
                msg,
            )

    def toggle(self):
        if self.connector_state == State.READY:
            self.connector.request_connect()

        elif self.connector_state in (
            State.WAIT_SERVER,
            State.CONNECTED,
            State.RUNNING,
        ):
            self.connector.request_disconnect()

    def closeEvent(self, event):
        self.connector.stop()
        event.accept()


def main(
    address="https://lab.open-roberta.org:443",
    fake_nxt=False,
):
    app = QApplication.instance() or QApplication(sys.argv)

    window = Window(
        address,
        fake_nxt=fake_nxt,
    )

    window.show()

    return app.exec()
