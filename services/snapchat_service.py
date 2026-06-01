"""
Snapchat Service  v2.0
=======================
Logique métier pure — tout est ici, zéro dépendance externe (pas de core/ ni modules/).
S'appuie uniquement sur requests (déjà dans requirements.txt).

Contrat attendu par routers/snapchat.py
"""

import io
import json
import logging
import random
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger("service.snapchat")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SnapConfig:
    timeout:     int   = 15
    max_retries: int   = 3
    delay_min:   float = 1.0
    delay_max:   float = 2.5
    debug:       bool  = False
    output_dir:  str   = "media"

# ══════════════════════════════════════════════════════════════════════════════
# MODÈLES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Profil:
    username:     str
    display_name: str  = "N/A"
    abonnes:      str  = "N/A"
    verified:     bool = False
    description:  str  = ""
    avatar_url:   str  = "N/A"

@dataclass
class Snap:
    snap_id:       str
    type:          str  = "unknown"
    media_url:     str  = ""
    thumbnail_url: str  = ""
    duration:      Optional[int] = None
    timestamp:     Optional[str] = None
    view_count:    Optional[int] = None
    title:         Optional[str] = None

@dataclass
class Commentaire:
    auteur:    str  = ""
    texte:     str  = ""
    likes:     int  = 0
    timestamp: Optional[str] = None

@dataclass
class ResultatScrape:
    profil:       Profil
    snaps:        list = field(default_factory=list)
    commentaires: list = field(default_factory=list)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION HTTP
# ══════════════════════════════════════════════════════════════════════════════

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
]

def _build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent":      random.choice(_USER_AGENTS),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT":             "1",
        "Connection":      "keep-alive",
    })
    return s

def _fetch_html(session: requests.Session, url: str, config: SnapConfig) -> Optional[str]:
    for attempt in range(1, config.max_retries + 1):
        try:
            r = session.get(url, timeout=config.timeout)
            if r.status_code == 200:
                return r.text
            if r.status_code in (403, 404):
                log.warning(f"HTTP {r.status_code} → {url}")
                return None
            log.warning(f"HTTP {r.status_code} tentative {attempt}/{config.max_retries}")
            time.sleep(2 * attempt)
        except requests.RequestException as e:
            log.warning(f"Erreur réseau tentative {attempt}: {e}")
            time.sleep(2)
    return None

# ══════════════════════════════════════════════════════════════════════════════
# PARSERS __NEXT_DATA__
# ══════════════════════════════════════════════════════════════════════════════

TAILLE_MIN_PAGE = 50_000  # bytes — pages vides ~144KB, avec contenu >200KB

def _extraire_next_data(html: str) -> Optional[dict]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

def _extraire_profil(props: dict, username: str) -> Profil:

    if not isinstance(props, dict):
        return Profil(username=username)

    user_profile = props.get("userProfile") or {}

    public_info = user_profile.get("publicProfileInfo") or {}

    return Profil(
        username=public_info.get("username", username),
        display_name=public_info.get("title", "N/A"),
        abonnes=public_info.get("subscriberCount", "N/A"),
        verified=public_info.get("badge", 0) > 0,
        description=public_info.get("bio", ""),
        avatar_url=public_info.get("profilePictureUrl", "N/A"),
    )

# def _extraire_snaps(props: dict) -> list:
#     if not isinstance(props, dict):
#         return []
#     story = props.get("story") or {} 
#     snaps_raw = (
#         story.get("snapList", [])
#         or story.get("snaps", [])
#         or props.get("snapList", [])
#         or props.get("snaps", [])
#         or []
#     )
#     snaps = []
#     for i, s in enumerate(snaps_raw):
#         snap_id = (
#             s.get("snapId", {}).get("value")
#             or s.get("id")
#             or s.get("snapId")
#             or f"snap_{i}"
#         )
#         media_url = (
#             s.get("snapUrls", {}).get("mediaUrl")
#             or s.get("mediaUrl")
#             or s.get("url")
#             or ""
#         )
#         thumb = s.get("snapUrls", {}).get("mediaPreviewUrl", {})
#         thumbnail_url = (
#             (thumb.get("value") if isinstance(thumb, dict) else thumb)
#             or s.get("thumbnailUrl")
#             or ""
#         )
#         snap_type = (
#             "video" if s.get("snapMediaType") == 0
#             else "image" if s.get("snapMediaType") == 1
#             else s.get("type", "unknown")
#         )
#         timestamp = s.get("timestampInSec", {}).get("value") or s.get("timestamp")
#         snaps.append(Snap(
#             snap_id=str(snap_id),
#             type=snap_type,
#             media_url=media_url,
#             thumbnail_url=thumbnail_url if isinstance(thumbnail_url, str) else "",
#             duration=s.get("duration") or s.get("durationMs"),
#             timestamp=str(timestamp) if timestamp else None,
#             title=s.get("title") or s.get("headline"),
#         ))
#     return snaps

