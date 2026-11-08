"""Вкладка «Очистка дубликатов фото»: группы похожих изображений."""

from __future__ import annotations

import os
from typing import List, Optional, Set

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLayout, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from send2trash import send2trash

from core.deduplicator import DedupWorker, ImageInfo
from core.utils import format_size, open_in_explorer


class FlowLayout(QLayout):
    """Простая потоковая раскладка: перенос миниатюр на новую строку."""

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        x, y = rect.x() + m.left(), rect.y() + m.top()
        right = rect.right() - m.right()
        start_x = x
        line_h = 0
        for item in self._items:
            hint = item.sizeHint()
            w, h = hint.width(), hint.height()
            if x + w > right and line_h > 0:
                x = start_x
                y += line_h + self.spacing()
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
            x += w + self.spacing()
            line_h = max(line_h, h)
        return y + line_h + m.bottom() - rect.y()


class ThumbWidget(QFrame):
    """Миниатюра изображения с метаданными и чекбоксом удаления."""

    def __init__(self, info: ImageInfo, is_original: bool, parent=None):
        super().__init__(parent)
        self.info = info
        self.setObjectName("thumb")
        self.setFixedSize(172, 218)
        self.setToolTip(info.path)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        pic = QLabel()
        pic.setFixedSize(156, 120)
        pic.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(info.path)
        if not pixmap.isNull():
            pic.setPixmap(pixmap.scaled(156, 120, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
        else:
            pic.setText("нет превью")
        layout.addWidget(pic)

        name = QLabel()
        fm = QFontMetrics(name.font())
        name.setText(fm.elidedText(os.path.basename(info.path),
                                   Qt.ElideMiddle, 150))
        name.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(name)

        meta = QLabel(f"{info.width}×{info.height} · {format_size(info.size)}")
        meta.setObjectName("muted")
        layout.addWidget(meta)

        if is_original:
            badge = QLabel("Оригинал")
            badge.setObjectName("badgeOriginal")
            layout.addWidget(badge)
            self.check = None
        else:
            self.check = QCheckBox("В корзину")
            self.check.setChecked(True)
            layout.addWidget(self.check)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        try:
            open_in_explorer(self.info.path)
        except OSError:
            pass


class GroupCard(QFrame):
    """Карточка одной группы дубликатов."""

    changed = Signal()

    def __init__(self, index: int, group: List[ImageInfo], parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.thumbs: List[ThumbWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel(f"Группа {index} · {len(group)} файлов")
        title.setObjectName("heading")
        savings = QLabel(f"можно освободить {format_size(sum(im.size for im in group[1:]))}")
        savings.setObjectName("muted")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(savings)
        layout.addLayout(header)

        flow = FlowLayout(spacing=8)
        for i, info in enumerate(group):
            thumb = ThumbWidget(info, is_original=(i == 0))
            self.thumbs.append(thumb)
            flow.addWidget(thumb)
        layout.addLayout(flow)

        buttons = QHBoxLayout()
        btn_keep = QPushButton("Оставить оригинал (наибольшее разрешение)")
        btn_keep.setObjectName("accent")
        btn_keep.clicked.connect(self.keep_original)
        self.btn_selected = QPushButton("Удалить выбранные")
        self.btn_selected.setObjectName("danger")
        self.btn_selected.clicked.connect(self.delete_selected)
        buttons.addWidget(btn_keep)
        buttons.addWidget(self.btn_selected)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ #

    @property
    def infos(self) -> List[ImageInfo]:
        return [t.info for t in self.thumbs]

    def keep_original(self) -> None:
        # Оригиналы уже первыми: наибольшее разрешение, при равенстве — размер.
        victims = [t.info.path for t in self.thumbs[1:]]
        self._trash(victims, "Оставить только оригинал (наибольшее разрешение)?")

    def delete_selected(self) -> None:
        victims = [t.info.path for t in self.thumbs
                   if t.check is not None and t.check.isChecked()]
        if not victims:
            QMessageBox.information(self, "SpaceLens", "Отметьте файлы для удаления.")
            return
        self._trash(victims, f"Отправить в корзину выбранные файлы ({len(victims)} шт.)?")

    def _trash(self, paths: List[str], question: str) -> None:
        if not paths:
            return
        answer = QMessageBox.question(
            self, "Удаление в корзину",
            f"{question}\n\nФайлы можно будет восстановить из корзины.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        deleted: Set[str] = set()
        errors: List[str] = []
        try:
            for path in paths:
                try:
                    send2trash(path)
                    deleted.add(path)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{os.path.basename(path)}: {exc}")
        finally:
            QApplication.restoreOverrideCursor()

        for thumb in list(self.thumbs):
            if thumb.info.path in deleted:
                self.thumbs.remove(thumb)
                thumb.setParent(None)
                thumb.deleteLater()

        if errors:
            QMessageBox.warning(self, "SpaceLens",
                                "Часть файлов не удалена:\n" + "\n".join(errors[:8]))
        self.changed.emit()


class DuplicatesTab(QWidget):
    """Вкладка поиска и очистки визуально похожих изображений."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[DedupWorker] = None
        self._cards: List[GroupCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Папка с фотографиями для поиска дубликатов")
        self.path_edit.returnPressed.connect(self.start_search)
        btn_browse = QPushButton("Обзор…")
        btn_browse.clicked.connect(self.choose_folder)
        self.btn_search = QPushButton("Найти дубликаты")
        self.btn_search.setObjectName("accent")
        self.btn_search.clicked.connect(self.start_search)
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.cancel_search)
        self.btn_cancel.hide()
        controls.addWidget(self.path_edit, 1)
        controls.addWidget(btn_browse)
        controls.addWidget(self.btn_search)
        controls.addWidget(self.btn_cancel)
        layout.addLayout(controls)

        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        self.stage = QLabel("")
        self.stage.setObjectName("muted")
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.stage)
        layout.addLayout(progress_row)

        self.summary = QLabel(
            "Поиск похожих и пережатых копий: jpg, jpeg, png, webp, bmp · "
            "расстояние Хэмминга ≤ 4"
        )
        self.summary.setObjectName("muted")
        layout.addWidget(self.summary)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self._results = QWidget()
        self._results_layout = QVBoxLayout(self._results)
        self._results_layout.setContentsMargins(0, 0, 4, 0)
        self._results_layout.setSpacing(10)
        self._results_layout.addStretch(1)
        self.scroll.setWidget(self._results)
        layout.addWidget(self.scroll, 1)

    # ------------------------------------------------------------------ #

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с фото")
        if folder:
            self.path_edit.setText(folder)

    def start_search(self) -> None:
        path = self.path_edit.text().strip().strip('"')
        if not path:
            QMessageBox.information(self, "SpaceLens", "Укажите папку для поиска.")
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "SpaceLens", f"Каталог не найден:\n{path}")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._clear_cards()
        self._worker = DedupWorker(path, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_groups.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self.btn_search.setEnabled(False)
        self.btn_cancel.show()
        self.progress.setValue(0)
        self.progress.show()
        self.stage.setText("Поиск изображений…")
        self.summary.setText("Идёт поиск…")
        self._worker.start()

    def cancel_search(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self.btn_cancel.setEnabled(False)

    def _reset_controls(self) -> None:
        self.btn_search.setEnabled(True)
        self.btn_cancel.hide()
        self.btn_cancel.setEnabled(True)
        self.progress.hide()
        self.stage.setText("")

    def _on_progress(self, stage: str, done: int, total: int) -> None:
        self.stage.setText(f"{stage}: {done:,} / {total:,}")
        self.progress.setValue(int(done * 100 / max(total, 1)))

    def _on_finished(self, groups: List[List[ImageInfo]]) -> None:
        self._reset_controls()
        self._worker = None
        for i, group in enumerate(groups, start=1):
            card = GroupCard(i, group)
            card.changed.connect(self._on_card_changed)
            self._cards.append(card)
            self._results_layout.insertWidget(self._results_layout.count() - 1, card)
        self._update_summary()
        if not groups:
            self.summary.setText("Дубликаты не найдены.")

    def _on_failed(self, message: str) -> None:
        self._reset_controls()
        self._worker = None
        self.summary.setText("Ошибка поиска")
        QMessageBox.warning(self, "SpaceLens", f"Поиск не удался:\n{message}")

    def _on_cancelled(self) -> None:
        self._reset_controls()
        self._worker = None
        self.summary.setText("Поиск отменён")

    # ------------------------------------------------------------------ #

    def _on_card_changed(self) -> None:
        card = self.sender()
        if isinstance(card, GroupCard) and len(card.thumbs) < 2:
            if card in self._cards:
                self._cards.remove(card)
            card.setParent(None)
            card.deleteLater()
        self._update_summary()

    def _update_summary(self) -> None:
        if not self._cards:
            return
        dup_count = sum(len(c.thumbs) - 1 for c in self._cards)
        savings = sum(sum(t.info.size for t in c.thumbs[1:]) for c in self._cards)
        self.summary.setText(
            f"Групп: {len(self._cards)} · лишних файлов: {dup_count} · "
            f"можно освободить: {format_size(savings)}"
        )

    def _clear_cards(self) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []