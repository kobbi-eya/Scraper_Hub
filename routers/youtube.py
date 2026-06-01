"""
Router YouTube
==============
Controller pur : valide les paramètres HTTP, appelle le service, retourne la réponse.
Aucune logique métier ici.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from exporters import to_csv_response
from services import youtube_service

router = APIRouter(prefix="/youtube", tags=["YouTube"])


# ── Vidéo ─────────────────────────────────────────────────────────────────────

@router.get("/video")
def get_video(url: str = Query(..., description="URL YouTube de la vidéo")):
    """Retourne les métadonnées complètes d'une vidéo YouTube."""
    try:
        return youtube_service.scrape_video(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur scraping vidéo : {e}")


@router.get("/video/export", response_class=StreamingResponse)
def export_video(url: str = Query(...)):
    """Export CSV des métadonnées d'une vidéo."""
    try:
        data = youtube_service.scrape_video(url)
        return to_csv_response([data], "video.csv")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Chaîne ────────────────────────────────────────────────────────────────────

@router.get("/channel")
def get_channel(
    url:   str = Query(..., description="URL de la chaîne YouTube"),
    limit: int = Query(10, ge=1, description="Nombre de vidéos à récupérer"),
):
    """Retourne les dernières vidéos d'une chaîne YouTube."""
    try:
        return youtube_service.scrape_channel(url, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur scraping chaîne : {e}")


@router.get("/channel/export", response_class=StreamingResponse)
def export_channel(
    url:   str = Query(...),
    limit: int = Query(10, ge=1),
):
    """Export CSV des vidéos d'une chaîne."""
    try:
        data = youtube_service.scrape_channel(url, limit)
        return to_csv_response(data, f"channel_{datetime.now().strftime('%Y%m%d')}.csv")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Recherche ─────────────────────────────────────────────────────────────────

@router.get("/search")
def search_videos(
    q:     str = Query(..., description="Terme de recherche"),
    limit: int = Query(10, ge=1, description="Nombre de résultats"),
):
    """Recherche des vidéos YouTube."""
    try:
        return youtube_service.scrape_search(q, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur recherche : {e}")


@router.get("/search/export", response_class=StreamingResponse)
def export_search(
    q:     str = Query(...),
    limit: int = Query(10, ge=1),
):
    """Export CSV des résultats de recherche."""
    try:
        data = youtube_service.scrape_search(q, limit)
        return to_csv_response(data, "search.csv")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Commentaires ──────────────────────────────────────────────────────────────

@router.get("/comments")
def get_comments(
    url:   str = Query(..., description="URL YouTube de la vidéo"),
    limit: int = Query(20, ge=1, description="Nombre de commentaires"),
):
    """Retourne les commentaires d'une vidéo YouTube."""
    try:
        return youtube_service.scrape_comments(url, limit)
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur commentaires : {e}")


@router.get("/comments/export", response_class=StreamingResponse)
def export_comments(
    url:   str = Query(...),
    limit: int = Query(20, ge=1),
):
    """Export CSV des commentaires d'une vidéo."""
    try:
        data = youtube_service.scrape_comments(url, limit)
        return to_csv_response(data, "comments.csv")
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))