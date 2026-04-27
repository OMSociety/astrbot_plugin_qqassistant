"""ConfigNode / PluginConfig 纯逻辑测试

使用 SimpleNamespace 模拟 AstrBotConfig，不依赖框架运行时。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import ConfigNode

# ═══════════════════════════════════════════════
# 测试用 ConfigNode 子类
# ═══════════════════════════════════════════════


class InnerNode(ConfigNode):
    """嵌套配置节点"""

    name: str
    enabled: bool


class RootNode(ConfigNode):
    """根配置（模拟 PluginConfig 结构）"""

    platform: str
    divided_manage: bool
    default: dict
    inner: InnerNode
    _secret: str = "hidden"


# ═══════════════════════════════════════════════
# ConfigNode 基础读写
# ═══════════════════════════════════════════════


class TestConfigNodeBasic:
    def test_declared_read(self):
        node = RootNode({"platform": "qq", "divided_manage": False, "default": {}})
        assert node.platform == "qq"
        assert node.divided_manage is False
        assert node.default == {}

    def test_declared_write(self):
        node = RootNode({"platform": "qq", "divided_manage": False, "default": {}})
        node.platform = "wechat"
        assert node.platform == "wechat"
        assert node.raw_data()["platform"] == "wechat"

    def test_missing_nested_raises_type_error(self):
        """未提供的嵌套 ConfigNode 字段在访问时应抛 TypeError（非 None）"""
        node = RootNode({"platform": "qq", "divided_manage": False, "default": {}})
        with pytest.raises(TypeError, match="期望 dict"):
            _ = node.inner

    def test_raw_data_is_readonly_view(self):
        node = RootNode({"platform": "qq", "divided_manage": True, "default": {}})
        raw = node.raw_data()
        assert raw["platform"] == "qq"
        # raw_data 应反映最新值
        node.platform = "wechat"
        assert node.raw_data()["platform"] == "wechat"

    def test_underscore_not_written_to_dict(self):
        """_ 前缀字段不写回 dict"""
        node = RootNode({"platform": "qq", "divided_manage": False, "default": {}})
        node._secret = "new_secret"
        assert node._secret == "new_secret"
        assert "_secret" not in node.raw_data()


# ═══════════════════════════════════════════════
# ConfigNode 嵌套
# ═══════════════════════════════════════════════


class TestConfigNodeNesting:
    def test_nested_node_read(self):
        node = RootNode(
            {
                "platform": "qq",
                "divided_manage": False,
                "default": {},
                "inner": {"name": "test", "enabled": True},
            }
        )
        assert node.inner.name == "test"
        assert node.inner.enabled is True

    def test_nested_node_write(self):
        node = RootNode(
            {
                "platform": "qq",
                "divided_manage": False,
                "default": {},
                "inner": {"name": "test", "enabled": True},
            }
        )
        node.inner.name = "updated"
        assert node.inner.name == "updated"
        assert node.raw_data()["inner"]["name"] == "updated"

    def test_nested_node_cache(self):
        """同一嵌套节点应缓存（同一对象）"""
        node = RootNode(
            {
                "platform": "qq",
                "divided_manage": False,
                "default": {},
                "inner": {"name": "test", "enabled": True},
            }
        )
        a = node.inner
        b = node.inner
        assert a is b

    def test_nested_wrong_type_raises(self):
        """inner 字段期望 dict 但给了字符串应抛错"""
        node = RootNode(
            {
                "platform": "qq",
                "divided_manage": False,
                "default": {},
                "inner": "not_a_dict",
            }
        )
        with pytest.raises(TypeError, match="期望 dict"):
            _ = node.inner.name
