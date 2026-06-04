# DocuMind

本地文档知识库 + Agent-Driven 跨文件分析。**不使用向量** — Agent 通过工具调用导航文档结构，FTS5 提供精确关键词检索。

## 架构

```
frontend/  Vue 3 + TS + Tailwind  (port 5173)
backend/   FastAPI + SQLite/FTS5  (port 8000)
data/      本地存储（uploads/ reports/ docuxmind.db）
```

## 快速启动

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
# 编辑 .env — 至少填 MIMO_API_KEY；如用本地，确保 LM Studio 在 1234 端口
uvicorn app.main:app --reload --port 8000
```

### 前端

```powershell
cd frontend
pnpm install   # 或 npm install
pnpm dev       # http://localhost:5173
```

## 核心能力

| 模块 | 说明 |
|---|---|
| 文件夹管理 | 增删改、色彩主题、软删除 |
| 文档上传 | 拖放/点击；sha256 去重；50MB 上限；txt/md/xlsx 已实现解析 |
| 索引 | 文档大纲（sheet/heading 列表）+ FTS5 全文倒排，BM25 排序 |
| Agent | 8 个工具（list/outline/search/read/write_report）+ SSE 流式回答 + 思考过程面板 |
| LLM | 云端 `mimo-v2.5-pro` 与本地 LM Studio 一键切换 + 能力自检 |
| 检索范围 | UI 上的 ctx-tag 决定 Agent 工具的 folder_id 作用域 |

## 健壮性要点

- WAL 模式 + 短连接事务，多上传并发安全
- 上传 sha256 去重；路径穿越校验；MIME 嗅探
- Agent 三重熔断：`AGENT_MAX_STEPS` / `AGENT_STEP_TIMEOUT_SEC` / `AGENT_TOTAL_TOKEN_LIMIT`
- 解析失败 → `doc.status='error'`，UI 显示重新索引按钮
- 草稿与会话写入 sessionStorage / `chat_messages` 表，刷新不丢
- SSE 支持中途取消（`request.is_disconnected()`）

## 下一阶段（v1.1）

- PDF / DOCX / CSV 解析器
- 文档状态实时推送（替换轮询）
- jieba / sudachipy CJK 分词后置
- 文件夹色彩选择 UI
