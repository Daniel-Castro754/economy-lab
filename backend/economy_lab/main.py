from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    version="2.13.1",
    description="Local-first economic simulation kernel API",
    lifespan=lifespan,
)

# Development origins. Production desktop will use a tighter policy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

app.include_router(router, prefix="/api/v1")
