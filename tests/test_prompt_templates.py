"""Tests for prompt template rendering (uses the real files under prompt/)."""

from pathlib import Path

from src.manim.builder import render_prompt_template
from src.options import ExplanationOptions

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompt"

_EXPLANATION = (_PROMPT_DIR / "ProblemExplanation.md").read_text(encoding="utf-8")
_CODEGEN = (_PROMPT_DIR / "CodeGeneration.md").read_text(encoding="utf-8")
_CODE_REVIEW = (_PROMPT_DIR / "CodeReview.md").read_text(encoding="utf-8")


def _context(options: ExplanationOptions, **extra) -> dict:
    ctx = {
        "ref_audio_path": "/audio/ref.wav",
        "options": options,
        "enabled_sections": options.enabled_labels(),
    }
    ctx.update(extra)
    return ctx


class TestProblemExplanationTemplate:
    def test_default_renders_all_modules(self):
        text = render_prompt_template(_EXPLANATION, **_context(ExplanationOptions()))
        for header in ("【题目原文】", "【题目知识点】", "【题目解答】",
                       "【题目答案】", "【题目答案验证】", "【考点、重点、难点】"):
            assert header in text
        assert "【练习与复习方法】" in text
        assert "{{" not in text and "{%" not in text

    def test_disabled_modules_are_removed(self):
        options = ExplanationOptions.from_selection(["solution_process"])
        text = render_prompt_template(_EXPLANATION, **_context(options))
        assert "【题目解答】" in text
        assert "【题目原文】" not in text
        assert "【题目知识点】" not in text
        assert "【题目答案验证】" not in text

    def test_answer_module_always_present(self):
        options = ExplanationOptions.from_selection(["restatement"])
        text = render_prompt_template(_EXPLANATION, **_context(options))
        assert "【题目答案】" in text  # never removable
        assert "【题目原文】" in text

    def test_brief_solution_switches_instruction(self):
        detailed_ctx = _context(ExplanationOptions(brief_solution=False))
        brief_ctx = _context(ExplanationOptions(brief_solution=True))
        assert "简要讲解解题思路" not in render_prompt_template(_EXPLANATION, **detailed_ctx)
        assert "简要讲解解题思路" in render_prompt_template(_EXPLANATION, **brief_ctx)

    def test_enabled_module_list_matches_selection(self):
        options = ExplanationOptions.from_selection(
            ["knowledge_points", "common_mistakes"]
        )
        text = render_prompt_template(_EXPLANATION, **_context(options))
        assert "- 知识点总结" in text
        assert "- 易错考点" in text
        assert "- 题目复述" not in text


class TestCodeGenerationTemplate:
    def test_lists_selected_modules(self):
        options = ExplanationOptions.from_selection(
            ["solution_process", "answer_verification"]
        )
        text = render_prompt_template(_CODEGEN, **_context(options))
        assert "- 题目解答过程" in text
        assert "- 答案验证" in text
        assert "- 题目复述" not in text

    def test_ref_audio_path_injected(self):
        text = render_prompt_template(_CODEGEN, **_context(ExplanationOptions()))
        assert repr("/audio/ref.wav") in text

    def test_problem_context_variables(self):
        ctx = _context(ExplanationOptions())

        text_text = render_prompt_template(
            _CODEGEN,
            problem_text="已知直角三角形两直角边为3和4，求斜边。",
            has_problem_image=False,
            **ctx,
        )
        assert "题目原文文本如下，请以该文本为准理解题意" in text_text
        assert "已随用户消息直接附带" not in text_text

        text_img = render_prompt_template(
            _CODEGEN,
            problem_text="",
            has_problem_image=True,
            **ctx,
        )
        assert "原题为图片，已随用户消息直接附带" in text_img

        text_none = render_prompt_template(
            _CODEGEN,
            problem_text="",
            has_problem_image=False,
            **ctx,
        )
        assert "未提供原题" in text_none

        # Jinja 条件渲染后不应残留模板语法
        for text in (text_text, text_img, text_none):
            assert "{%" not in text
            assert "{{" not in text

    def test_json_output_format_preserved(self):
        text = render_prompt_template(_CODEGEN, **_context(ExplanationOptions()))
        assert '"Scene Name"' in text
        assert "BailianService(ref_audio_path=" in text


class TestCodeReviewTemplate:
    def test_reviewer_sees_required_modules(self):
        options = ExplanationOptions.from_selection(
            ["restatement", "practice_methods"]
        )
        text = render_prompt_template(_CODE_REVIEW, **_context(options))
        assert "- 题目复述" in text
        assert "- 练习方法、复习方法" in text

    def test_ref_audio_path_still_injected(self):
        text = render_prompt_template(_CODE_REVIEW, **_context(ExplanationOptions()))
        assert repr("/audio/ref.wav") in text


class TestRenderPromptTemplate:
    def test_missing_variable_renders_empty(self):
        # Jinja2 default: undefined variables render as empty string
        assert render_prompt_template("Hi {{ missing_var }}!") == "Hi !"

    def test_plain_text_passthrough(self):
        assert render_prompt_template("no vars here") == "no vars here"
