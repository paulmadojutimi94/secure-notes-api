"""The FastAPI application: wires the routers together and creates tables on startup."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models  # noqa: F401  (registers the tables on Base.metadata)
from .database import Base, engine
from .routers import auth, notes


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Secure Notes API",
    version="1.0.0",
    description="Register, log in, and manage notes that only you can see.",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(notes.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
