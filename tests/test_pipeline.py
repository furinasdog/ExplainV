"""Tests for src.core.pipeline — orchestration logic with mocked LLM/manim."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.pipeline import Pipeline, PipelineResult
from src.llm.parser import GeneratedScene
from src.manim.builder import RenderError


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
