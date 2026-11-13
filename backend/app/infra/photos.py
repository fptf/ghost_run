"""Фото к треку: перекодирование без EXIF (координаты съёмки не должны утечь)."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}
MAX_SIDE = 2048


class BadPhotoError(ValueError):
    pass


def sanitize(data: bytes) -> tuple[bytes, str, str]:
    """Возвращает (байты, content-type, расширение) без метаданных."""
    try:
        opened = Image.open(io.BytesIO(data))
        fmt = opened.format or ""
        if fmt not in ALLOWED:
            raise BadPhotoError(fmt)
        img: Image.Image = ImageOps.exif_transpose(opened)
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    except (UnidentifiedImageError, OSError) as exc:
        raise BadPhotoError("unreadable") from exc
    if fmt == "JPEG" and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out = io.BytesIO()
    # Сохраняем без exif/icc/xmp: Pillow не переносит метаданные, если их не передать явно.
    img.save(out, format=fmt, **({"quality": 88} if fmt != "PNG" else {}))
    content_type, ext = ALLOWED[fmt]
    return out.getvalue(), content_type, ext
