"""Tests for src.manim.builder — pure helpers and script writing (no rendering)."""

import os
import sys

import pytest

from src.manim.builder import (
    ManimBuilder,
    RenderError,
    _interpreter_env_dirs,
    build_child_env,
    render_code_generation_prompt,
)


class TestRenderError:
    def test_no_output(self):
        assert RenderError("boom").error_output == "(no output captured)"

    def test_stdout_only(self):
        err = RenderError("boom", stdout="some output")
        text = err.error_output
        assert "【程序标准输出 stdout】" in text
        assert "some output" in text
        assert "stderr" not in text

    def test_stderr_only(self):
        err = RenderError("boom", stderr="traceback")
        text = err.error_output
        assert "【程序错误输出 stderr】" in text
        assert "traceback" in text

    def test_both_outputs_joined(self):
        err = RenderError("boom", stdout="out", stderr="err")
        assert err.error_output.index("stdout") < err.error_output.index("stderr")

    def test_whitespace_only_treated_as_empty(self):
        assert RenderError("m", stdout="  \n").error_output == "(no output captured)"


class TestInterpreterEnvDirs:
    def test_returns_existing_dirs_without_duplicates(self):
        dirs = _interpreter_env_dirs()
        assert dirs
        for path in dirs:
            assert path.is_dir()
        assert len(dirs) == len(set(dirs))


class TestBuildChildEnv:
    def test_path_is_prepended(self):
        env = build_child_env({"PATH": "/usr/bin"})
        dll_dirs = [str(p) for p in _interpreter_env_dirs()]
        assert env["PATH"].split(os.pathsep)[: len(dll_dirs)] == dll_dirs
        assert env["PATH"].endswith("/usr/bin")

    def test_other_keys_preserved(self):
        env = build_child_env({"HOME": "/root"})
        assert env["HOME"] == "/root"

    def test_input_dict_not_mutated(self):
        original = {"PATH": "/usr/bin"}
        build_child_env(original)
        assert original["PATH"] == "/usr/bin"

    def test_missing_path_key_handled(self):
        env = build_child_env({})
        assert env["PATH"]


class TestRenderCodeGenerationPrompt:
    def test_substitution(self):
        template = "Audio file: {{ ref_audio_path }}"
        rendered = render_code_generation_prompt(template, "C:/audio/ref.wav")
        assert rendered == f"Audio file: {repr('C:/audio/ref.wav')}"

    def test_multiple_occurrences(self):
        template = "{{ ref_audio_path }} then {{ ref_audio_path }}"
        rendered = render_code_generation_prompt(template, "/x.wav")
        assert rendered.count(repr("/x.wav")) == 2

    def test_untouched_template_text(self):
        template = "# Title\n\nNo placeholders here."
        assert render_code_generation_prompt(template, "/x.wav") == template


class TestManimBuilder:
    def test_creates_data_dir(self, tmp_path):
        data_dir = tmp_path / "nested" / "data"
        ManimBuilder(data_dir=data_dir)
        assert data_dir.is_dir()

    def test_write_script_with_uuid(self, tmp_path):
        builder = ManimBuilder(data_dir=tmp_path)
        path = builder.write_script("MyScene", "print('hi')", task_uuid="abc123")
        assert path == tmp_path / "abc123.py"
        assert path.read_text(encoding="utf-8") == "print('hi')"

    def test_write_script_generates_uuid(self, tmp_path):
        builder = ManimBuilder(data_dir=tmp_path)
        path = builder.write_script("MyScene", "x")
        assert len(path.stem) == 36  # canonical uuid4 length
        assert path.parent == tmp_path

    def test_build_command_structure(self, tmp_path):
        builder = ManimBuilder(quality="l", data_dir=tmp_path)
        script = tmp_path / "task.py"
        cmd = builder.build_command(script, "MyScene", "task")

        assert cmd[0] == sys.executable
        assert cmd[1:3] == ["-m", "manim"]
        assert "-ql" in cmd
        assert "--format" in cmd and "mp4" in cmd
        assert cmd[-2:] == [str(script), "MyScene"]

    @pytest.mark.parametrize(
        ("quality", "flag"),
        [("l", "-ql"), ("m", "-qm"), ("h", "-qh"), ("k", "-qk")],
    )
    def test_build_command_quality_flags(self, tmp_path, quality, flag):
        builder = ManimBuilder(quality=quality, data_dir=tmp_path)
        cmd = builder.build_command(tmp_path / "s.py", "S", "u")
        assert flag in cmd
