"""
Router YouTube
==============
Controller pur : valide les paramètres HTTP, appelle le service, retourne la réponse.
Aucune logique métier ici.

Note : chaque endpoint accepte `?format=json` (défaut) ou `?format=csv`.
Les anciennes routes `/export` dédiées ont été fusionnées ici pour supprimer
la duplication (1 route par ressource au lieu de 2).
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from services import youtube_service
from exporters import to_csv_response

router = APIRouter(prefix="/youtube", tags=["YouTube"])

# Paramètre de format réutilisable (alias public = "format", évite de masquer le builtin)
FormatQuery = Query("json", alias="format", pattern="^(json|csv)$",
                    description="Format de sortie : json (défaut) ou csv")


def _respond(data, fmt: str, filename: str):
    """Renvoie soit le JSON brut, soit un CSV téléchargeable selon `fmt`."""
    if fmt == "csv":
        rows = data if isinstance(data, list) else [data]
        return to_csv_response(rows, filename)
    return data


# -- Video / Short -------------------------------------------------------------

@router.get("/video")
def get_video(
    url: str = Query(..., description="URL YouTube de la video ou du short"),
    fmt: str = FormatQuery,
):
    """Metadonnees completes d'une video ou d'un short YouTube."""
    try:
        return _respond(youtube_service.scrape_video(url), fmt, "video.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur scraping video : {e}")


# -- Chaine : details ----------------------------------------------------------

@router.get("/channel/details")
def get_channel_details(
    url: str = Query(..., description="URL de la chaine YouTube"),
    fmt: str = FormatQuery,
):
    """Metadonnees d'une chaine (nom, abonnes, description...)."""
    try:
        return _respond(youtube_service.scrape_channel_details(url), fmt, "channel_details.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur details chaine : {e}")


# -- Chaine : videos -----------------------------------------------------------

@router.get("/channel")
def get_channel(
    url:   str = Query(..., description="URL de la chaine YouTube"),
    limit: int = Query(10, ge=1, description="Nombre de videos a recuperer"),
    fmt:   str = FormatQuery,
):
    """Dernieres videos d'une chaine YouTube."""
    try:
        data = youtube_service.scrape_channel(url, limit)
        return _respond(data, fmt, f"channel_{datetime.now().strftime('%Y%m%d')}.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur scraping chaine : {e}")


# -- Chaine : playlists --------------------------------------------------------

@router.get("/channel/playlists")
def get_channel_playlists(
    url:   str = Query(..., description="URL de la chaine YouTube"),
    limit: int = Query(10, ge=1, description="Nombre de playlists a recuperer"),
    fmt:   str = FormatQuery,
):
    """Playlists d'une chaine YouTube."""
    try:
        data = youtube_service.scrape_channel_playlists(url, limit)
        return _respond(data, fmt, "channel_playlists.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur playlists chaine : {e}")


# -- Chaine : lives ------------------------------------------------------------

@router.get("/channel/lives")
def get_channel_lives(
    url:   str = Query(..., description="URL de la chaine YouTube"),
    limit: int = Query(10, ge=1, description="Nombre de lives a recuperer"),
    fmt:   str = FormatQuery,
):
    """Lives (onglet /streams) d'une chaine YouTube."""
    try:
        data = youtube_service.scrape_channel_lives(url, limit)
        return _respond(data, fmt, "channel_lives.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lives chaine : {e}")


# -- Chaine : shorts -----------------------------------------------------------

@router.get("/channel/shorts")
def get_channel_shorts(
    url:   str = Query(..., description="URL de la chaine YouTube"),
    limit: int = Query(10, ge=1, description="Nombre de shorts a recuperer"),
    fmt:   str = FormatQuery,
):
    """Shorts d'une chaine YouTube."""
    try:
        data = youtube_service.scrape_channel_shorts(url, limit)
        return _respond(data, fmt, "channel_shorts.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur shorts chaine : {e}")


