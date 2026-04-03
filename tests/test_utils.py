from pathlib import Path
from app.utils import safe_join, format_bytes


def test_safe_join_prevents_traversal(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "file.txt").write_text("ok")

    result = safe_join(base, "file.txt")
    assert result.name == "file.txt"

    with pytest.raises(ValueError, match="路径穿越"):
        safe_join(base, "../outside.txt")


def test_format_bytes():
    assert format_bytes(512) == "512.0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"


import pytest
