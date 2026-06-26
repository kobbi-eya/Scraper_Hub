"""
Scraper Hub — main.py
======================
Point d'entrée FastAPI.
Monte tous les routers. N'a aucune logique métier.

Lancement :
    uvicorn main:app --reload --port 8000
    python main.py
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import youtube_router, twitter_router, snapchat_router, linkedin_router, reddit_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="🕷️ Scraper Hub",
    description=(
        "## Multi-platform scraper API\n\n"
        "| Plateforme | Préfixe       | Status  |\n"
        "|------------|---------------|---------|\n"
        "| YouTube    | `/youtube`    | ✅ Live |\n"
        "| Twitter/X  | `/twitter`    | ✅ Live |\n"
        "| Snapchat   | `/snapchat`   | ✅ Live   |\n"
        "| Linkedin   | `/Linkedin`   | 🔧 WIP  |\n\n"
        "**Docs interactives** : [/docs](/docs) · [/redoc](/redoc)"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(youtube_router)
app.include_router(twitter_router)
app.include_router(snapchat_router)
app.include_router(linkedin_router)
app.include_router(reddit_router)

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Info"])
def root():
    return JSONResponse({
        "name":    "Scraper Hub",
        "version": "1.0.0",
        "docs":    "/docs",
        "scrapers": {
            "youtube": {
                "status": "live",
                "endpoints": [
                    "GET /youtube/video?url=...",
                    "GET /youtube/channel?url=...&limit=10",
                    "GET /youtube/search?q=...&limit=10",
                    "GET /youtube/comments?url=...&limit=20",
                    "GET /youtube/*/export  (CSV)",
                ]
            },
            "twitter": {
                "status": "live",
                "endpoints": [
                    "GET /twitter/profile?username=...",
                    "GET /twitter/user/tweets?username=...",
                    "GET /twitter/tweet/{id}",
                    "GET /twitter/transcript/{id}",
                    "GET /twitter/community/{id}",
                    "GET /twitter/community-tweets/{id}",
                    "GET /twitter/start-full-scrape?username=...",
                    "GET /twitter/export/csv?username=...",
                    "GET /twitter/export/json?username=...",
                ]
            },
            "snapchat": {
                "status": "wip",
                "endpoints": [
                    "GET /snapchat/profile?username=...",
                    "GET /snapchat/stories?username=...",
                    "GET /snapchat/spotlight?q=...&limit=10",
                ]
            },
        }
    })


# ── Entrypoint direct ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")