"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload

Routers get registered here as they're implemented under app/api/routes/.
"""

from fastapi import FastAPI

app = FastAPI(title="Sift API", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
