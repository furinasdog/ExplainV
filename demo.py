"""
ExplainV — Gradio demo UI.

Launch::

    python demo.py

Opens a web interface where you can:
    - Enter problem text or upload an image
    - Upload reference audio for voice cloning
    - Generate an animated explanation video
"""

import sys
import traceback
import uuid
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load environment variables
from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

import gradio as gr

from src.core.pipeline import Pipeline, PipelineResult
from utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_REF_AUDIO = str(_PROJECT_ROOT / "asset" / "mar7th.wav")


def _generate_video(
    problem_text: str | None,
    problem_image,
    ref_audio_file,
    quality: str,
    progress=gr.Progress(track_tqdm=False),
):
    """Run the full pipeline and return results for the Gradio UI.

    Returns:
        (video_path, explanation_text, code_text, status_text)
    """
    progress(0, desc="初始化...")

    # -- Validate inputs --
    has_text = problem_text and problem_text.strip()
    has_image = problem_image is not None

    if not has_text and not has_image:
        return None, "", "", "❌ 请输入题目文本或上传题目图片"

    # -- Resolve reference audio --
    if ref_audio_file is not None:
        ref_audio = ref_audio_file if isinstance(ref_audio_file, str) else ref_audio_file.name
    else:
        ref_audio = _DEFAULT_REF_AUDIO

    if not Path(ref_audio).exists():
        return None, "", "", f"❌ 参考音频不存在: {ref_audio}"

    logger.info("Starting generation — ref_audio=%s, quality=%s", ref_audio, quality)

    # -- Build pipeline --
    try:
        def on_progress(stage: str, value: float):
            stage_labels = {
                "pipeline": "整体进度",
                "explanation": "生成题解",
                "code_generation": "生成代码",
                "parsing": "解析代码",
                "code_reviewing": "审查优化代码",
                "rendering": "渲染视频",
                "code_fixing": "自动修复代码",
            }
            label = stage_labels.get(stage, stage)
            progress(value, desc=f"{label}...")

        pipeline = Pipeline(
            ref_audio_path=ref_audio,
            quality=quality,
            on_progress=on_progress,
        )

        # -- Run --
        progress(0.05, desc="正在生成题解...")

        if has_image:
            # Gradio Image component returns a filepath string or numpy array
            # We need to save it to a temp file if it's an array
            import numpy as np
            from PIL import Image as PILImage

            if isinstance(problem_image, np.ndarray):
                tmp_img = _PROJECT_ROOT / "data" / f"_tmp_{uuid.uuid4().hex[:8]}.png"
                tmp_img.parent.mkdir(parents=True, exist_ok=True)
                PILImage.fromarray(problem_image).save(str(tmp_img))
                img_path = str(tmp_img)
            else:
                img_path = str(problem_image)

            result: PipelineResult = pipeline.run_image(img_path)
        else:
            result = pipeline.run_text(problem_text.strip())

        progress(1.0, desc="完成！")

        status = (
            f"✅ 生成完成！\nUUID: {result.uuid}\n"
            f"场景: {result.scene.scene_name}\n视频: {result.video_path}"
        )
        return (
            str(result.video_path),
            result.explanation,
            result.scene.code,
            status,
        )

    except Exception as e:
        logger.exception("Pipeline failed")
        tb = traceback.format_exc()
        return None, "", "", f"❌ 生成失败:\n{str(e)}\n\n{tb}"


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    """Build and return the Gradio Blocks interface."""

    with gr.Blocks(
        title="ExplainV — AI 题解视频生成器",
    ) as demo:
        gr.Markdown(
            """
            # 🎬 ExplainV — AI 题解视频生成器
            输入一道题目（文本或图片），自动生成带语音讲解的动画视频。
            """
        )

        with gr.Row():
            # -- Left panel: Inputs --
            with gr.Column(scale=1):
                gr.Markdown("### 📝 题目输入")

                problem_text = gr.Textbox(
                    label="题目文本",
                    placeholder="例如：已知直角三角形两条直角边分别为3和4，求斜边长度。",
                    lines=5,
                )

                problem_image = gr.Image(
                    label="或上传题目图片",
                    type="numpy",
                    sources=["upload", "clipboard"],
                )

                gr.Markdown("### 🔊 语音设置")

                ref_audio = gr.Audio(
                    label="参考音频（可选，默认使用 mar7th.wav）",
                    type="filepath",
                    sources=["upload"],
                )

                quality = gr.Radio(
                    choices=[
                        ("低画质 (480p, 快速)", "l"),
                        ("中画质 (720p)", "m"),
                        ("高画质 (1080p)", "h"),
                        ("超高清 (4K, 很慢)", "k"),
                    ],
                    value="l",
                    label="渲染画质",
                )

                generate_btn = gr.Button(
                    "🚀 生成视频",
                    variant="primary",
                    size="lg",
                )

            # -- Right panel: Outputs --
            with gr.Column(scale=1):
                gr.Markdown("### 🎥 输出结果")

                status_text = gr.Textbox(
                    label="状态",
                    interactive=False,
                    lines=3,
                )

                video_output = gr.Video(
                    label="生成的视频",
                    autoplay=False,
                )

                with gr.Accordion("📖 题解内容", open=False):
                    explanation_output = gr.Textbox(
                        label="LLM 生成的题解",
                        interactive=False,
                        lines=15,
                    )

                with gr.Accordion("💻 Manim 代码", open=False):
                    code_output = gr.Code(
                        label="生成的 Manim 代码",
                        language="python",
                        interactive=False,
                    )

        # -- Wire up the button --
        generate_btn.click(
            fn=_generate_video,
            inputs=[problem_text, problem_image, ref_audio, quality],
            outputs=[video_output, explanation_output, code_output, status_text],
        )

        gr.Markdown(
            """
            ---
            **使用说明：**
            1. 在左侧输入题目文本或上传图片
            2. 可选择上传参考音频（用于语音克隆，不上传则使用默认音频）
            3. 选择渲染画质
            4. 点击"生成视频"按钮
            5. 等待生成完成后在右侧查看视频

            **注意：** 首次运行需要上传参考音频进行语音克隆，耗时较长。
            """
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(),
    )
