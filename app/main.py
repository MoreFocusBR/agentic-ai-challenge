from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import router
from app.database.connection import close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()


app = FastAPI(
    title="Assistente Corporativo Agêntico",
    description="Agente de IA com RAG, memória e geração de PDF.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
async def frontend():
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
