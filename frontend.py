import streamlit as st
import requests

API_URL = "https://your-backend-url.onrender.com"

st.set_page_config(page_title="YouTube RAG", layout="wide")

st.title("🎥 YouTube Video RAG System")

# ---------------------------
# Ingest Section
# ---------------------------

st.header("1️⃣ Ingest YouTube Video")

video_url = st.text_input("Enter YouTube URL")

if st.button("Ingest Video"):
    if video_url:
        response = requests.post(f"{API_URL}/ingest", json={"url": video_url})

        if response.status_code == 200:
            data = response.json()
            st.session_state.video_id = data["video_id"]
            st.success(f"Video ingested successfully!")
            st.write(f"Video ID: {st.session_state.video_id}")
        else:
            st.error("Ingestion failed")
    else:
        st.warning("Please enter a URL")

# ---------------------------
# Query Section
# ---------------------------

st.header("2️⃣ Ask Questions")

video_id = st.session_state.get("video_id", "")
question = st.text_input("Ask a question about the video")

if st.button("Get Answer"):
    if video_id and question:
        response = requests.post(
            f"{API_URL}/query", json={"video_id": video_id, "question": question}
        )

        if response.status_code == 200:
            data = response.json()

            st.subheader("Answer")
            st.write(data["answer"])

        if "sources" in data and data["sources"]:
            st.subheader("Sources")

            for source in data["sources"]:
                start = int(source["start"])
                youtube_link = f"https://www.youtube.com/watch?v={video_id}&t={start}s"

                st.markdown(
                    f"[⏱ {round(source['start'],2)}s - {round(source['end'],2)}s]({youtube_link})"
                )
        else:
            st.info("No source timestamps available.")
    else:
        st.warning("Enter both video_id and question")
