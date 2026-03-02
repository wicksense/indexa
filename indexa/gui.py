from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .rename import scan_and_rename, undo_renames


class IndexaWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Indexa")
        self.resize(950, 620)

        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        layout = QtWidgets.QVBoxLayout(root)

        # Folder row
        folder_row = QtWidgets.QHBoxLayout()
        self.folder_edit = QtWidgets.QLineEdit(str(Path.home() / "Downloads"))
        browse_btn = QtWidgets.QPushButton("Browse…")
        browse_btn.clicked.connect(self.pick_folder)
        folder_row.addWidget(QtWidgets.QLabel("Folder:"))
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        # Options row
        opts_row = QtWidgets.QHBoxLayout()
        self.title_words = QtWidgets.QSpinBox()
        self.title_words.setRange(3, 20)
        self.title_words.setValue(8)
        self.undo_log = QtWidgets.QLineEdit(".indexa-renames.jsonl")
        opts_row.addWidget(QtWidgets.QLabel("Title words:"))
        opts_row.addWidget(self.title_words)
        opts_row.addSpacing(20)
        opts_row.addWidget(QtWidgets.QLabel("Undo log:"))
        opts_row.addWidget(self.undo_log)
        layout.addLayout(opts_row)

        # Buttons row
        btn_row = QtWidgets.QHBoxLayout()
        preview_btn = QtWidgets.QPushButton("Preview Scan")
        apply_btn = QtWidgets.QPushButton("Apply Scan")
        undo_preview_btn = QtWidgets.QPushButton("Preview Undo")
        undo_apply_btn = QtWidgets.QPushButton("Apply Undo")
        clear_btn = QtWidgets.QPushButton("Clear")

        preview_btn.clicked.connect(lambda: self.run_scan(dry_run=True))
        apply_btn.clicked.connect(lambda: self.run_scan(dry_run=False))
        undo_preview_btn.clicked.connect(lambda: self.run_undo(dry_run=True))
        undo_apply_btn.clicked.connect(lambda: self.run_undo(dry_run=False))
        clear_btn.clicked.connect(self.output_clear)

        for b in [preview_btn, apply_btn, undo_preview_btn, undo_apply_btn, clear_btn]:
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.steps_spin = QtWidgets.QSpinBox()
        self.steps_spin.setRange(0, 100000)
        self.steps_spin.setValue(0)
        self.steps_spin.setSpecialValueText("All")
        steps_row = QtWidgets.QHBoxLayout()
        steps_row.addWidget(QtWidgets.QLabel("Undo steps:"))
        steps_row.addWidget(self.steps_spin)
        steps_row.addStretch(1)
        layout.addLayout(steps_row)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Indexa output will appear here...")
        layout.addWidget(self.output)

    def pick_folder(self) -> None:
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose folder", self.folder_edit.text())
        if selected:
            self.folder_edit.setText(selected)

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

    def run_scan(self, dry_run: bool) -> None:
        folder = self._ensure_folder()
        if not folder:
            return

        self._append(f"\n=== {'PREVIEW' if dry_run else 'APPLY'} SCAN: {folder} ===")
        self._capture_stdout(
            lambda: scan_and_rename(
                str(folder),
                dry_run=dry_run,
                title_words=self.title_words.value(),
                undo_log_path=self.undo_log.text().strip() or ".indexa-renames.jsonl",
            )
        )

    def run_undo(self, dry_run: bool) -> None:
        folder = self._ensure_folder()
        if not folder:
            return

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

    def _capture_stdout(self, fn) -> None:
        import io
        import contextlib

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                fn()
        except Exception as e:
            self._append(f"ERROR: {e}")
            return
        out = buf.getvalue().strip()
        if out:
            self._append(out)
        else:
            self._append("(no output)")


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    w = IndexaWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
