"""
Command-line argument parsing for ExplainV.

Usage::

    from utils.command_line import parse_args
    args = parse_args()
    print(args.input_text)
"""

import argparse
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse ExplainV CLI arguments.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed :class:`argparse.Namespace` with the following attributes:

        - ``input_text`` (str | None): Problem text.
        - ``input_image`` (str | None): Path to problem image.
        - ``ref_audio`` (str): Path to reference audio for voice cloning.
        - ``output`` (str | None): Output video path override.
        - ``model`` (str): LLM model name override.
        - ``quality`` (str): Manim render quality (``l`` / ``m`` / ``h`` / ``k``).
        - ``verbose`` (bool): Enable debug logging.
    """
    parser = argparse.ArgumentParser(
        prog="explainv",
        description="ExplainV — AI-powered educational video generator",
    )

    # -- Input ---------------------------------------------------------------
    input_group = parser.add_argument_group("Input")
    input_group.add_argument(
        "-t", "--text",
        dest="input_text",
        type=str,
        default=None,
        help="Problem text (mutually exclusive with --image)",
    )
    input_group.add_argument(
        "-i", "--image",
        dest="input_image",
        type=str,
        default=None,
        help="Path to problem image (mutually exclusive with --text)",
    )

    # -- Audio ---------------------------------------------------------------
    parser.add_argument(
        "-a", "--ref-audio",
        dest="ref_audio",
        type=str,
        default=str(Path("asset") / "mar7th.wav"),
        help="Path to reference audio for voice cloning (default: asset/mar7th.wav)",
    )

    # -- Output --------------------------------------------------------------
    parser.add_argument(
        "-o", "--output",
        dest="output",
        type=str,
        default=None,
        help="Output video path (default: data/<uuid>.mp4)",
    )

    # -- Model / quality -----------------------------------------------------
    parser.add_argument(
        "-m", "--model",
        dest="model",
        type=str,
        default=None,
        help="Override LLM model name",
    )
    parser.add_argument(
        "-q", "--quality",
        dest="quality",
        type=str,
        choices=["l", "m", "h", "k"],
        default="l",
        help="Manim render quality: l=480p, m=720p, h=1080p, k=4K (default: l)",
    )
    parser.add_argument(
        "-r", "--max-retries",
        dest="max_retries",
        type=int,
        default=3,
        help="Max LLM auto-repair rounds when rendering fails (default: 3)",
    )

    # -- Misc ----------------------------------------------------------------
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging",
    )

    args = parser.parse_args(argv)

    # -- Validation ----------------------------------------------------------
    if args.input_text is None and args.input_image is None:
        parser.error("At least one of --text or --image is required")

    if args.input_text and args.input_image:
        parser.error("--text and --image are mutually exclusive")

    if args.input_image and not Path(args.input_image).exists():
        parser.error(f"Image file not found: {args.input_image}")

    if args.ref_audio and not Path(args.ref_audio).exists():
        parser.error(f"Reference audio not found: {args.ref_audio}")

    if args.max_retries < 0:
        parser.error("--max-retries must be >= 0")

    return args
