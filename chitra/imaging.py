"""Image decoding, EXIF dates and thumbnails."""

import io
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Optional

from PIL import Image, ImageOps

from .config import DRAFT_SIZE, THUMB_SIZE

try:  # optional HEIC/HEIF support (iPhone photos)
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

Image.MAX_IMAGE_PIXELS = 400_000_000  # allow large panoramas without DecompressionBombError

EXIF_IFD = 0x8769
DATETIME_ORIGINAL = 36867
DATETIME = 306


class LoadedImage(NamedTuple):
    image: Image.Image  # RGB, downscaled for the model
    width: int  # original dimensions
    height: int
    taken_at: Optional[str]  # ISO timestamp from EXIF, if present


def read_taken_at(img: Image.Image) -> Optional[str]:
    try:
        exif = img.getexif()
        value = exif.get_ifd(EXIF_IFD).get(DATETIME_ORIGINAL) or exif.get(DATETIME)
        if value:
            return datetime.strptime(str(value).strip()[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        pass
    return None


def load_image(path: Path) -> LoadedImage:
    with Image.open(path) as img:
        width, height = img.size
        taken_at = read_taken_at(img)
        img.draft("RGB", (DRAFT_SIZE, DRAFT_SIZE))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.getchannel("A"))
            img = background
        else:
            img = img.convert("RGB")
    return LoadedImage(img, width, height, taken_at)


def save_thumbnail(img: Image.Image, dest: Path) -> None:
    thumb = img.copy()
    thumb.thumbnail((THUMB_SIZE, THUMB_SIZE))
    thumb.save(dest, "JPEG", quality=82)


def to_jpeg_bytes(path: Path) -> bytes:
    """Convert formats browsers can't show (HEIC, TIFF) to JPEG."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
    return buf.getvalue()
