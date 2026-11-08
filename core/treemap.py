"""Squarified Treemap (алгоритм Брюльса, Хёйзинга и ван Вейка).

Прямоугольники стремятся к квадрату: строки элементов укладываются вдоль
короткой стороны контейнера, пока это улучшает худшее соотношение сторон.
Веса нормализуются по площади контейнера; нулевые веса и пустые контейнеры
обрабатываются корректно (вырожденные прямоугольники нулевой площади).
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

Rect = Tuple[float, float, float, float]  # x, y, w, h

_EPS = 1e-9


def _worst(row: Sequence[float], side: float) -> float:
    """Худшее (максимальное) соотношение сторон в строке вдоль стороны side."""
    s = sum(row)
    if s <= _EPS or side <= _EPS:
        return float("inf")
    rmax, rmin = max(row), min(row)
    if rmin <= _EPS:
        return float("inf")
    side2, s2 = side * side, s * s
    return max(side2 * rmax / s2, s2 / (side2 * rmin))


def squarify(values: Sequence[float], x: float, y: float,
             w: float, h: float) -> List[Rect]:
    """Разбить контейнер (x, y, w, h) на прямоугольники пропорционально values.

    Порядок результата совпадает с порядком values (обычно отсортирован
    по убыванию). Нулевые веса получают вырожденные прямоугольники.
    Итеративная реализация — безопасна для сотен тысяч элементов.
    """
    n = len(values)
    rects: List[Rect] = [(x, y, 0.0, 0.0)] * n
    if n == 0 or w <= _EPS or h <= _EPS:
        return rects

    total = sum(max(v, 0.0) for v in values)
    if total <= _EPS:
        return rects

    # Нормализация весов по площади контейнера.
    scale = (w * h) / total
    areas = [max(v, 0.0) * scale for v in values]

    i = 0
    while i < n:
        if w <= _EPS or h <= _EPS:
            break
        if i == n - 1:
            rects[i] = (x, y, w, h)
            break

        short = min(w, h)
        row = [areas[i]]
        j = i + 1
        # Наращиваем строку, пока худший aspect ratio не ухудшается.
        while j < n:
            candidate = row + [areas[j]]
            if _worst(candidate, short) <= _worst(row, short):
                row = candidate
                j += 1
            else:
                break

        row_area = sum(row)
        if w >= h:
            # Вертикальная полоса слева.
            strip_w = row_area / h
            cy = y
            for k in range(i, j):
                rh = areas[k] / strip_w if strip_w > _EPS else 0.0
                rects[k] = (x, cy, strip_w, rh)
                cy += rh
            x += strip_w
            w -= strip_w
        else:
            # Горизонтальная полоса сверху.
            strip_h = row_area / w
            cx = x
            for k in range(i, j):
                rw = areas[k] / strip_h if strip_h > _EPS else 0.0
                rects[k] = (cx, y, rw, strip_h)
                cx += rw
            y += strip_h
            h -= strip_h
        i = j

    return rects