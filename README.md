# ExplainV : 基于 Manim 的讲题视频生成引擎

---

## 项目简介

ExplainV 是一个基于视觉语言模型（VLM）与 Manim 动画引擎的自动化讲题视频生成系统。本项目的核心目标是将复杂的理科题目转化为高质量的动态讲解视频，并自动集成语音合成（TTS）技术。通过结合大模型的逻辑推理能力与 Manim 的数学可视化能力，ExplainV 旨在实现教育辅导内容的自动化与标准化生产。

## 核心特性

- **智能题目解析**：利用 VLM 对输入的题目（文本或图像）进行深度语义理解，自动生成结构化的讲解脚本与分镜逻辑。
- **动态可视化生成**：将解题步骤转化为 Manim 代码，自动生成严谨且直观的数学或物理动画。
- **代码审查校验**：生成代码后自动携带原题与题解交由 LLM 复审，排查元素堆叠、排版越界等问题并优化画面布局。
- **音视频精准同步**：集成 TTS 引擎生成语音旁白，并通过时间戳算法实现音频与动画帧的精准对齐。
- **自动修复机制**：渲染失败时自动将报错回传 LLM 修复代码并重试（最多 3 轮）。
- **端到端自动化**：支持从题目输入到最终 MP4 视频输出的全流程自动化处理。
- **可定制讲解模块**：用户可选择视频包含哪些讲解模块（题目复述、知识点、解答过程、答案验证、易错考点等）。

## 部署方式

### 方式一：CLI / Gradio 演示（本地开发）

适合本地开发和测试。

```bash
git clone <repository-url> && cd ExplainV
conda create -n explainv python=3.10 -y && conda activate explainv
pip install -r requirements.txt
cp .env.example .env  # 编辑填写 API 密钥

# CLI 生成视频
python main.py -t "已知直角三角形两条直角边分别为3和4，求斜边长度。"

# Gradio Web UI（http://localhost:7860）
python demo.py
```

### 方式二：FastAPI 服务 + Docker + Kubernetes（生产部署）

适合线上服务部署，支持多 Pod 并行生成、按需扩缩容、视频自动上传 OSS。

**架构概览：**

```
WebUI 后端（Node.js）
  │  提交任务 → 扩容 Pod → 提交到 API
  ▼
ExplainV API（FastAPI，k8s Pod，按需 0~10 个）
  │  Pipeline 生成视频 → 上传 OSS → 返回链接
  ▼
阿里云 OSS（视频存储）
```

**快速启动（Docker Compose）：**

```bash
docker compose up --build
# API: http://localhost:8000
# curl http://localhost:8000/health
```

**Kubernetes 部署（阿里云 ACK Serverless）：**

```bash
# 创建命名空间和资源
kubectl apply -f k8s/

# 创建 Secret（API 密钥 + OSS 配置）
kubectl create secret generic explainv-secrets -n explainv \
  --from-literal=EXPLAINV_API_URL="..." \
  --from-literal=EXPLAINV_API_KEY="..." \
  --from-literal=EXPLAINV_USE_MODEL="..." \
  --from-literal=DASHSCOPE_WORKSPACE_ID="..." \
  --from-literal=DASHSCOPE_WORKSPACE_KEY="..." \
  --from-literal=EXPLAINV_OSS_REGION="https://oss-cn-beijing.aliyuncs.com" \
  --from-literal=EXPLAINV_OSS_BUCKET="..." \
  --from-literal=EXPLAINV_OSS_ACCESS_KEY_ID="..." \
  --from-literal=EXPLAINV_OSS_ACCESS_KEY_SECRET="..."
```

Pod 默认 0 副本，由 WebUI 后端按需扩缩。

### 方式三：WebUI（全栈 Web 应用）

独立的 Web 前端 + Node.js 后端，支持用户注册登录、任务管理、管理员后台。

```bash
cd webui
npm run install:all
cp .env.example .env  # 编辑填写配置
npm run dev
# 前端: http://localhost:5173
# 后端: http://localhost:3000
```

**WebUI 功能：**

| 功能 | 说明 |
|------|------|
| 用户注册/登录 | JWT 认证，bcrypt 密码哈希 |
| 创建任务 | 文本/图片输入、画质选择、讲解模块勾选 |
| 任务列表 | 实时进度、阶段显示、自动刷新 |
| 视频下载 | 生成完成后 OSS 签名链接直接下载 |
| 管理员后台 | Pod 管理（列表/删除/扩缩容）、用户管理、任务管理 |
| 深色/浅色主题 | GitHub 风格 UI，一键切换 |

**管理员默认账户：** `Admin` / `Admin@321`

## 环境变量

