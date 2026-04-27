"""utils 模块纯函数测试"""

import sys
from pathlib import Path

import pytest

# 确保插件在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils import format_time, parse_bool

# ═══════════════════════════════════════════════
# parse_bool
# ═══════════════════════════════════════════════


class TestParseBool:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("开", True),
            ("开启", True),
            ("启用", True),
            ("on", True),
            ("ON", True),
            ("true", True),
            ("1", True),
            ("是", True),
            ("真", True),
            ("关", False),
            ("关闭", False),
            ("禁用", False),
            ("off", False),
            ("OFF", False),
            ("false", False),
            ("0", False),
            ("否", False),
            ("假", False),
        ],
    )
    def test_valid_values(self, raw, expected):
        assert parse_bool(raw) is expected

    @pytest.mark.parametrize("raw", ["", "   ", "maybe", "yes", "no"])
    def test_invalid_values(self, raw):
        assert parse_bool(raw) is None

    def test_bool_input_passthrough(self):
        """布尔值应原样返回"""
        assert parse_bool(True) is True
        assert parse_bool(False) is False

    def test_stripped_whitespace(self):
        """带前后空白应正确解析"""
        assert parse_bool(" 开 ") is True
        assert parse_bool("\t关\n") is False


# ═══════════════════════════════════════════════
# format_time
# ═══════════════════════════════════════════════


class TestFormatTime:
    def test_epoch(self):
        """Unix 纪元 0 → 1970-01-01"""
        assert format_time(0) == "1970-01-01"

    def test_known_date(self):
        """2000-01-01 UTC 午夜"""
        assert format_time(946684800) == "2000-01-01"

    def test_2025_some_day(self):
        """2025-06-15 正午 UTC"""
        assert format_time(1749974400) == "2025-06-15"

    def test_negative_timestamp(self):
        """负时间戳应能正常格式化"""
        result = format_time(-1)
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD
