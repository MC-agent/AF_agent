# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from src.agents.translate_agent import agent

# FastAPI app
app = FastAPI(
    title="AF Agent API",
    description="Translation Agent API Server",
    version="1.0.0"
)

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
