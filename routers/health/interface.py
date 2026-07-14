from fastapi import APIRouter
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger("app")

class TestResponse(BaseModel):
    message: str

@router.post("/test", response_model=TestResponse)
def test():
    logger.info("Demo /test called")
    return {"message": "Hello Manuscript!"}