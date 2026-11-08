"""Детектор визуально похожих изображений.

Конвейер:
  1. Обход каталога (os.scandir, без симлинков/junctions), отбор картинок
     по расширениям jpg/jpeg/png/webp/bmp.
  2. Быстрый фильтр: группировка по точному размеру файла — файлы с
     одинаковым размером и одинаковым хешем считаются дубликатами сразу.
  3. Для всех кандидатов вычисляется 64-битный разностный хеш (dHash,
     9x8 пикселей в градациях серого через Pillow).
  4. Поиск пар с расстоянием Хэмминга <= 4. Чтобы не сравнивать каждый с
     каждым, хеш разбивается на 5 полос: при <= 4 различающихся битах хотя
     бы одна полоса совпадает целиком (принцип Дирихле), поэтому пары-
     кандидаты берутся только из корзин с совпадающими полосами. Это
     находит и пережатые копии с другим размером файла.

Результат — группы файлов (>= 2), отсортированные по убыванию разрешения.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PIL import Image
from PySide6.QtCore import QThread, Signal

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
HAMMING_THRESHOLD = 4

_FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

# 5 полос, покрывающих все 64 бита: 13+13+13+13+12.
_BANDS: Tuple[Tuple[int, int], ...] = ((0, 13), (13, 26), (26, 39), (39, 52), (52, 64))


@dataclass
class ImageInfo:
    path: str
    size: int          # размер файла в байтах
    width: int
    height: int
    dhash: int

    @property
    def pixels(self) -> int:
        return self.width * self.height


def hamming(a: int, b: int) -> int:
    """Расстояние Хэмминга между двумя 64-битными хешами."""
    return bin(a ^ b).count("1")


def compute_dhash(path: str) -> Optional[Tuple[int, int, int]]:
    """(width, height, dhash) для изображения либо None, если файл битый."""
    try:
        with Image.open(path) as im:
            width, height = im.size
            # draft ускоряет JPEG: декодирование сразу в малый размер.
            try:
                im.draft("L", (9, 8))
            except Exception:  # noqa: BLE001 — не для всех форматов
                pass
            gray = im.convert("L").resize((9, 8), Image.LANCZOS)
            px = list(gray.getdata())
            bits = 0
            for row in range(8):
                base = row * 9
                for col in range(8):
                    bits = (bits << 1) | (1 if px[base + col] > px[base + col + 1] else 0)
            return width, height, bits
    except Exception:  # noqa: BLE001 — битые/нечитаемые файлы пропускаем
        return None


class _DedupCancelled(Exception):
    pass


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


class DedupWorker(QThread):
    """Фоновый поиск дубликатов.

    Сигналы:
        progress(str, int, int) — этап, выполнено, всего;
        finished_groups(list)   — список групп List[ImageInfo];
        cancelled();
        failed(str).
    """

    progress = Signal(str, int, int)
    finished_groups = Signal(object)
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, root_path: str, parent=None):
        super().__init__(parent)
        self.root_path = os.path.abspath(root_path)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _check_cancel(self) -> None:
        if self._cancelled:
            raise _DedupCancelled()

    # ------------------------------------------------------------------ #

    def run(self) -> None:  # noqa: D102
        try:
            if not os.path.isdir(self.root_path):
                raise NotADirectoryError(f"Каталог не существует: {self.root_path}")

            candidates = self._collect_images(self.root_path)
            if not candidates:
                self.finished_groups.emit([])
                return

            images = self._hash_all(candidates)
            groups = self._group_similar(images)
            self.finished_groups.emit(groups)
        except _DedupCancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def _collect_images(self, root: str) -> List[Tuple[str, int]]:
        """Обход дерева без симлинков/junctions; возврат (path, size)."""
        result: List[Tuple[str, int]] = []
        stack = [root]
        while stack:
            self._check_cancel()
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        self._check_cancel()
                        try:
                            st = entry.stat(follow_symlinks=False)
                            if entry.is_symlink() or (
                                getattr(st, "st_file_attributes", 0)
                                & _FILE_ATTRIBUTE_REPARSE_POINT
                            ):
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                if os.path.splitext(entry.name)[1].lower() in IMAGE_EXTS:
                                    result.append((entry.path, st.st_size))
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
                continue
        return result

    def _hash_all(self, candidates: List[Tuple[str, int]]) -> List[ImageInfo]:
        images: List[ImageInfo] = []
        total = len(candidates)
        for idx, (path, size) in enumerate(candidates):
            self._check_cancel()
            hashed = compute_dhash(path)
            if hashed is not None:
                w, h, dhash = hashed
                images.append(ImageInfo(path, size, w, h, dhash))
            if idx % 10 == 0 or idx == total - 1:
                self.progress.emit("Вычисление хешей", idx + 1, total)
        return images

    def _group_similar(self, images: List[ImageInfo]) -> List[List[ImageInfo]]:
        n = len(images)
        uf = _UnionFind(n)

        # Быстрый фильтр: одинаковый размер файла + одинаковый хеш.
        by_size_hash: Dict[Tuple[int, int], int] = {}
        for i, img in enumerate(images):
            key = (img.size, img.dhash)
            if key in by_size_hash:
                uf.union(i, by_size_hash[key])
            else:
                by_size_hash[key] = i

        # Поиск визуально похожих (в т.ч. пережатых, с другим размером):
        # корзины по 5 полосам хеша, затем точная проверка Хэмминга <= 4.
        buckets: Dict[Tuple[int, int], List[int]] = {}
        for i, img in enumerate(images):
            self._check_cancel()
            for band_idx, (lo, hi) in enumerate(_BANDS):
                key = (band_idx, (img.dhash >> lo) & ((1 << (hi - lo)) - 1))
                for j in buckets.get(key, ()):
                    if uf.find(i) != uf.find(j) and hamming(img.dhash, images[j].dhash) <= HAMMING_THRESHOLD:
                        uf.union(i, j)
                buckets.setdefault(key, []).append(i)
            if i % 200 == 0:
                self.progress.emit("Сравнение изображений", i + 1, n)

        clusters: Dict[int, List[int]] = {}
        for i in range(n):
            clusters.setdefault(uf.find(i), []).append(i)

        groups: List[List[ImageInfo]] = []
        for members in clusters.values():
            if len(members) < 2:
                continue
            # Оригиналы (наибольшее разрешение) — первыми.
            group = sorted((images[i] for i in members),
                           key=lambda im: (im.pixels, im.size), reverse=True)
            groups.append(group)

        # Крупные потенциально освобождаемые группы — выше.
        groups.sort(key=lambda g: sum(im.size for im in g[1:]), reverse=True)
        return groups