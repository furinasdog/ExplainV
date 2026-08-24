"""
Alibaba Cloud Bailian TTS module with voice cloning support.

Uses qwen-audio-3.0-tts-plus model for high-quality speech synthesis.

Workflow:
    1. VoiceCloner — upload reference audio to create a cloned voice
    2. TTS — synthesize speech with the cloned voice

Example::

    from src.audio import VoiceCloner, TTS

    cloner = VoiceCloner("./reference.wav")
    voice_id = cloner.create_voice()

    tts = TTS(voice_id)
    tts.save("你好，欢迎使用语音合成", "./output.mp3")
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

import dashscope
import requests
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "qwen-audio-3.0-tts-plus"
DEFAULT_AUDIO_FORMAT = AudioFormat.MP3_24000HZ_MONO_256KBPS
DEFAULT_VOICE_PREFIX = "explainv"

# MIME types for supported audio formats
_MIME_MAP = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}


# ---------------------------------------------------------------------------
# VoiceCloner
# ---------------------------------------------------------------------------

class VoiceCloner:
    """Create a custom voice by uploading a reference audio file.

    The reference audio should be 10–20 seconds of clear speech
    (WAV / MP3 / M4A, ≥ 16 kHz, ≤ 10 MB).

    Args:
        audio_path: Local path to the reference audio file.
        model:      Target TTS model to bind the voice to.
        prefix:     Name prefix for the created voice.
    """

    def __init__(
        self,
        audio_path: str,
        model: str = DEFAULT_MODEL,
        prefix: str = DEFAULT_VOICE_PREFIX,
    ):
        self.api_key: Optional[str] = os.getenv("DASHSCOPE_WORKSPACE_KEY")
        self.workspace_id: Optional[str] = os.getenv("DASHSCOPE_WORKSPACE_ID")

        if not self.api_key:
            raise RuntimeError("DASHSCOPE_WORKSPACE_KEY not set in environment")
        if not self.workspace_id:
            raise RuntimeError("DASHSCOPE_WORKSPACE_ID not set in environment")

        self.audio_path = Path(audio_path)
        if not self.audio_path.exists():
            raise FileNotFoundError(f"Reference audio not found: {audio_path}")

        self.model = model
        self.prefix = prefix

        ext = self.audio_path.suffix.lower()
        if ext not in _MIME_MAP:
            raise ValueError(
                f"Unsupported audio format '{ext}'. "
                f"Supported: {', '.join(_MIME_MAP)}"
            )
        self.mime_type = _MIME_MAP[ext]

        # URL for the voice-enrollment HTTP API (Beijing region)
        self._enrollment_url = (
            f"https://{self.workspace_id}.cn-beijing.maas.aliyuncs.com"
            f"/api/v1/services/audio/tts/customization"
        )

    def create_voice(self) -> str:
        """Encode the reference audio and call the voice-enrollment API.

        Returns:
            The ``voice_id`` string that can be passed to :class:`TTS`.

        Raises:
            RuntimeError: If the API call fails or returns an error.
        """
        logger.info("Encoding reference audio: %s", self.audio_path)
        audio_b64 = base64.b64encode(self.audio_path.read_bytes()).decode()
        data_uri = f"data:{self.mime_type};base64,{audio_b64}"

        payload = {
            "model": "voice-enrollment",
            "input": {
                "action": "create_voice",
                "target_model": self.model,
                "prefix": self.prefix,
                "url": data_uri,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "Creating voice (model=%s, prefix=%s) ...", self.model, self.prefix
        )
        resp = requests.post(self._enrollment_url, json=payload, headers=headers)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Voice enrollment failed [{resp.status_code}]: {resp.text}"
            )

        data = resp.json()

        # Extract voice_id — field name differs across model families:
        #   Qwen-Audio-TTS / CosyVoice  → output.voice_id
        #   Qwen-TTS                     → output.voice
        output = data.get("output", {})
        voice_id = output.get("voice_id") or output.get("voice")

        if not voice_id:
            raise RuntimeError(f"Failed to parse voice_id from response: {data}")

        logger.info("Voice created: %s", voice_id)
        return voice_id


# ---------------------------------------------------------------------------
# TTS (Text-to-Speech)
# ---------------------------------------------------------------------------

class TTS:
    """Text-to-speech synthesis using Alibaba Cloud Bailian TTS.

    Uses the DashScope SDK's :class:`SpeechSynthesizer` (WebSocket-based,
    non-streaming) to convert text into audio bytes — similar to how
    ``gTTS.save()`` writes an audio file.

    Args:
        voice_id:     Voice ID (from :meth:`VoiceCloner.create_voice` or a
                      built-in system voice name).
        model:        TTS model name.
        audio_format: Output audio format (an :class:`AudioFormat` enum value).
    """

    def __init__(
        self,
        voice_id: str,
        model: str = DEFAULT_MODEL,
        audio_format: AudioFormat = DEFAULT_AUDIO_FORMAT,
    ):
        self.api_key: Optional[str] = os.getenv("DASHSCOPE_WORKSPACE_KEY")
        self.workspace_id: Optional[str] = os.getenv("DASHSCOPE_WORKSPACE_ID")

        if not self.api_key:
            raise RuntimeError("DASHSCOPE_WORKSPACE_KEY not set in environment")
        if not self.workspace_id:
            raise RuntimeError("DASHSCOPE_WORKSPACE_ID not set in environment")

        self.voice_id = voice_id
        self.model = model
        self.audio_format = audio_format

        # Configure DashScope SDK for Beijing region
        dashscope.api_key = self.api_key
        dashscope.base_websocket_api_url = (
            f"wss://{self.workspace_id}.cn-beijing.maas.aliyuncs.com"
            f"/api-ws/v1/inference"
        )

    def synthesize(self, text: str) -> bytes:
        """Synthesize *text* into raw audio bytes.

        Args:
            text: The text to convert to speech.

        Returns:
            Raw audio data as ``bytes``.

        Raises:
            RuntimeError: If synthesis fails or returns no audio.
        """
        logger.info("Synthesizing (%d chars, voice=%s) ...", len(text), self.voice_id)

        synthesizer = SpeechSynthesizer(
            model=self.model,
            voice=self.voice_id,
            format=self.audio_format,
        )
        audio = synthesizer.call(text)

        if audio is None:
            raise RuntimeError(
                "TTS synthesis returned no audio data. "
                f"request_id={synthesizer.get_last_request_id()}"
            )

        logger.info(
            "Synthesis done — %d bytes | request_id=%s | first_packet=%sms",
            len(audio),
            synthesizer.get_last_request_id(),
            synthesizer.get_first_package_delay(),
        )
        return audio

    def save(self, text: str, output_path: str) -> Path:
        """Synthesize *text* and write the audio to a local file.

        Args:
            text:        The text to convert to speech.
            output_path: Destination file path.

        Returns:
            A :class:`~pathlib.Path` to the saved file.
        """
        audio = self.synthesize(text)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        logger.info("Audio saved → %s (%d bytes)", path, len(audio))
        return path


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    # Step 1: Create a cloned voice from reference audio
    cloner = VoiceCloner("./reference.wav")
    voice_id = cloner.create_voice()
    print(f"voice_id = {voice_id}")

    # Step 2: Synthesize speech with the cloned voice
    tts = TTS(voice_id)
    tts.save("今天天气真不错，适合出去走走。", "./output.mp3")
