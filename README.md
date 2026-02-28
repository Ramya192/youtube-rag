YouTube RAG System

A production-style Retrieval-Augmented Generation (RAG) system that enables semantic question-answering over YouTube videos using vector search and LLMs.

This project demonstrates clean separation of ingestion and serving, official API integration, vector database usage (pgvector), production deployment practices, and infrastructure debugging.

What This System Does

Given a YouTube video and a question, the system:

1. Retrieves relevant transcript chunks using vector similarity search
2. Constructs a grounded context
3. Generates an answer strictly based on retrieved content
4. Returns structured metadata and timestamp links

Architecture Overview

Local Ingestion Layer (ETL)
    ↓
Supabase (PostgreSQL + pgvector)
    ↓
Render (Stateless Query API)
    ↓
OpenAI (Answer Generation)

Separation of Responsibilities

Local Ingestion Layer
---------------------
Runs locally to avoid YouTube cloud IP restrictions.

Flow:

1. Extract video_id from URL
2. Validate video using YouTube Data API v3
3. Fetch official metadata
4. Fetch transcript locally
5. Chunk transcript with token overlap
6. Generate embeddings
7. Store metadata + vectors in Supabase

Production Query Layer (Render)
-------------------------------
Stateless API that:

1. Accepts user question
2. Generates query embedding
3. Performs pgvector similarity search
4. Retrieves top relevant transcript chunks
5. Constructs grounded prompt
6. Calls LLM for final answer
7. Returns structured response
8. Production does not perform ingestion.

Key Engineering Decisions
1️⃣ Ingestion Disabled in Production

1. Prevents abuse
2. Avoids cost spikes
3. Avoids YouTube cloud IP blocking
4. Keeps production stateless

2️⃣ Transaction Pooler for Supabase

1. Render requires IPv4-compatible DB connections.
2. Using Supabase transaction pooler ensures reliable connectivity.

3️⃣ Vector Search via pgvector

1. Cosine similarity (<=>)
2. HNSW indexing for performance
3. Thresholding to avoid irrelevant LLM calls

4️⃣ Rate Limiting (10 requests/minute)

Prevents:

1. API abuse
2. OpenAI cost explosions
3. Accidental load testing

5️⃣ Retrieval Thresholding

1. Prevents calling the LLM if similarity is too low.
2. This reduces hallucinations and improves grounding.

Database Schema for videos table
Column	      Description
id	            YouTube video ID (Primary Key)
title	            Video title
description	      Video description
channel	      Channel name
published_at	Publish timestamp
views	            View count

video_chunks_with_indx table
Column	      Description
video_id	      Foreign key → videos.id
chunk_index	      Order within transcript
content	      Transcript text chunk
token_count	      Token size
start_time	      Chunk start timestamp
end_time	      Chunk end timestamp
embedding	      pgvector embedding

Example Query Response
{
  "answer": "...",
  "confidence": "medium",
  "similarity_score": 0.71,
  "video": {
    "video_id": "osKyvYJ3PRM",
    "title": "Everything You Need To Know About Large Language Models (LLMs)",
    "channel": "Matthew Berman"
  },
  "top_match": {
    "start": 0.16,
    "end": 260.639,
    "youtube_link": "https://www.youtube.com/watch?v=osKyvYJ3PRM&t=0s"
  }
}

Debug mode optionally returns retrieved chunks.

Tech Stack

1. Python
2. FastAPI
3. Supabase (PostgreSQL + pgvector)
4. OpenAI Embeddings (text-embedding-3-small)
5. YouTube Data API v3
6. youtube-transcript-api (local only)
7. Render (deployment)
8. SlowAPI (rate limiting)

Running Locally
1️ Install dependencies
pip install -r backend/requirements.txt

2️ Environment variables
OPENAI_API_KEY=your_key
YOUTUBE_API_KEY=your_key
DATABASE_URL=your_supabase_url
ENVIRONMENT=local

3 Run ingestion
POST /ingest

4 Start API
uvicorn backend.app:app --reload

Production Deployment
---------------------
1. Hosted on Render
2. Supabase used as managed vector database
3. Ingestion disabled in production (ENVIRONMENT=production)
4. Rate limiting enabled
5. Stateless query-only API

Production Hardening Implemented
--------------------------------
1. Environment-based route control
2. Rate limiting
3. Retrieval relevance threshold
4. Structured response format
5. Cloud IPv6 issue resolved via transaction pooler
6. Foreign key integrity
7. Clean error handling

Possible Future Improvements
----------------------------
1. Authentication for ingestion
2. Hybrid search (vector + keyword)
3. Multi-video querying
4. Caching layer
5. Frontend UI
6. Background ingestion queue

Why This Project Is Strong
--------------------------
This project demonstrates:

1. Real-world RAG architecture
2. Vector database integration
3. LLM grounding strategies
4. Cloud deployment debugging
5. API hardening
6. Infrastructure-level problem solving (IPv4/IPv6 networking issue)
7. Clean separation of ETL and serving layers