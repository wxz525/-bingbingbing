from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import market_router, news_router
from app.config import get_settings
from app.errors import register_exception_handlers
from app.market_repository import MarketDataRepository
from app.market_service import MarketService
from app.news_repository import NewsIndexRepository, SummaryRepository
from app.news_service import NewsService


def create_app() -> FastAPI:
    settings = get_settings()
    market_repository = MarketDataRepository(settings.market_data_path)
    news_repository = NewsIndexRepository(settings.news_csv_path, settings.news_index_path)
    summary_repository = SummaryRepository(settings.summary_data_path)

    application = FastAPI(title="Fund Archive API", version="1.0.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    application.state.market_service = MarketService(market_repository)
    application.state.news_service = NewsService(news_repository, summary_repository)
    application.include_router(market_router)
    application.include_router(news_router)
    register_exception_handlers(application)
    news_repository.start_background_build()
    return application


app = create_app()
