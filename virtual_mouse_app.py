"""PySide6 desktop control room; mouse control is off until explicitly enabled."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from mouse_controller import ControllerSettings
from tracking_worker import TrackingWorker

STYLE = """
QMainWindow, QWidget#root { background:#10191b; color:#e8eeea; font-family:'Segoe UI',sans-serif; }
QFrame#topbar, QFrame#panel { background:#172326; border:1px solid #29383a; }
QFrame#previewShell { background:#0a1112; border:1px solid #304346; }
QLabel#eyebrow { color:#7cc5ae; font-size:10px; font-weight:700; letter-spacing:2px; }
QLabel#title { color:#f0f2e8; font-size:29px; font-weight:600; }
QLabel#subtitle, QLabel#muted { color:#9aa9a5; font-size:12px; }
QLabel#status { color:#d4bb82; font-size:11px; font-weight:700; padding:7px 10px; background:#2a2a20; border:1px solid #51482f; }
QLabel#gesture { color:#dff1e8; font-family:Georgia,serif; font-size:24px; }
QLabel#preview { color:#637472; font-family:Georgia,serif; font-size:17px; }
QLabel#panelTitle { color:#edf1e9; font-size:16px; font-weight:600; }
QLabel#controlWarning { color:#e2be79; font-size:11px; }
QComboBox, QSpinBox { background:#10191b; color:#e8eeea; border:1px solid #3b4b4d; padding:8px; min-height:20px; }
QPushButton { background:#315d55; color:#f5f6ed; border:0; padding:11px 16px; font-weight:650; }
QPushButton:hover { background:#3d7468; }
QPushButton#stop { background:#493b35; }
QPushButton:disabled { background:#283537; color:#75817f; }
QCheckBox { spacing:10px; color:#edf1e9; font-weight:600; }
QCheckBox::indicator { width:18px; height:18px; }
QSlider::groove:horizontal { height:4px; background:#344448; }
QSlider::handle:horizontal { background:#75b9a4; width:14px; margin:-6px 0; border-radius:7px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, worker_factory=TrackingWorker):
        super().__init__()
        self._worker_factory = worker_factory
        self.worker = None
        self._last_error = None
        self._close_pending = False
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(50)
        self._shutdown_timer.timeout.connect(self._check_shutdown_complete)
        self.setWindowTitle("Motion Desk · AI Virtual Mouse")
        self.setMinimumSize(940, 680)
        self.resize(1120, 760)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._set_status("READY · PREVIEW ONLY")

    def _build_ui(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(28, 24, 28, 22)
        page.setSpacing(18)

        top = QFrame(objectName="topbar")
        header = QHBoxLayout(top)
        header.setContentsMargins(20, 16, 20, 16)
        identity = QVBoxLayout()
        eyebrow = QLabel("COMPUTER VISION  /  INPUT SYSTEMS", objectName="eyebrow")
        title = QLabel("Motion Desk", objectName="title")
        subtitle = QLabel("A camera-first workspace for touch-free pointer control.", objectName="subtitle")
        identity.addWidget(eyebrow); identity.addWidget(title); identity.addWidget(subtitle)
        header.addLayout(identity); header.addStretch(1)
        self.status = QLabel(objectName="status")
        header.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop)
        page.addWidget(top)

        content = QHBoxLayout()
        content.setSpacing(18)
        preview_column = QVBoxLayout()
        preview_column.setSpacing(10)
        self.preview_shell = QFrame(objectName="previewShell")
        self.preview_shell.setMinimumSize(590, 390)
        preview_layout = QVBoxLayout(self.preview_shell)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self.preview = QLabel("Camera preview is paused", objectName="preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(560, 350)
        self.preview.setWordWrap(True)
        preview_layout.addWidget(self.preview)
        preview_column.addWidget(self.preview_shell, 1)
        self.gesture = QLabel("Waiting for camera", objectName="gesture")
        self.gesture_hint = QLabel("Your hand landmarks and gesture state will appear here.", objectName="muted")
        preview_column.addWidget(self.gesture)
        preview_column.addWidget(self.gesture_hint)
        content.addLayout(preview_column, 3)

        panel = QFrame(objectName="panel")
        panel.setMinimumWidth(270)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(13)
        panel_layout.addWidget(QLabel("Session controls", objectName="panelTitle"))
        panel_layout.addWidget(QLabel("CAMERA SOURCE", objectName="eyebrow"))
        camera_row = QHBoxLayout()
        self.camera = QSpinBox()
        self.camera.setRange(0, 9)
        self.camera.setValue(0)
        self.camera.setAccessibleName("Camera device index")
        self.camera.setToolTip("Camera device index. Try 1 if the default camera does not connect.")
        camera_row.addWidget(self.camera)
        camera_row.addWidget(QLabel("device index", objectName="muted"))
        panel_layout.addLayout(camera_row)

        self.control_toggle = QCheckBox("Enable system pointer")
        self.control_toggle.setChecked(False)
        self.control_toggle.setAccessibleName("Enable system pointer control")
        self.control_toggle.setToolTip("Unchecked means preview only. Enabling this allows pointer movement and pinch clicks.")
        self.control_toggle.toggled.connect(self._update_worker_settings)
        panel_layout.addWidget(self.control_toggle)
        self.control_warning = QLabel("OFF · hand tracking only; no system input", objectName="controlWarning")
        self.control_warning.setWordWrap(True)
        panel_layout.addWidget(self.control_warning)

        self.sensitivity = self._add_slider(panel_layout, "Movement sensitivity", 50, 200, 100, "1.00×")
        self.smoothing = self._add_slider(panel_layout, "Cursor smoothing", 1, 15, 7, "7 frames")
        self.threshold = self._add_slider(panel_layout, "Pinch distance", 15, 80, 35, "35 px")
        self.sensitivity.valueChanged.connect(lambda value: self._update_slider_label(self.sensitivity, f"{value / 100:.2f}×"))
        self.smoothing.valueChanged.connect(lambda value: self._update_slider_label(self.smoothing, f"{value} frames"))
        self.threshold.valueChanged.connect(lambda value: self._update_slider_label(self.threshold, f"{value} px"))
        for slider in (self.sensitivity, self.smoothing, self.threshold):
            slider.valueChanged.connect(self._update_worker_settings)

        panel_layout.addWidget(QLabel("GESTURES", objectName="eyebrow"))
        panel_layout.addWidget(QLabel("Index up + middle down    Move", objectName="muted"))
        panel_layout.addWidget(QLabel("Index + middle pinch       Click", objectName="muted"))
        panel_layout.addStretch(1)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start preview")
        self.start_button.setAccessibleName("Start safe camera preview")
        self.stop_button = QPushButton("Stop", objectName="stop")
        self.stop_button.setAccessibleName("Stop tracking and release the camera")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_tracking)
        self.stop_button.clicked.connect(self.stop_tracking)
        buttons.addWidget(self.start_button); buttons.addWidget(self.stop_button)
        panel_layout.addLayout(buttons)
        content.addWidget(panel, 1)
        page.addLayout(content, 1)

        note = QLabel("SAFE BY DEFAULT  ·  Preview never moves or clicks your pointer. Toggle system control only when you intend to use it.", objectName="muted")
        note.setWordWrap(True)
        page.addWidget(note)

    @staticmethod
    def _add_slider(layout, title, minimum, maximum, value, suffix):
        caption = QLabel(title, objectName="muted")
        layout.addWidget(caption)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setAccessibleName(title)
        slider.setRange(minimum, maximum); slider.setValue(value)
        slider.setToolTip(f"Adjust {title.lower()}")
        slider._value_caption = QLabel(suffix, objectName="muted")
        row = QHBoxLayout(); row.addWidget(slider, 1); row.addWidget(slider._value_caption)
        layout.addLayout(row)
        return slider

    @staticmethod
    def _update_slider_label(slider, text):
        slider._value_caption.setText(text)

    def _settings(self):
        return ControllerSettings(
            margin=80,
            smoothing=float(self.smoothing.value()),
            sensitivity=self.sensitivity.value() / 100.0,
            pinch_threshold=float(self.threshold.value()),
        )

    def _update_worker_settings(self, *_):
        enabled = self.control_toggle.isChecked()
        self.control_warning.setText(
            "ON · system pointer and pinch clicks are active" if enabled
            else "OFF · hand tracking only; no system input"
        )
        if self.worker and self.worker.isRunning():
            self.worker.configure(self._settings(), enabled)

    def _set_status(self, text):
        if self._close_pending and text in {"Stopped", "READY · PREVIEW ONLY"}:
            text = "STOPPING · CONFIRMING WORKER EXIT"
        self.status.setText(text)

    def start_tracking(self):
        if self.worker and self.worker.isRunning():
            return
        self._last_error = None
        self.preview.setText("Connecting to camera…")
        self.gesture.setText("Waiting for hand")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.camera.setEnabled(False)
        self._set_status("CONNECTING")
        self.worker = self._worker_factory(self.camera.value(), self._settings())
        self.worker.frame_ready.connect(self._show_frame)
        self.worker.status_changed.connect(self._set_status)
        self.worker.gesture_changed.connect(self.gesture.setText)
        self.worker.error_occurred.connect(self._show_error)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def stop_tracking(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.stop_button.setEnabled(False)
            self._set_status("STOPPING")

    def _show_frame(self, image):
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def _show_error(self, message):
        self._last_error = message
        self.preview.setPixmap(QPixmap())
        self.preview.setText(message)
        self.gesture.setText("Camera unavailable")
        self.gesture_hint.setText("Check permissions, connection, or choose another device index.")

    def _worker_finished(self):
        if self._close_pending:
            self._set_status("STOPPING · CONFIRMING WORKER EXIT")
            return
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.camera.setEnabled(True)
        self.control_toggle.setChecked(False)
        self._set_status("CAMERA ERROR" if self._last_error else "READY · PREVIEW ONLY")
        if not self._last_error and self.preview.pixmap().isNull():
            self.preview.setText("Camera preview is paused")

    def _check_shutdown_complete(self):
        if self.worker and self.worker.isRunning():
            return
        self._shutdown_timer.stop()
        if self._close_pending:
            self._close_pending = False
            self.close()

    def closeEvent(self, event: QCloseEvent):
        if self.worker and self.worker.isRunning():
            if not self._close_pending:
                self._close_pending = True
                self.worker.request_stop()
                self._set_status("STOPPING · WAITING FOR CAMERA RELEASE")
                self.gesture_hint.setText(
                    "Waiting for the camera worker to return and release its resources."
                )
                self._shutdown_timer.start()
            event.ignore()
            return
        self._shutdown_timer.stop()
        self._close_pending = False
        event.accept()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
