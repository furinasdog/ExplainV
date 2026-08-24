# ExplainV : 基于Manim的讲题视频生成引擎

---

## 项目简介

ExplainV 是一个基于视觉语言模型（VLM）与 Manim 动画引擎的自动化讲题视频生成系统。本项目的核心目标是将复杂的理科题目转化为高质量的动态讲解视频，并自动集成语音合成（TTS）技术。通过结合大模型的逻辑推理能力与 Manim 的数学可视化能力，ExplainV 旨在实现教育辅导内容的自动化与标准化生产。

## 核心特性

- **智能题目解析**：利用 VLM 对输入的题目（文本或图像）进行深度语义理解，自动生成结构化的讲解脚本与分镜逻辑。
- **动态可视化生成**：将解题步骤转化为 Manim 代码，自动生成严谨且直观的数学或物理动画。
- **代码审查校验**：生成代码后自动携带原题与题解交由 LLM 复审，排查元素堆叠、排版越界等问题并优化画面布局。
- **音视频精准同步**：集成 TTS 引擎生成语音旁白，并通过时间戳算法实现音频与动画帧的精准对齐。
- **端到端自动化**：支持从题目输入到最终 MP4 视频输出的全流程自动化处理。

## 安装说明

### 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | ≥ 3.10 | 代码使用了 `str \| Path` 等 PEP 604 语法 |
| FFmpeg | 最新稳定版 | Manim 渲染与音视频合成必需，需加入 PATH |
| LaTeX | 可选 | 若生成的动画包含数学公式（`MathTex`），需安装 [MiKTeX](https://miktex.org/)（Windows）或 TeX Live |
| Conda | 推荐 | Windows 下强烈推荐使用 Miniconda/Anaconda，可自动配置 Pango/Cairo 等原生依赖 |

> **Windows 用户注意**：Manim 依赖 Pango、Cairo 等原生库，通过 Conda 安装可避免 DLL 缺失问题。本项目已内置对未激活 Conda 环境（如 PyCharm 直接启动）的兼容处理。

### 安装步骤

**1. 克隆仓库**

```bash
git clone <repository-url>
cd ExplainV
```

**2. 创建虚拟环境**

```bash
# 推荐使用 Conda
conda create -n explainv python=3.10 -y
conda activate explainv

# 或使用 venv
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

**3. 安装依赖**

```bash
# 项目基础依赖
pip install -r requirements.txt

# Manim 渲染引擎与语音同步组件
pip install manim manim-voiceover
```

**4. 配置环境变量**

复制 `.env.example` 为 `.env` 并填写：

```bash
cp .env.example .env
```

```env
# LLM 服务配置（用于题解生成与 Manim 代码生成）
EXPLAINV_API_URL=<OpenAI 兼容 API 端点>
EXPLAINV_API_KEY=<API Key>
EXPLAINV_USE_MODEL=<模型名称，如 Kimi-k3>

# 阿里云百炼平台配置（用于 TTS 语音克隆与合成）
DASHSCOPE_WORKSPACE_ID=<业务空间 ID>
DASHSCOPE_WORKSPACE_KEY=<API Key>
```

**5. 准备参考音频**

项目默认使用 `asset/mar7th.wav` 进行声音克隆。如需自定义音色，请准备一段 10–20 秒、清晰无背景音的 WAV/MP3 朗读音频（详见 `src/audio/README.md`）。

### 验证安装

```bash
# 文本输入生成视频
python main.py -t "已知直角三角形两条直角边分别为3和4，求斜边长度。"

# 图片输入生成视频
python main.py -i ./problem.png

# 自定义参考音频与画质（l/m/h/k 对应 480p~4K）
python main.py -t "求解方程 x^2 + 2x + 1 = 0" -a asset/anaxa.wav -q m

# 启动 Web 演示界面（http://localhost:7860）
python demo.py
```

生成成功后，输出视频位于 `data/<uuid>.mp4`。

## 系统工作流程

1. **输入阶段**：接收用户提供的题目文本或截图。
2. **脚本生成**：VLM 分析题目考点与解题步骤，输出包含文本旁白与动画指令的 JSON 或领域特定语言（DSL）脚本。
3. **代码审查**：将原题、题解与生成的代码一并交给审查 LLM，校验内容正确性并修复元素堆叠、排版布局等视觉问题。
4. **动画渲染**：解析脚本中的动画指令，调用 Manim 引擎渲染对应的视频片段；渲染失败时自动将报错回传 LLM 修复并重试。
5. **语音合成**：调用 TTS 接口将旁白文本转换为音频文件，并计算语音时长。
6. **后期合成**：根据语音时长动态调整 Manim 动画的播放速率，使用 FFmpeg 将音视频轨道合并并输出最终视频。

## 贡献指南

欢迎对本项目提出改进建议或贡献代码。在提交 Pull Request 之前，请确保：

1. 代码符合项目的 PEP 8 规范。
2. 新增功能包含相应的单元测试。
3. 提交信息清晰、准确地描述所做的更改。