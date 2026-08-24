"""
ExplainV — CLI entry point.

Usage::

    # Text input
    python main.py -t "已知直角三角形两条直角边分别为3和4，求斜边长度。"

    # Image input
    python main.py -i ./problem.png

    # Custom reference audio and quality
    python main.py -t "求解方程 x^2 + 2x + 1 = 0" -a asset/anaxa.wav -q m
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

import logging

from src.core.pipeline import Pipeline
from utils.command_line import parse_args
from utils.logger import get_logger, setup_logging


def main() -> None:
    args = parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=level)
    logger = get_logger("explainv")

    logger.info("ExplainV CLI starting...")
    logger.info("  Input text:  %s", args.input_text[:80] if args.input_text else "(none)")
    logger.info("  Input image: %s", args.input_image or "(none)")
    logger.info("  Ref audio:   %s", args.ref_audio)
    logger.info("  Quality:     %s", args.quality)
    logger.info("  Max retries: %s", args.max_retries)

    # Progress display
    def on_progress(stage: str, value: float):
        stage_labels = {
            "pipeline": "整体",
            "explanation": "题解生成",
            "code_generation": "代码生成",
            "parsing": "代码解析",
            "code_reviewing": "代码审查优化",
            "rendering": "视频渲染",
            "code_fixing": "错误自动修复",
        }
        label = stage_labels.get(stage, stage)
        bar_len = 30
        filled = int(bar_len * value)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {label} {value:.0%}", end="", flush=True)

    # Build pipeline
    pipeline = Pipeline(
        ref_audio_path=args.ref_audio,
        quality=args.quality,
        max_retries=args.max_retries,
        on_progress=on_progress,
    )

    # Run
    print("\n🎬 ExplainV — 开始生成\n")

    try:
        if args.input_image:
            result = pipeline.run_image(args.input_image)
        else:
            result = pipeline.run_text(args.input_text)

        print()  # newline after progress bar
        print("\n✅ 生成完成！")
        print(f"   UUID:   {result.uuid}")
        print(f"   场景:   {result.scene.scene_name}")
        print(f"   脚本:   {result.script_path}")
        print(f"   视频:   {result.video_path}")

    except Exception as e:
        logger.exception("Pipeline failed")
        print(f"\n\n❌ 生成失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
