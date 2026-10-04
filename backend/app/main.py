import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.api.routes import router as api_router
from app.api.websocket import ws_router, simulation_background_loop
from app.config import settings
from app.ai_client import ask_ai


class ChatRequest(BaseModel):
    message: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: spawn background loop for simulation ticks
    sim_task = asyncio.create_task(simulation_background_loop())
    yield
    # Shutdown
    sim_task.cancel()

app = FastAPI(
    title="ReliefChain API",
    description="Intelligent and Transparent Disaster Relief Resource Allocation Platform. Allocate smarter. Prove everything.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS — FRONTEND_URL may be a comma-separated list of origins
# Local Vite (5173) and same-origin Docker/backend (8000) are always included
allowed_origins = settings.frontend_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,  # no cookies; JWT in Authorization header
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.post("/api/chat")
def chat(request: ChatRequest):
    return {"reply": ask_ai(request.message)}


import os
from fastapi.staticfiles import StaticFiles

# Check for built frontend in dist/ directory (production / Docker)
dist_dirs = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dist"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "dist"),
    os.path.join(os.getcwd(), "dist"),
]

static_dist = None
for d in dist_dirs:
    if os.path.exists(d) and os.path.exists(os.path.join(d, "index.html")):
        static_dist = d
        break

if static_dist:
    app.mount("/", StaticFiles(directory=static_dist, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {
            "platform": "ReliefChain",
            "tagline": "Allocate smarter. Prove everything.",
            "project": "EL-02 Intelligent Disaster Relief Resource Allocation",
            "scenario": "Mumbai Monsoon Surge",
            "docs": "/docs",
            "health": "/api/health"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.BACKEND_PORT, reload=True)
