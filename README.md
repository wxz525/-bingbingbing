# bingbingbing 金科TRAE竞赛项目

小组3人协作项目

## 目录说明
- openspec：需求规格四件套（proposal / design / spec / tasks）
- backend：FastAPI 后端服务（行情 / 资讯接口）
- frontend：Vue3 + Vite 前端页面
- data‑etl：竞赛数据集 ETL 入库脚本、建表 SQL 与数据字典（data‑etl/docs）

> 中间件（MySQL / ClickHouse / MinIO）需自行准备，仓库不再包含 docker-compose 部署配置。

## 本地启动

后端（默认 http://127.0.0.1:8000）：

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # 填写 MYSQL_* 连接信息
uvicorn app.main:app --reload --port 8000
```

前端（默认 http://127.0.0.1:5173）：

```bash
cd frontend
npm install
cp .env.example .env    # VITE_API_BASE_URL 指向后端地址
npm run dev
```

后端默认允许 `http://localhost:5173`、`http://127.0.0.1:5173` 跨域，可用 `CORS_ALLOW_ORIGINS`（逗号分隔）覆盖。

## 小组分工
- A：数据ETL、数据库、中间件环境
- B：后端业务开发、OpenSpec需求文档
- C：前端页面、数据看板

## TRAE竞赛规则
每次开启新会话，先执行绑定指令
`/efficiency-bind REQ-001-子任务名称`
开发完成执行上传
`/efficiency-upload`
查看状态
`/efficiency-status`
