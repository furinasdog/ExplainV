"""Tests for src.core.pipeline — orchestration logic with mocked LLM/manim."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.pipeline import Pipeline, PipelineResult
from src.llm.parser import GeneratedScene
from src.manim.builder import RenderError
from src.options import ExplanationOptions


@pytest.fixture
def scene():
    return GeneratedScene(scene_name="MyScene", code="x = 1")


@pytest.fixture
def pipe(tmp_path):
    return Pipeline(max_retries=2, data_dir=tmp_path)


class TestInit:
    def test_negative_max_retries_clamped_to_zero(self, tmp_path):
        assert Pipeline(max_retries=-5, data_dir=tmp_path).max_retries == 0

    def test_max_retries_kept(self, tmp_path):
        assert Pipeline(max_retries=7, data_dir=tmp_path).max_retries == 7

    def test_ref_audio_resolved_absolute(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pipe = Pipeline(ref_audio_path="rel.wav", data_dir=tmp_path)
        audio = Path(pipe.ref_audio_path)
        assert audio.is_absolute()
        assert audio.name == "rel.wav"

    def test_default_ref_audio(self, tmp_path):
        pipe = Pipeline(data_dir=tmp_path)
        assert pipe.ref_audio_path.endswith("mar7th.wav")

    def test_no_progress_callback_by_default(self, tmp_path):
        Pipeline(data_dir=tmp_path)._progress("stage", 0.5)  # must not raise


class TestClip:
    def test_empty_text(self):
        assert Pipeline._clip("", 10) == "(empty)"

    def test_short_text_stripped(self):
        assert Pipeline._clip("  hello \n", 10) == "hello"

    def test_long_text_tail_truncated(self):
        text = "A" * 100 + "TAIL"
        clipped = Pipeline._clip(text, 4)
        assert clipped == "...(truncated)...\nTAIL"

    def test_exact_limit_not_truncated(self):
        assert Pipeline._clip("12345", 5) == "12345"


class TestProgressCallback:
    def test_callback_receives_stage_and_value(self, tmp_path):
        calls = []
        pipe = Pipeline(
            data_dir=tmp_path,
            on_progress=lambda stage, value: calls.append((stage, value)),
        )
        pipe._progress("rendering", 0.25)
        assert calls == [("rendering", 0.25)]


class TestRunStageSequence:
    """run_* must emit one specific stage per step (not just "pipeline")."""

    def _mocked_pipeline(self, tmp_path):
        calls = []
        pipe = Pipeline(
            max_retries=1,
            data_dir=tmp_path,
            on_progress=lambda stage, value: calls.append((stage, value)),
        )

        explanation_client = MagicMock()
        explanation_client.call_model_without_image.return_value = "题解内容"
        explanation_client.call_model_with_image.return_value = "题解内容"
        codegen_client = MagicMock()
        codegen_client.call_model_without_image.return_value = json.dumps(
            {"Scene Name": "MyScene", "Code": "x = 1"}
        )
        codegen_client.call_model_with_image.return_value = json.dumps(
            {"Scene Name": "MyScene", "Code": "x = 1"}
        )
        review_client = MagicMock()
        review_client.call_model_without_image.side_effect = RuntimeError("skip")
        review_client.call_model_with_image.side_effect = RuntimeError("skip")
        pipe._explanation_client = explanation_client
        pipe._codegen_client = codegen_client
        pipe._codereview_client = review_client

        builder = MagicMock()
        builder.write_script.side_effect = (
            lambda name, code, uuid: tmp_path / f"{uuid}.py"
        )
        builder.render.return_value = tmp_path / "v.mp4"
        pipe._manim_builder = builder
        return pipe, calls

    def test_run_text_emits_step_stages(self, tmp_path):
        pipe, calls = self._mocked_pipeline(tmp_path)
        pipe.run_text("题目")

        assert [stage for stage, _ in calls] == [
            "explanation",
            "code_generation",
            "code_reviewing",
            "rendering",
            "done",
        ]

    def test_run_text_progress_is_monotonic_and_completes(self, tmp_path):
        pipe, calls = self._mocked_pipeline(tmp_path)
        pipe.run_text("题目")

        values = [value for _, value in calls]
        assert values == sorted(values)
        assert values[0] > 0
        assert values[-1] == 1.0

    def test_render_failure_reports_code_fixing_stage(self, tmp_path):
        pipe, calls = self._mocked_pipeline(tmp_path)
        pipe._manim_builder.render.side_effect = [
            RenderError("fail"),
            tmp_path / "v.mp4",
        ]
        pipe.fix_code = MagicMock(
            return_value=GeneratedScene(scene_name="MyScene", code="fixed")
        )

        result = pipe.run_text("题目")

        stages = [stage for stage, _ in calls]
        assert stages.count("rendering") == 2
        assert stages.count("code_fixing") == 1
        assert stages[-1] == "done"
        assert result.scene.code == "fixed"


class TestReviewCode:
    def test_llm_failure_returns_original_scene(self, pipe, scene):
        client = MagicMock()
        client.call_model_without_image.side_effect = RuntimeError("network down")
        pipe._codereview_client = client

        assert pipe.review_code(scene, explanation="解释") is scene

    def test_with_image_uses_image_call(self, pipe, scene):
        client = MagicMock()
        client.call_model_with_image.return_value = (
            '{"Scene Name": "ReviewedScene", "Code": "y = 2"}'
        )
        pipe._codereview_client = client

        result = pipe.review_code(scene, explanation="e", problem_image="img.png")

        client.call_model_with_image.assert_called_once()
        _, kwargs = client.call_model_with_image.call_args
        assert kwargs["img_path"] == "img.png"
        assert result.scene_name == "ReviewedScene"

    def test_empty_response_returns_original_scene(self, pipe, scene):
        client = MagicMock()
        client.call_model_without_image.return_value = ""
        pipe._codereview_client = client

        assert pipe.review_code(scene, explanation="e") is scene

    def test_unparseable_response_returns_original_scene(self, pipe, scene):
        client = MagicMock()
        client.call_model_without_image.return_value = "sorry, no json"
        pipe._codereview_client = client

        assert pipe.review_code(scene, explanation="e") is scene

    def test_valid_response_returns_reviewed_scene(self, pipe, scene):
        client = MagicMock()
        client.call_model_without_image.return_value = json.dumps(
            {"Scene Name": "ReviewedScene", "Code": "y = 2"}
        )
        pipe._codereview_client = client

        result = pipe.review_code(scene, explanation="e")
        assert (result.scene_name, result.code) == ("ReviewedScene", "y = 2")


class TestRenderVideo:
    def test_delegates_to_builder(self, pipe, scene, tmp_path):
        video = tmp_path / "out.mp4"
        builder = MagicMock()
        builder.build_and_render.return_value = video
        pipe._manim_builder = builder

        assert pipe.render_video(scene, task_uuid="u1") == video
        builder.build_and_render.assert_called_once_with(
            scene_name="MyScene", code="x = 1", task_uuid="u1"
        )


class TestRenderWithAutoFix:
    def _install_builder(self, pipe, tmp_path, render_side_effects):
        builder = MagicMock()
        builder.write_script.side_effect = (
            lambda name, code, uuid: tmp_path / f"{uuid}.py"
        )
        builder.render.side_effect = render_side_effects
        pipe._manim_builder = builder
        return builder

    def test_success_on_first_attempt(self, pipe, scene, tmp_path):
        video = tmp_path / "v.mp4"
        self._install_builder(pipe, tmp_path, [video])
        pipe.fix_code = MagicMock()

        final, script_path, video_path = pipe._render_with_auto_fix(scene, "u1")

        assert final is scene
        assert video_path == video
        pipe.fix_code.assert_not_called()

    def test_success_after_repair_round(self, pipe, scene, tmp_path):
        video = tmp_path / "v.mp4"
        self._install_builder(pipe, tmp_path, [RenderError("fail"), video])
        fixed = GeneratedScene(scene_name="MyScene", code="fixed")
        pipe.fix_code = MagicMock(return_value=fixed)

        final, _, video_path = pipe._render_with_auto_fix(scene, "u1")

        assert final is fixed
        assert video_path == video
        pipe.fix_code.assert_called_once()

    def test_gives_up_after_all_attempts(self, scene, tmp_path):
        pipe = Pipeline(max_retries=1, data_dir=tmp_path)
        builder = self._install_builder(
            pipe, tmp_path, [RenderError("fail"), RenderError("fail again")]
        )
        pipe.fix_code = MagicMock(
            return_value=GeneratedScene(scene_name="S", code="fixed")
        )

        with pytest.raises(RenderError):
            pipe._render_with_auto_fix(scene, "u1")

        assert builder.write_script.call_count == 2  # initial + 1 repair round
        pipe.fix_code.assert_called_once()

    def test_write_script_receives_latest_code(self, pipe, tmp_path):
        """The repaired code — not the original — is written on retry."""
        video = tmp_path / "v.mp4"
        builder = self._install_builder(pipe, tmp_path, [RenderError("f1"), video])
        pipe.fix_code = MagicMock(
            return_value=GeneratedScene(scene_name="MyScene", code="fixed-code")
        )

        pipe._render_with_auto_fix(GeneratedScene("MyScene", "orig"), "u1")

        second_write = builder.write_script.call_args_list[1]
        assert second_write.args[1] == "fixed-code"


class TestPipelineResult:
    def test_dataclass_fields(self, scene, tmp_path):
        result = PipelineResult(
            uuid="id",
            explanation="exp",
            scene=scene,
            script_path=tmp_path / "s.py",
            video_path=tmp_path / "v.mp4",
        )
        assert result.uuid == "id"
        assert result.explanation == "exp"
        assert result.scene is scene


class TestOptions:
    """User-customizable explanation modules."""

    def test_default_options_attached(self, tmp_path):
        assert isinstance(Pipeline(data_dir=tmp_path).options, ExplanationOptions)

    def test_custom_options_attached(self, tmp_path):
        options = ExplanationOptions.from_selection(["solution_process"])
        assert Pipeline(data_dir=tmp_path, options=options).options is options

    @pytest.fixture
    def env_client(self, monkeypatch):
        monkeypatch.setenv("EXPLAINV_API_KEY", "k")
        monkeypatch.setenv("EXPLAINV_API_URL", "https://api.example.test/v1")

    def test_explanation_prompt_reflects_options(self, tmp_path, env_client):
        options = ExplanationOptions.from_selection(["knowledge_points"])
        pipe = Pipeline(data_dir=tmp_path, options=options)
        prompt = pipe.explanation_client.system_prompt
        assert "- 知识点总结" in prompt
        assert "【题目原文】" not in prompt  # disabled module removed from template
        assert "【题目知识点】" in prompt

    def test_codegen_prompt_lists_selected_modules(self, tmp_path, env_client):
        options = ExplanationOptions.from_selection(
            ["solution_process"], brief=True
        )
        pipe = Pipeline(data_dir=tmp_path, options=options)
        prompt = pipe.codegen_client.system_prompt
        assert "- 题目解答过程" in prompt
        assert "简略模式" in prompt


class TestGenerateCodeProblemContext:
    """The code-generation LLM must see the original problem itself."""

    @staticmethod
    def _pipe_with_mock(tmp_path):
        pipe = Pipeline(data_dir=tmp_path)
        client = MagicMock()
        client.call_model_without_image.return_value = json.dumps(
            {"Scene Name": "S", "Code": "c"}
        )
        client.call_model_with_image.return_value = json.dumps(
            {"Scene Name": "S", "Code": "c-img"}
        )
        pipe._codegen_client = client
        return pipe, client

    def test_text_input_embeds_original_problem(self, tmp_path):
        pipe, client = self._pipe_with_mock(tmp_path)
        pipe._problem_text = "已知 a=3, b=4，求 c。"

        pipe.generate_code("题解内容")

        user_text = client.call_model_without_image.call_args.kwargs["text"]
        assert "【原题】" in user_text
        assert "已知 a=3, b=4，求 c。" in user_text

    def test_image_input_uses_multimodal_call(self, tmp_path):
        pipe, client = self._pipe_with_mock(tmp_path)
        img = tmp_path / "problem.png"
        img.write_bytes(b"png")
        pipe._problem_image = str(img)

        scene = pipe.generate_code("题解内容")

        kwargs = client.call_model_with_image.call_args.kwargs
        assert kwargs["img_path"] == str(img)
        assert "图片形式附带" in kwargs["text"]
        client.call_model_without_image.assert_not_called()
        assert scene.code == "c-img"

    def test_no_problem_falls_back_to_text_call(self, tmp_path):
        pipe, client = self._pipe_with_mock(tmp_path)

        pipe.generate_code("题解内容")

        user_text = client.call_model_without_image.call_args.kwargs["text"]
        assert "未提供" in user_text
        client.call_model_with_image.assert_not_called()

    def test_run_text_sets_problem_context(self, tmp_path):
        pipe, _ = TestRunStageSequence()._mocked_pipeline(tmp_path)

        pipe.run_text("勾股定理题目文本")

        user_text = (
            pipe._codegen_client.call_model_without_image.call_args.kwargs["text"]
        )
        assert "勾股定理题目文本" in user_text

    def test_run_image_sets_problem_context(self, tmp_path):
        pipe, _ = TestRunStageSequence()._mocked_pipeline(tmp_path)
        img = tmp_path / "img.png"
        img.write_bytes(b"png")

        pipe.run_image(str(img))

        assert pipe.codegen_client is not None  # property resolves without error
        call_kwargs = pipe._codegen_client.call_model_with_image.call_args
        assert call_kwargs.kwargs["img_path"] == str(img)
