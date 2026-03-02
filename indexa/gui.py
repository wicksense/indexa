from __future__ import annotations

import contextlib
import io
import platform
import sys
import threading
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .rename import scan_and_rename, undo_renames

TEMPLATE_PRESETS = {
    "Author - Title - Year": "{first_author_last}-{short_title}-{year}",
    "Year - Author - Title": "{year}-{first_author_last}-{short_title}",
    "Title - Year - Author": "{short_title}-{year}-{first_author_last}",
}


APP_QSS = """
QMainWindow { background: #0f172a; }
QLabel { color: #e2e8f0; font-size: 13px; }
QGroupBox { color: #cbd5e1; border: 1px solid #334155; border-radius: 10px; margin-top: 10px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QComboBox {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
    color: #e5e7eb;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid #334155;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: #1f2937;
}
QComboBox::down-arrow {
    width: 0px; height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 7px solid #cbd5e1;
}
QComboBox QAbstractItemView {
    background: #111827;
    color: #e5e7eb;
    border: 1px solid #334155;
    selection-background-color: #0f766e;
    selection-color: #ecfeff;
    outline: 0;
}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    width: 16px;
    border-left: 1px solid #334155;
    background: #1f2937;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: #273548;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 0px; height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 6px solid #cbd5e1;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0px; height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #cbd5e1;
}
QCheckBox { color: #e5e7eb; }
QPushButton { background: #1f2937; color: #e5e7eb; border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; font-weight: 600; }
QPushButton:hover { background: #273548; border: 1px solid #475569; }
QPushButton:pressed { background: #111827; }
QPushButton#primary { background: #0f766e; border: 1px solid #0f766e; color: #ecfeff; }
QPushButton#primary:hover { background: #0d9488; border: 1px solid #0d9488; }
QPushButton#secondary { background: #374151; }
QPushButton#secondary:hover { background: #4b5563; }
"""


class WatcherThread(threading.Thread):
    def __init__(self, app: "IndexaWindow") -> None:
        super().__init__(daemon=True)
        self.app = app
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            out = self.app.scan_tick_output()
            if out:
                self.app.log_signal.emit(out)
            interval = max(0.5, self.app.interval_spin.value())
            self.stop_event.wait(interval)