def _extraire_snaps(props: dict) -> list:
    if not isinstance(props, dict):
        return []

    snaps_raw = []

    # 1) Story classique
    story = props.get("story")
    if isinstance(story, dict):
        snaps_raw.extend(story.get("snapList", []) or [])

    # 2) Curated Highlights
    for highlight in props.get("curatedHighlights", []) or []:
        if isinstance(highlight, dict):
            snaps_raw.extend(highlight.get("snapList", []) or [])

    # 3) Spotlight Highlights
    for highlight in props.get("spotlightHighlights", []) or []:
        if isinstance(highlight, dict):
            snaps_raw.extend(highlight.get("snapList", []) or [])

    snaps = []

    for i, s in enumerate(snaps_raw):
        if not isinstance(s, dict):
            continue

        # ---------------- ID ----------------
        snap_id = (
            s.get("snapId", {}).get("value")
            if isinstance(s.get("snapId"), dict)
            else None
        ) or s.get("id") or f"snap_{i}"

        # ---------------- URL MEDIA ----------------
        snap_urls = s.get("snapUrls") or {}
        media_url = snap_urls.get("mediaUrl") or s.get("mediaUrl") or s.get("url") or ""

        # ---------------- THUMBNAIL ----------------
        preview = snap_urls.get("mediaPreviewUrl")
        if isinstance(preview, dict):
            thumbnail_url = preview.get("value") or ""
        else:
            thumbnail_url = preview or s.get("thumbnailUrl") or ""

        # ---------------- TYPE (robuste Snapchat) ----------------
        media_type = s.get("snapMediaType")

        has_audio = bool(s.get("audioTranscriptionObjectUrl"))

        # Spotlight = presque toujours vidéo
        if has_audio or media_type == 0:
            snap_type = "video"
        elif media_type == 1:
            snap_type = "image"
        else:
            snap_type = "unknown"

        # ---------------- TIMESTAMP ----------------
        timestamp = None
        t = s.get("timestampInSec")

        if isinstance(t, dict):
            timestamp = t.get("value")
        else:
            timestamp = s.get("timestamp")

        # ---------------- TITLE ----------------
        title = s.get("snapTitle") or s.get("title") or s.get("headline")

        # ---------------- OBJECT FINAL ----------------
        snaps.append(
            Snap(
                snap_id=str(snap_id),
                type=snap_type,
                media_url=media_url,
                thumbnail_url=thumbnail_url,
                duration=s.get("duration") or s.get("durationMs"),
                timestamp=str(timestamp) if timestamp else None,
                title=title,
            )
        )

    return snaps

def _extraire_commentaires(props: dict) -> list:
    
    if not isinstance(props, dict):
        return []
    comments_raw = (
        props.get("comments", [])
        or (props.get("story") or {}).get("comments", [])  # ← "or {}" ici
        or []
    )
    return [
        Commentaire(
            auteur=c.get("author") or c.get("username") or "",
            texte=c.get("text") or c.get("body") or "",
            likes=int(c.get("likes") or c.get("likeCount") or 0),
            timestamp=str(c.get("timestamp")) if c.get("timestamp") else None,
        )
        for c in comments_raw
    ]

