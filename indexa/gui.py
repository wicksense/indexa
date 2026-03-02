from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

from PySide6 import QtWidgets

from .rename import scan_and_rename, undo_renames


APP_QSS = """
QMainWindow {
    background: #0f172a;
}
QLabel {
    color: #e2e8f0;
    font-size: 13px;
}
QGroupBox {
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 10px;
    margin-top: 10px;
    padding-top: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QLineEdit, QSpinBox, QPlainTextEdit {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
    color: #e5e7eb;
    selection-background-color: #2563eb;
}
QPushButton {
    background: #1d4ed8;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: #2563eb;
}
QPushButton:pressed {
    background: #1e40af;
}
QPushButton#secondary {
    background: #334155;
}
QPushButton#secondary:hover {
    background: #475569;
}
"""


class IndexaWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Indexa")
        self.resize(1000, 680)

        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        title = QtWidgets.QLabel("Indexa · Journal PDF Organizer")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #f8fafc;")
        subtitle = QtWidgets.QLabel("Preview, apply, and undo filename normalization")
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
        self.title_words = QtWidgets.QSpinBox()
        self.title_words.setRange(3, 20)
        self.title_words.setValue(8)
        self.undo_log = QtWidgets.QLineEdit(".indexa-renames.jsonl")
        self.steps_spin = QtWidgets.QSpinBox()
        self.steps_spin.setRange(0, 100000)
        self.steps_spin.setValue(0)
        self.steps_spin.setSpecialValueText("All")

        opts_row.addWidget(QtWidgets.QLabel("Title words"))
        opts_row.addWidget(self.title_words)
        opts_row.addSpacing(12)
        opts_row.addWidget(QtWidgets.QLabel("Undo steps"))
        opts_row.addWidget(self.steps_spin)
        opts_row.addSpacing(12)
        opts_row.addWidget(QtWidgets.QLabel("Undo log"))
        opts_row.addWidget(self.undo_log)
        cfg_layout.addLayout(opts_row)

        outer.addWidget(cfg_box)

        actions_box = QtWidgets.QGroupBox("Actions")
        actions_row = QtWidgets.QHBoxLayout(actions_box)
        preview_btn = QtWidgets.QPushButton("Preview Scan")
        apply_btn = QtWidgets.QPushButton("Apply Scan")
        undo_preview_btn = QtWidgets.QPushButton("Preview Undo")
        undo_apply_btn = QtWidgets.QPushButton("Apply Undo")
        clear_btn = QtWidgets.QPushButton("Clear Output")
        clear_btn.setObjectName("secondary")

        preview_btn.clicked.connect(lambda: self.run_scan(dry_run=True))
        apply_btn.clicked.connect(lambda: self.run_scan(dry_run=False))
        undo_preview_btn.clicked.connect(lambda: self.run_undo(dry_run=True))
        undo_apply_btn.clicked.connect(lambda: self.run_undo(dry_run=False))
        clear_btn.clicked.connect(self.output_clear)

        for b in [preview_btn, apply_btn, undo_preview_btn, undo_apply_btn, clear_btn]:
            actions_row.addWidget(b)

        outer.addWidget(actions_box)

        self.status = QtWidgets.QLabel("Ready")
        self.status.setStyleSheet("color:#22c55e; font-weight: 600;")
        outer.addWidget(self.status)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Indexa output will appear here...")
        outer.addWidget(self.output, 1)

        self.setStyleSheet(APP_QSS)

    def pick_folder(self) -> None:
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose folder", self.folder_edit.text())
        if selected:
            self.folder_edit.setText(selected)

    def _ensure_folder(self) -> Path | None:
        p = Path(self.folder_edit.text()).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            QtWidgets.QMessageBox.warning(self, "Invalid folder", f"Folder does not exist:\n{p}")
            self.status.setText("Invalid folder")
            self.status.setStyleSheet("color:#ef4444; font-weight: 600;")
            return None
        return p

    def _append(self, text: str) -> None:
        self.output.appendPlainText(text)

    def output_clear(self) -> None:
        self.output.clear()

    def run_scan(self, dry_run: bool) -> None:
        folder = self._ensure_folder()
        if not folder:
            return
        self.status.setText("Scanning…")
        self.status.setStyleSheet("color:#f59e0b; font-weight: 600;")

        self._append(f"\n=== {'PREVIEW' if dry_run else 'APPLY'} SCAN: {folder} ===")
        self._capture_stdout(
            lambda: scan_and_rename(
                str(folder),
                dry_run=dry_run,
                title_words=self.title_words.value(),
                undo_log_path=self.undo_log.text().strip() or ".indexa-renames.jsonl",
            )
        )
        self.status.setText("Done")
        self.status.setStyleSheet("color:#22c55e; font-weight: 600;")

    def run_undo(self, dry_run: bool) -> None:
        folder = self._ensure_folder()
        if not folder:
            return
        self.status.setText("Undoing…")
        self.status.setStyleSheet("color:#f59e0b; font-weight: 600;")

        steps = self.steps_spin.value()
        self._append(f"\n=== {'PREVIEW' if dry_run else 'APPLY'} UNDO: {folder} (steps={steps or 'all'}) ===")
        self._capture_stdout(
            lambda: undo_renames(
                str(folder),
                undo_log_path=self.undo_log.text().strip() or ".indexa-renames.jsonl",
                steps=steps,
                dry_run=dry_run,
            )
        )
        self.status.setText("Done")
        self.status.setStyleSheet("color:#22c55e; font-weight: 600;")

    def _capture_stdout(self, fn) -> None:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                fn()
        except Exception as e:
            self._append(f"ERROR: {e}")
            self.status.setText("Error")
            self.status.setStyleSheet("color:#ef4444; font-weight: 600;")
            return
        out = buf.getvalue().strip()
        self._append(out if out else "(no output)")


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    w = IndexaWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
