"""Operaciones de archivo en segundo plano, con progreso y cancelación.

Copiar y mover se hacen a mano en bloques en vez de con shutil.copytree, porque
hace falta reportar bytes a medida que avanzan y poder cancelar en el medio de
un archivo grande. El borrado a la papelera lo resuelve `platform`, que sabe
hacerlo en cada sistema.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from PySide6.QtCore import QMutex, QThread, QWaitCondition, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout,
)

from . import platform
from .i18n import t

CHUNK = 1024 * 1024

# Respuestas ante un conflicto de sobreescritura.
OV_ASK, OV_OVERWRITE, OV_SKIP, OV_ALL, OV_NONE, OV_NEWER, OV_CANCEL = range(7)


@dataclass
class ScanResult:
    files: int = 0
    dirs: int = 0
    total_bytes: int = 0


def scan(paths: list[str]) -> ScanResult:
    """Cuenta archivos y bytes de una lista de rutas, recursivamente."""
    r = ScanResult()
    for p in paths:
        if os.path.isdir(p):
            r.dirs += 1
            for dirpath, dirnames, filenames in os.walk(p, onerror=lambda e: None):
                r.dirs += len(dirnames)
                for fn in filenames:
                    r.files += 1
                    try:
                        r.total_bytes += os.path.getsize(os.path.join(dirpath, fn))
                    except OSError:
                        pass
        else:
            r.files += 1
            try:
                r.total_bytes += os.path.getsize(p)
            except OSError:
                pass
    return r


class _Worker(QThread):
    """Base con cancelación cooperativa y diálogo de conflicto sincrónico."""

    progress = Signal(str, int, int)        # archivo actual, hechos, total
    file_done = Signal(str)
    conflict = Signal(str, str)             # origen, destino
    failed = Signal(str, str)               # ruta, motivo
    completed = Signal(int, list)           # procesados, errores

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = False
        self._mutex = QMutex()
        self._wait = QWaitCondition()
        self._answer = OV_ASK
        self.policy = OV_ASK
        self.errors: list[str] = []
        self.processed = 0
        self.done_bytes = 0
        self.total_bytes = 0

    def cancel(self) -> None:
        self._cancel = True
        self._mutex.lock()
        self._answer = OV_CANCEL
        self._wait.wakeAll()
        self._mutex.unlock()

    def answer_conflict(self, answer: int) -> None:
        self._mutex.lock()
        self._answer = answer
        self._wait.wakeAll()
        self._mutex.unlock()

    def _resolve_conflict(self, src: str, dst: str) -> int:
        """Devuelve OV_OVERWRITE, OV_SKIP o OV_CANCEL. Bloquea si hay que preguntar."""
        if self.policy == OV_ALL:
            return OV_OVERWRITE
        if self.policy == OV_NONE:
            return OV_SKIP
        if self.policy == OV_NEWER:
            try:
                return OV_OVERWRITE if os.path.getmtime(src) > os.path.getmtime(dst) else OV_SKIP
            except OSError:
                return OV_SKIP

        self._mutex.lock()
        self._answer = OV_ASK
        self.conflict.emit(src, dst)
        while self._answer == OV_ASK:
            self._wait.wait(self._mutex)
        ans = self._answer
        self._mutex.unlock()

        if ans in (OV_ALL, OV_NONE, OV_NEWER):
            self.policy = ans
            return self._resolve_conflict(src, dst)
        return ans

    def _copy_file(self, src: str, dst: str) -> bool:
        """Copia un archivo reportando progreso. False si se canceló."""
        try:
            with open(src, "rb") as fi, open(dst, "wb") as fo:
                while True:
                    if self._cancel:
                        fo.close()
                        try:
                            os.remove(dst)  # no dejar un archivo truncado
                        except OSError:
                            pass
                        return False
                    buf = fi.read(CHUNK)
                    if not buf:
                        break
                    fo.write(buf)
                    self.done_bytes += len(buf)
                    self.progress.emit(src, self.done_bytes, self.total_bytes)
            shutil.copystat(src, dst, follow_symlinks=False)
        except OSError as exc:
            self.errors.append(f"{src}: {exc.strerror or exc}")
            self.failed.emit(src, str(exc))
        return True


class CopyMoveWorker(_Worker):
    def __init__(self, sources: list[str], dest_dir: str, move: bool,
                 rename_to: str | None = None, parent=None):
        super().__init__(parent)
        self.sources = sources
        self.dest_dir = dest_dir
        self.move = move
        # Copiar/mover renombrando en un paso: sólo tiene sentido con un origen.
        self.rename_to = rename_to if len(sources) == 1 else None

    def run(self) -> None:
        self.total_bytes = scan(self.sources).total_bytes
        for src in self.sources:
            if self._cancel:
                break
            name = self.rename_to or os.path.basename(src.rstrip("\\/"))
            self._transfer(src, os.path.join(self.dest_dir, name))
        self.completed.emit(self.processed, self.errors)

    def _transfer(self, src: str, dst: str) -> None:
        if self._cancel:
            return
        if os.path.isdir(src):
            # Mover dentro del mismo volumen: un rename resuelve todo el árbol.
            if self.move and not os.path.exists(dst) and self._same_volume(src, dst):
                try:
                    os.replace(src, dst)
                    self.processed += 1
                    self.file_done.emit(src)
                    return
                except OSError:
                    pass  # cae al recorrido recursivo
            try:
                os.makedirs(dst, exist_ok=True)
            except OSError as exc:
                self.errors.append(f"{dst}: {exc.strerror or exc}")
                return
            try:
                children = os.listdir(src)
            except OSError as exc:
                self.errors.append(f"{src}: {exc.strerror or exc}")
                return
            for name in children:
                self._transfer(os.path.join(src, name), os.path.join(dst, name))
            if self.move and not self._cancel and not self.errors:
                try:
                    os.rmdir(src)
                except OSError:
                    pass
            self.processed += 1
            return

        if os.path.exists(dst):
            if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
                self.errors.append(f"{src}: origen y destino son el mismo archivo")
                return
            ans = self._resolve_conflict(src, dst)
            if ans == OV_CANCEL:
                self._cancel = True
                return
            if ans == OV_SKIP:
                try:
                    self.done_bytes += os.path.getsize(src)
                except OSError:
                    pass
                return
            try:
                os.chmod(dst, 0o666)  # destino de sólo lectura
            except OSError:
                pass

        if self.move and self._same_volume(src, dst):
            try:
                os.replace(src, dst)
                self.processed += 1
                try:
                    self.done_bytes += os.path.getsize(dst)
                except OSError:
                    pass
                self.progress.emit(src, self.done_bytes, self.total_bytes)
                self.file_done.emit(src)
                return
            except OSError:
                pass  # cae a copiar y borrar

        if not self._copy_file(src, dst):
            return
        if self.move:
            try:
                os.remove(src)
            except OSError as exc:
                self.errors.append(f"{src}: no se pudo borrar tras mover ({exc.strerror or exc})")
        self.processed += 1
        self.file_done.emit(src)

    @staticmethod
    def _same_volume(a: str, b: str) -> bool:
        return os.path.splitdrive(os.path.abspath(a))[0].lower() == \
               os.path.splitdrive(os.path.abspath(b))[0].lower()


# --- borrado -----------------------------------------------------------


class DeleteWorker(_Worker):
    def __init__(self, paths: list[str], to_recycle: bool, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.to_recycle = to_recycle

    def run(self) -> None:
        if self.to_recycle:
            ok, msg = platform.send_to_trash(self.paths)
            if not ok:
                self.errors.append(msg)
            else:
                self.processed = len(self.paths)
            self.completed.emit(self.processed, self.errors)
            return

        total = scan(self.paths)
        self.total_bytes = max(total.files + total.dirs, 1)
        for p in self.paths:
            if self._cancel:
                break
            self._delete(p)
        self.completed.emit(self.processed, self.errors)

    def _delete(self, path: str) -> None:
        if self._cancel:
            return
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                for name in os.listdir(path):
                    self._delete(os.path.join(path, name))
                if self._cancel:
                    return
                os.rmdir(path)
            else:
                try:
                    os.chmod(path, 0o666)
                except OSError:
                    pass
                os.remove(path)
            self.processed += 1
            self.done_bytes += 1
            self.progress.emit(path, self.done_bytes, self.total_bytes)
        except OSError as exc:
            self.errors.append(f"{path}: {exc.strerror or exc}")


# --- interfaz ----------------------------------------------------------


def human(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for u in ("KB", "MB", "GB", "TB"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.1f} {u}"
    return f"{n:.1f} PB"


class ConflictDialog(QDialog):
    """Preguntar qué hacer cuando el destino ya existe."""

    def __init__(self, src: str, dst: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("El archivo ya existe"))
        self.answer = OV_SKIP
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>" + t("El destino ya existe:") + "</b><br>" + dst))
        lay.addWidget(QLabel(self._compare(src, dst)))

        row1, row2 = QHBoxLayout(), QHBoxLayout()
        for text, ans, row in (
            (t("&Sobreescribir"), OV_OVERWRITE, row1),
            (t("&Omitir"), OV_SKIP, row1),
            (t("Sobreescribir &todos"), OV_ALL, row2),
            (t("Omitir t&odos"), OV_NONE, row2),
            (t("Sólo los más &nuevos"), OV_NEWER, row2),
        ):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, a=ans: self._choose(a))
            row.addWidget(b)
        lay.addLayout(row1)
        lay.addLayout(row2)

        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.rejected.connect(lambda: self._choose(OV_CANCEL))
        lay.addWidget(bb)

    @staticmethod
    def _compare(src: str, dst: str) -> str:
        import datetime

        def info(p):
            try:
                st = os.stat(p)
                ts = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")
                return f"{human(st.st_size)} — {ts}"
            except OSError:
                return "?"

        return t("Origen:  {a}\nDestino: {b}", a=info(src), b=info(dst))

    def _choose(self, answer: int) -> None:
        self.answer = answer
        self.accept()


class ProgressDialog(QDialog):
    """Progreso de una operación, cancelable. Cierra solo al terminar."""

    def __init__(self, title: str, worker: _Worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.worker = worker
        self.result_errors: list[str] = []
        self.result_count = 0

        lay = QVBoxLayout(self)
        self.lbl = QLabel(t("Preparando…"))
        self.lbl.setWordWrap(True)
        self.lbl.setMinimumHeight(34)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.sub = QLabel("")
        lay.addWidget(self.lbl)
        lay.addWidget(self.bar)
        lay.addWidget(self.sub)

        bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Cancel).setText(t("Cancelar"))
        bb.rejected.connect(self._cancel)
        lay.addWidget(bb)

        worker.progress.connect(self._on_progress)
        worker.conflict.connect(self._on_conflict)
        worker.completed.connect(self._on_completed)

    def _cancel(self) -> None:
        self.lbl.setText(t("Cancelando…"))
        self.worker.cancel()

    def _on_progress(self, path: str, done: int, total: int) -> None:
        self.lbl.setText(os.path.basename(path) or path)
        if total > 0:
            self.bar.setValue(min(100, int(done * 100 / total)))
            self.sub.setText(t("{done} de {total}", done=human(done), total=human(total)))

    def _on_conflict(self, src: str, dst: str) -> None:
        dlg = ConflictDialog(src, dst, self)
        dlg.exec()
        self.worker.answer_conflict(dlg.answer)

    def _on_completed(self, count: int, errors: list) -> None:
        self.result_count = count
        self.result_errors = list(errors)
        self.accept()

    def run(self) -> tuple[int, list[str]]:
        self.worker.start()
        self.exec()
        self.worker.wait(5000)
        return self.result_count, self.result_errors
