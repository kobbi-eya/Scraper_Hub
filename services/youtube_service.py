"""
YouTube Service
===============
Logique métier pure — aucune dépendance FastAPI.
Utilise yt-dlp et youtube-comment-downloader.

Dépendances :
    pip install yt-dlp
    pip install youtube-comment-downloader   # commentaires + réponses
La transcription utilise yt-dlp (sous-titres) : aucune dépendance en plus.
"""

import json
from urllib.request import Request, urlopen

import yt_dlp

try:
    from youtube_comment_downloader import YoutubeCommentDownloader
    COMMENTS_ENABLED = True
except ImportError:
    COMMENTS_ENABLED = False


class TranscriptUnavailable(Exception):
    """Aucun sous-titre / aucune transcription disponible pour cette vidéo."""


class CommunityPostUnavailable(Exception):
    """Post Community introuvable, supprimé ou privé."""


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNES
# ══════════════════════════════════════════════════════════════════════════════

def _flat_entries(target: str, limit: int) -> list[dict]:
    """Extraction « flat » (rapide, sans télécharger chaque vidéo) d'une page/onglet."""
    ydl_opts = {
        "quiet":        True,
        "extract_flat": True,
        "playlistend":  limit,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target, download=False)
        return info.get("entries", []) or []


def _map_videos(entries: list[dict]) -> list[dict]:
    """Normalise une liste d'entrées vidéo (vidéos, shorts, lives, playlist, recherche)."""
    out = []
    for v in entries:
        vid = v.get("id", "")
        out.append({
            "titre": v.get("title", "N/A"),
            "url":   f"https://www.youtube.com/watch?v={vid}" if vid else v.get("url"),
            "duree": v.get("duration", "N/A"),
            "vues":  v.get("view_count", "N/A"),
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# VIDEO  (existant)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_video(url: str) -> dict:
    """
    Retourne les métadonnées complètes d'une vidéo (ou d'un short) YouTube.
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
# CHAÎNE — DÉTAILS  (nouveau)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_channel_details(url: str) -> dict:
    """
    Retourne les métadonnées d'une chaîne (nom, abonnés, description, etc.).
    Différent de scrape_channel(), qui renvoie la LISTE des vidéos.
    """
    ydl_opts = {
        "quiet":        True,
        "extract_flat": True,
        "playlistend":  1,  # on ne veut que les métadonnées de la chaîne
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "nom":         info.get("channel") or info.get("uploader") or info.get("title"),
            "channel_id":  info.get("channel_id") or info.get("id"),
            "url":         info.get("channel_url") or info.get("webpage_url"),
            "description": info.get("description"),
            "abonnes":     info.get("channel_follower_count"),
            "tags":        info.get("tags"),
            "thumbnails":  info.get("thumbnails"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# CHAÎNE — VIDÉOS  (existant)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_channel(url: str, limit: int = 10) -> list[dict]:
    """Retourne les dernières vidéos d'une chaîne YouTube."""
    entries = _flat_entries(f"{url.rstrip('/')}/videos", limit)
    return _map_videos(entries)


# ══════════════════════════════════════════════════════════════════════════════
# CHAÎNE — PLAYLISTS  (nouveau)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_channel_playlists(url: str, limit: int = 10) -> list[dict]:
    """Retourne les playlists publiées par une chaîne."""
    entries = _flat_entries(f"{url.rstrip('/')}/playlists", limit)
    out = []
    for e in entries:
        pid = e.get("id", "")
        out.append({
            "titre":    e.get("title", "N/A"),
            "url":      e.get("url") or (f"https://www.youtube.com/playlist?list={pid}" if pid else None),
            "nb_videos": e.get("playlist_count") or e.get("video_count"),
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════
# CHAÎNE — LIVES  (nouveau)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_channel_lives(url: str, limit: int = 10) -> list[dict]:
    """Retourne les lives (passés/en cours) d'une chaîne — onglet /streams."""
    entries = _flat_entries(f"{url.rstrip('/')}/streams", limit)
    return _map_videos(entries)


# ══════════════════════════════════════════════════════════════════════════════
# CHAÎNE — SHORTS  (nouveau)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_channel_shorts(url: str, limit: int = 10) -> list[dict]:
    """Retourne les Shorts d'une chaîne — onglet /shorts."""
    entries = _flat_entries(f"{url.rstrip('/')}/shorts", limit)
    return _map_videos(entries)


# ══════════════════════════════════════════════════════════════════════════════
# TRANSCRIPT  (yt-dlp — sans dépendance externe)
# ══════════════════════════════════════════════════════════════════════════════

_LANG_NAMES = {
    "en": "English", "fr": "French", "es": "Spanish", "de": "German",
    "it": "Italian", "pt": "Portuguese", "ar": "Arabic", "ru": "Russian",
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "hi": "Hindi",
    "nl": "Dutch", "tr": "Turkish", "pl": "Polish",
}


def _lang_name(code: str) -> str:
    """Nom lisible d'une langue à partir de son code (fallback = le code brut)."""
    base = (code or "").split("-")[0]
    return _LANG_NAMES.get(base, code)


def _fmt_time(seconds: float) -> str:
    """Formate des secondes en 'M:SS' ou 'H:MM:SS' (comme l'UI YouTube)."""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _select_track(manual: dict, auto: dict, lang: str):
    """
    Sélectionne la meilleure piste -> (formats, code_langue, generee_auto).
    Priorité : sous-titres manuels exacts > auto exacts > préfixe > 1re dispo.
    """
    for is_auto, tracks in ((False, manual), (True, auto)):
        if tracks and lang in tracks:
            return tracks[lang], lang, is_auto
    for is_auto, tracks in ((False, manual), (True, auto)):
        for key in (tracks or {}):
            if key.split("-")[0] == lang:
                return tracks[key], key, is_auto
    for is_auto, tracks in ((False, manual), (True, auto)):
        if tracks:
            key = next(iter(tracks))
            return tracks[key], key, is_auto
    return None, None, None


def _available_languages(manual: dict, auto: dict) -> list[dict]:
    """Liste dédupliquée des langues disponibles (manuel prioritaire)."""
    seen = {}
    for code in (manual or {}):
        seen.setdefault(code, {"code": code, "nom": _lang_name(code), "auto": False})
    for code in (auto or {}):
        seen.setdefault(code, {"code": code, "nom": _lang_name(code), "auto": True})
    return list(seen.values())


def _fetch_caption(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_json3(raw: str) -> list[dict]:
    """Parse le format json3 de YouTube -> [{text, start, dur}] (secondes)."""
    doc = json.loads(raw)
    out = []
    for ev in doc.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if not text:
            continue
        out.append({
            "text":  text,
            "start": ev.get("tStartMs", 0) / 1000,
            "dur":   ev.get("dDurationMs", 0) / 1000,
        })
    return out


def _parse_vtt(raw: str) -> list[dict]:
    """Parse basique du format WebVTT (fallback) -> [{text, start, dur}]."""
    import re as _re
    ts = _re.compile(
        r"(\d+):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d+):(\d{2}):(\d{2})\.(\d{3})"
    )

    def to_s(h, m, s, ms):
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    out = []
    for block in _re.split(r"\n\n+", raw):
        m = ts.search(block)
        if not m:
            continue
        start, end = to_s(*m.groups()[:4]), to_s(*m.groups()[4:])
        lines = [
            l for l in block.splitlines()
            if l.strip() and not ts.search(l) and l.strip().upper() != "WEBVTT"
        ]
        text = _re.sub(r"<[^>]+>", "", " ".join(lines)).strip()
        if text:
            out.append({"text": text, "start": start, "dur": end - start})
    return out


def scrape_transcript(url: str, lang: str = "en") -> dict:
    """
    Retourne la transcription d'une vidéo via yt-dlp, sous forme d'enveloppe
    riche (parité avec les API concurrentes) :

        {
          success, type, url, video_id, language, language_code,
          is_generated, available_languages,
          transcript: [{texte, debut, duree, fin, startMs, endMs, startTimeText}],
          transcript_text: "<texte complet d'un bloc>"
        }

    Lève TranscriptUnavailable si aucune piste n'est disponible.
    """
    ydl_opts = {
        "quiet":             True,
        "skip_download":     True,
        "writesubtitles":    True,
        "writeautomaticsub": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    manual = info.get("subtitles") or {}
    auto   = info.get("automatic_captions") or {}

    formats, lang_code, is_auto = _select_track(manual, auto, lang)
    if not formats:
        raise TranscriptUnavailable(
            f"Aucune transcription disponible (langue demandée : {lang})."
        )

    # priorité json3 (parse propre), sinon vtt, sinon dernier format dispo
    chosen = (
        next((f for f in formats if f.get("ext") == "json3"), None)
        or next((f for f in formats if f.get("ext") == "vtt"), None)
        or formats[-1]
    )
    raw = _fetch_caption(chosen["url"])

    if chosen.get("ext") == "json3":
        base = _parse_json3(raw)
    elif chosen.get("ext") == "vtt":
        base = _parse_vtt(raw)
    else:
        try:
            base = _parse_json3(raw)
        except Exception:
            base = _parse_vtt(raw)

    if not base:
        raise TranscriptUnavailable("Transcription vide ou illisible.")

    segments, parts = [], []
    for seg in base:
        start = round(seg["start"], 3)
        dur   = round(seg["dur"], 3)
        segments.append({
            "texte":         seg["text"],
            "debut":         start,
            "duree":         dur,
            "fin":           round(start + dur, 3),
            "startMs":       int(seg["start"] * 1000),
            "endMs":         int((seg["start"] + seg["dur"]) * 1000),
            "startTimeText": _fmt_time(start),
        })
        parts.append(seg["text"])

    return {
        "success":             True,
        "type":                "video",
        "url":                 url,
        "video_id":            info.get("id"),
        "language":            _lang_name(lang_code),
        "language_code":       lang_code,
        "is_generated":        is_auto,
        "available_languages": _available_languages(manual, auto),
        "transcript":          segments,
        "transcript_text":     " ".join(parts),
    }


# ══════════════════════════════════════════════════════════════════════════════
# RECHERCHE  (existant)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_search(query: str, limit: int = 10) -> list[dict]:
    """Recherche des vidéos YouTube."""
    ydl_opts = {"quiet": True, "extract_flat": True}
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
# RECHERCHE PAR HASHTAG  (nouveau)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_hashtag(tag: str, limit: int = 10) -> list[dict]:
    """Retourne les vidéos associées à un hashtag."""
    tag = tag.lstrip("#").strip()
    entries = _flat_entries(f"https://www.youtube.com/hashtag/{tag}", limit)
    return _map_videos(entries)


# ══════════════════════════════════════════════════════════════════════════════
# PLAYLIST  (nouveau)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_playlist(url: str, limit: int = 10) -> list[dict]:
    """Retourne les vidéos d'une playlist (URL playlist?list=...)."""
    entries = _flat_entries(url, limit)
    return _map_videos(entries)


# ══════════════════════════════════════════════════════════════════════════════
# TRENDING SHORTS  (nouveau — best-effort)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_trending_shorts(limit: int = 10) -> list[dict]:
    """
    Retourne des Shorts tendance (best-effort).

    ⚠️ YouTube n'expose pas d'onglet stable « Trending Shorts » exploitable par
    yt-dlp. On lit le feed Trending et on filtre heuristiquement les Shorts
    (URL /shorts/ ou durée <= 60s). Les résultats peuvent varier selon la région.
    """
    entries = _flat_entries("https://www.youtube.com/feed/trending", limit * 3)
    shorts = []
    for v in entries:
        url = v.get("url", "") or ""
        dur = v.get("duration")
        is_short = "/shorts/" in url or (isinstance(dur, (int, float)) and dur <= 60)
        if is_short:
            shorts.append(v)
        if len(shorts) >= limit:
            break
    return _map_videos(shorts)


# ══════════════════════════════════════════════════════════════════════════════
# COMMENTAIRES  (existant)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_comments(url: str, limit: int = 20) -> list[dict]:
    """
    Retourne les commentaires (de premier niveau + réponses mélangés) d'une vidéo.
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
            "id":     comment.get("cid"),
            "auteur": comment.get("author"),
            "texte":  comment.get("text"),
            "likes":  comment.get("votes"),
            "date":   comment.get("time"),
            "reponses": comment.get("replies"),
        })
        if len(comments) >= limit:
            break
    return comments


# ══════════════════════════════════════════════════════════════════════════════
# RÉPONSES À UN COMMENTAIRE  (nouveau)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_comment_replies(url: str, comment_id: str, limit: int = 20) -> list[dict]:
    """
    Retourne les réponses à un commentaire donné.

    youtube-comment-downloader diffuse les réponses avec un `cid` de la forme
    "PARENT.REPLY". On filtre donc les entrées dont le cid commence par
    `comment_id`. On stream en mode récent (sort_by=1) pour remonter les fils.
    """
    if not COMMENTS_ENABLED:
        raise RuntimeError(
            "youtube-comment-downloader non installé. "
            "Lancez : pip install youtube-comment-downloader"
        )
    downloader = YoutubeCommentDownloader()
    replies    = []
    for comment in downloader.get_comments_from_url(url, sort_by=1):
        cid = comment.get("cid", "")
        if "." in cid and cid.split(".", 1)[0] == comment_id:
            replies.append({
                "id":     cid,
                "auteur": comment.get("author"),
                "texte":  comment.get("text"),
                "likes":  comment.get("votes"),
                "date":   comment.get("time"),
            })
            if len(replies) >= limit:
                break
    return replies


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY POST DETAILS  (scraping ytInitialData — sans dépendance)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_html(url: str) -> str:
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_initial_data(html: str) -> dict | None:
    """Extrait le bloc JSON `ytInitialData` du HTML (par appariement d'accolades)."""
    idx = html.find("ytInitialData")
    if idx == -1:
        return None
    brace = html.find("{", idx)
    if brace == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(brace, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[brace:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _find_first(obj, key):
    """Première valeur trouvée pour `key` en parcourant récursivement obj."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_first(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_first(v, key)
            if r is not None:
                return r
    return None


def _runs_text(node) -> str | None:
    """Aplatit un noeud texte YouTube ({simpleText} ou {runs:[...]})."""
    if not isinstance(node, dict):
        return None
    if "simpleText" in node:
        return node["simpleText"]
    runs = node.get("runs")
    if runs:
        return "".join(r.get("text", "") for r in runs)
    return None


def _best_thumb(node: dict) -> str | None:
    """URL de la plus grande miniature d'un noeud image."""
    thumbs = ((node or {}).get("image") or node or {}).get("thumbnails")
    if thumbs:
        return thumbs[-1].get("url")
    return None


def scrape_community_post(post_id: str) -> dict:
    """
    Détails d'un post Community, via scraping de `ytInitialData`.

    Accepte un ID (`Ugkx...`) ou une URL complète (`.../post/Ugkx...`).
    Lève CommunityPostUnavailable si le post est introuvable/supprimé/privé.
    """
    pid = post_id.strip()
    if "/post/" in pid:
        pid = pid.split("/post/", 1)[1].split("?", 1)[0].split("/", 1)[0]

    url = f"https://www.youtube.com/post/{pid}?hl=en"
    data = _extract_initial_data(_fetch_html(url))
    if not data:
        raise CommunityPostUnavailable(f"Post Community introuvable : {pid}")

    post = (_find_first(data, "backstagePostRenderer")
            or _find_first(data, "sharedPostRenderer"))
    if not post:
        raise CommunityPostUnavailable(f"Post Community introuvable : {pid}")

    attachment = post.get("backstageAttachment", {}) or {}

    # images (post simple ou multi-images)
    images = []
    single = _find_first(attachment, "backstageImageRenderer")
    if single:
        u = _best_thumb(single)
        if u:
            images.append(u)
    multi = _find_first(attachment, "postMultiImageRenderer")
    if multi:
        for img in (multi.get("images") or []):
            u = _best_thumb(_find_first(img, "backstageImageRenderer") or img)
            if u:
                images.append(u)

    # vidéo attachée
    video = _find_first(attachment, "videoRenderer")
    video_attachee = None
    if video and video.get("videoId"):
        video_attachee = {
            "video_id": video.get("videoId"),
            "titre":    _runs_text(video.get("title")),
            "url":      f"https://www.youtube.com/watch?v={video['videoId']}",
        }

    # sondage
    poll = _find_first(attachment, "pollRenderer")
    sondage = None
    if poll:
        sondage = {
            "choix": [_runs_text(c.get("text")) for c in (poll.get("choices") or [])],
            "total_votes": _runs_text(poll.get("totalVotes")),
        }

    author_ep = post.get("authorEndpoint", {}) or {}
    channel_id = (author_ep.get("browseEndpoint", {}) or {}).get("browseId")

    return {
        "success":        True,
        "type":           "community_post",
        "url":            f"https://www.youtube.com/post/{pid}",
        "post_id":        post.get("postId", pid),
        "auteur":         _runs_text(post.get("authorText")),
        "channel_id":     channel_id,
        "texte":          _runs_text(post.get("contentText")),
        "date":           _runs_text(post.get("publishedTimeText")),
        "likes":          _runs_text(post.get("voteCount")),
        "images":         images,
        "video_attachee": video_attachee,
        "sondage":        sondage,
    }