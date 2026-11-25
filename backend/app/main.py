from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings
from app.database import create_database_engine
from app.errors import register_exception_handlers
from app.repository import FundArchiveRepository
from app.service import EtlRedemptionRuleService, FundArchiveService


def create_app() -> FastAPI:
    settings = get_settings()
    engine = create_database_engine(settings)
    repository = FundArchiveRepository(engine)

    application = FastAPI(title="Fund Archive API", version="1.0.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    application.state.default_operator = settings.default_operator
    application.state.fund_archive_service = FundArchiveService(repository)
    application.state.etl_redemption_rule_service = EtlRedemptionRuleService(
        repository,
        settings.etl_system_operator,
    )
    application.include_router(router)
    register_exception_handlers(application)
    return application


app = create_app()
