"""Health assistant chat and term lookups. Both require sign-in so the model is not open to anonymous use."""
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user
from app.models import User
from app.schemas import ChatInput, MedicineInput, TermInput
from extras_client import extras_client
from grok_client import grok_brain

router = APIRouter(prefix="/api/v1", tags=["assistant"])


BUSY_MESSAGE = "The AI assistant is busy right now. Please try again in a moment."


def _lookup_error(message: str) -> HTTPException:
    """The lookup client returns 'Could not ...' when the AI service fails, and a sentence when the input is out of scope."""
    if message.startswith("Could not"):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, BUSY_MESSAGE)
    return HTTPException(422, message)

# Small, bounded cache for first-turn questions only. Capped so memory cannot grow without limit.
_CACHE_MAX = 256
_chat_cache: "OrderedDict[str, dict]" = OrderedDict()


@router.post("/chat")
async def chat(body: ChatInput, user: User = Depends(get_current_user)):
    key = body.message.lower().strip()
    if not body.history and key in _chat_cache:
        return _chat_cache[key]

    result = await grok_brain.classify_and_respond(body.message, [t.model_dump() for t in body.history])
    out = {"reply": result.get("reply", ""), "suggestions": result.get("suggestions", [])}

    if not body.history and result.get("status") == "allowed":
        _chat_cache[key] = out
        _chat_cache.move_to_end(key)
        while len(_chat_cache) > _CACHE_MAX:
            _chat_cache.popitem(last=False)
    return out


@router.post("/lookups/dictionary")
async def dictionary(body: TermInput, user: User = Depends(get_current_user)):
    res = await extras_client.get_dictionary_definition(body.term)
    if "error" in res:
        raise _lookup_error(res["error"])
    return res


@router.post("/lookups/medicine")
async def medicine(body: MedicineInput, user: User = Depends(get_current_user)):
    res = await extras_client.get_medicine_info(body.name)
    if "error" in res:
        raise _lookup_error(res["error"])
    return res