class IndexaWindow(QtWidgets.QMainWindow):
    log_signal = QtCore.Signal(str)

    def __init__(self, start_minimized: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Indexa")
        self.resize(1040, 720)
        self.watcher: WatcherThread | None = None

        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        title = QtWidgets.QLabel("Indexa · Journal PDF Organizer")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #f8fafc;")
        subtitle = QtWidgets.QLabel("Preview, apply, undo, and watch folders in background")
        subtitle.setStyleSheet("color: #94a3b8;")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        cfg_box = QtWidgets.QGroupBox("Configuration")
        cfg_layout = QtWidgets.QVBoxLayout(cfg_box)

        folder_row = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit(str(Path.home() / "Downloads"))
        browse_btn = QtWidgets.QPushButton("Browse…")
        browse_btn.clicked.connect(self.pick_folder)
        folder_row.addWidget(QtWidgets.QLabel("Folder"))
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(browse_btn)
        cfg_layout.addLayout(folder_row)

        opts_row = QtWidgets.QHBoxLayout()
        self.title_words = QtWidgets.QSpinBox(); self.title_words.setRange(3, 20); self.title_words.setValue(8)
        self.steps_spin = QtWidgets.QSpinBox(); self.steps_spin.setRange(0, 100000); self.steps_spin.setValue(0); self.steps_spin.setSpecialValueText("All")
        self.interval_spin = QtWidgets.QDoubleSpinBox(); self.interval_spin.setRange(0.5, 600.0); self.interval_spin.setValue(3.0)
        self.undo_log = QtWidgets.QLineEdit(".indexa-renames.jsonl")

        opts_row.addWidget(QtWidgets.QLabel("Title words")); opts_row.addWidget(self.title_words)
        opts_row.addWidget(QtWidgets.QLabel("Undo steps")); opts_row.addWidget(self.steps_spin)
        opts_row.addWidget(QtWidgets.QLabel("Watch interval (s)")); opts_row.addWidget(self.interval_spin)
        opts_row.addWidget(QtWidgets.QLabel("Undo log")); opts_row.addWidget(self.undo_log)
        cfg_layout.addLayout(opts_row)

        tpl_row = QtWidgets.QHBoxLayout()
        self.template_mode = QtWidgets.QComboBox()
        self.template_mode.addItems(list(TEMPLATE_PRESETS.keys()) + ["Custom (Advanced)"])
        self.template_mode.currentTextChanged.connect(self.on_template_mode_changed)
        tpl_row.addWidget(QtWidgets.QLabel("Filename style"))
        tpl_row.addWidget(self.template_mode, 1)
        cfg_layout.addLayout(tpl_row)

        self.template_row_widget = QtWidgets.QWidget()
        tr = QtWidgets.QHBoxLayout(self.template_row_widget)
        tr.setContentsMargins(0, 0, 0, 0)
        self.template_label = QtWidgets.QLabel("Template")
        self.template_edit = QtWidgets.QLineEdit(TEMPLATE_PRESETS["Author - Title - Year"])
        self.template_edit.setEnabled(True)
        tr.addWidget(self.template_label)
        tr.addWidget(self.template_edit)
        cfg_layout.addWidget(self.template_row_widget)
        self.template_row_widget.hide()

        self.autostart_checkbox = QtWidgets.QCheckBox("Enable Windows autostart")
        self.autostart_checkbox.stateChanged.connect(self.on_autostart_changed)
        if platform.system() == "Windows":
            self.autostart_checkbox.setChecked(self.get_windows_autostart())
        else:
            self.autostart_checkbox.setEnabled(False)
        cfg_layout.addWidget(self.autostart_checkbox)
        outer.addWidget(cfg_box)

        actions_box = QtWidgets.QGroupBox("Actions")
        actions_row = QtWidgets.QHBoxLayout(actions_box)
        preview_btn = QtWidgets.QPushButton("Preview Scan")
        apply_btn = QtWidgets.QPushButton("Apply Scan"); apply_btn.setObjectName("primary")
        undo_preview_btn = QtWidgets.QPushButton("Preview Undo")
        undo_apply_btn = QtWidgets.QPushButton("Apply Undo"); undo_apply_btn.setObjectName("primary")
        self.watch_start_btn = QtWidgets.QPushButton("Start Watch"); self.watch_start_btn.setObjectName("primary")
        self.watch_stop_btn = QtWidgets.QPushButton("Stop Watch"); self.watch_stop_btn.setObjectName("secondary"); self.watch_stop_btn.setEnabled(False)
        clear_btn = QtWidgets.QPushButton("Clear Output"); clear_btn.setObjectName("secondary")

        preview_btn.clicked.connect(lambda: self.run_scan(dry_run=True))
        apply_btn.clicked.connect(lambda: self.run_scan(dry_run=False))
        undo_preview_btn.clicked.connect(lambda: self.run_undo(dry_run=True))
        undo_apply_btn.clicked.connect(lambda: self.run_undo(dry_run=False))
        self.watch_start_btn.clicked.connect(self.start_watch)
        self.watch_stop_btn.clicked.connect(self.stop_watch)
        clear_btn.clicked.connect(self.output_clear)

        for b in [preview_btn, apply_btn, undo_preview_btn, undo_apply_btn, self.watch_start_btn, self.watch_stop_btn, clear_btn]:
            actions_row.addWidget(b)
        outer.addWidget(actions_box)

        self.status = QtWidgets.QLabel("Ready")
        self.status.setStyleSheet("color:#22c55e; font-weight: 600;")
        outer.addWidget(self.status)

        self.output = QtWidgets.QPlainTextEdit(); self.output.setReadOnly(True)
        outer.addWidget(self.output, 1)

        self.setStyleSheet(APP_QSS)
        self.log_signal.connect(self._append)
        self.setup_tray()

        if start_minimized:
            QtCore.QTimer.singleShot(0, lambda: self.hide_to_tray(initial=True))

    def setup_tray(self) -> None:
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QtWidgets.QSystemTrayIcon(self)
        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.setWindowIcon(icon)
        menu = QtWidgets.QMenu()
        menu.addAction("Open", self.show_normal)
        self.tray_toggle_watch_action = menu.addAction("Start Watch", self.toggle_watch)
        menu.addAction("Quit", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show_normal() if r == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def show_normal(self) -> None:
        self.show(); self.activateWindow()

    def hide_to_tray(self, initial: bool = False) -> None:
        self.hide()
        if getattr(self, "tray", None):
            self.tray.showMessage("Indexa", "Running in tray" if not initial else "Started minimized to tray")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if getattr(self, "tray", None):
            event.ignore(); self.hide_to_tray(); return
        super().closeEvent(event)

    def quit_app(self) -> None:
        self.stop_watch()
        if getattr(self, "tray", None):
            self.tray.hide()
        QtWidgets.QApplication.quit()

    def toggle_watch(self) -> None:
        if self.watcher and self.watcher.is_alive():
            self.stop_watch()
        else:
            self.start_watch()

    def on_template_mode_changed(self, text: str) -> None:
        if text == "Custom (Advanced)":
            self.template_row_widget.show()
            self.template_edit.setEnabled(True)
        else:
            self.template_row_widget.hide()
            self.template_edit.setText(TEMPLATE_PRESETS[text])

    def current_template(self) -> str:
        t = self.template_edit.text().strip()
        return t or TEMPLATE_PRESETS["Author - Title - Year"]

    def pick_folder(self) -> None:
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose folder", self.folder_edit.text())
        if selected: self.folder_edit.setText(selected)

    def _ensure_folder(self) -> Path | None:
        p = Path(self.folder_edit.text()).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            QtWidgets.QMessageBox.warning(self, "Invalid folder", f"Folder does not exist:\n{p}")
            return None
        return p

    def _append(self, text: str) -> None:
        self.output.appendPlainText(text)

    def output_clear(self) -> None:
        self.output.clear()

    def _capture_stdout(self, fn) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn()
        return buf.getvalue().strip()

    def run_scan(self, dry_run: bool) -> None:
        folder = self._ensure_folder()
        if not folder:
            return
        out = self._capture_stdout(
            lambda: scan_and_rename(
                str(folder),
                dry_run=dry_run,
                title_words=self.title_words.value(),
                undo_log_path=self.undo_log.text().strip() or ".indexa-renames.jsonl",
                template=self.current_template(),
            )
        )
        self._append(out or "(no output)")

    def scan_tick_output(self) -> str:
        folder = Path(self.folder_edit.text()).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            return ""
        return self._capture_stdout(
            lambda: scan_and_rename(
                str(folder),
                dry_run=False,
                title_words=self.title_words.value(),
                undo_log_path=self.undo_log.text().strip() or ".indexa-renames.jsonl",
                template=self.current_template(),
            )
        )

    def start_watch(self) -> None:
        if not self._ensure_folder() or (self.watcher and self.watcher.is_alive()):
            return
        self.watcher = WatcherThread(self)
        self.watcher.start()
        self.watch_start_btn.setEnabled(False); self.watch_stop_btn.setEnabled(True)
        if hasattr(self, "tray_toggle_watch_action"): self.tray_toggle_watch_action.setText("Stop Watch")
        self.status.setText("Watching")

    def stop_watch(self) -> None:
        if self.watcher and self.watcher.is_alive():
            self.watcher.stop_event.set(); self.watcher.join(timeout=1.5)
        self.watcher = None
        self.watch_start_btn.setEnabled(True); self.watch_stop_btn.setEnabled(False)
        if hasattr(self, "tray_toggle_watch_action"): self.tray_toggle_watch_action.setText("Start Watch")
        self.status.setText("Watch stopped")

    def run_undo(self, dry_run: bool) -> None:
        folder = self._ensure_folder()
        if not folder:
            return
        steps = self.steps_spin.value()
        out = self._capture_stdout(lambda: undo_renames(str(folder), undo_log_path=self.undo_log.text().strip() or ".indexa-renames.jsonl", steps=steps, dry_run=dry_run))
        self._append(out or "(no output)")

    def on_autostart_changed(self, state: int) -> None:
        if platform.system() != "Windows":
            return
        enabled = state == int(QtCore.Qt.CheckState.Checked)
        ok, msg = self.set_windows_autostart(enabled)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Autostart", msg)

    def get_windows_autostart(self) -> bool:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, "Indexa")
            return True
        except Exception:
            return False

    def set_windows_autostart(self, enabled: bool) -> tuple[bool, str]:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    cmd = f'"{sys.executable}" -m indexa.gui --start-minimized'
                    winreg.SetValueEx(key, "Indexa", 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, "Indexa")
                    except FileNotFoundError:
                        pass
            return True, "OK"
        except Exception as e:
            return False, str(e)


def main() -> None:
    start_minimized = "--start-minimized" in sys.argv
    if start_minimized:
        sys.argv = [x for x in sys.argv if x != "--start-minimized"]

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    w = IndexaWindow(start_minimized=start_minimized)
    w.show()
    if start_minimized:
        w.hide_to_tray(initial=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
