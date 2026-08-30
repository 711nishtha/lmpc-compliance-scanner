import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import auth, dashboard, reports, scans
from app.config import APP_ENV, CORS_ORIGINS, ENABLE_DOCS, IS_PRODUCTION
from app.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("lmpc")

app = FastAPI(
    title="Legal Metrology Packaged Commodities Compliance Scanner",
    description=(
        "SIH26034 prototype — scans packaged-commodity labels and checks declarations against "
        "the Legal Metrology (Packaged Commodities) Rules, 2011. See docs/LEGAL_REQUIREMENTS.md "
        "for the source-cited rule checklist and docs/ARCHITECTURE.md for pipeline design."
    ),
    version="0.1.0",
    # Deliberate: docs are ON in development (they double as judge-facing technical documentation)
    # and OFF in production unless ENABLE_DOCS=true. See app/config.py and docs/DEPLOYMENT.md.
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

# Locked to known origins — never "*". A wildcard with allow_credentials=True is additionally
# rejected outright by browsers, so the previous ["*"] + credentials config was both insecure
# and non-functional for credentialed requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Deliberate HTTPExceptions carry operator-facing messages we WANT the client to see
    (e.g. 'OCR engine unavailable', 'rate limit reached') — pass those through unchanged."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Request validation failed.", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Unhandled errors: full detail to the server log, a correlation id and a generic message
    to the client. Stack traces and internal file paths must never reach the frontend."""
    error_id = uuid.uuid4().hex[:12]
    logger.exception(
        "unhandled error id=%s on %s %s", error_id, request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred. Quote this reference when reporting it.",
            "error_id": error_id,
        },
    )


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info(
        "starting APP_ENV=%s docs=%s cors_origins=%s",
        APP_ENV, "on" if ENABLE_DOCS else "off", CORS_ORIGINS,
    )
    if IS_PRODUCTION and ENABLE_DOCS:
        logger.warning("API docs are exposed in production (ENABLE_DOCS=true was set explicitly).")


app.include_router(auth.router)
app.include_router(scans.router)
app.include_router(reports.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
