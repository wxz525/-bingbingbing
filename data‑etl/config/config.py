"""ETL 全局配置加载。

路径全部基于 __file__ 自动解析，不依赖运行时的工作目录，因此脚本可以在
任意目录下被调用（python data-etl/scripts/run_all.py 亦可）。

配置优先级（从高到低）：
    1. 进程环境变量（CI / 临时覆盖）
    2. 项目根目录 .env 文件（本机开发、Docker 部署共用，不提交仓库）
    3. config/config.yaml（非敏感默认值）

密码等敏感信息只允许出现在 .env 或环境变量中，config.yaml 保持留空。
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# 本文件位于：<project_root>/data-etl/config/config.py
BASE_DIR: Path = Path(__file__).resolve().parent.parent  # data-etl 目录
PROJECT_ROOT: Path = BASE_DIR.parent                      # 项目根目录（与 data/ 同级）
DATA_DIR: Path = PROJECT_ROOT / "data"                    # 原始数据根目录
SQL_DIR: Path = BASE_DIR / "sql"
DOCS_DIR: Path = BASE_DIR / "docs"
CONFIG_FILE: Path = BASE_DIR / "config" / "config.yaml"
ENV_FILE: Path = PROJECT_ROOT / ".env"

# 环境变量 -> (配置段, 配置键, 类型)
_ENV_BINDINGS = [
    ("mysql", "host", "MYSQL_HOST", str),
    ("mysql", "port", "MYSQL_PORT", int),
    ("mysql", "user", "MYSQL_USER", str),
    ("mysql", "database", "MYSQL_DATABASE", str),
    ("mysql", "password", "MYSQL_PASSWORD", str),
    ("clickhouse", "host", "CLICKHOUSE_HOST", str),
    ("clickhouse", "port", "CLICKHOUSE_PORT", int),
    ("clickhouse", "user", "CLICKHOUSE_USER", str),
    ("clickhouse", "database", "CLICKHOUSE_DATABASE", str),
    ("clickhouse", "password", "CLICKHOUSE_PASSWORD", str),
    ("minio", "endpoint", "MINIO_ENDPOINT", str),
    ("minio", "access_key", "MINIO_ACCESS_KEY", str),
    ("minio", "secret_key", "MINIO_SECRET_KEY", str),
    ("minio", "bucket", "MINIO_BUCKET", str),
]


def _load_dotenv() -> None:
    """加载项目根 .env；已存在的进程环境变量优先，不被覆盖。"""
    try:
        from dotenv import load_dotenv
    except ImportError:  # 未安装 python-dotenv 时退化为仅读环境变量
        return
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)


def load_config(path: Path | str | None = None) -> dict:
    """加载 config.yaml，并用 .env / 环境变量覆盖。"""
    _load_dotenv()

    cfg_path = Path(path) if path else CONFIG_FILE
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    for section in ("mysql", "clickhouse", "minio", "etl"):
        cfg.setdefault(section, {})

    for section, key, env_name, caster in _ENV_BINDINGS:
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        try:
            cfg[section][key] = caster(raw)
        except (TypeError, ValueError):
            raise ValueError(f"环境变量 {env_name}={raw!r} 无法转换为 {caster.__name__}") from None

    return cfg


# 模块级单例，脚本直接 from config.config import CONFIG, DATA_DIR
CONFIG: dict = load_config()
