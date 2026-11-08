"""Интерактивная карта диска: Squarified Treemap + хлебные крошки."""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from send2trash import send2trash

from core.scanner import Node, ScanWorker
from core.treemap import squarify
from core.utils import format_size, open_in_explorer

# Родственные hue для детей одного родителя: slate, indigo, teal, amber.
_HUES = (215, 243, 172, 38)
_BG = QColor("#0f1420")
_TEXT = QColor("#e2e8f0")
_HOVER_BORDER = QColor("#a5b4fc")


def _color_for(index: int, is_dir: bool) -> QColor:
    hue = _HUES[index % len(_HUES)]
    rank = index // len(_HUES)
    if is_dir:
        sat = 0.44
        val = max(0.60 - rank * 0.045, 0.38)
    else:
        sat = 0.20
        val = max(0.36 - rank * 0.03, 0.22)
    return QColor.fromHsvF(hue / 360.0, sat, val)


class TreemapCanvas(QWidget):
    """Кастомный виджет карты на QPainter.

    Сигналы:
        drill_down(Node) — пользователь провалился в папку;
        tree_changed()   — узел удалён, размеры пересчитаны.
    """

    drill_down = Signal(object)
    tree_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(240)
        self._node: Optional[Node] = None
        self._items: List[Tuple[QRectF, Node]] = []
        self._hover: int = -1
        self._font = QFont("Segoe UI", 9)
        self._font_small = QFont("Segoe UI", 8)

    # ------------------------------------------------------------------ #

    def set_node(self, node: Optional[Node]) -> None:
        self._node = node
        self._hover = -1
        self._rebuild()
        self.update()

    def _rebuild(self) -> None:
        self._items = []
        if self._node is None:
            return
        children = [c for c in self._node.children if c.size > 0]
        if not children:
            return
        w = max(self.width() - 8, 1)
        h = max(self.height() - 8, 1)
        rects = squarify([c.size for c in children], 4.0, 4.0, w, h)
        self._items = [(QRectF(*r), c) for r, c in zip(rects, children)]

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rebuild()

    def _item_at(self, pos: QPoint) -> int:
        for i in range(len(self._items) - 1, -1, -1):
            if self._items[i][0].contains(pos):
                return i
        return -1

    # ------------------------------------------------------------------ #

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), _BG)

        if self._node is None:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "Выберите папку и нажмите «Сканировать»,\n"
                             "чтобы построить карту занятого места")
            painter.end()
            return
        if not self._items:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "Пустая папка")
            painter.end()
            return

        for i, (rect, node) in enumerate(self._items):
            r = rect.adjusted(1, 1, -1, -1)
            if r.width() < 2 or r.height() < 2:
                continue
            painter.setPen(Qt.NoPen)
            painter.setBrush(_color_for(i, node.is_dir))
            painter.drawRoundedRect(r, 3, 3)

            # Подписи только там, где хватает места.
            if r.width() > 56 and r.height() > 24:
                painter.setClipRect(r.adjusted(4, 2, -4, -2))
                painter.setPen(_TEXT)
                fm = QFontMetrics(self._font)
                painter.setFont(self._font)
                name = fm.elidedText(node.name, Qt.ElideMiddle, int(r.width()) - 8)
                painter.drawText(QRectF(r.x() + 4, r.y() + 3,
                                        r.width() - 8, fm.height()),
                                 Qt.AlignLeft | Qt.AlignVCenter, name)
                if r.height() > 44:
                    fm_s = QFontMetrics(self._font_small)
                    painter.setFont(self._font_small)
                    painter.setPen(QColor("#cbd5e1"))
                    painter.drawText(QRectF(r.x() + 4, r.y() + 3 + fm.height(),
                                            r.width() - 8, fm_s.height()),
                                     Qt.AlignLeft | Qt.AlignVCenter,
                                     format_size(node.size))
                painter.setClipping(False)

            if i == self._hover:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(_HOVER_BORDER, 2))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)
        painter.end()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        idx = self._item_at(event.position().toPoint())
        if idx != self._hover:
            self._hover = idx
            self.update()
        if idx >= 0:
            node = self._items[idx][1]
            tip = f"{node.path}\n{format_size(node.size)}"
            if node.is_dir and node.children:
                tip += "\nКлик — открыть папку"
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
            self.setCursor(Qt.PointingHandCursor
                           if node.is_dir and node.children else Qt.ArrowCursor)
        else:
            from PySide6.QtWidgets import QToolTip
            QToolTip.hideText()
            self.setCursor(Qt.ArrowCursor)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        idx = self._item_at(event.position().toPoint())
        if idx < 0:
            return
        node = self._items[idx][1]
        if event.button() == Qt.LeftButton:
            if node.is_dir and node.children:
                self.drill_down.emit(node)
        elif event.button() == Qt.RightButton:
            self._context_menu(node, event.globalPosition().toPoint())

    # ------------------------------------------------------------------ #

    def _context_menu(self, node: Node, global_pos: QPoint) -> None:
        menu = QMenu(self)
        act_open = menu.addAction("Открыть в Проводнике")
        menu.addSeparator()
        act_trash = menu.addAction("Удалить в корзину")
        chosen = menu.exec(global_pos)
        if chosen is act_open:
            try:
                open_in_explorer(node.path)
            except OSError as exc:
                QMessageBox.warning(self, "SpaceLens", f"Не удалось открыть: {exc}")
        elif chosen is act_trash:
            self._trash_node(node)

    def _trash_node(self, node: Node) -> None:
        answer = QMessageBox.question(
            self, "Удаление в корзину",
            f"Отправить в корзину?\n\n{node.path}\n({format_size(node.size)})",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            send2trash(node.path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "SpaceLens", f"Не удалось удалить: {exc}")
            return

        parent = node.parent
        if parent is not None and node in parent.children:
            parent.children.remove(node)
        ancestor = parent
        while ancestor is not None:
            ancestor.size = max(ancestor.size - node.size, 0)
            ancestor = ancestor.parent
        self._rebuild()
        self.update()
        self.tree_changed.emit()


class Breadcrumbs(QWidget):
    """Панель навигации по уровням дерева."""

    navigate = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(34)
        self._container = QWidget()
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._layout.addStretch(1)
        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

    def set_path(self, path: List[Node]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, node in enumerate(path):
            if i > 0:
                sep = QLabel("›")
                sep.setObjectName("muted")
                self._layout.addWidget(sep)
            btn = QPushButton(f"{node.name}  ·  {format_size(node.size)}")
            btn.setObjectName("crumbCurrent" if i == len(path) - 1 else "crumb")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, n=node: self.navigate.emit(n))
            self._layout.addWidget(btn)
        self._layout.addStretch(1)


class DiskMapTab(QWidget):
    """Вкладка «Карта диска»: сканирование + карта + навигация."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[ScanWorker] = None
        self._root: Optional[Node] = None
        self._path: List[Node] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Путь к папке или диску, например C:\\")
        self.path_edit.returnPressed.connect(self.start_scan)
        btn_browse = QPushButton("Обзор…")
        btn_browse.clicked.connect(self.choose_folder)
        self.btn_scan = QPushButton("Сканировать")
        self.btn_scan.setObjectName("accent")
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.cancel_scan)
        self.btn_cancel.hide()
        controls.addWidget(self.path_edit, 1)
        controls.addWidget(btn_browse)
        controls.addWidget(self.btn_scan)
        controls.addWidget(self.btn_cancel)
        layout.addLayout(controls)

        self.crumbs = Breadcrumbs()
        self.crumbs.navigate.connect(self.navigate_to)
        layout.addWidget(self.crumbs)

        self.canvas = TreemapCanvas()
        self.canvas.drill_down.connect(self.drill_down)
        self.canvas.tree_changed.connect(self._refresh_after_delete)
        layout.addWidget(self.canvas, 1)

        self.status = QLabel("Готово к сканированию")
        self.status.setObjectName("muted")
        layout.addWidget(self.status)

    # ------------------------------------------------------------------ #

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
        if folder:
            self.path_edit.setText(folder)

    def start_scan(self) -> None:
        import os

        path = self.path_edit.text().strip().strip('"')
        if not path:
            QMessageBox.information(self, "SpaceLens", "Укажите папку для сканирования.")
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "SpaceLens", f"Каталог не найден:\n{path}")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._worker = ScanWorker(path, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_scan.connect(self._on_scanned)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self.btn_scan.setEnabled(False)
        self.btn_cancel.show()
        self.status.setText("Сканирование…")
        self._worker.start()

    def cancel_scan(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self.btn_cancel.setEnabled(False)

    def _reset_controls(self) -> None:
        self.btn_scan.setEnabled(True)
        self.btn_cancel.hide()
        self.btn_cancel.setEnabled(True)

    def _on_progress(self, path: str, files: int, total_bytes: int) -> None:
        fm = QFontMetrics(self.status.font())
        elided = fm.elidedText(path, Qt.ElideMiddle, max(self.status.width() - 260, 80))
        self.status.setText(f"Сканирование: {files:,} файлов · {format_size(total_bytes)} · {elided}")

    def _on_scanned(self, root: Node) -> None:
        self._reset_controls()
        self._root = root
        self._path = [root]
        self.crumbs.set_path(self._path)
        self.canvas.set_node(root)
        self.status.setText(
            f"{root.path} · {format_size(root.size)} · {root.total_files():,} файлов"
        )
        self._worker = None

    def _on_failed(self, message: str) -> None:
        self._reset_controls()
        self._worker = None
        self.status.setText("Ошибка сканирования")
        QMessageBox.warning(self, "SpaceLens", f"Не удалось просканировать:\n{message}")

    def _on_cancelled(self) -> None:
        self._reset_controls()
        self._worker = None
        self.status.setText("Сканирование отменено")

    # ------------------------------------------------------------------ #

    def drill_down(self, node: Node) -> None:
        self._path.append(node)
        self.crumbs.set_path(self._path)
        self.canvas.set_node(node)

    def navigate_to(self, node: Node) -> None:
        if node in self._path:
            self._path = self._path[: self._path.index(node) + 1]
        else:
            self._path = [node]
        self.crumbs.set_path(self._path)
        self.canvas.set_node(node)

    def _refresh_after_delete(self) -> None:
        self.crumbs.set_path(self._path)
        if self._root is not None:
            self.status.setText(
                f"{self._root.path} · {format_size(self._root.size)} · "
                f"{self._root.total_files():,} файлов"
            )