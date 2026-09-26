from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from app.api.errors import ApiError
from app.models import ErrorResponse, SttResponse, TtsRequest
from app.voice.client import VoiceUnavailable
from app.voice.stt import AudioTooLarge, UnsupportedAudioType, transcribe
from app.voice.tts import TextTooLong, synthesize

router = APIRouter(prefix="/voice")

_VOICE_UNAVAILABLE = "The voice service is unavailable right now — type your request instead."


@router.post(
    "/stt",
    response_model=SttResponse,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def stt(audio: UploadFile = File(...)) -> SttResponse:
    """VOX-1: transcribe a short recorded clip. Failures fall back to typed input on the client."""
    data = await audio.read()
    try:
        text = transcribe(data, audio.content_type, filename=audio.filename or "audio.webm")
    except AudioTooLarge as exc:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", str(exc)) from exc
    except UnsupportedAudioType as exc:
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", str(exc)) from exc
    except VoiceUnavailable as exc:
        raise ApiError(503, "VOICE_UNAVAILABLE", _VOICE_UNAVAILABLE) from exc
    return SttResponse(text=text)


@router.post(
    "/tts",
    responses={
        200: {"content": {"audio/mpeg": {}}},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def tts(req: TtsRequest) -> Response:
    """VOX-2: synthesize a short spoken line to MP3 (disk-cached). Failures fall back to the browser."""
    try:
        audio = synthesize(req.text)
    except TextTooLong as exc:
        raise ApiError(422, "TEXT_TOO_LONG", str(exc)) from exc
    except VoiceUnavailable as exc:
        raise ApiError(503, "VOICE_UNAVAILABLE", _VOICE_UNAVAILABLE) from exc
    return Response(content=audio, media_type="audio/mpeg")
