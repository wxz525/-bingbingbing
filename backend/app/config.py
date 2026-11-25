from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_PROJECT_DIR / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = Field(min_length=1)
    mysql_password: str = Field(min_length=1)
    mysql_database: str = "gy_meta"
    default_operator: str = "system"
    etl_system_operator: str = "etl-system"
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    market_data_dir: str = ""
    data_dir: str = ""
    news_index_dir: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allow_origins.split(",") if item.strip()]

    @property
    def data_root_path(self) -> Path:
        if self.data_dir.strip():
            return Path(self.data_dir.strip()).expanduser()
        return _PROJECT_DIR.parent / "data"

    @property
    def market_data_path(self) -> Path:
        if self.market_data_dir.strip():
            return Path(self.market_data_dir.strip()).expanduser()
        return self.data_root_path / "目标资产价格变量"

    @property
    def news_csv_path(self) -> Path:
        return self.data_root_path / "新闻" / "无标题.csv"

    @property
    def summary_data_path(self) -> Path:
        return self.data_root_path / "全球资金信息摘要"

    @property
    def news_index_path(self) -> Path:
        if self.news_index_dir.strip():
            return Path(self.news_index_dir.strip()).expanduser() / "news.db"
        return Path.home() / ".cache" / "fund-archive" / "news.db"

    @field_validator("default_operator", "etl_system_operator")
    @classmethod
    def validate_operator(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 64:
            raise ValueError("操作人标识长度必须为 1～64 个字符")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
