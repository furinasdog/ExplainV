# ExplainV API 服务镜像
# 基于 Manim 官方社区镜像（已预装 TeX Live + FFmpeg + Python）

FROM manimcommunity/manim:latest

USER root

WORKDIR /app

# 安装系统依赖 + 中文字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 用 tlmgr 安装中文 LaTeX 包（manim 使用 /usr/local/texlive）
RUN tlmgr install ctex xecjk fontspec \
    && tlmgr update --self

# 复制依赖文件，利用 Docker 缓存
COPY requirements.txt .

# 配置阿里云 pip 镜像源 + 安装 Python 依赖
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        fastapi \
        "uvicorn[standard]" \
        python-multipart \
        pydantic-settings

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/media

# 切换回 manim 用户
USER manimuser

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
