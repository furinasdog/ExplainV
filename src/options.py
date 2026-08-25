"""
User-customizable explanation modules for ExplainV.

Users select which content modules the generated video should cover
(checkboxes in the web UI / ``--sections`` on the CLI). The selection is
injected into every LLM prompt template (ProblemExplanation.md,
CodeGeneration.md, CodeReview.md) so all models agree on what must be
explained.

Usage::

    from src.core.options import ExplanationOptions

    options = ExplanationOptions.from_selection(
        ["knowledge_points", "solution_process"], brief=True
    )
    pipe = Pipeline(options=options)
"""

from dataclasses import dataclass, replace

# Option key -> Chinese label shown in the UI / prompts.
SECTION_LABELS: dict[str, str] = {
    "restatement": "题目复述",
    "knowledge_points": "知识点总结",
    "solution_process": "题目解答过程",
    "answer_verification": "答案验证",
    "common_mistakes": "易错考点",
    "practice_methods": "练习方法、复习方法",
}

# Label of the sub-option that only applies when solution_process is enabled.
BRIEF_SOLUTION_LABEL = "简略解答（仅讲解思路）"


@dataclass(frozen=True)
class ExplanationOptions:
    """Which explanation modules the video should contain.

    Attributes:
        restatement:         题目复述（【题目原文】模块）。
        knowledge_points:    知识点总结（【题目知识点】模块）。
        solution_process:    题目解答过程（【题目解答】模块）。
        brief_solution:      简略解答，仅讲思路不展开计算；
                             隐含要求 ``solution_process=True``。
        answer_verification: 答案验证（【题目答案验证】模块）。
        common_mistakes:     易错考点（【考点、重点、难点】模块）。
        practice_methods:    练习方法、复习方法（新增模块）。

    Note:
        【题目答案】始终保留——它不在可勾选范围内，且是答案验证的前提。
    """

    restatement: bool = True
    knowledge_points: bool = True
    solution_process: bool = True
    brief_solution: bool = False
    answer_verification: bool = True
    common_mistakes: bool = True
    practice_methods: bool = True

    def __post_init__(self) -> None:
        if self.brief_solution and not self.solution_process:
            # 勾选"简略解答"即视为同时勾选"题目解答过程"
            object.__setattr__(self, "solution_process", True)
        if not any(
            getattr(self, key) for key in SECTION_LABELS
        ):
            raise ValueError("至少需要启用一个讲解模块")

    # -- Constructors --------------------------------------------------------

    @classmethod
    def from_selection(
        cls,
        selected: "list[str] | set[str] | tuple[str, ...] | None",
        brief: bool = False,
    ) -> "ExplanationOptions":
        """Build options from a collection of enabled section keys.

        Args:
            selected: Enabled section keys (see :data:`SECTION_LABELS`).
                      ``None`` means the default selection (all except
                      *brief*).
            brief:    Whether the 简略解答 sub-option is checked. Implies
                      ``solution_process``.

        Raises:
            ValueError: If an unknown section key is passed or nothing
                        would be enabled.
        """
        if selected is None:
            return cls(brief_solution=brief)

        unknown = set(selected) - set(SECTION_LABELS)
        if unknown:
            raise ValueError(f"未知的讲解模块: {sorted(unknown)}")

        kwargs = dict.fromkeys(SECTION_LABELS, False)
        for key in selected:
            kwargs[key] = True
        kwargs["brief_solution"] = brief
        return cls(**kwargs)

    def with_brief(self, brief: bool) -> "ExplanationOptions":
        """Return a copy with the 简略解答 flag set to *brief*."""
        return replace(self, brief_solution=brief)

    # -- Prompt helpers ------------------------------------------------------

    def enabled_sections(self) -> list[str]:
        """Enabled section keys, ordered as defined in :data:`SECTION_LABELS`."""
        return [key for key in SECTION_LABELS if getattr(self, key)]

    def enabled_labels(self) -> list[str]:
        """Chinese labels of the enabled sections (prompt/UI friendly)."""
        return [SECTION_LABELS[key] for key in self.enabled_sections()]

    def summary(self) -> str:
        """One-line human-readable summary, e.g. for logs."""
        parts = self.enabled_labels()
        if self.brief_solution and self.solution_process:
            parts[parts.index("题目解答过程")] += f"（{BRIEF_SOLUTION_LABEL}）"
        return "、".join(parts)
