# 基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 将 Poetry 添加到 PATH
ENV PATH="/root/.local/bin:$PATH"

# 复制 Poetry 配置
COPY pyproject.toml poetry.lock* /app/

# 配置 Poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# 复制应用代码
COPY app /app/app
COPY vectorizer /app/vectorizer
COPY knowledge /app/knowledge
COPY data /app/data

# 设置环境变量
ENV PYTHONPATH="/app"

# 暴露 Web 服务端口
EXPOSE 8501

# 默认启动命令行版本
CMD ["python", "-m", "app.cli"]
