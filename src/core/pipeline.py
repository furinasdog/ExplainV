"""
ExplainV core pipeline.

Orchestrates the full video-generation flow:

    Problem (text/image)
        → Step 1: LLM explanation  (ProblemExplanation.md)
        → Step 2: LLM code gen     (CodeGeneration.md + Jinja2)
        → Step 3: Parse response
        → Step 3.5: LLM code review (CodeReview.md — layout/overlap check)
        → Step 4: Write script & render with Manim
        → Output: MP4 video

Usage::

    from src.core import Pipeline

    pipe = Pipeline()
    video_path = pipe.run_text("求三角形ABC的面积...")
    video_path = pipe.run_image("./problem.png")
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from src.llm.client import Client
from src.llm.parser import (
    GeneratedScene,
    ParseError,
    parse_code_generation_response,
)
from src.manim.builder import ManimBuilder, RenderError, render_prompt_template
from src.options import ExplanationOptions
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PROMPT_DIR = _PROJECT_ROOT / "prompt"

_EXPLANATION_PROMPT_PATH = _PROMPT_DIR / "ProblemExplanation.md"
_CODE_GEN_PROMPT_PATH = _PROMPT_DIR / "CodeGeneration.md"
_CODE_FIX_PROMPT_PATH = _PROMPT_DIR / "CodeFix.md"
_CODE_REVIEW_PROMPT_PATH = _PROMPT_DIR / "CodeReview.md"

# Max characters of stdout/stderr fed back to the LLM (tracebacks are at the end)
_STDOUT_CLIP = 4000
_STDERR_CLIP = 8000

# Rendering (incl. auto-repair rounds) occupies this slice of overall progress
_RENDER_PROGRESS_BASE = 0.5
_RENDER_PROGRESS_SPAN = 0.4

# Stage names emitted via the progress callback (in typical order):
#   explanation -> code_generation -> code_reviewing -> rendering
#   -> code_fixing (only when repairing) -> done
STAGE_EXPLANATION = "explanation"
STAGE_CODE_GENERATION = "code_generation"
STAGE_CODE_REVIEWING = "code_reviewing"
STAGE_RENDERING = "rendering"
STAGE_CODE_FIXING = "code_fixing"
STAGE_DONE = "done"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    uuid: str
    explanation: str
    scene: GeneratedScene
    script_path: Path
    video_path: Path


# ---------------------------------------------------------------------------
# Progress callback type
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[str, float], None]
"""Callback signature: ``callback(stage_name: str, progress: float)`` where
*progress* is 0.0 – 1.0 and monotonically non-decreasing across the run.

Standard stage names emitted by :class:`Pipeline`:

