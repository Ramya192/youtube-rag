from fastapi import FastAPI
from fastapi import Request
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from pydantic import BaseModel
from typing import Optional
from backend.rag import ingest_video, query_video
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()
app.mount("/", StaticFiles(directory="static", html=True), name="static")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

app.add_middleware(SlowAPIMiddleware)

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

app = FastAPI(title="YouTube RAG API")


class IngestRequest(BaseModel):
    url: str


class QueryRequest(BaseModel):
    question: str
    video_id: Optional[str] = None
    debug: Optional[bool] = False


if ENVIRONMENT != "production":

    @app.post("/ingest")
    def ingest(request: IngestRequest):
        return ingest_video(request.url)


@app.post("/query")
@limiter.limit("10/minute")
def query(request: Request, body: QueryRequest):
    return query_video(body.question, body.video_id)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
    )