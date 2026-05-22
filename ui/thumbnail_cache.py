"""Shared product thumbnail cache for image-heavy product views."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


class ThumbnailCache:
    """Caches scaled thumbnails keyed by image path, size, and file mtime."""

    _cache: OrderedDict[tuple[str, int, int, int], QPixmap] = OrderedDict()
    _max_items = 512

    @classmethod
    def get(
        cls,
        image_path: str,
        width: int,
        height: int,
        base_dir: Path | None = None,
    ) -> QPixmap:
        resolved_path = cls.resolve_path(image_path, base_dir)
        if resolved_path is None:
            return QPixmap()

        try:
            mtime_ns = resolved_path.stat().st_mtime_ns
        except OSError:
            return QPixmap()

        cache_key = (str(resolved_path), width, height, mtime_ns)
        cached = cls._cache.get(cache_key)
        if cached is not None:
            cls._cache.move_to_end(cache_key)
            return cached

        source_pixmap = QPixmap(str(resolved_path))
        if source_pixmap.isNull():
            return QPixmap()

        thumbnail = source_pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        cls._cache[cache_key] = thumbnail
        cls._cache.move_to_end(cache_key)
        while len(cls._cache) > cls._max_items:
            cls._cache.popitem(last=False)
        return thumbnail

    @staticmethod
    def resolve_path(image_path: str, base_dir: Path | None = None) -> Path | None:
        if not image_path:
            return None

        resolved_path = Path(image_path)
        if not resolved_path.is_absolute() and base_dir is not None:
            resolved_path = base_dir / resolved_path
        return resolved_path if resolved_path.exists() else None

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()
