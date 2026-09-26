from fastapi import APIRouter, File, UploadFile

from app.api.errors import not_implemented
from app.models import ErrorResponse, SttResponse, TtsRequest

router = APIRouter(prefix="/voice")


@router.post("/stt", response_model=SttResponse, responses={501: {"model": ErrorResponse}})
async def stt(audio: UploadFile = File(...)) -> SttResponse:
    raise not_implemented("VOX-1")


@router.post("/tts", responses={200: {"content": {"audio/mpeg": {}}}, 501: {"model": ErrorResponse}})
def tts(req: TtsRequest):
    raise not_implemented("VOX-2")
