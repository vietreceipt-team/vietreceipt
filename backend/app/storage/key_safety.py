from pathlib import PurePosixPath

def validate_object_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    raw_parts = key.split("/")
    if not key or path.is_absolute() or "\\" in key or any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("Object key must be a safe relative POSIX path")
    return path
