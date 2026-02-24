import os
import tiktoken
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import text
from youtube_transcript_api import YouTubeTranscriptApi
from backend.database import engine

# Load environment variables
load_dotenv()

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def create_embeddings_batch(texts: list[str]):

    response = client.embeddings.create(model="text-embedding-3-small", input=texts)

    return [item.embedding for item in response.data]


# ---------------------------------------
# Helper: Extract video ID
# ---------------------------------------
def extract_video_id(url: str) -> str:
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    return url


# ---------------------------------------
# Ingest Video (simplified version)
# ---------------------------------------
def ingest_video(url: str):

    video_id = extract_video_id(url)

    transcript = YouTubeTranscriptApi().fetch(video_id)

    chunks = build_chunks(transcript)

    texts = [chunk["text"] for chunk in chunks]

    embeddings = create_embeddings_batch(texts)

    with engine.begin() as conn:

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):

            vector_str = "[" + ",".join(map(str, embedding)) + "]"

            conn.execute(
                text(
                    """
                    INSERT INTO video_chunks_with_indx
                    (video_id, chunk_index, content, token_count,
                     start_time, end_time, embedding)
                    VALUES
                    (:video_id, :chunk_index, :content, :token_count,
                     :start_time, :end_time, :embedding)
                """
                ),
                {
                    "video_id": video_id,
                    "chunk_index": i,
                    "content": chunk["text"],
                    "token_count": chunk["token_count"],
                    "start_time": chunk["start"],
                    "end_time": chunk["end"],
                    "embedding": vector_str,
                },
            )

    return {
        "status": "Video ingested successfully",
        "video_id": video_id,
        "chunks_created": len(chunks),
    }


encoding = tiktoken.encoding_for_model("text-embedding-3-small")


def count_tokens(text: str):
    return len(encoding.encode(text))


def build_chunks(transcript, max_tokens=800, overlap_tokens=100):
    chunks = []
    current_chunk = []
    current_tokens = 0

    for item in transcript:
        text = item.text
        tokens = count_tokens(text)

        if current_tokens + tokens > max_tokens and current_chunk:

            chunk_text = " ".join([c["text"] for c in current_chunk])

            chunks.append(
                {
                    "text": chunk_text,
                    "start": current_chunk[0]["start"],
                    "end": current_chunk[-1]["end"],
                    "token_count": count_tokens(chunk_text),
                }
            )

            # overlap logic
            overlap = []
            overlap_count = 0

            for c in reversed(current_chunk):
                t = count_tokens(c["text"])
                if overlap_count + t > overlap_tokens:
                    break
                overlap.insert(0, c)
                overlap_count += t

            current_chunk = overlap
            current_tokens = overlap_count

        current_chunk.append(
            {"text": text, "start": item.start, "end": item.start + item.duration}
        )

        current_tokens += tokens

    if current_chunk:
        chunk_text = " ".join([c["text"] for c in current_chunk])

        chunks.append(
            {
                "text": chunk_text,
                "start": current_chunk[0]["start"],
                "end": current_chunk[-1]["end"],
                "token_count": count_tokens(chunk_text),
            }
        )

    return chunks


# ---------------------------------------
# Query Video
# ---------------------------------------
def query_video(question: str, video_id: str):

    # 1️⃣ Embed question
    query_embedding = create_embeddings_batch([question])[0]
    vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

    # 2️⃣ Retrieve top chunks
    query_sql = """
        SELECT content, start_time, end_time,
               embedding <-> :query_vector AS distance
        FROM video_chunks_with_indx
        WHERE video_id = :video_id
        ORDER BY embedding <-> :query_vector
        LIMIT 5
    """

    with engine.connect() as conn:
        results = conn.execute(
            text(query_sql), {"query_vector": vector_str, "video_id": video_id}
        ).fetchall()

    if not results:
        return {"answer": "No relevant content found."}

    # 3️⃣ Relevance threshold
    top_distance = results[0][3]

    print("Top distance:", top_distance)

    if top_distance > 1.50:
        return {"answer": "Question is irrelevant to this video."}

    # 4️⃣ Build structured context
    context_blocks = []

    for r in results:
        context_blocks.append(f"[{round(r[1],2)}s - {round(r[2],2)}s]\n{r[0]}")

    context = "\n\n".join(context_blocks)

    # 5️⃣ Ask LLM with strict grounding
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict assistant. "
                    "Answer ONLY using the provided transcript context. "
                    "If answer is not in context, say: "
                    "'The question is not answered in the video.'"
                ),
            },
            {
                "role": "user",
                "content": f"Transcript Context:\n{context}\n\nQuestion: {question}",
            },
        ],
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": [
            {
                "start": round(r[1], 2),
                "end": round(r[2], 2),
                "youtube_link": f"https://www.youtube.com/watch?v={video_id}&t={int(r[1])}s",
            }
            for r in results
        ],
    }
