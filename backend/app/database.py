from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL

from app.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    url = URL.create(
        "mysql+pymysql",
        username=settings.mysql_user,
        password=settings.mysql_password,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
