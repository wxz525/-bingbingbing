# bingbingbing 金科TRAE竞赛项目

小组3人协作项目

## 目录说明
- docs：需求文档、PRD
- openspec：OpenSpec需求规格四件套
- backend：后端服务代码
- frontend：前端Web页面
- data‑etl：竞赛数据集ETL入库脚本
- docker‑compose：中间件部署配置 mysql/clickhouse/kafka/flink/redis/minio

## 小组分工
- A：数据ETL、数据库、docker环境
- B：后端业务开发、OpenSpec需求文档
- C：前端页面、数据看板

## TRAE竞赛规则
每次开启新会话，先执行绑定指令
`/efficiency-bind REQ-001-子任务名称`
开发完成执行上传
`/efficiency-upload`
查看状态
`/efficiency-status`
