"""
make.py — Demo video: explain the Pythagorean theorem with voice + animation.

Usage:
    manim -pql make.py PythagoreanScene

    Or simply:
    python make.py
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work
_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

# Load environment variables from .env
from dotenv import load_dotenv

load_dotenv(_project_root / ".env")

from manim_voiceover import VoiceoverScene

from manim import *
from src.audio.bailian_service import BailianService

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REF_AUDIO = str(_project_root / "asset" / "mar7th.wav")


class PythagoreanScene(VoiceoverScene):
    """A short animated explanation of the Pythagorean theorem."""

    def construct(self):
        self.set_speech_service(BailianService(ref_audio_path=REF_AUDIO))

        # ── Title ──────────────────────────────────────────────────────
        title = Text("勾股定理", font_size=56, color=YELLOW)

        with self.voiceover(text="大家好，今天我们来学习勾股定理。") as tracker:
            self.play(Write(title), run_time=tracker.duration)

        self.wait(0.5)
        self.play(FadeOut(title))

        # ── Theorem statement ──────────────────────────────────────────
        theorem = MathTex("a^2", "+", "b^2", "=", "c^2", font_size=64)
        theorem[0].set_color(RED)
        theorem[2].set_color(GREEN)
        theorem[4].set_color(BLUE)

        with self.voiceover(text="勾股定理告诉我们，a的平方加上b的平方，等于c的平方。") as tracker:
            self.play(FadeIn(theorem, shift=UP * 0.3), run_time=tracker.duration)

        self.wait(1)

        # ── Right triangle ─────────────────────────────────────────────
        A = np.array([-2, -1.5, 0])
        B = np.array([2, -1.5, 0])
        C = np.array([-2, 1.5, 0])

        triangle = Polygon(A, B, C, color=WHITE, stroke_width=3)
        right_angle = Square(side_length=0.25, color=WHITE, stroke_width=2)
        right_angle.move_to(A + np.array([0.125, 0.125, 0]))

        label_a = MathTex("a", color=GREEN, font_size=36).next_to(
            Line(A, C), LEFT, buff=0.2
        )
        label_b = MathTex("b", color=RED, font_size=36).next_to(
            Line(A, B), DOWN, buff=0.2
        )
        label_c = MathTex("c", color=BLUE, font_size=36).next_to(
            Line(B, C).get_center(), UR, buff=0.15
        )

        with self.voiceover(text="在直角三角形中，a和b是两条直角边，c是斜边。") as tracker:
            self.play(
                Create(triangle),
                Create(right_angle),
                run_time=tracker.duration * 0.6,
            )
            self.play(
                Write(label_a),
                Write(label_b),
                Write(label_c),
                run_time=tracker.duration * 0.4,
            )

        self.wait(1)

        # ── Concrete example (3-4-5) ───────────────────────────────────
        example = MathTex("3^2", "+", "4^2", "=", "5^2", font_size=48)
        example.set_color_by_tex("3", GREEN)
        example.set_color_by_tex("4", RED)
        example.set_color_by_tex("5", BLUE)

        with self.voiceover(text="比如，3的平方加4的平方，等于5的平方。") as tracker:
            self.play(theorem.animate.shift(UP * 1.5), run_time=0.5)
            self.play(Write(example), run_time=tracker.duration)

        self.wait(0.5)

        # ── Verify calculation ─────────────────────────────────────────
        calc = MathTex("9", "+", "16", "=", "25", font_size=48, color=GREY_B)
        check = Text("✓", font_size=48, color=GREEN)

        with self.voiceover(text="9加16等于25，完全正确！") as tracker:
            self.play(TransformFromCopy(example, calc), run_time=tracker.duration * 0.7)
            check.next_to(calc, RIGHT, buff=0.3)
            self.play(FadeIn(check, scale=1.5), run_time=tracker.duration * 0.3)

        self.wait(1)

        # ── Ending ─────────────────────────────────────────────────────
        ending = Text("感谢观看！", font_size=56, color=YELLOW)

        with self.voiceover(text="这就是勾股定理，感谢观看！") as tracker:
            self.play(
                *[FadeOut(m) for m in self.mobjects],
                run_time=tracker.duration * 0.5,
            )
            self.play(FadeIn(ending, scale=1.2), run_time=tracker.duration * 0.5)

        self.wait(0.5)


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Default: render at 480p quality with preview
    os.system(f"manim -ql -p {__file__} PythagoreanScene")
