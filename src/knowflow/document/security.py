"""Upload boundary checks."""

from pathlib import PurePath


def validate_filename(filename: str) -> str:
    if not filename or PurePath(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("INVALID_FILENAME")
    return filename
