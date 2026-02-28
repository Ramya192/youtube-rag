from importlib.metadata import metadata
from multiprocessing.util import debug
import os
from urllib import response
from fastapi import params
import tiktoken
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy import text
from youtube_transcript_api import YouTubeTranscriptApi
from backend.database import engine
from .youtube_api import get_video_metadata

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
def extract_video_id(url: str):
    if "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    else:
        raise ValueError("Invalid YouTube URL")


# ---------------------------------------
# Ingest Video (simplified version)
# ---------------------------------------
def ingest_video(url: str):

    video_id = extract_video_id(url)

    metadata = get_video_metadata(video_id)

    if not metadata:
        raise ValueError("Invalid or unavailable video")

    transcript = YouTubeTranscriptApi().fetch(video_id)

    chunks = build_chunks(transcript)

    texts = [chunk["text"] for chunk in chunks]

    embeddings = create_embeddings_batch(texts)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO videos (id, title, description, channel, published_at, views)
            VALUES (:id, :title, :description, :channel, :published_at, :views)
            ON CONFLICT (id) DO NOTHING;
        """
            ),
            metadata,
        )

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
def query_video(question: str, video_id: str = None, debug: bool = False):

    # 1️⃣ Embed question
    query_embedding = create_embeddings_batch([question])[0]
    vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

    if video_id:
        where_clause = "WHERE c.video_id = :video_id"
    else:
        where_clause = ""

    query_sql = f"""
        SELECT 
           c.content,
           c.start_time,
           c.end_time,
           c.video_id,
           v.title,
           v.channel,
           v.published_at,
           c.embedding <=> :query_vector AS distance
        FROM video_chunks_with_indx c
        JOIN videos v ON c.video_id = v.id
        {where_clause}
        ORDER BY c.embedding <=> :query_vector
        LIMIT 5
    """

    with engine.connect() as conn:

        # Build parameters dynamically
        params = {"query_vector": vector_str}

        if video_id:
            params["video_id"] = video_id

        results = conn.execute(text(query_sql), params).fetchall()

    if not results:
        return {
            "answer": "This video has not been ingested yet or no relevant transcript content was found. Please ingest the video locally first.",
            "confidence": "none",
        }

    # --- Define similarity metrics FIRST ---
    top_distance = results[0].distance
    similarity_score = 1 - top_distance

    # confidence calculation
    if top_distance < 0.45:
        confidence = "high"
    elif top_distance < 0.75:
        confidence = "medium"
    elif top_distance < 0.95:
        confidence = "low"
    else:
        confidence = "very_low"

    summary_triggers = ["what is this video about", "summarize", "summary", "overview"]

    is_summary_query = any(trigger in question.lower() for trigger in summary_triggers)

    # optional irrelevance guard
    if top_distance > 0.85 and not is_summary_query:
        return {
            "answer": "The question appears unrelated to the video content.",
            "confidence": "very_low",
        }

    # 3️⃣ Convert to structured chunks
    top_chunks = []

    for row in results:
        top_chunks.append(
            {
                "content": row[0],
                "start_time": row[1],
                "end_time": row[2],
                "video_id": row[3],
                "title": row[4],
                "channel": row[5],
                "published_at": row[6],
                "distance": row[7],
            }
        )

    # youtube timestamp link
    start_time = int(top_chunks[0]["start_time"])
    matched_video_id = top_chunks[0]["video_id"]
    youtube_link = f"https://www.youtube.com/watch?v={matched_video_id}&t={start_time}s"

    # 5️⃣ Build context
    context_blocks = []

    for chunk in top_chunks:
        context_blocks.append(
            f"[{round(chunk['start_time'],2)}s - {round(chunk['end_time'],2)}s]\n{chunk['content']}"
        )

    context = "\n\n".join(context_blocks)

    # 6️⃣ Ask LLM
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a retrieval-grounded assistant."
                    "Answer strictly using ONLY the transcript context provided."
                    "If the answer cannot be found in the context, say:"
                    "The question is not answered in the video."
                    "Be precise and avoid assumptions."
                ),
            },
            {
                "role": "user",
                "content": f"Transcript Context:\n{context}\n\nQuestion: {question}",
            },
        ],
    )

    answer = response.choices[0].message.content

    # 7️⃣ Return enriched response

    response = {
        "answer": answer,
        "confidence": confidence,
        "distance": top_distance,
        "video": {
            "video_id": top_chunks[0]["video_id"],
            "title": top_chunks[0]["title"],
            "channel": top_chunks[0]["channel"],
            "published_at": top_chunks[0]["published_at"],
        },
        "top_match": {
            "start": top_chunks[0]["start_time"],
            "end": top_chunks[0]["end_time"],
            "youtube_link": youtube_link,
        },
    }

    if debug:
        response["retrieved_chunks"] = top_chunks

    return response