- ``explanation``       — generating the structured explanation (LLM)
- ``code_generation``   — converting the explanation into Manim code (LLM)
- ``code_reviewing``    — LLM layout review of the generated code
- ``rendering``         — Manim rendering (one update per attempt)
- ``code_fixing``       — LLM auto-repair after a failed render attempt
- ``done``              — pipeline finished (progress = 1.0)
"""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """End-to-end video generation pipeline.

    When rendering fails, the captured stdout/stderr is sent back to the LLM
    for automatic code repair, then rendering is retried (up to
    ``max_retries`` repair rounds).

    Args:
        ref_audio_path: Path to reference audio for voice cloning.
        quality:        Manim render quality (``l`` / ``m`` / ``h`` / ``k``).
        data_dir:       Working directory for scripts and output.
        max_retries:    Max LLM auto-repair rounds on render failure.
        on_progress:    Optional progress callback.
        options:        User-customizable explanation modules
                        (:class:`~src.core.options.ExplanationOptions`).
    """

    def __init__(
        self,
        ref_audio_path: str | Path | None = None,
        quality: str = "l",
        data_dir: str | Path | None = None,
        max_retries: int = 3,
        on_progress: ProgressCallback | None = None,
        options: ExplanationOptions | None = None,
    ):
        if ref_audio_path is None:
            ref_audio_path = _PROJECT_ROOT / "asset" / "mar7th.wav"
        self.ref_audio_path = str(Path(ref_audio_path).resolve())

        self.quality = quality
        self.data_dir = data_dir
        self.max_retries = max(0, int(max_retries))
        self.options = options if options is not None else ExplanationOptions()
        self._on_progress = on_progress or (lambda *_: None)

        # Current problem context (set by run_text / run_image, used to give
        # the code-generation model direct access to the original problem)
        self._problem_text: str | None = None
        self._problem_image: str | Path | None = None

        # Lazy-loaded components
        self._explanation_client: Optional[Client] = None
        self._codegen_client: Optional[Client] = None
        self._codefix_client: Optional[Client] = None
        self._codereview_client: Optional[Client] = None
        self._manim_builder: Optional[ManimBuilder] = None

    # -- Lazy init -----------------------------------------------------------

    def _template_context(self) -> dict:
        """Common Jinja2 variables shared by all prompt templates."""
        return {
            "ref_audio_path": self.ref_audio_path,
            "options": self.options,
            "enabled_sections": self.options.enabled_labels(),
        }

    @property
    def explanation_client(self) -> Client:
        if self._explanation_client is None:
            raw_prompt = _EXPLANATION_PROMPT_PATH.read_text(encoding="utf-8")
            rendered_prompt = render_prompt_template(
                raw_prompt, **self._template_context()
            )
            self._explanation_client = Client(system_prompt=rendered_prompt)
        return self._explanation_client

    @property
    def codegen_client(self) -> Client:
        if self._codegen_client is None:
            raw_prompt = _CODE_GEN_PROMPT_PATH.read_text(encoding="utf-8")
            rendered_prompt = render_prompt_template(
                raw_prompt,
                problem_text=self._problem_text or "",
                has_problem_image=self._problem_image is not None,
                **self._template_context(),
            )
            self._codegen_client = Client(system_prompt=rendered_prompt)
        return self._codegen_client

    @property
    def code_fix_client(self) -> Client:
        if self._codefix_client is None:
            raw_prompt = _CODE_FIX_PROMPT_PATH.read_text(encoding="utf-8")
            rendered_prompt = render_prompt_template(
                raw_prompt, **self._template_context()
            )
            self._codefix_client = Client(system_prompt=rendered_prompt)
        return self._codefix_client

    @property
    def code_review_client(self) -> Client:
        if self._codereview_client is None:
            raw_prompt = _CODE_REVIEW_PROMPT_PATH.read_text(encoding="utf-8")
            rendered_prompt = render_prompt_template(
                raw_prompt, **self._template_context()
            )
            self._codereview_client = Client(system_prompt=rendered_prompt)
        return self._codereview_client

    @property
    def manim_builder(self) -> ManimBuilder:
        if self._manim_builder is None:
            self._manim_builder = ManimBuilder(
                quality=self.quality,
                data_dir=self.data_dir,
            )
        return self._manim_builder

    # -- Progress helper -----------------------------------------------------

    def _progress(self, stage: str, value: float) -> None:
        logger.info("[%s] %.0f%%", stage, value * 100)
        self._on_progress(stage, value)

    # -- Step 1: Explanation -------------------------------------------------

    def generate_explanation(
        self,
        text: str | None = None,
        image_path: str | None = None,
    ) -> str:
        """Step 1: Generate a structured explanation of the problem.

        Args:
            text:       Problem text (if providing text input).
            image_path: Path to problem image (if providing image input).

        Returns:
            The LLM's structured explanation text.
        """

        user_prompt = "请解答以下题目："
        if text:
            user_prompt += f"\n\n{text}"

        if image_path:
            logger.info("Calling LLM with image: %s", image_path)
            response = self.explanation_client.call_model_with_image(
                text=user_prompt, img_path=image_path
            )
        else:
            logger.info("Calling LLM with text input")
            response = self.explanation_client.call_model_without_image(
                text=user_prompt
            )

        if not response:
            raise RuntimeError("LLM returned empty explanation")

        logger.info("Explanation generated (%d chars)", len(response))
        return response

    # -- Step 2: Code generation ---------------------------------------------

    def generate_code(self, explanation: str) -> GeneratedScene:
        """Step 2: Convert the explanation into Manim code.

        Args:
            explanation: The structured explanation from Step 1.

        Returns:
            A :class:`GeneratedScene` with scene name and code.
        """
        # Prefix user message to reinforce the task instruction, and attach
        # the ORIGINAL problem (text inline / image via the multimodal API)
        # so the model sees the problem itself instead of only the
        # LLM-generated explanation.
        if self._problem_text:
            problem_block = f"【原题】\n{self._problem_text}"
        elif self._problem_image:
            problem_block = "【原题】原题以图片形式附带，请直接查看图片理解题目。"
        else:
            problem_block = "【原题】（未提供，请依据下方题解内容生成动画）"

        user_text = (
            "请严格按照系统提示中的要求，将以下题解转换为Manim动画代码。"
            "只输出JSON，不要输出任何其他内容。\n\n"
            f"{problem_block}\n\n"
            f"---\n\n{explanation}"
        )

        logger.info("Calling LLM for code generation (prompt=%d chars, input=%d chars)",
                     len(self.codegen_client.system_prompt), len(user_text))
        logger.debug("Code gen system prompt:\n%s",
                      self.codegen_client.system_prompt[:500])

        if self._problem_image:
            logger.info("Code generation with original image: %s", self._problem_image)
            response = self.codegen_client.call_model_with_image(
                text=user_text, img_path=str(self._problem_image)
            )
        else:
            response = self.codegen_client.call_model_without_image(
                text=user_text
            )

        if not response:
            raise RuntimeError("LLM returned empty code generation response")

        logger.debug("Raw code gen response:\n%s", response[:1000])

        scene = parse_code_generation_response(response)

        return scene

    # -- Step 3.5: Code review -----------------------------------------------

    def review_code(
        self,
        scene: GeneratedScene,
        explanation: str,
        problem_text: str | None = None,
        problem_image: str | Path | None = None,
    ) -> GeneratedScene:
        """Step 3.5: Send generated code back to an LLM for layout review.

        The reviewer receives the original problem (text and/or image), the
        structured explanation and the generated Manim code, then checks for
        element stacking / overlap, out-of-frame layout issues and content
        mismatches, returning optimized code.

        Args:
            scene:         Parsed scene from code generation.
            explanation:   The structured explanation from Step 1.
            problem_text:  Original problem text (if text input).
            problem_image: Path to original problem image (if image input).

        Returns:
            A new :class:`GeneratedScene` with reviewed/optimized code. Falls
            back to the input *scene* if the reviewer's response cannot be
            parsed (review is best-effort, it must not kill the pipeline).
        """
        problem_section = "（原题以图片形式附带，请结合图片内容审查）"
        if problem_text:
            problem_section = problem_text

        user_text = (
            "请严格按照系统提示中的要求审查以下Manim动画代码，"
            "重点检查元素堆叠、排版布局和内容问题，"
            "输出优化后的完整代码。只输出JSON，不要输出任何其他内容。\n\n"
            "---\n\n"
            f"【原题】\n{problem_section}\n\n"
            f"【题解】\n{explanation}\n\n"
            f"【生成的代码】\n```python\n{scene.code}\n```"
        )

        logger.info(
            "Calling LLM for code review (code=%d chars, explanation=%d chars)",
            len(scene.code), len(explanation),
        )

        if problem_image:
            try:
                response = self.code_review_client.call_model_with_image(
                    text=user_text, img_path=str(problem_image)
                )
            except Exception as err:
                logger.warning(
                    "Code-review LLM call failed (%s) — keeping unreviewed code",
                    err,
                )
                return scene
        else:
            try:
                response = self.code_review_client.call_model_without_image(
                    text=user_text
                )
            except Exception as err:
                logger.warning(
                    "Code-review LLM call failed (%s) — keeping unreviewed code",
                    err,
                )
                return scene

        if not response:
            logger.warning("LLM returned empty code-review response — keeping unreviewed code")
            return scene

        try:
            reviewed_scene = parse_code_generation_response(response)
        except ParseError as err:
            logger.warning(
                "Code-review response failed to parse (%s) — keeping unreviewed code", err
            )
            return scene

        logger.info(
            "Code review received: scene=%s (%d chars of code)",
            reviewed_scene.scene_name, len(reviewed_scene.code),
        )
        return reviewed_scene

    # -- Step 4: Render ------------------------------------------------------

    def render_video(
        self,
        scene: GeneratedScene,
        task_uuid: str | None = None,
    ) -> Path:
        """Step 4: Write the Manim script and render the video.

        Args:
            scene:     The parsed scene from Step 2–3.
            task_uuid: UUID for file naming (auto-generated if *None*).

        Returns:
            Path to the rendered ``.mp4`` file.
        """
        if task_uuid is None:
            task_uuid = str(uuid.uuid4())

        video_path = self.manim_builder.build_and_render(
            scene_name=scene.scene_name,
            code=scene.code,
            task_uuid=task_uuid,
        )

        return video_path

    # -- Step 4.5: Auto-repair on render failure -----------------------------

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        """Return the tail of *text* up to *limit* chars (tracebacks live at the end)."""
        if not text:
            return "(empty)"
        text = text.strip()
        if len(text) <= limit:
            return text
        return f"...(truncated)...\n{text[-limit:]}"

    def fix_code(self, scene: GeneratedScene, render_error: RenderError) -> GeneratedScene:
        """Send render error output back to the LLM and get repaired code.

        Args:
            scene:        The scene whose code failed to render.
            render_error: The :class:`RenderError` with captured stdout/stderr.

        Returns:
            A new :class:`GeneratedScene` with the fixed code.

        Raises:
            ParseError: If the LLM's repair response cannot be parsed.
        """
        user_text = (
            "渲染你生成的代码时发生了错误，请根据以下信息修复代码，"
            "只输出JSON，不要输出任何其他内容。\n\n"
            "---\n\n"
            f"【原始代码】\n```python\n{scene.code}\n```\n\n"
            f"【程序标准输出 stdout】\n{self._clip(render_error.stdout, _STDOUT_CLIP)}\n\n"
            f"【程序错误输出 stderr】\n{self._clip(render_error.stderr, _STDERR_CLIP)}"
        )

        logger.info(
            "Calling LLM for code repair (code=%d chars, stdout=%d chars, stderr=%d chars)",
            len(scene.code),
            len(render_error.stdout),
            len(render_error.stderr),
        )

        response = self.code_fix_client.call_model_without_image(text=user_text)

        if not response:
            raise RuntimeError("LLM returned empty code-fix response")

        fixed_scene = parse_code_generation_response(response)

        logger.info(
            "Code repair received: scene=%s (%d chars of code)",
            fixed_scene.scene_name, len(fixed_scene.code),
        )
        return fixed_scene

    def _render_with_auto_fix(
        self,
        scene: GeneratedScene,
        task_uuid: str,
    ) -> tuple[GeneratedScene, Path, Path]:
        """Render *scene*, auto-repairing the code via the LLM on failure.

        Args:
            scene:     Parsed scene from code generation.
            task_uuid: UUID for file naming.

        Returns:
            Tuple of (final scene, script path, video path). The scene may be
            a repaired version if any retry round succeeded.

        Raises:
            RenderError: If rendering still fails after all repair rounds.
        """
        current = scene
        total_attempts = self.max_retries + 1  # 1 initial attempt + N repairs

        for attempt in range(1, total_attempts + 1):
            script_path = self.manim_builder.write_script(
                current.scene_name, current.code, task_uuid
            )

            render_progress = (
                _RENDER_PROGRESS_BASE
                + _RENDER_PROGRESS_SPAN * (attempt - 1) / total_attempts
            )
            self._progress(STAGE_RENDERING, min(render_progress, 0.95))

            try:
                video_path = self.manim_builder.render(
                    script_path, current.scene_name, task_uuid
                )
                if attempt > 1:
                    logger.info("Render succeeded after %d repair round(s)", attempt - 1)
                return current, script_path, video_path

            except RenderError as err:
                rounds_left = total_attempts - attempt
                if rounds_left <= 0:
                    logger.error("Rendering failed after %d attempt(s), giving up", attempt)
                    raise

                logger.warning(
                    "Render failed (attempt %d/%d) — sending error back to LLM "
                    "for auto-repair (%d round(s) left)",
                    attempt, total_attempts, rounds_left,
                )
                fix_progress = (
                    _RENDER_PROGRESS_BASE
                    + _RENDER_PROGRESS_SPAN * attempt / total_attempts
                )
                self._progress(STAGE_CODE_FIXING, min(fix_progress, 0.95))
                current = self.fix_code(current, err)

        raise RuntimeError("unreachable: render loop exited")

    # -- Full pipeline -------------------------------------------------------

    def run_text(self, text: str) -> PipelineResult:
        """Run the full pipeline with text input.

        Args:
            text: The problem text.

        Returns:
            A :class:`PipelineResult` with all intermediate outputs.
        """
        task_uuid = str(uuid.uuid4())
        logger.info("=== Pipeline start (text) — uuid=%s ===", task_uuid)
        logger.info("Explanation modules: %s", self.options.summary())

        self._problem_text = text
        self._problem_image = None

        self._progress(STAGE_EXPLANATION, 0.05)
        explanation = self.generate_explanation(text=text)

        self._progress(STAGE_CODE_GENERATION, 0.35)
        scene = self.generate_code(explanation)

        self._progress(STAGE_CODE_REVIEWING, 0.45)
        scene = self.review_code(scene, explanation, problem_text=text)

        scene, script_path, video_path = self._render_with_auto_fix(scene, task_uuid)

        self._progress(STAGE_DONE, 1.0)

        logger.info("=== Pipeline complete — video: %s ===", video_path)
        return PipelineResult(
            uuid=task_uuid,
            explanation=explanation,
            scene=scene,
            script_path=script_path,
            video_path=video_path,
        )

    def run_image(self, image_path: str) -> PipelineResult:
        """Run the full pipeline with image input.

        Args:
            image_path: Path to the problem image.

        Returns:
            A :class:`PipelineResult` with all intermediate outputs.
        """
        task_uuid = str(uuid.uuid4())
        logger.info("=== Pipeline start (image) — uuid=%s ===", task_uuid)
        logger.info("Explanation modules: %s", self.options.summary())

        self._problem_text = None
        self._problem_image = image_path

        self._progress(STAGE_EXPLANATION, 0.05)
        explanation = self.generate_explanation(image_path=image_path)

        self._progress(STAGE_CODE_GENERATION, 0.35)
        scene = self.generate_code(explanation)

        self._progress(STAGE_CODE_REVIEWING, 0.45)
        scene = self.review_code(scene, explanation, problem_image=image_path)

        scene, script_path, video_path = self._render_with_auto_fix(scene, task_uuid)

        self._progress(STAGE_DONE, 1.0)

        logger.info("=== Pipeline complete — video: %s ===", video_path)
        return PipelineResult(
            uuid=task_uuid,
            explanation=explanation,
            scene=scene,
            script_path=script_path,
            video_path=video_path,
        )