# ══════════════════════════════════════════════════════════════════════════════
# SCRAPE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def _scrape(username: str, config: SnapConfig = None) -> Optional[ResultatScrape]:

   
    if config is None:
        config = SnapConfig()

    session = _build_session()
    html    = _fetch_html(session, f"https://story.snapchat.com/@{username}", config)

    if not html:
        return None
    if len(html.encode("utf-8")) < TAILLE_MIN_PAGE:
        log.info(f"@{username} → page vide ({len(html.encode()):,} bytes)")
        return None

    next_data = _extraire_next_data(html)
    print("NEXT DATA FOUND:", next_data is not None)

    if next_data:
        print("TOP KEYS:", list(next_data.keys()))

        props = next_data.get("props", {}).get("pageProps", {})
        for key in props.keys():
            value = props[key]

            if isinstance(value, (list, dict)):
                try:
                    size = len(value)
                except:
                    size = "?"
            else:
                size = "-"
        print("\n================ USERPROFILE ================")
        print(type(props.get("userProfile")))
        print(repr(props.get("userProfile"))[:2000])

        print("\n================ STORY ================")
        print(type(props.get("story")))
        print(repr(props.get("story"))[:2000])

        print("PAGE PROPS KEYS:")
        print(list(props.keys()))
    
    if not next_data:
        return None

    props = next_data.get("props", {}).get("pageProps", {})
    for key in props.keys():
        value = props[key]

        if isinstance(value, (list, dict)):
            try:
                size = len(value)
            except:
                size = "?"
        else:
            size = "-"

    print(f"{key} -> {type(value).__name__} -> {size}")
    print("\n================ USERPROFILE ================")
    print(type(props.get("userProfile")))
    print(repr(props.get("userProfile"))[:2000])

    print("\n================ STORY ================")
    print(type(props.get("story")))
    print(repr(props.get("story"))[:2000])

    if not props:
        return None

    print("\n===== CURATED HIGHLIGHTS =====")
    print("curated len =", len(props.get("curatedHighlights", [])))

    if props.get("curatedHighlights"):
        print(json.dumps(props.get("curatedHighlights"), indent=2)[:5000])

    print("\n===== SPOTLIGHT HIGHLIGHTS =====")
    print("spotlight len =", len(props.get("spotlightHighlights", [])))

    if props.get("spotlightHighlights"):
        print(json.dumps(props.get("spotlightHighlights"), indent=2)[:5000])


    with open("userProfile.json", "w", encoding="utf-8") as f:
        json.dump(props.get("userProfile"), f, indent=2, ensure_ascii=False)

    with open("story.json", "w", encoding="utf-8") as f:
        json.dump(props.get("story"), f, indent=2, ensure_ascii=False)

    profil       = _extraire_profil(props, username)
    snaps        = _extraire_snaps(props)
    commentaires = _extraire_commentaires(props)

    if profil.display_name == "N/A" and not snaps:
        log.info(f"@{username} → parsé mais vide")
        return None

    log.info(f"✅ @{username} | {profil.display_name} | {len(snaps)} snaps")
    return ResultatScrape(profil=profil, snaps=snaps, commentaires=commentaires)

# ══════════════════════════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════════════════════════

_ALIASES: dict[str, list[str]] = {
    "national geographic": ["natgeo", "nationalgeographic"],
    "bbc news": ["bbcnews", "bbc"], "nasa": ["nasa"],
    "cnn": ["cnn"], "nba": ["nba"], "nfl": ["nfl"],
    "espn": ["espn"], "disney": ["disney"], "red bull": ["redbull"],
    "vice": ["vice"], "buzzfeed": ["buzzfeed"],
}
_WEB_BLACKLIST = {"add", "search", "explore", "spotlight", "lens", "map", "stories", "topic", "tag", "t"}

def _deviner_usernames(query: str) -> list[str]:
    q    = query.strip().lower()
    mots = [m for m in re.split(r"[\s\-_]+", q) if m]
    vus, out = set(), []
    for c in list(_ALIASES.get(q, [])) + ["".join(mots), "_".join(mots), mots[0]]:
        c = re.sub(r"[^a-z0-9_\-\.]", "", c)
        if c and len(c) >= 2 and c not in vus:
            vus.add(c); out.append(c)
    return out

def _recherche_web(query: str, session: requests.Session, config: SnapConfig) -> list[str]:
    sq = f"site:story.snapchat.com {query}"
    for engine in [
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(sq)}",
        f"https://www.google.com/search?q={urllib.parse.quote(sq)}&num=10",
    ]:
        try:
            r = session.get(engine, timeout=config.timeout)
            if r.status_code == 200 and "snapchat" in r.text.lower():
                decoded = urllib.parse.unquote(r.text)
                found = re.findall(r"story\.snapchat\.com/@([\w\-\.]+)", decoded, re.IGNORECASE)
                found += re.findall(r"snapchat\.com/@([\w\-\.]+)", decoded, re.IGNORECASE)
                vus = set()
                out = []
                for u in found:
                    if u.lower() not in vus and u.lower() not in _WEB_BLACKLIST:
                        vus.add(u.lower()); out.append(u)
                return out[:8]
        except requests.RequestException:
            time.sleep(1)
    return []

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS → dict
# ══════════════════════════════════════════════════════════════════════════════

def _p(p: Profil) -> dict:
    return {
        "username": p.username, "display_name": p.display_name,
        "abonnes": p.abonnes, "verified": p.verified,
        "description": p.description, "avatar_url": p.avatar_url,
        "profile_url": f"https://story.snapchat.com/@{p.username}",
    }

def _s(s: Snap) -> dict:
    return {
        "snap_id": s.snap_id, "type": s.type,
        "media_url": s.media_url, "thumbnail_url": s.thumbnail_url,
        "duration": s.duration, "timestamp": s.timestamp,
        "view_count": s.view_count, "title": s.title,
    }

def _c(c: Commentaire) -> dict:
    return {"auteur": c.auteur, "texte": c.texte, "likes": c.likes, "timestamp": c.timestamp}

# ══════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE — utilisée par routers/snapchat.py
# ══════════════════════════════════════════════════════════════════════════════

