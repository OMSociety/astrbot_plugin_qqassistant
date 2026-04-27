"""qqassistant 测试夹具与辅助工具"""

import io
import struct
import zlib
from pathlib import Path

import pytest

# ═══════════════════════════════════════════════
# 插件路径辅助
# ═══════════════════════════════════════════════


@pytest.fixture
def plugin_dir():
    return Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════
# 最小 PNG（测试用）
# ═══════════════════════════════════════════════


@pytest.fixture
def minimal_png_bytes():
    """1×1 红色 PNG"""

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\x00"
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def minimal_png_stream(minimal_png_bytes):
    return io.BytesIO(minimal_png_bytes)
