"""
YouTube Service
===============
Logique métier pure — aucune dépendance FastAPI.
Utilise yt-dlp et youtube-comment-downloader.
"""

import yt_dlp

try:
    from youtube_comment_downloader import YoutubeCommentDownloader
    COMMENTS_ENABLED = True
except ImportError:
    COMMENTS_ENABLED = False


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO
# ══════════════════════════════════════════════════════════════════════════════

def scrape_video(url: str) -> dict:
    """
    Retourne les métadonnées complètes d'une vidéo YouTube.
    Lève une exception si l'URL est invalide ou inaccessible.
    """
    ydl_opts = {"quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "titre":       info.get("title"),
            "vues":        info.get("view_count"),
            "likes":       info.get("like_count"),
            "description": info.get("description"),
            "duree":       info.get("duration"),
            "chaine":      info.get("channel"),
            "date":        info.get("upload_date"),
            "tags":        info.get("tags"),
            "thumbnail":   info.get("thumbnail"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# CHAÎNE
# ══════════════════════════════════════════════════════════════════════════════

def scrape_channel(url: str, limit: int = 10) -> list[dict]:
    """
    Retourne les dernières vidéos d'une chaîne YouTube.
    `limit` : nombre de vidéos à récupérer (sans borne max imposée).
    """
    ydl_opts = {
        "quiet":        True,
        "extract_flat": True,
        "playlistend":  limit,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"{url.rstrip('/')}/videos", download=False)
        return [
            {
                "titre": v.get("title", "N/A"),
                "url":   f"https://www.youtube.com/watch?v={v.get('id', '')}",
                "duree": v.get("duration", "N/A"),
                "vues":  v.get("view_count", "N/A"),
            }
            for v in info.get("entries", [])
        ]


# ══════════════════════════════════════════════════════════════════════════════
# RECHERCHE
# ══════════════════════════════════════════════════════════════════════════════

def scrape_search(query: str, limit: int = 10) -> list[dict]:
    """
    Recherche des vidéos YouTube.
    `limit` : nombre de résultats (sans borne max imposée).
    """
    ydl_opts = {
        "quiet":        True,
        "extract_flat": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        return [
            {
                "titre":  v.get("title"),
                "url":    v.get("url"),
                "chaine": v.get("channel"),
                "duree":  v.get("duration"),
            }
            for v in info.get("entries", [])
        ]


# ══════════════════════════════════════════════════════════════════════════════
# COMMENTAIRES
# ══════════════════════════════════════════════════════════════════════════════

def scrape_comments(url: str, limit: int = 20) -> list[dict]:
    """
    Retourne les commentaires d'une vidéo YouTube.
    Lève RuntimeError si youtube-comment-downloader n'est pas installé.
    """
    if not COMMENTS_ENABLED:
        raise RuntimeError(
            "youtube-comment-downloader non installé. "
            "Lancez : pip install youtube-comment-downloader"
        )
    downloader = YoutubeCommentDownloader()
    comments   = []
    for comment in downloader.get_comments_from_url(url, sort_by=0):
        comments.append({
            "auteur": comment.get("author"),
            "texte":  comment.get("text"),
            "likes":  comment.get("votes"),
            "date":   comment.get("time"),
        })
        if len(comments) >= limit:
            break
    return comments