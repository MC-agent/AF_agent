# -*- coding: utf-8 -*-
import logging
import logging.config
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
import uvicorn
from src.routers import pipeline, chat, auth
from src.database.mysql import init_db
from src.config import settings

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "src": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
    },
})

# FastAPI app
app = FastAPI(
    title="AF Agent API",
    description="Translation Agent and Integrated Pipeline API Server",
    version="1.0.0"
)

@app.middleware("http")
async def add_charset_utf8(request: Request, call_next):
    response: Response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type and "charset" not in content_type:
        response.headers["content-type"] = content_type + "; charset=utf-8"
    return response

# 라우터 등록
app.include_router(auth.router)  # 인증 API
app.include_router(chat.router)  # 채팅 API
if settings.enable_pipeline_routes:
    app.include_router(pipeline.router)

# Request model
class TranslateRequest(BaseModel):
    text: str

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, how are you?"
            }
        }

# Response model
class TranslateResponse(BaseModel):
    original_text: str
    response: str

# Startup event
@app.on_event("startup")
async def startup_event():
    """앱 시작 시 실행"""
    try:
        init_db()  # users, chats, messages 테이블 생성
        print("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        print(f"⚠️ 데이터베이스 초기화 실패: {e}")

# Health check endpoints
@app.get("/")
async def root():
    return {"message": "AF Agent API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Translation endpoint
@app.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest):
    """
    Detect text language and respond in the same language.
    - Korean input -> Korean response
    - English input -> English response
    - Japanese input -> Japanese response
    """
    try:
        # Lazy import
        from src.agents.translate_agent import agent

        # Execute Agent
        result = agent.invoke({
            "messages": [{"role": "user", "content": request.text}]
        })

        # Extract response
        response_text = result['messages'][-1].content

        return TranslateResponse(
            original_text=request.text,
            response=response_text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")

if __name__ == "__main__":
     uvicorn.run(
         "main:app",
         host="0.0.0.0",
         port=8000,
         reload=True
     )
