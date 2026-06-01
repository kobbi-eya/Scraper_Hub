"""
Router Snapchat
================
Controller pur : HTTP in, HTTP out.
Toute la logique est dans snapchat_service.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from exporters import to_csv_response, to_json_response
from services.snapchat_service import (
    scrape_profile,
    scrape_stories,
    scrape_full,
    scrape_spotlight,
    search_accounts,
    download_snaps,
    scrape_multiple,
)

router = APIRouter(prefix="/snapchat", tags=["Snapchat"])


# ── Profil ────────────────────────────────────────────────────────────────────

@router.get("/profile")
def get_profile(username: str = Query(..., description="Nom d'utilisateur Snapchat (sans @)")):
    """Retourne les infos publiques d'un profil Snapchat."""
    result = scrape_profile(username)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── Stories ───────────────────────────────────────────────────────────────────

@router.get("/stories")
def get_stories(username: str = Query(..., description="Nom d'utilisateur Snapchat")):
    """Retourne les snaps/stories publics d'un utilisateur."""
    result = scrape_stories(username)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/stories/export/csv")
def export_stories_csv(username: str = Query(...)):
    """Export CSV des stories."""
    result = scrape_stories(username)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return to_csv_response(result["snaps"], f"snapchat_stories_{username}.csv")


@router.get("/stories/export/json")
def export_stories_json(username: str = Query(...)):
    """Export JSON des stories."""
    result = scrape_stories(username)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return to_json_response(result, f"snapchat_stories_{username}.json")


# ── Full scrape ───────────────────────────────────────────────────────────────

@router.get("/full")
def get_full(username: str = Query(..., description="Nom d'utilisateur Snapchat")):
    """Scrape complet : profil + snaps + commentaires."""
    result = scrape_full(username)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── Spotlight ─────────────────────────────────────────────────────────────────

@router.get("/spotlight")
def get_spotlight(
    q:     str = Query(..., description="Terme de recherche Spotlight"),
    limit: int = Query(10, ge=1, le=50, description="Nombre de résultats"),
):
    """Recherche des vidéos Spotlight Snapchat."""
    result = scrape_spotlight(q, limit)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/search")
def search(
    q:           str       = Query(..., description="Nom ou mot-clé"),
    strategies:  list[str] = Query(["username", "web"], description="Stratégies : username, web"),
    max_results: int       = Query(10, ge=1, le=50),
):
    """Recherche des comptes Snapchat par nom ou mot-clé."""
    result = search_accounts(q, strategies=strategies, max_results=max_results)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Download ──────────────────────────────────────────────────────────────────

@router.get("/download")
def download(
    username:      str  = Query(..., description="Nom d'utilisateur Snapchat"),
    out_dir:       str  = Query("media", description="Dossier de destination"),
    use_thumbnail: bool = Query(False,   description="Miniatures au lieu des médias HD"),
):
    """Scrape et télécharge tous les médias d'un compte."""
    result = download_snaps(username, out_dir=out_dir, use_thumbnail=use_thumbnail)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── Multiple ──────────────────────────────────────────────────────────────────

@router.post("/multiple")
def multiple(usernames: list[str]):
    """Scrape plusieurs comptes en séquentiel."""
    if not usernames:
        raise HTTPException(status_code=400, detail="Liste de usernames vide")
    if len(usernames) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 comptes par requête")
    result = scrape_multiple(usernames)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result