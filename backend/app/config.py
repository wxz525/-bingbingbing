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
