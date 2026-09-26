"""Keep dependency patches from invalidating unchanged compiler inputs."""

from pathlib import Path


def write_text_if_changed(path: Path, text: str, encoding: str = "utf-8") -> None:
    if path.read_text(encoding=encoding) != text:
        path.write_text(text, encoding=encoding)
