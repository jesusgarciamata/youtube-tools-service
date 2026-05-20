import os
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

app = FastAPI(title="YouTube Tools Service")

API_KEY = os.getenv("API_KEY", "").strip()


class TranscriptRequest(BaseModel):
    video_id: str
    languages: List[str] = ["en", "en-US", "es"]


def check_api_key(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcript")
def get_transcript(
    request: TranscriptRequest,
    x_api_key: Optional[str] = Header(default=None),
):
    check_api_key(x_api_key)

    video_id = request.video_id.strip()

    if not video_id:
        raise HTTPException(status_code=400, detail="Missing video_id")

    try:
        segments = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=request.languages,
        )

        full_text = " ".join(
            segment.get("text", "").replace("\n", " ").strip()
            for segment in segments
            if segment.get("text")
        )

        return {
            "video_id": video_id,
            "transcript_status": "found",
            "transcript": full_text,
            "segments": segments,
            "segment_count": len(segments),
        }

    except TranscriptsDisabled:
        return {
            "video_id": video_id,
            "transcript_status": "disabled",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": "Transcripts are disabled for this video.",
        }

    except NoTranscriptFound:
        return {
            "video_id": video_id,
            "transcript_status": "not_found",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": "No transcript found for requested languages.",
        }

    except VideoUnavailable:
        return {
            "video_id": video_id,
            "transcript_status": "video_unavailable",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": "Video unavailable.",
        }

    except Exception as e:
        return {
            "video_id": video_id,
            "transcript_status": "error",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": str(e),
        }