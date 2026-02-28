from googleapiclient.discovery import build
import os

def get_video_metadata(video_id: str):
    youtube = build(
        "youtube",
        "v3",
        developerKey=os.getenv("YOUTUBE_API_KEY")
    )

    request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id
    )

    response = request.execute()

    if not response["items"]:
        return None

    video = response["items"][0]

    return {
        "id": video_id,
        "title": video["snippet"]["title"],
        "description": video["snippet"]["description"],
        "channel": video["snippet"]["channelTitle"],
        "published_at": video["snippet"]["publishedAt"],
        "views": int(video["statistics"].get("viewCount", 0))
    }