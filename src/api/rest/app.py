from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.rest.routes.assignment_routes import router as assignment_router
from src.api.rest.routes.attachment_routes import router as attachment_router
from src.api.rest.routes.client_routes import router as client_router
from src.api.rest.routes.client_rules_routes import router as client_rule_router
from src.api.rest.routes.content_extract_rotues import router as content_extract_router
from src.api.rest.routes.department_routes import router as department_router
from src.api.rest.routes.email_routes import router as email_router
from src.api.rest.routes.employee_rotues import router as employee_router
from src.api.rest.routes.health_routes import router as health_router
from src.api.rest.routes.operation_settings_routes import router as operation_settings_router
from src.api.rest.routes.polling_routes import router as polling_router
from src.api.rest.routes.timecard_routes import router as timecard_router
from src.api.rest.routes.timesheet_routes import router as timesheet_router
from src.core.exceptions import handlers as exception_handlers
from src.core.services.gmail_polling_controller import gmail_polling_controller
from src.data.clients import postgress_client
from src.data.clients.postgress_client import dispose_async_engine, init_async_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_async_engine()
    if postgress_client.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized")

    yield

    await gmail_polling_controller.stop()

    await dispose_async_engine()


def get_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    exception_handlers.register_exception_handlers(app)
    app.include_router(client_router)
    app.include_router(email_router)
    app.include_router(employee_router)
    app.include_router(timesheet_router)
    app.include_router(timecard_router)
    app.include_router(client_rule_router)
    app.include_router(department_router)
    app.include_router(assignment_router)
    app.include_router(content_extract_router)
    app.include_router(attachment_router)
    app.include_router(polling_router)
    app.include_router(operation_settings_router)
    app.include_router(health_router)
    return app