### 核心配置（`.env`）

| 变量 | 说明 |
|------|------|
| `EXPLAINV_API_URL` | OpenAI 兼容 API 端点 |
| `EXPLAINV_API_KEY` | API Key |
| `EXPLAINV_USE_MODEL` | 模型名称（如 `qwen3.7-plus`） |
| `DASHSCOPE_WORKSPACE_ID` | 阿里云百炼业务空间 ID |
| `DASHSCOPE_WORKSPACE_KEY` | 百炼 API Key |

### API 服务配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EXPLAINV_OSS_REGION` | — | OSS 区域（如 `https://oss-cn-beijing.aliyuncs.com`） |
| `EXPLAINV_OSS_BUCKET` | — | OSS Bucket 名称 |
| `EXPLAINV_OSS_ACCESS_KEY_ID` | — | 阿里云 AccessKey ID |
| `EXPLAINV_OSS_ACCESS_KEY_SECRET` | — | 阿里云 AccessKey Secret |

### WebUI 配置（`webui/.env`）

| 变量 | 说明 |
|------|------|
| `JWT_SECRET` | JWT 签名密钥 |
| `KUBECONFIG_PATH` | kubeconfig 文件路径 |
| `ACK_NAMESPACE` | k8s 命名空间（默认 `explainv`） |
| `ACK_DEPLOYMENT` | Deployment 名称 |
| `ACK_SERVICE_URL` | ExplainV API 公网地址 |
| `OSS_REGION` / `OSS_BUCKET` / `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` | OSS 配置 |

## 系统工作流程

1. **输入阶段**：接收用户提供的题目文本或截图。
2. **脚本生成**：VLM 分析题目考点与解题步骤，输出结构化的讲解内容。
3. **代码生成**：将题解转换为 Manim 动画代码。
4. **代码审查**：将原题、题解与代码交由审查 LLM，校验内容正确性并修复排版问题。
5. **动画渲染**：调用 Manim 引擎渲染视频；失败时自动回传 LLM 修复并重试（最多 3 轮）。
6. **语音合成**：TTS 引擎生成语音旁白，与动画帧精准同步。
7. **视频上传**：生成完成后自动上传至 OSS，返回签名下载链接。

## 项目结构

```
ExplainV/
├── src/
│   ├── api/              # FastAPI 服务
│   │   ├── app.py        # API 路由 + Pipeline 调度
│   │   ├── config.py     # 配置管理
│   │   └── schemas.py    # 请求/响应模型
│   ├── core/
│   │   └── pipeline.py   # 核心 Pipeline（解释→生成→审查→渲染→修复）
│   ├── llm/
│   │   ├── client.py     # OpenAI 兼容 LLM 客户端（流式调用）
│   │   └── parser.py     # LLM 响应解析器
│   ├── manim/
│   │   └── builder.py    # Manim 脚本编写与渲染
│   ├── audio/
│   │   ├── tts.py        # DashScope TTS 语音克隆与合成
│   │   └── bailian_service.py  # manim-voiceover 适配器
│   └── options.py        # 可定制讲解模块
├── prompt/               # LLM 提示词模板（Jinja2）
├── webui/                # Web 全栈应用
│   ├── backend/          # Node.js + Express 后端
│   │   ├── routes/       # 认证、任务、管理员路由
│   │   └── services/     # k8s 集群控制、OSS 上传、任务轮询
│   └── frontend/         # Vue 3 + Vite 前端
│       └── src/
│           ├── views/    # 登录、注册、Dashboard、创建任务、管理后台
│           ├── components/  # 导航栏、任务卡片
│           └── styles/   # GitHub 风格主题 CSS
├── k8s/                  # Kubernetes 部署文件
├── tests/                # 单元测试（144+ 测试用例）
├── Dockerfile            # Docker 镜像（基于 manimcommunity/manim）
├── docker-compose.yml    # 本地容器编排
└── .env.example          # 环境变量模板
```

## 环境要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | ≥ 3.10 | 代码使用了 `str \| Path` 等 PEP 604 语法 |
| FFmpeg | 最新稳定版 | Manim 渲染与音视频合成必需 |
| LaTeX | TeX Live 或 MiKTeX | 数学公式渲染必需（Docker 镜像已内置） |
| Node.js | ≥ 18 | WebUI 后端（可选） |
| Docker | 最新稳定版 | 容器化部署（可选） |

## 贡献指南

欢迎对本项目提出改进建议或贡献代码。在提交 Pull Request 之前，请确保：

1. 代码符合项目的 PEP 8 规范（已配置 Ruff linter）。
2. 新增功能包含相应的单元测试。
3. 提交信息清晰、准确地描述所做的更改。