# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from src.agents.translate_agent import agent
from src.routers import pipeline, chat
from src.database.mysql import init_db

# FastAPI app
app = FastAPI(
    title="AF Agent API",
    description="Translation Agent and Integrated Pipeline API Server",
    version="1.0.0"
)

# 라우터 등록
app.include_router(chat.router) # 채팅 API
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
