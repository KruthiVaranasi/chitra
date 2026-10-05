"""Shared constants."""

INDEX_DIRNAME = ".chitra"
DEFAULT_MODEL = "google/siglip-base-patch16-224"

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif",
    ".tif", ".tiff", ".heic", ".heif",
}
# Formats browsers can display directly; everything else is converted to JPEG when served.
BROWSER_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

# Directories never worth scanning (system folders on removable drives, tool caches).
SKIP_DIRS = {
    INDEX_DIRNAME, "$RECYCLE.BIN", "System Volume Information", "node_modules",
    "__pycache__", ".git", ".Trash", ".Trashes", ".Spotlight-V100", ".fseventsd",
}

THUMB_SIZE = 320
DRAFT_SIZE = 512  # JPEG decode target; models only need ~224px, so decoding full-res is wasted work
