from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from economy_lab.api.routes import router

app = FastAPI(
    title="Economy Lab API",
    version="2.11.0",
    description="Local-first economic simulation kernel API",
)

# Development origins. Production desktop will use a tighter policy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

app.include_router(router, prefix="/api/v1")
