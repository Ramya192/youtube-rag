from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from backend.rag import ingest_video, query_video
import os
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


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
def query(request: QueryRequest):
    return query_video(request.question, request.video_id, request.debug)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
    )