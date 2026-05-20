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


def normalize_segments(fetched):
    segments = []

    for segment in fetched:
        segments.append({
            "text": getattr(segment, "text", ""),
            "start": getattr(segment, "start", 0),
            "duration": getattr(segment, "duration", 0),
        })

    return segments


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/transcript-list/{video_id}")
def transcript_list(
    video_id: str,
    x_api_key: Optional[str] = Header(default=None),
):
    check_api_key(x_api_key)

    try:
        ytt_api = YouTubeTranscriptApi()
        transcripts = ytt_api.list(video_id)

        available = []

        for transcript in transcripts:
            available.append({
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": transcript.is_generated,
                "is_translatable": transcript.is_translatable,
                "translation_languages": [
                    {
                        "language": lang["language"],
                        "language_code": lang["language_code"],
                    }
                    for lang in transcript.translation_languages
                ],
            })

        return {
            "video_id": video_id,
            "status": "found",
            "available_transcripts": available,
        }

    except Exception as e:
        return {
            "video_id": video_id,
            "status": "error",
            "error": str(e),
        }


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
        ytt_api = YouTubeTranscriptApi()

        fetched = ytt_api.fetch(
            video_id,
            languages=request.languages,
        )

        segments = normalize_segments(fetched)

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
            "language_code": getattr(fetched, "language_code", ""),
            "language": getattr(fetched, "language", ""),
            "is_generated": getattr(fetched, "is_generated", None),
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