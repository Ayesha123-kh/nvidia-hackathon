import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import config, pipeline
from .llm import LLM
from .schemas import IdeaCanvas

state: dict = {}
hits: dict[str, list[float]] = defaultdict(list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["llm_factory"] = LLM.create
    yield


app = FastAPI(title="Peperio", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "?"
    now = time.time()
    hits[ip] = [t for t in hits[ip] if now - t < 3600]
    if len(hits[ip]) >= config.RUNS_PER_VISITOR_PER_HOUR:
        raise HTTPException(429, "Run limit reached; try the recorded replay.")
    hits[ip].append(now)


class IdeaText(BaseModel):
    text: str


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/canvas")
async def canvas(body: IdeaText) -> IdeaCanvas:
    llm = await state["llm_factory"]()
    return await pipeline.extract_canvas(llm, body.text)


@app.post("/run")
async def run(canvas: IdeaCanvas, request: Request):
    rate_limit(request)
    llm = await state["llm_factory"]()
    return EventSourceResponse(pipeline.run(llm, canvas))
