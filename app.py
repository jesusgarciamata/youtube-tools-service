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


@app.get("/transcript-list/{video_id}")
def transcript_list(
    video_id: str,
    x_api_key: Optional[str] = Header(default=None),
):
    check_api_key(x_api_key)

    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

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
                        "language_code": lang["language_code"]
                    }
                    for lang in transcript.translation_languages
                ]
            })

        return {
            "video_id": video_id,
            "status": "found",
            "available_transcripts": available
        }

    except Exception as e:
        return {
            "video_id": video_id,
            "status": "error",
            "error": str(e)
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
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        selected = None
        selected_reason = ""

        # 1. Try requested languages first
        for lang in request.languages:
            try:
                selected = transcript_list.find_transcript([lang])
                selected_reason = f"matched_requested_language:{lang}"
                break
            except Exception:
                pass

        # 2. Fallback: use first available transcript
        if selected is None:
            all_transcripts = list(transcript_list)
            if all_transcripts:
                selected = all_transcripts[0]
                selected_reason = "fallback_first_available"

        if selected is None:
            return {
                "video_id": video_id,
                "transcript_status": "not_found",
                "transcript": "",
                "segments": [],
                "segment_count": 0,
                "error": "No transcript found."
            }

        # 3. Optional: translate to first requested language if possible
        translated = False

        target_language = request.languages[0] if request.languages else None

        if target_language and selected.language_code != target_language:
            try:
                selected = selected.translate(target_language)
                translated = True
            except Exception:
                translated = False

        segments = selected.fetch()

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
            "language": selected.language,
            "language_code": selected.language_code,
            "is_generated": selected.is_generated,
            "is_translated": translated,
            "selected_reason": selected_reason
        }

    except TranscriptsDisabled:
        return {
            "video_id": video_id,
            "transcript_status": "disabled",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": "Transcripts are disabled for this video."
        }

    except NoTranscriptFound:
        return {
            "video_id": video_id,
            "transcript_status": "not_found",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": "No transcript found."
        }

    except VideoUnavailable:
        return {
            "video_id": video_id,
            "transcript_status": "video_unavailable",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": "Video unavailable."
        }

    except Exception as e:
        return {
            "video_id": video_id,
            "transcript_status": "error",
            "transcript": "",
            "segments": [],
            "segment_count": 0,
            "error": str(e)
        }