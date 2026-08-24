"""Tests for src.llm.parser — LLM response parsing (pure logic)."""

import pytest

from src.llm.parser import (
    GeneratedScene,
    ParseError,
    _extract_json_from_text,
    _strip_code_fences,
    parse_code_generation_response,
)


class TestStripCodeFences:
    def test_json_fence(self):
        text = '```json\n{"Scene Name": "S"}\n```'
        assert _strip_code_fences(text) == '{"Scene Name": "S"}'

    def test_plain_fence(self):
        text = '```\n{"a": 1}\n```'
        assert _strip_code_fences(text) == '{"a": 1}'

    def test_no_fence_strips_whitespace(self):
        assert _strip_code_fences('  {"a": 1}  ') == '{"a": 1}'

    def test_unbalanced_fence_returned_as_is(self):
        text = '```json\n{"a": 1}'
        assert _strip_code_fences(text) == '```json\n{"a": 1}'


class TestExtractJson:
    def test_direct_parse(self):
        data = _extract_json_from_text('{"Scene Name": "S", "Code": "C"}')
        assert data == {"Scene Name": "S", "Code": "C"}

    def test_fenced_parse(self):
        text = '```json\n{"Scene Name": "S", "Code": "C"}\n```'
        assert _extract_json_from_text(text)["Scene Name"] == "S"

    def test_embedded_in_prose(self):
        text = (
            "好的，以下是生成的代码：\n"
            '{"Scene Name": "MyScene", "Code": "x = 1"}\n'
            "希望对你有帮助！"
        )
        assert _extract_json_from_text(text)["Code"] == "x = 1"

    def test_invalid_returns_none(self):
        assert _extract_json_from_text("totally not json") is None


class TestParseCodeGenerationResponse:
    def test_valid_response(self):
        scene = parse_code_generation_response(
            '{"Scene Name": "PythagoreanScene", "Code": "from manim import *"}'
        )
        assert isinstance(scene, GeneratedScene)
        assert scene.scene_name == "PythagoreanScene"
        assert scene.code == "from manim import *"

    def test_fenced_valid_response(self):
        response = (
            "```json\n"
            '{"Scene Name": "MyScene", "Code": "print(1)"}\n'
            "```"
        )
        scene = parse_code_generation_response(response)
        assert scene.scene_name == "MyScene"

    def test_empty_response_raises(self):
        with pytest.raises(ParseError, match="empty"):
            parse_code_generation_response("")

    def test_whitespace_only_response_raises(self):
        with pytest.raises(ParseError):
            parse_code_generation_response("   \n\t  ")

    def test_non_json_raises(self):
        with pytest.raises(ParseError, match="JSON"):
            parse_code_generation_response("I cannot do that.")

    def test_missing_scene_name_raises(self):
        with pytest.raises(ParseError, match="Scene Name"):
            parse_code_generation_response('{"Code": "x = 1"}')

    def test_missing_code_raises(self):
        with pytest.raises(ParseError, match="Code"):
            parse_code_generation_response('{"Scene Name": "S"}')

    def test_empty_code_raises(self):
        with pytest.raises(ParseError, match="Code"):
            parse_code_generation_response('{"Scene Name": "S", "Code": ""}')

    def test_non_string_code_raises(self):
        with pytest.raises(ParseError, match="string"):
            payload = '{"Scene Name": "S", "Code": ["line1"]}'
            parse_code_generation_response(payload)

    def test_scene_name_coerced_to_str(self):
        scene = parse_code_generation_response(
            '{"Scene Name": 12345, "Code": "c"}'
        )
        assert scene.scene_name == "12345"

    def test_code_with_escaped_newlines(self):
        # \n inside the JSON payload decodes to a real newline character
        scene = parse_code_generation_response(
            '{"Scene Name": "S", "Code": "line1\\nline2"}'
        )
        assert scene.code == "line1\nline2"