def scrape_profile(username: str) -> dict:
    try:
        r = _scrape(username)
        if r is None:
            return {"error": f"@{username} introuvable ou sans contenu public"}
        return {"success": True, "profile": _p(r.profil),
                "snap_count": len(r.snaps), "comment_count": len(r.commentaires)}
    except Exception as e:
        log.exception(f"[scrape_profile] @{username}"); return {"error": str(e)}


def scrape_stories(username: str) -> dict:
    try:
        r = _scrape(username)
        if r is None:
            return {"error": f"@{username} introuvable ou sans contenu public"}
        by_type: dict[str, int] = {}
        for s in r.snaps:
            by_type[s.type] = by_type.get(s.type, 0) + 1
        return {"success": True, "username": username,
                "count": len(r.snaps), "by_type": by_type,
                "snaps": [_s(s) for s in r.snaps]}
    except Exception as e:
        log.exception(f"[scrape_stories] @{username}"); return {"error": str(e)}


def scrape_full(username: str) -> dict:
    try:
        r = _scrape(username)
        if r is None:
            return {"error": f"@{username} introuvable ou sans contenu public"}
        return {
            "success": True, "profile": _p(r.profil),
            "snaps": [_s(s) for s in r.snaps],
            "commentaires": [_c(c) for c in r.commentaires],
            "stats": {
                "snap_count": len(r.snaps), "comment_count": len(r.commentaires),
                "top_comment": max((c.likes for c in r.commentaires), default=0),
            },
        }
    except Exception as e:
        log.exception(f"[scrape_full] @{username}"); return {"error": str(e)}


def search_accounts(query: str, strategies: list = None, max_results: int = 10) -> dict:
    if strategies is None:
        strategies = ["username", "web"]
    try:
        config = SnapConfig(); session = _build_session()
        found: list[dict] = []; seen: set[str] = set()

        if "username" in strategies:
            for u in _deviner_usernames(query)[:5]:
                if u in seen: continue
                seen.add(u)
                r = _scrape(u, config)
                if r:
                    found.append({**_p(r.profil), "source": "username_guess"})
                time.sleep(random.uniform(0.8, 1.5))

        if "web" in strategies:
            for u in _recherche_web(query, session, config)[:5]:
                if u in seen: continue
                seen.add(u)
                r = _scrape(u, config)
                if r:
                    found.append({**_p(r.profil), "source": "web_search"})
                time.sleep(random.uniform(0.5, 1.2))

        return {"success": True, "query": query, "count": len(found),
                "results": found[:max_results]}
    except Exception as e:
        log.exception(f"[search_accounts] '{query}'"); return {"error": str(e)}


def scrape_spotlight(query: str, limit: int = 10) -> dict:
    result = search_accounts(query, strategies=["web"], max_results=limit)
    if "error" in result:
        return result
    return {"success": True, "query": query,
            "count": result["count"], "results": result["results"]}


def download_snaps(username: str, out_dir: str = "media", use_thumbnail: bool = False) -> dict:
    try:
        r = _scrape(username)
        if r is None:
            return {"error": f"@{username} introuvable"}
        dest = Path(out_dir) / username
        dest.mkdir(parents=True, exist_ok=True)
        session = _build_session()
        ok = 0; failed = 0; total_size = 0; errors = []
        for snap in r.snaps:
            url = snap.thumbnail_url if use_thumbnail else snap.media_url
            if not url:
                failed += 1; continue
            ext  = Path(url.split("?")[0]).suffix or ".mp4"
            path = dest / f"{snap.snap_id[:16]}{ext}"
            if path.exists():
                ok += 1; continue
            try:
                resp = session.get(url, timeout=15, stream=True)
                resp.raise_for_status()
                size = 0
                with open(path, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk); size += len(chunk)
                total_size += size; ok += 1
                time.sleep(random.uniform(0.3, 0.8))
            except Exception as e:
                failed += 1; errors.append({"snap_id": snap.snap_id, "error": str(e)})
        return {"success": True, "username": username, "total": len(r.snaps),
                "downloaded": ok, "failed": failed, "output_dir": str(dest),
                "total_size": total_size, "errors": errors}
    except Exception as e:
        log.exception(f"[download_snaps] @{username}"); return {"error": str(e)}


def scrape_multiple(usernames: list) -> dict:
    try:
        config = SnapConfig(); resultats = []
        for i, u in enumerate(usernames):
            r = _scrape(u, config)
            if r:
                resultats.append({"profile": _p(r.profil),
                                   "snap_count": len(r.snaps),
                                   "comment_count": len(r.commentaires)})
            if i < len(usernames) - 1:
                time.sleep(random.uniform(1.0, 2.5))
        return {"success": True, "total": len(usernames),
                "scraped": len(resultats), "failed": len(usernames) - len(resultats),
                "results": resultats}
    except Exception as e:
        log.exception("[scrape_multiple]"); return {"error": str(e)}