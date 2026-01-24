from fastapi import FastAPI
from backend.routers import voice, admin

app = FastAPI(title="Agentic Voice Backend")

app.include_router(voice.router)
app.include_router(admin.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
