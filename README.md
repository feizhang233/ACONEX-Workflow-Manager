# ACONEX Workflow Manager

完整的 ACONEX Workflow 自动化管理系统：从 ACONEX API 拉取 Workflow / Step / Final Mail，写入 SQLite，按可配置规则同步到 Google Sheets，并支持手动运行与持久化定时任务。

**数据流：** `ACONEX API → FastAPI → SQLite → Google Sheets`

## 目录结构

```
backend/          # Python FastAPI 服务
frontend/         # React + Vite + TypeScript UI
data/             # SQLite 与运行数据（自动创建）
docker-compose.yml
.env.example
```

## 快速启动（本地）

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 在项目根目录准备 .env（可复制 .env.example）
export PYTHONPATH=.
export SECRET_KEY=dev-secret-change-me
export DATABASE_URL=sqlite:////absolute/path/to/AcoenxUpdateForEveryone/data/aconex_manager.db

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：`http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：`http://127.0.0.1:5173`（Vite 已代理 `/api` 到后端）。

### Docker Compose

```bash
cp .env.example .env
# 编辑 SECRET_KEY 等
docker compose up --build
```

- 前端：http://localhost:5173  
- 后端健康检查：http://localhost:5173/api/health
- API 文档：http://localhost:5173/docs

Compose 中的后端只暴露在 Docker 内部网络，并由前端 Nginx 代理 `/api`、`/docs`，
因此不会再占用宿主机的 `8000` 端口。如果之前因
`Bind for 0.0.0.0:8000 failed: port is already allocated` 启动失败，可直接重新运行：

```bash
docker compose up --build
```

## ACONEX OAuth 配置

1. 打开前端 **ACONEX 设置**。
2. 填写：
   - Authorization URL（默认 Oracle Construction：`https://constructionandengineering.oraclecloud.com/auth/authorize`）
   - Token URL（`.../auth/token`）
   - Base URL（如 `https://eu1.aconex.com`）
   - Client ID / Client Secret
   - Redirect URI（需与 Oracle 应用一致，如 `http://localhost:8080/callback`）
   - Project ID
3. 点击 **生成授权地址**，浏览器登录授权后，从回调 URL 复制 `code`。
4. 粘贴 Authorization Code，点击 **用 Code 交换 Token**。
5. 系统会加密保存 Access / Refresh Token；之后可点 **测试连接**，并 **获取 Projects** 选择项目。

也可直接粘贴已有 **Refresh Token** 并保存。

**安全：** Client Secret、Token、Service Account JSON 仅后端 Fernet 加密存储；API 只返回掩码；前端不写 localStorage。

## Google Sheets 配置

1. 在 Google Cloud 创建 Service Account，下载 JSON 密钥。
2. 将 Spreadsheet 共享给该 Service Account 邮箱（编辑权限）。
3. 在前端 **Google Sheets** 页填写：
   - Spreadsheet ID 或完整 URL
   - Sheet 名称
   - Service Account JSON
   - 输出字段 / 列名 / 列顺序
4. **测试连接** 确认可读表格元数据。

同步行为：

- 业务键：`Workflow Number + Step`（按列映射中的 step 字段匹配）
- 增量：只写 pending/failed 或规则触发的行；已存在键则更新，不重复插入
- 全量：可在手动/参数中 `full_sheet_sync`
- 写入失败：Step 标记 `failed`，队列保留，下次可重试

## 数据库结构（SQLite，WAL）

| 表 | 用途 |
|----|------|
| `aconex_settings` | OAuth / Project 配置（密文） |
| `google_sheets_settings` | Sheets 配置与列映射（SA JSON 密文） |
| `tracked_workflows` | 用户追踪的 Workflow 编号 |
| `workflows` | Workflow 主数据 |
| `workflow_steps` | 各 Step 状态、逾期、Final Mail、Sheet 同步状态 |
| `workflow_history` | 状态变更历史 |
| `workflow_comments` | Final Mail 评论 |
| `feedback_rules` | Step/字段/状态/触发规则 |
| `scheduled_jobs` | 持久化定时任务定义 |
| `job_locks` | 防止同任务并发 |
| `update_runs` / `run_logs` | 运行记录与分阶段日志 |
| `sync_queue` | Sheets 待同步/失败队列 |

## 定时任务

前端 **定时任务** 页可创建：

- 每隔 N 分钟 / 小时
- 每天指定时间
- 指定星期 + 时间
- Cron（`分 时 日 月 周`，如 `0 10 * * 1-5`）

默认时区：`Europe/Belgrade`。任务保存在 `scheduled_jobs`，进程启动时由 APScheduler 重新加载。`max_instances=1` + DB `job_locks` 保证同一逻辑任务不并发。

## 页面一览

1. Dashboard — 手动 Pipeline / 分步同步、实时进度与 SSE 日志  
2. ACONEX 设置 — OAuth、Token、Project  
3. Google Sheets 设置 — SA、列映射  
4. Workflow 追踪 — 批量/范围编号、启用暂停  
5. Step/反馈规则 — 不写死 Step  
6. 定时任务  
7. 运行历史 — 重试失败任务  
8. Workflow 数据 — Step 与历史  

## 测试与构建

```bash
# 后端（Mock ACONEX / Google，不访问真实服务）
cd backend
source .venv/bin/activate
export PYTHONPATH=.
pytest -q

# 前端
cd frontend
npm run typecheck   # 或 npm run build 内含 tsc
npm run lint
npm run build
```

## 已实现功能

- ACONEX OAuth code 交换、Refresh Token 自动刷新、401 重试
- Workflow / Current / 按编号搜索；Step 规范化入库与历史
- 可配置 Feedback Rule（Step 选择、字段、状态、触发、Final Mail）
- Final Mail 扫描（按规则，非固定 Step 2）
- Google Sheets 全量/增量、业务键去重、失败保留
- 手动运行 + 持久化调度 + 防并发
- 运行日志、SSE 进度、失败重试
- 敏感信息加密与掩码
- SQLite WAL、指数退避（429/5xx）

## 已知限制

- ACONEX Project 列表端点因租户差异可能不可用，可手填 Project ID
- Final Mail 依赖主题形如 `Final (WF-xxx)` 的邮件
- Google Sheets 行匹配依赖列映射中的 Workflow Number 与 Step 列；改列结构后建议全量同步
- 单进程 APScheduler；多副本部署需外部分布式锁
- 前端无独立用户认证（默认内网/单人使用）
- 逾期时长为简化标签，未做完整工时计算

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET/PUT | `/api/settings/aconex` | ACONEX 配置 |
| POST | `/api/settings/aconex/exchange-code` | Code → Token |
| POST | `/api/runs` | 启动 pipeline / sync_* |
| GET | `/api/runs/{id}/events` | SSE 进度 |
| CRUD | `/api/tracked-workflows` | 追踪列表 |
| CRUD | `/api/feedback-rules` | 反馈规则 |
| CRUD | `/api/scheduled-jobs` | 定时任务 |

本地直接运行后端时 OpenAPI：`http://127.0.0.1:8000/docs`

Docker Compose 启动时 OpenAPI：`http://127.0.0.1:5173/docs`
