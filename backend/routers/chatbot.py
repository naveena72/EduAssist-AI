from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..database import get_db
from ..services import chatbot_service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


class AskRequest(BaseModel):
    message: str


@router.post("/ask")
def ask(body: AskRequest, user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)):
    if not body.message.strip():
        raise HTTPException(422, "Message is empty")
    return chatbot_service.answer(db, user, body.message[:500])


@router.get("/history")
def history(limit: int = 20, user: models.User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    rows = (db.query(models.ChatLog).filter_by(user_id=user.id)
            .order_by(models.ChatLog.id.desc()).limit(min(limit, 100)).all())
    return [{"question": r.question, "answer": r.answer, "intent": r.intent,
             "timestamp": r.timestamp.isoformat(timespec="seconds")} for r in reversed(rows)]
