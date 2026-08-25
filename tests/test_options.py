"""Tests for src.core.options — user-customizable explanation modules."""

import pytest

from src.options import SECTION_LABELS, ExplanationOptions


class TestDefaults:
    def test_all_main_sections_enabled_by_default(self):
        options = ExplanationOptions()
        assert options.enabled_sections() == list(SECTION_LABELS)

    def test_brief_solution_disabled_by_default(self):
        assert ExplanationOptions().brief_solution is False

    def test_labels_match_keys(self):
        options = ExplanationOptions()
        assert options.enabled_labels() == [
            "题目复述",
            "知识点总结",
            "题目解答过程",
            "答案验证",
            "易错考点",
            "练习方法、复习方法",
        ]


class TestValidation:
    def test_empty_selection_raises(self):
        with pytest.raises(ValueError, match="至少"):
            ExplanationOptions(
                restatement=False,
                knowledge_points=False,
                solution_process=False,
                answer_verification=False,
                common_mistakes=False,
                practice_methods=False,
            )

    def test_brief_implies_solution_process(self):
        options = ExplanationOptions(
            solution_process=False,
            brief_solution=True,
            restatement=False,
            knowledge_points=False,
            answer_verification=False,
            common_mistakes=False,
            practice_methods=False,
        )
        assert options.solution_process is True
        assert options.brief_solution is True

    def test_from_selection_unknown_key_raises(self):
        with pytest.raises(ValueError, match="未知的讲解模块"):
            ExplanationOptions.from_selection(["no_such_section"])


class TestFromSelection:
    def test_none_uses_defaults(self):
        options = ExplanationOptions.from_selection(None)
        assert options == ExplanationOptions()

    def test_partial_selection_disables_rest(self):
        options = ExplanationOptions.from_selection(
            ["restatement", "solution_process"]
        )
        assert options.restatement is True
        assert options.solution_process is True
        assert options.knowledge_points is False
        assert options.answer_verification is False
        assert options.common_mistakes is False
        assert options.practice_methods is False

    def test_brief_flag_sets_sub_option(self):
        options = ExplanationOptions.from_selection(
            ["solution_process"], brief=True
        )
        assert options.brief_solution is True

    def test_accepts_set_and_tuple(self):
        a = ExplanationOptions.from_selection({"knowledge_points"})
        b = ExplanationOptions.from_selection(("knowledge_points",))
        assert a == b


class TestHelpers:
    def test_with_brief_returns_modified_copy(self):
        original = ExplanationOptions()
        modified = original.with_brief(True)
        assert modified.brief_solution is True
        assert original.brief_solution is False  # unchanged (frozen)

    def test_summary_contains_selected_modules(self):
        options = ExplanationOptions.from_selection(["solution_process"], brief=True)
        summary = options.summary()
        assert "题目解答过程" in summary
        assert "简略解答" in summary
        assert "题目复述" not in summary
