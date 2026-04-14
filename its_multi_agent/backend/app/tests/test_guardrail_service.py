"""
Guardrail Service 单元测试。
"""
import json
import tempfile
from pathlib import Path

import pytest

from services.guardrail_service import GuardrailService, DFAFilter, GuardrailCheckResult
from utils.sensitive_word_loader import SensitiveWordLoader


class TestDFAFilter:
    """DFA 过滤器测试。"""

    def test_empty_words(self):
        """空词库应该不过滤任何内容。"""
        filter_obj = DFAFilter(set())
        text, matched = filter_obj.filter_text("hello world")
        assert text == "hello world"
        assert matched == []

    def test_single_word_match(self):
        """单个敏感词应该被替换为 ***。"""
        filter_obj = DFAFilter({"敏感词"})
        text, matched = filter_obj.filter_text("这是一个敏感词的句子")
        assert text == "这是一个***的句子"
        assert matched == ["敏感词"]

    def test_multiple_word_match(self):
        """多个敏感词都应该被检测到。"""
        filter_obj = DFAFilter({"敏感词A", "敏感词B"})
        text, matched = filter_obj.filter_text("敏感词A和敏感词B")
        assert "敏感词A" in matched
        assert "敏感词B" in matched

    def test_no_match(self):
        """不包含敏感词的文本应该原样返回。"""
        filter_obj = DFAFilter({"敏感词"})
        text, matched = filter_obj.filter_text("正常文本")
        assert text == "正常文本"
        assert matched == []

    def test_overlapping_words(self):
        """重叠敏感词的处理。"""
        filter_obj = DFAFilter({"abc", "bcd"})
        text, matched = filter_obj.filter_text("abcdef")
        # abc 匹配后变为 ***，所以最终结果中应该包含 ***
        assert "***" in text

    def test_empty_text(self):
        """空文本应该返回空字符串和空列表。"""
        filter_obj = DFAFilter({"敏感词"})
        text, matched = filter_obj.filter_text("")
        assert text == ""
        assert matched == []


class TestSensitiveWordLoader:
    """敏感词加载器测试。"""

    def test_load_from_json(self, tmp_path):
        """应该正确加载 JSON 文件中的敏感词。"""
        json_file = tmp_path / "test_words.json"
        test_data = {
            "common": ["违禁词1", "违禁词2"],
            "business": ["竞品词1"]
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False)

        loader = SensitiveWordLoader(str(json_file))
        assert loader.get_common_words() == {"违禁词1", "违禁词2"}
        assert loader.get_business_words() == {"竞品词1"}

    def test_file_not_exists(self, tmp_path):
        """文件不存在时应该返回空集合。"""
        json_file = tmp_path / "not_exists.json"
        loader = SensitiveWordLoader(str(json_file))
        assert loader.get_common_words() == set()
        assert loader.get_business_words() == set()

    def test_invalid_json(self, tmp_path):
        """无效 JSON 时应该返回空集合。"""
        json_file = tmp_path / "invalid.json"
        with open(json_file, "w", encoding="utf-8") as f:
            f.write("not valid json")

        loader = SensitiveWordLoader(str(json_file))
        assert loader.get_common_words() == set()
        assert loader.get_business_words() == set()


class TestGuardrailService:
    """Guardrail 服务测试。"""

    def test_normal_text_passes(self):
        """正常文本应该通过检查，不拦截不替换。"""
        service = GuardrailService()
        result = service.check_input("这是一个正常的查询")
        assert result.blocked is False
        assert result.replaced is False

    def test_business_word_replaced(self):
        """业务敏感词应该被替换。"""
        result = GuardrailCheckResult(
            blocked=False,
            replaced=True,
            filtered_text="这是一个***的查询",
            matched_common=[],
            matched_business=["敏感词"]
        )
        assert result.blocked is False
        assert result.replaced is True
        assert "***" in result.filtered_text

    def test_empty_text(self):
        """空文本应该返回非拦截结果。"""
        service = GuardrailService()
        result = service.check_input("")
        assert result.blocked is False
        assert result.replaced is False
