from fastapi import FastAPI
from backend.routers import voice

app = FastAPI(title="Agentic Voice Backend")

app.include_router(voice.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
