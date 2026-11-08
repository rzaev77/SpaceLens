"""Сканер файловой системы.

Работает в отдельном QThread, не блокирует GUI. Обходит дерево через
os.scandir, пропуская символические ссылки и reparse points (junctions)
Windows, чтобы избежать зацикливания. Ошибки доступа к отдельным файлам
и каталогам не прерывают сканирование.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

# Флаг reparse point есть в модуле stat только под Windows.
_FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass
class Node:
    """Узел дерева файловой системы."""

    name: str
    path: str
    size: int = 0
    is_dir: bool = False
    children: List["Node"] = field(default_factory=list)
    parent: Optional["Node"] = field(default=None, repr=False, compare=False)

    def total_files(self) -> int:
        if not self.is_dir:
            return 1
        return sum(c.total_files() for c in self.children)


class _ScanCancelled(Exception):
    """Внутреннее исключение для остановки обхода."""


class ScanWorker(QThread):
    """Фоновое сканирование каталога.

    Сигналы:
        progress(str, int, int) — текущий путь, число файлов, суммарный объём;
        finished_scan(Node)     — корень готового дерева;
        cancelled()             — сканирование отменено пользователем;
        failed(str)             — фатальная ошибка (недоступный корень и т.п.).
    """

    progress = Signal(str, int, int)
    finished_scan = Signal(object)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, root_path: str, parent=None):
        super().__init__(parent)
        self.root_path = os.path.abspath(root_path)
        self._cancelled = False
        self._file_count = 0
        self._byte_count = 0

    def cancel(self) -> None:
        self._cancelled = True

    # ------------------------------------------------------------------ #

    def run(self) -> None:  # noqa: D102
        try:
            if not os.path.isdir(self.root_path):
                raise NotADirectoryError(f"Каталог не существует: {self.root_path}")
            root = self._scan_dir(self.root_path)
            self._link_parents(root)
            self.progress.emit(self.root_path, self._file_count, self._byte_count)
            self.finished_scan.emit(root)
        except _ScanCancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001 — показываем пользователю любую ошибку
            self.failed.emit(str(exc))

    def _check_cancel(self) -> None:
        if self._cancelled:
            raise _ScanCancelled()

    def _is_reparse_or_link(self, entry: os.DirEntry, st: os.stat_result) -> bool:
        if entry.is_symlink():
            return True
        # Windows junctions / reparse points не видны как symlink.
        return bool(getattr(st, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)

    def _scan_dir(self, path: str) -> Node:
        node = Node(name=os.path.basename(path.rstrip("\\/")) or path,
                    path=path, is_dir=True)
        try:
            with os.scandir(path) as it:
                for entry in it:
                    self._check_cancel()
                    try:
                        st = entry.stat(follow_symlinks=False)
                        if self._is_reparse_or_link(entry, st):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            child = self._scan_dir(entry.path)
                            child.parent = node
                            node.children.append(child)
                        elif entry.is_file(follow_symlinks=False):
                            size = st.st_size
                            child = Node(name=entry.name, path=entry.path, size=size)
                            child.parent = node
                            node.children.append(child)
                            self._file_count += 1
                            self._byte_count += size
                            if self._file_count % 250 == 0:
                                self.progress.emit(entry.path, self._file_count,
                                                   self._byte_count)
                    except _ScanCancelled:
                        raise
                    except (PermissionError, FileNotFoundError, OSError):
                        # Недоступный/исчезнувший элемент — пропускаем.
                        continue
        except _ScanCancelled:
            raise
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            # Каталог недоступен целиком — возвращаем пустой узел.
            pass

        node.size = sum(c.size for c in node.children)
        node.children.sort(key=lambda c: c.size, reverse=True)
        return node

    @staticmethod
    def _link_parents(root: Node) -> None:
        """Итеративно проставить parent во всём дереве (без рекурсии)."""
        stack = [root]
        while stack:
            node = stack.pop()
            for child in node.children:
                child.parent = node
                if child.is_dir:
                    stack.append(child)