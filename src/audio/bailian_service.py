"""
manim-voiceover SpeechService backed by Alibaba Cloud Bailian TTS
with voice cloning (qwen-audio-3.0-tts-plus).
"""

import json
import logging
from pathlib import Path

from manim import logger

try:
    from manim_voiceover._typing import VoiceoverData
    from manim_voiceover.helper import remove_bookmarks, prompt_ask_missing_extras
    from manim_voiceover.services.base import (
        PathLike,
        SpeechService,
        initialize_speech_service,
        path_to_string,
    )
except ImportError:
    logger.error(
        "manim-voiceover is required. Install it with: pip install manim-voiceover"
    )

from src.audio.tts import VoiceCloner, TTS

_VOICE_ID_CACHE = ".voice_id_cache.json"


class BailianService(SpeechService):
    """Speech service using Alibaba Cloud Bailian TTS with voice cloning.

    On first use the reference audio is uploaded to create a cloned voice;
    the resulting ``voice_id`` is cached locally so subsequent runs skip
    the upload step.

    Args:
        ref_audio_path: Path to a 10–20 s reference audio file
                        (WAV / MP3 / M4A).
        **kwargs:       Forwarded to ``SpeechService.__init__``.
    """

    def __init__(self, ref_audio_path: str, **kwargs) -> None:
        initialize_speech_service(self, kwargs)
        self.ref_audio_path = ref_audio_path
        self._voice_id: str | None = self._load_cached_voice_id()

        if self._voice_id is None:
            cloner = VoiceCloner(ref_audio_path)
            self._voice_id = cloner.create_voice()
            self._cache_voice_id(self._voice_id)

        self._tts = TTS(self._voice_id)

    # -- Voice ID cache helpers ------------------------------------------

    def _cache_path(self) -> Path:
        return Path(self.ref_audio_path).parent / _VOICE_ID_CACHE

    def _load_cached_voice_id(self) -> str | None:
        p = self._cache_path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                return data.get("voice_id")
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _cache_voice_id(self, voice_id: str) -> None:
        p = self._cache_path()
        p.write_text(json.dumps({"voice_id": voice_id}, indent=2))
        logger.info("Cached voice_id → %s", p)

    # -- SpeechService interface -----------------------------------------

    def generate_from_text(
        self,
        text: str,
        cache_dir: PathLike | None = None,
        path: PathLike | None = None,
        **kwargs,
    ) -> VoiceoverData:
        if cache_dir is None:
            cache_dir = self.cache_dir

        input_text = remove_bookmarks(text)
        input_data = {
            "input_text": input_text,
            "service": "bailian",
            "config": {
                "voice_id": self._voice_id,
                "model": self._tts.model,
            },
        }

        cached = self.get_cached_result(input_data, cache_dir)
        if cached is not None:
            return cached

        if path is None:
            audio_path = self.get_audio_basename(input_data) + ".mp3"
        else:
            audio_path = path_to_string(path)

        output_file = Path(cache_dir) / audio_path
        self._tts.save(input_text, str(output_file))

        result: VoiceoverData = {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }
        return result