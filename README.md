# Multi-Agent RAG 客服系统

这是一个基于 LangGraph、LangChain、Qdrant 和 FastAPI 的多智能体客服项目。主助手负责识别用户意图并将任务委派给航班、酒店、租车、行程、电商、表单或博客专业助手；查询操作直接执行，修改类操作进入人工审批流程。

## 目录结构

```text
Multi-Agent/
├── app/          # 核心应用：状态图、助手、工具、CLI 与 Web 入口
├── vectorizer/   # 文档分块、Embedding 生成和 Qdrant 写入
├── knowledge/    # FAQ 原始文档、配置和增量更新服务
├── data/         # SQLite 数据库、会话数据和运行日志
├── docs/         # 详细说明、学习指南和原项目文档
├── assets/       # 系统流程图和演示图片
├── scripts/      # 开发辅助脚本
└── drafts/       # 迁移前的学习草稿和旧目录残留，不参与运行
```

## 关键入口

- 对话图：`app/graph.py`
- 命令行入口：`app/cli.py`
- Web 入口：`app/web.py`
- 专业助手：`app/assistants/`
- 工具函数：`app/tools/`
- 向量化入口：`vectorizer/main.py`
- 项目学习指南：`docs/PROJECT_GUIDE.md`

## 启动方式

安装依赖并启动 Qdrant：

```bash
poetry install
docker compose up qdrant -d
```

Embedding 服务可通过环境变量切换。例如使用硅基流动的 BGE-M3：

```dotenv
EMBEDDING_API_KEY=your_siliconflow_api_key
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
```

更换模型或向量维度后，需要重建 Qdrant collections，不能复用不同维度的旧索引。

初始化数据库和向量数据：

```bash
poetry run python setup_database.py
poetry run python -m vectorizer.main
```

启动命令行版本：

```bash
poetry run python -m app.cli
```

启动 Web 版本：

```bash
poetry run uvicorn app.web:app --reload --host 0.0.0.0 --port 8000
```

详细架构、模块说明和阅读顺序见 [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md)。
