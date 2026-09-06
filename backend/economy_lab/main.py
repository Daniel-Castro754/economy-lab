import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from economy_lab import __version__
from economy_lab.api.routes import router
from economy_lab.jobs.manager import shutdown_all_job_managers


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # Signal every in-flight simulation job to cancel at its next checkpoint
    # instead of letting ThreadPoolExecutor's atexit joiner block process exit
    # on a job's full remaining timeout.
    shutdown_all_job_managers(wait=False)


app = FastAPI(
    title="Economy Lab API",
    version=__version__,
    description="Local-first economic simulation kernel API",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, exc: RequestValidationError):
    # Invalid inputs can themselves contain NaN/Infinity or non-JSON context.
    # Return useful field errors without echoing those values into JSON.
    detail = [{key: error[key] for key in ("loc", "msg", "type") if key in error}
              for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})

# Local development origins (Vite dev server).
_DEV_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
# Origins the Tauri desktop shell actually uses to reach the sidecar backend.
_DESKTOP_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
)

_CORS_SHARED_KWARGS = dict(
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)


class _RuntimeModeCORSMiddleware:
    """CORS gate that re-reads ``ECONOMY_LAB_RUNTIME_MODE`` on every request.

    The desktop sidecar entry point (``economy_lab.desktop_entry``) only sets
    ``ECONOMY_LAB_RUNTIME_MODE`` inside its ``main()`` function, which runs
    *after* this module (and therefore ``app``) has already been imported.
    Freezing ``allow_origins`` once at import/middleware-construction time
    would miss that assignment, so the allowed origin set is decided per
    request instead. Desktop mode is restricted to the Tauri origins it
    actually needs; every other mode keeps local development functional.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._desktop = CORSMiddleware(
            app, allow_origins=list(_DESKTOP_ORIGINS), **_CORS_SHARED_KWARGS
        )
        self._default = CORSMiddleware(
            app,
            allow_origins=list(_DEV_ORIGINS + _DESKTOP_ORIGINS),
            **_CORS_SHARED_KWARGS,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        mode = os.getenv("ECONOMY_LAB_RUNTIME_MODE", "web-local")
        target = self._desktop if mode == "desktop-sidecar" else self._default
        await target(scope, receive, send)


app.add_middleware(_RuntimeModeCORSMiddleware)

app.include_router(router, prefix="/api/v1")
