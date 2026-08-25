"""
Manim command builder and executor.

Handles:
    1. Writing generated Manim code to ``data/<uuid>.py``
    2. Building the manim CLI command
    3. Executing the command and returning the output video path

Usage::

    from src.manim import ManimBuilder

    builder = ManimBuilder()
    script_path = builder.write_script(scene_name, code, uuid)
    video_path = builder.render(script_path, scene_name, uuid)
"""

import os
import shutil
import subprocess
import sys
import uuid as _uuid
from pathlib import Path

from jinja2 import Template

from utils.logger import get_logger

logger = get_logger(__name__)


class RenderError(RuntimeError):
    """Raised when manim rendering fails.

    Carries the raw process output so callers can feed it back to an LLM
    for automatic code repair.

    Attributes:
        stdout: Full standard output of the failed manim process.
        stderr: Full standard error of the failed manim process.
    """

    def __init__(self, message: str, stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.stdout = stdout or ""
        self.stderr = stderr or ""

    @property
    def error_output(self) -> str:
        """Combined stdout/stderr text suitable for LLM consumption."""
        parts = []
        if self.stdout.strip():
            parts.append(f"【程序标准输出 stdout】\n{self.stdout}")
        if self.stderr.strip():
            parts.append(f"【程序错误输出 stderr】\n{self.stderr}")
        return "\n\n".join(parts) if parts else "(no output captured)"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"

_QUALITY_MAP = {
    "l": "480p15",
    "m": "720p30",
    "h": "1080p60",
    "k": "2160p60",
}


# ---------------------------------------------------------------------------
# Interpreter environment helpers
# ---------------------------------------------------------------------------

def _interpreter_env_dirs() -> list[Path]:
    """Return interpreter-relative directories containing native DLLs.

    Conda environments place native dependencies (libffi, pango, cairo,
    api-ms-* runtimes, ...) under ``<env>\\Library\\bin`` and executables
    under ``<env>\\Scripts``. IDEs like PyCharm often launch ``python.exe``
    directly WITHOUT running ``conda activate``, so those directories are
    missing from PATH and manim's native extensions crash during import
    with Windows exception 0xC06D007F (delay-load module not found).

    Returns:
        Existing directories for both ``sys.prefix`` and ``sys.base_prefix``
        (covers venv-on-top-of-conda layouts), deduplicated and ordered so
        they can be safely prepended to PATH.
    """
    candidates: list[Path] = []
    for prefix in dict.fromkeys((sys.prefix, sys.base_prefix)):
        base = Path(prefix)
        candidates.append(base / "Library" / "bin")  # conda native DLLs
        candidates.append(base / "Scripts")
        candidates.append(base)
    seen: set[Path] = set()
    return [p for p in candidates if p.is_dir() and not (p in seen or seen.add(p))]


def build_child_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build the environment for manim subprocesses.

    Takes *base_env* (defaults to ``os.environ``) and prepends the
    interpreter's native-DLL directories to PATH so rendering works even
    when the parent process was launched without conda activation
    (e.g. from PyCharm's run button).

    Args:
        base_env: Environment mapping to start from (default: current env).

    Returns:
        A copy of the environment with a hardened PATH.
    """
    env = dict(base_env) if base_env is not None else os.environ.copy()

    dll_dirs = _interpreter_env_dirs()
    if dll_dirs:
        existing_path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join(
            [str(p) for p in dll_dirs]
            + ([existing_path] if existing_path else [])
        )
        logger.debug(
            "Prepended interpreter dirs to child-process PATH: %s",
            os.pathsep.join(str(p) for p in dll_dirs),
        )
    return env


# ---------------------------------------------------------------------------
# Prompt template rendering
# ---------------------------------------------------------------------------

def render_prompt_template(template_text: str, **variables) -> str:
    """Render a Jinja2 prompt template with the given variables.

    Used for all prompt templates under ``prompt/`` (CodeGeneration.md,
    CodeReview.md, ProblemExplanation.md, ...). Templates may use
    ``{{ var }}`` placeholders and ``{% if %}`` blocks.

    Args:
        template_text: Raw template text.
        **variables:   Template variables. ``ref_audio_path``, if given,
                       is injected as a Python repr (quoted string).

    Returns:
        Rendered prompt string.
    """
    if "ref_audio_path" in variables:
        variables["ref_audio_path"] = repr(variables["ref_audio_path"])
    tpl = Template(template_text, trim_blocks=True, lstrip_blocks=True)
    return tpl.render(**variables)


def render_code_generation_prompt(
    template_text: str,
    ref_audio_path: str,
) -> str:
    """Render the CodeGeneration prompt, filling in ``ref_audio_path``.

    Backwards-compatible wrapper around :func:`render_prompt_template`.

    Args:
        template_text:  Raw prompt template text (from ``prompt/CodeGeneration.md``).
        ref_audio_path: Absolute path to the reference audio file.

    Returns:
        Rendered prompt string.
    """
    return render_prompt_template(template_text, ref_audio_path=ref_audio_path)


# ---------------------------------------------------------------------------
# ManimBuilder
# ---------------------------------------------------------------------------

class ManimBuilder:
    """Build and execute manim rendering commands.

    Args:
        quality:  Render quality — ``l`` (480p), ``m`` (720p),
                  ``h`` (1080p), ``k`` (4K). Default ``l``.
        data_dir: Directory for scripts and output. Default ``data/``.
    """

    def __init__(
        self,
        quality: str = "l",
        data_dir: str | Path | None = None,
    ):
        self.quality = quality
        self.data_dir = Path(data_dir) if data_dir else _DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # -- Script writing ------------------------------------------------------

    def write_script(
        self,
        scene_name: str,
        code: str,
        task_uuid: str | None = None,
    ) -> Path:
        """Write generated Manim code to a Python script file.

        Args:
            scene_name: The Manim scene class name (e.g. ``PythagoreanScene``).
            code:       Complete, runnable Python code for the scene.
            task_uuid:  UUID for this task. If *None*, one is generated.

        Returns:
            Path to the written ``data/<uuid>.py`` file.
        """
        if task_uuid is None:
            task_uuid = str(_uuid.uuid4())

        script_path = self.data_dir / f"{task_uuid}.py"
        script_path.write_text(code, encoding="utf-8")
        logger.info("Script written → %s (scene=%s)", script_path, scene_name)
        return script_path

    # -- Command building ----------------------------------------------------

    def build_command(
        self,
        script_path: Path,
        scene_name: str,
        task_uuid: str,
    ) -> list[str]:
        """Build the manim CLI command as a list of arguments.

        Args:
            script_path: Path to the ``.py`` script.
            scene_name:  The scene class name to render.
            task_uuid:   UUID for output naming.

        Returns:
            Command as a list of strings suitable for :func:`subprocess.run`.
        """
        quality_flag = f"-q{self.quality}"

        cmd = [
            sys.executable, "-m", "manim",
            quality_flag,
            "--media_dir", str(self.data_dir),
            "--format", "mp4",
            str(script_path),
            scene_name,
        ]
        logger.info("Manim command: %s", " ".join(cmd))
        return cmd

    # -- Rendering -----------------------------------------------------------

    def render(
        self,
        script_path: Path,
        scene_name: str,
        task_uuid: str | None = None,
    ) -> Path:
        """Execute manim to render the scene and return the video path.

        Args:
            script_path: Path to the ``.py`` script.
            scene_name:  The scene class name to render.
            task_uuid:   UUID for output naming. Extracted from *script_path*
                         if *None*.

        Returns:
            Path to the rendered ``.mp4`` file.

        Raises:
            RenderError: If manim exits with a non-zero code, times out,
                         or the expected output video is not found.
        """
        if task_uuid is None:
            task_uuid = script_path.stem

        cmd = self.build_command(script_path, scene_name, task_uuid)

        # Determine expected output path:
        #   manim outputs to: <media_dir>/videos/<script_stem>/<quality>/<SceneName>.mp4
        quality_dir = _QUALITY_MAP.get(self.quality, "480p15")
        expected_video = (
            self.data_dir / "videos" / task_uuid / quality_dir / f"{scene_name}.mp4"
        )

        logger.info("Rendering scene=%s (uuid=%s) ...", scene_name, task_uuid)

        # Hardened environment: interpreter-relative DLL dirs on PATH
        # (fixes IDE launches without conda activation, e.g. PyCharm)
        env = build_child_env()

        # Set PYTHONPATH so the script can import src.* modules
        project_root = str(_PROJECT_ROOT)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{project_root}{os.pathsep}{existing_pp}" if existing_pp else project_root
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
                env=env,
                timeout=600,  # 10-minute timeout
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout
            stderr = exc.stderr
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            raise RenderError(
                "Manim rendering timed out after 600s.",
                stdout=stdout or "",
                stderr=stderr or "TimeoutExpired: rendering exceeded the 10-minute limit.",
            ) from exc

        if result.returncode != 0:
            logger.error(
                "Manim failed (exit %d / %s):\nSTDOUT:\n%s\nSTDERR:\n%s",
                result.returncode,
                hex(result.returncode & 0xFFFFFFFF),
                result.stdout[-2000:] if result.stdout else "(empty)",
                result.stderr[-2000:] if result.stderr else "(empty)",
            )
            raise RenderError(
                f"Manim rendering failed (exit code {result.returncode}).",
                stdout=result.stdout or "",
                stderr=result.stderr or "",
            )

        logger.info("Manim output:\n%s", result.stdout[-1000:] if result.stdout else "")

        if not expected_video.exists():
            # Try to find the video in the media directory
            found = list(
                (self.data_dir / "videos" / task_uuid).rglob(f"{scene_name}.mp4")
            )
            if found:
                expected_video = found[0]
            else:
                raise RenderError(
                    f"Expected video not found: {expected_video}\n"
                    f"Searched under: {self.data_dir / 'videos' / task_uuid}",
                    stdout=result.stdout or "",
                    stderr=result.stderr or "",
                )

        # Copy to data/<uuid>.mp4 for easy access
        final_path = self.data_dir / f"{task_uuid}.mp4"
        shutil.copy2(str(expected_video), str(final_path))
        logger.info("Video rendered → %s", final_path)

        return final_path

    # -- Convenience: full pipeline for a single task ------------------------

    def build_and_render(
        self,
        scene_name: str,
        code: str,
        task_uuid: str | None = None,
    ) -> Path:
        """Write script and render in one call.

        Args:
            scene_name: The scene class name.
            code:       Complete runnable Python code.
            task_uuid:  UUID (auto-generated if *None*).

        Returns:
            Path to the rendered ``.mp4`` file.
        """
        if task_uuid is None:
            task_uuid = str(_uuid.uuid4())

        script_path = self.write_script(scene_name, code, task_uuid)
        return self.render(script_path, scene_name, task_uuid)
