YouTube RAG System

A production-style Retrieval-Augmented Generation (RAG) system that enables semantic question-answering over YouTube videos.

This project demonstrates clean separation of ingestion and serving, official API integration, vector search with pgvector, and scalable backend deployment.

Features

✅ YouTube Data API v3 integration for official metadata validation
✅ Local transcript ingestion to avoid cloud IP blocking
✅ Semantic chunking and embedding generation
✅ Supabase (PostgreSQL + pgvector) vector storage
✅ FastAPI backend deployed on Render
✅ Production-ready query-only API
✅ Clean relational database design

Production Design Decisions

Ingestion disabled in production to prevent abuse and cost spikes

Query endpoint rate-limited (10 requests/minute)

Vector search uses cosine similarity via pgvector

Retrieval thresholding prevents irrelevant LLM calls

Debug mode optional for development


Why Ingestion Is Local

Transcript fetching from cloud IPs can be blocked by YouTube.
Therefore ingestion runs locally, while production remains query-only and stateless.

Architecture
User → FastAPI → Embedding → pgvector similarity search
      → Metadata JOIN → Context construction → LLM → Structured Response

Local Ingestion (Transcript + Embeddings)
        ↓
Supabase (PostgreSQL + pgvector)
        ↓
Render (Stateless Query API)
        ↓
OpenAI (Answer Generation)
      
This system separates ingestion from serving.

🔹 Local Ingestion Layer (ETL)

Runs locally to avoid YouTube cloud IP restrictions.

Flow:
1. Extract video_id from URL
2. Validate video via YouTube Data API v3
3. Fetch video metadata
4. Fetch transcript locally
5. Chunk transcript
6. Generate embeddings
7. Store metadata + embeddings in Supabase

Production Query Layer (Render)

Stateless API that:

1. Accepts user question
2. Generates query embedding
3. Performs vector similarity search (pgvector)
4. Retrieves top relevant chunks
5. Generates final answer using LLM
6. Render does not perform transcript ingestion.

System Diagram:
User → Render API → Supabase (Vector Search)
                      ↑
                Local Ingestion
         (YouTube API + Transcript + Embeddings)

Database Design - videos table

Column	        Description
id	            YouTube video ID (Primary Key)
title	        Video title
description	    Video description
channel	        Channel name
published_at	Publish timestamp
views	        View count

Database Design - videos table

Column	        Description
id	            YouTube video ID (Primary Key)
title	        Video title
description	    Video description
channel	        Channel name
published_at	Publish timestamp
views	        View count

Tech Stack

1. Python
2. FastAPI
3. Supabase (PostgreSQL + pgvector)
4. OpenAI Embeddings
5. YouTube Data API v3
6. youtube-transcript-api (local only)
7. Render (deployment)

Running Locally
1️⃣ Install dependencies
pip install -r backend/requirements.txt

2️⃣ Set environment variables
OPENAI_API_KEY=your_key
YOUTUBE_API_KEY=your_key
DATABASE_URL=your_supabase_url
ENVIRONMENT=local

3️⃣ Run ingestion
POST /ingest

4️⃣ Run backend
uvicorn backend.app:app --reload

🌍 Production Deployment

Backend deployed on Render

Supabase used as managed vector database

Ingestion disabled in production environment

🎯 Key Engineering Decisions

1. Separated ingestion from serving to avoid YouTube cloud IP blocking
2. Used official YouTube API for validation and metadata
3. Implemented foreign key constraints for relational integrity
4. Designed stateless production API
5. Used vector indexing (HNSW) for fast similarity search

📈 Future Improvements

1. Add authentication for ingestion
2. Add multi-video querying
3. Add timestamp-aware answer highlighting
4. Add frontend UI
5. Add caching layer

💡 Why This Project Is Interesting

This project demonstrates:

1. Real-world AI system design
2. Vector database integration
3. API deployment
4. Handling external service limitations
5. Clean backend architecture