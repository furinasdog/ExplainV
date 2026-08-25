"""Tests for utils.command_line — CLI parsing and validation."""

import pytest

from utils.command_line import parse_args


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Run from an isolated dir containing a dummy ref audio + image."""
    (tmp_path / "ref.wav").write_bytes(b"RIFF....")
    (tmp_path / "problem.png").write_bytes(b"PNG")
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestValidParsing:
    def test_text_input_defaults(self, workspace):
        args = parse_args(["-t", "题目", "-a", "ref.wav"])
        assert args.input_text == "题目"
        assert args.input_image is None
        assert args.quality == "l"
        assert args.max_retries == 3
        assert args.verbose is False
        assert args.output is None
        assert args.model is None

    def test_long_options(self, workspace):
        args = parse_args(
            ["--text", "题", "--ref-audio", "ref.wav",
             "--quality", "h", "--max-retries", "0", "--verbose"]
        )
        assert args.quality == "h"
        assert args.max_retries == 0
        assert args.verbose is True

    def test_image_input(self, workspace):
        args = parse_args(["-i", "problem.png", "-a", "ref.wav"])
        assert args.input_image == "problem.png"
        assert args.input_text is None

    def test_all_quality_choices(self, workspace):
        for quality in ("l", "m", "h", "k"):
            args = parse_args(["-t", "x", "-a", "ref.wav", "-q", quality])
            assert args.quality == quality


class TestValidationErrors:
    def test_no_input_exits(self, workspace):
        with pytest.raises(SystemExit) as exc:
            parse_args(["-a", "ref.wav"])
        assert exc.value.code == 2

    def test_text_and_image_mutually_exclusive(self, workspace):
        argv = ["-t", "x", "-i", "problem.png", "-a", "ref.wav"]
        with pytest.raises(SystemExit) as exc:
            parse_args(argv)
        assert exc.value.code == 2

    def test_missing_image_file_exits(self, workspace):
        with pytest.raises(SystemExit):
            parse_args(["-i", "nope.png", "-a", "ref.wav"])

    def test_missing_ref_audio_exits(self, workspace):
        with pytest.raises(SystemExit):
            parse_args(["-t", "x", "-a", "ghost.wav"])

    def test_negative_max_retries_exits(self, workspace):
        argv = ["-t", "x", "-a", "ref.wav", "-r", "-1"]
        with pytest.raises(SystemExit):
            parse_args(argv)

    def test_invalid_quality_exits(self, workspace):
        argv = ["-t", "x", "-a", "ref.wav", "-q", "ultra"]
        with pytest.raises(SystemExit):
            parse_args(argv)

    def test_non_integer_max_retries_exits(self, workspace):
        argv = ["-t", "x", "-a", "ref.wav", "-r", "abc"]
        with pytest.raises(SystemExit):
            parse_args(argv)


class TestSectionOptions:
    """--sections / --brief-solution for explanation customization."""

    def test_defaults_are_none_and_false(self, workspace):
        args = parse_args(["-t", "x", "-a", "ref.wav"])
        assert args.sections is None
        assert args.brief_solution is False

    def test_sections_accept_multiple_values(self, workspace):
        argv = [
            "-t", "x", "-a", "ref.wav",
            "--sections", "solution_process", "answer_verification",
        ]
        args = parse_args(argv)
        assert args.sections == ["solution_process", "answer_verification"]

    def test_invalid_section_exits(self, workspace):
        argv = ["-t", "x", "-a", "ref.wav", "--sections", "no_such_module"]
        with pytest.raises(SystemExit):
            parse_args(argv)

    def test_brief_solution_flag(self, workspace):
        args = parse_args(["-t", "x", "-a", "ref.wav", "--brief-solution"])
        assert args.brief_solution is True
