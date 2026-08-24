# src/audio — 百炼 TTS 语音合成模块

基于阿里云百炼平台（DashScope）的语音合成模块，支持 **声音复刻** 和 **文本转语音**。

## 架构

```
src/audio/
├── __init__.py              # 导出 VoiceCloner, TTS
├── tts.py                   # 核心：VoiceCloner + TTS
├── bailian_service.py       # manim-voiceover 集成
├── doc.txt                  # 百炼 API 官方文档
├── gtts_demo.py             # gTTS 参考实现
└── README.md                # 本文件
```

## 使用的百炼 API

### 模型

| 用途 | 模型名 | 说明 |
|------|--------|------|
| 语音合成 | `qwen-audio-3.0-tts-plus` | Qwen-Audio-TTS 高质量版，非实时 HTTP 合成 |
| 声音复刻 | `voice-enrollment` | 上传参考音频创建定制音色 |

### API 端点

| 功能 | 方法 | 端点 |
|------|------|------|
| 声音复刻 | POST | `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization` |
| 语音合成 | WebSocket | `wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference` |

> 以上均为 **华北2（北京）** 地域端点。

### 认证

通过 `.env` 配置：

```env
DASHSCOPE_WORKSPACE_ID=<业务空间ID>
DASHSCOPE_WORKSPACE_KEY=<API Key>
```

## 核心类

### VoiceCloner

上传参考音频文件，创建复刻音色。

```python
from src.audio import VoiceCloner

cloner = VoiceCloner("./asset/mar7th.wav")
voice_id = cloner.create_voice()
# → "qwen-audio-3.0-tts-plus-explainv-xxxxx"
```

**参考音频要求：**
- 格式：WAV (16bit) / MP3 / M4A
- 时长：10–20 秒（最长 60 秒）
- 大小：≤ 10 MB
- 采样率：≥ 16 kHz
- 内容：连续清晰的朗读，无背景音

### TTS

使用音色 ID 合成语音，保存为本地文件。

```python
from src.audio import TTS

tts = TTS(voice_id="qwen-audio-3.0-tts-plus-explainv-xxxxx")
tts.save("今天天气真不错", "./output.mp3")
```

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `synthesize(text)` | `bytes` | 返回原始音频数据 |
| `save(text, path)` | `Path` | 合成并保存到文件 |

**构造参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `voice_id` | (必填) | 音色 ID（复刻或系统音色） |
| `model` | `qwen-audio-3.0-tts-plus` | TTS 模型 |
| `format` | `mp3` | 输出格式 |
| `sample_rate` | `24000` | 采样率 (Hz) |

### BailianService

manim-voiceover 的 `SpeechService` 适配器，用于在 Manim 动画中同步语音和动画。

```python
from manim import *
from manim_voiceover import VoiceoverScene
from src.audio.bailian_service import BailianService

class MyScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(
            BailianService(ref_audio_path="./asset/mar7th.wav")
        )
        with self.voiceover(text="你好世界") as tracker:
            self.play(Create(Circle()), run_time=tracker.duration)
```

**工作流程：**
1. 首次运行时，自动上传参考音频创建复刻音色
2. `voice_id` 缓存到 `.voice_id_cache.json`，后续运行跳过上传
3. 每段文本通过 DashScope SDK 的 `SpeechSynthesizer` (WebSocket) 合成
4. 合成结果由 manim-voiceover 缓存，重复文本不会重复合成

## 典型工作流

```
参考音频 (WAV/MP3)
    │
    ▼
VoiceCloner.create_voice()  ──→  voice_id
    │                                │
    │  缓存到 .voice_id_cache.json   │
    ▼                                ▼
TTS(voice_id).save(text, path)  ──→  output.mp3
    │
    ▼
BailianService (manim-voiceover)
    │
    ▼
Manim Scene  ──→  带语音的视频
```

## 依赖

```
dashscope       # DashScope SDK (语音合成 WebSocket)
requests        # HTTP 请求 (声音复刻)
python-dotenv   # .env 加载
manim-voiceover # Manim 语音同步 (仅 BailianService 需要)
```