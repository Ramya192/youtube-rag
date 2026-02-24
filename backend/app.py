from fastapi import FastAPI
from pydantic import BaseModel
from backend.rag import ingest_video, query_video

app = FastAPI(title="YouTube RAG API")


class IngestRequest(BaseModel):
    url: str


class QueryRequest(BaseModel):
    question: str
    video_id: str


@app.post("/ingest")
def ingest(request: IngestRequest):
    return ingest_video(request.url)


@app.post("/query")
def query(request: QueryRequest):
    return query_video(request.question, request.video_id)