# -- Transcript ----------------------------------------------------------------

@router.get("/transcript")
def get_transcript(
    url:  str = Query(..., description="URL YouTube de la video"),
    lang: str = Query("en", description="Langue preferee (ex: en, fr)"),
    fmt:  str = FormatQuery,
):
    """Transcription d'une video, segment par segment."""
    try:
        data = youtube_service.scrape_transcript(url, lang)
        if fmt == "csv":
            return to_csv_response(data["transcript"], "transcript.csv")
        return data
    except youtube_service.TranscriptUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur transcription : {e}")


# -- Recherche -----------------------------------------------------------------

@router.get("/search")
def search_videos(
    q:     str = Query(..., description="Terme de recherche"),
    limit: int = Query(10, ge=1, description="Nombre de resultats"),
    fmt:   str = FormatQuery,
):
    """Recherche de videos YouTube."""
    try:
        data = youtube_service.scrape_search(q, limit)
        return _respond(data, fmt, "search.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur recherche : {e}")


# -- Recherche par hashtag -----------------------------------------------------

@router.get("/search/hashtag")
def search_hashtag(
    tag:   str = Query(..., description="Hashtag (avec ou sans #)"),
    limit: int = Query(10, ge=1, description="Nombre de resultats"),
    fmt:   str = FormatQuery,
):
    """Recherche de videos par hashtag."""
    try:
        data = youtube_service.scrape_hashtag(tag, limit)
        return _respond(data, fmt, "hashtag.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur recherche hashtag : {e}")


# -- Playlist ------------------------------------------------------------------

@router.get("/playlist")
def get_playlist(
    url:   str = Query(..., description="URL de la playlist (playlist?list=...)"),
    limit: int = Query(10, ge=1, description="Nombre de videos a recuperer"),
    fmt:   str = FormatQuery,
):
    """Videos d'une playlist YouTube."""
    try:
        data = youtube_service.scrape_playlist(url, limit)
        return _respond(data, fmt, "playlist.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur playlist : {e}")


# -- Trending Shorts -----------------------------------------------------------

@router.get("/trending/shorts")
def get_trending_shorts(
    limit: int = Query(10, ge=1, description="Nombre de shorts tendance"),
    fmt:   str = FormatQuery,
):
    """Shorts tendance (best-effort, depend de la region)."""
    try:
        data = youtube_service.scrape_trending_shorts(limit)
        return _respond(data, fmt, "trending_shorts.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur trending shorts : {e}")


# -- Commentaires --------------------------------------------------------------

@router.get("/comments")
def get_comments(
    url:   str = Query(..., description="URL YouTube de la video"),
    limit: int = Query(20, ge=1, description="Nombre de commentaires"),
    fmt:   str = FormatQuery,
):
    """Commentaires d'une video YouTube."""
    try:
        data = youtube_service.scrape_comments(url, limit)
        return _respond(data, fmt, "comments.csv")
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur commentaires : {e}")


# -- Reponses a un commentaire -------------------------------------------------

@router.get("/comments/replies")
def get_comment_replies(
    url:        str = Query(..., description="URL YouTube de la video"),
    comment_id: str = Query(..., description="ID du commentaire parent (cid)"),
    limit:      int = Query(20, ge=1, description="Nombre de reponses"),
    fmt:        str = FormatQuery,
):
    """Reponses a un commentaire donne."""
    try:
        data = youtube_service.scrape_comment_replies(url, comment_id, limit)
        return _respond(data, fmt, "comment_replies.csv")
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur reponses : {e}")


# -- Community Post Details ----------------------------------------------------

@router.get("/community/post")
def get_community_post(
    post_id: str = Query(..., description="ID du post Community"),
):
    """Details d'un post Community (auteur, texte, likes, images, video, sondage)."""
    try:
        return youtube_service.scrape_community_post(post_id)
    except youtube_service.CommunityPostUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur community post : {e}")