"""
Reddit Service  v0.1  — API JSON publique (sans authentification)
=================================================================
Reddit expose une API JSON publique via /<endpoint>.json
Pas besoin de cle API pour les donnees publiques.

Endpoints couverts :
  - search_posts()      : recherche de posts
  - get_subreddit()     : infos + posts chauds d'un subreddit
  - get_post()          : detail d'un post + commentaires
  - get_user()          : profil d'un utilisateur
  - get_user_posts()    : posts d'un utilisateur
  - trending_subreddits(): subreddits tendance
"""

import logging
import re
from typing import Optional

import requests

log = logging.getLogger("service.reddit")

_BASE = "https://www.reddit.com"

_HEADERS = {
    "User-Agent": "scraper-hub/0.1 (public data only)",
    "Accept":     "application/json",
}


class RedditUnavailable(Exception):
    """Ressource Reddit introuvable, privee, ou bloquee."""


# ══════════════════════════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════════════════════════

def _get(url: str, params: dict | None = None, timeout: int = 15) -> dict:
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
    except requests.RequestException as e:
        raise RedditUnavailable(f"Erreur reseau Reddit : {e}")
    if r.status_code == 404:
        raise RedditUnavailable(f"Ressource introuvable (404) : {url}")
    if r.status_code == 403:
        raise RedditUnavailable("Acces refuse (403) — subreddit prive ou utilisateur suspendu.")
    if r.status_code == 429:
        raise RedditUnavailable("Rate limit Reddit (429). Reessayez dans quelques secondes.")
    if r.status_code != 200:
        raise RedditUnavailable(f"Reponse Reddit inattendue (HTTP {r.status_code}).")
    return r.json()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_post(post: dict) -> dict:
    """Normalise un objet post Reddit (data d'un 'thing' t3)."""
    return {
        "post_id":       post.get("id"),
        "titre":         post.get("title"),
        "auteur":        post.get("author"),
        "subreddit":     post.get("subreddit"),
        "score":         post.get("score", 0),
        "upvote_ratio":  post.get("upvote_ratio", 0),
        "nb_commentaires": post.get("num_comments", 0),
        "url_post":      f"{_BASE}{post.get('permalink', '')}",
        "url_contenu":   post.get("url"),
        "texte":         post.get("selftext") or None,
        "image":         post.get("thumbnail") if post.get("thumbnail", "").startswith("http") else None,
        "flair":         post.get("link_flair_text"),
        "is_video":      post.get("is_video", False),
        "is_nsfw":       post.get("over_18", False),
        "date":          _ts(post.get("created_utc")),
        "awards":        post.get("total_awards_received", 0),
    }


def _fmt_comment(c: dict) -> dict:
    """Normalise un commentaire Reddit."""
    return {
        "comment_id": c.get("id"),
        "auteur":     c.get("author"),
        "texte":      c.get("body"),
        "score":      c.get("score", 0),
        "date":       _ts(c.get("created_utc")),
        "url":        f"{_BASE}{c.get('permalink', '')}",
    }


def _ts(ts) -> Optional[str]:
    """Convertit un timestamp Unix en ISO 8601."""
    if not ts:
        return None
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _children(data: dict, kind: str = "t3") -> list[dict]:
    """Extrait les enfants d'un listing Reddit."""
    listing  = data.get("data", {})
    children = listing.get("children", [])
    return [c["data"] for c in children if c.get("kind") == kind and c.get("data")]


# ══════════════════════════════════════════════════════════════════════════════
# 1. RECHERCHE DE POSTS
# ══════════════════════════════════════════════════════════════════════════════

def search_posts(
    query:     str,
    subreddit: str = "",
    sort:      str = "relevance",
    time:      str = "all",
    limit:     int = 25,
) -> list[dict]:
    """
    Recherche de posts Reddit.

    query     : termes de recherche
    subreddit : limiter a un subreddit (ex: 'python') ou '' pour tout Reddit
    sort      : relevance | hot | new | top | comments
    time      : hour | day | week | month | year | all
    limit     : nombre de posts (max 100)
    """
    if subreddit:
        url = f"{_BASE}/r/{subreddit}/search.json"
        params: dict = {"q": query, "restrict_sr": "1", "sort": sort, "t": time,
                        "limit": min(limit, 100)}
    else:
        url = f"{_BASE}/search.json"
        params = {"q": query, "sort": sort, "t": time, "limit": min(limit, 100)}

    data  = _get(url, params=params)
    posts = _children(data, "t3")
    return [_fmt_post(p) for p in posts[:limit]]


# ══════════════════════════════════════════════════════════════════════════════
# 2. SUBREDDIT — INFOS + POSTS
# ══════════════════════════════════════════════════════════════════════════════

def get_subreddit(
    subreddit: str,
    tri:       str = "hot",
    limit:     int = 25,
) -> dict:
    """
    Infos et posts d'un subreddit.

    subreddit : nom du subreddit (ex: 'python', 'MachineLearning')
    tri       : hot | new | top | rising
    limit     : nombre de posts a retourner
    """
    # Infos du subreddit
    about = _get(f"{_BASE}/r/{subreddit}/about.json")
    info  = about.get("data", {})

    # Posts
    posts_data = _get(f"{_BASE}/r/{subreddit}/{tri}.json",
                      params={"limit": min(limit, 100)})
    posts = _children(posts_data, "t3")

    return {
        "nom":          info.get("display_name"),
        "titre":        info.get("title"),
        "description":  info.get("public_description"),
        "nb_membres":   info.get("subscribers", 0),
        "nb_actifs":    info.get("active_user_count", 0),
        "is_nsfw":      info.get("over18", False),
        "date_creation": _ts(info.get("created_utc")),
        "url":          f"{_BASE}/r/{subreddit}/",
        "posts":        [_fmt_post(p) for p in posts[:limit]],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. DETAIL POST + COMMENTAIRES
# ══════════════════════════════════════════════════════════════════════════════

def get_post(post_id: str, nb_commentaires: int = 10) -> dict:
    """
    Detail d'un post Reddit avec ses commentaires.

    post_id         : ID du post (ex: '1abc2de') ou URL complète
    nb_commentaires : nombre de commentaires a retourner (max 50)
    """
    # Extrait l'ID si URL complète
    m = re.search(r'/comments/([a-z0-9]+)/', post_id, re.IGNORECASE)
    pid = m.group(1) if m else post_id.strip()

    data = _get(f"{_BASE}/comments/{pid}.json",
                params={"limit": min(nb_commentaires, 50), "depth": 1})

    if not isinstance(data, list) or len(data) < 2:
        raise RedditUnavailable(f"Post '{pid}' introuvable.")

    # Post
    posts = _children(data[0], "t3")
    if not posts:
        raise RedditUnavailable(f"Post '{pid}' introuvable.")
    post = _fmt_post(posts[0])

    # Commentaires
    comments_raw = _children(data[1], "t1")
    post["commentaires"] = [_fmt_comment(c) for c in comments_raw[:nb_commentaires]]

    return post


# ══════════════════════════════════════════════════════════════════════════════
# 4. PROFIL UTILISATEUR
# ══════════════════════════════════════════════════════════════════════════════

def get_user(username: str) -> dict:
    """
    Profil public d'un utilisateur Reddit.
    username : nom d'utilisateur (sans u/)
    """
    data = _get(f"{_BASE}/user/{username}/about.json")
    u    = data.get("data", {})

    if not u.get("name"):
        raise RedditUnavailable(f"Utilisateur '{username}' introuvable ou suspendu.")

    return {
        "username":      u.get("name"),
        "karma_post":    u.get("link_karma", 0),
        "karma_comment": u.get("comment_karma", 0),
        "karma_total":   u.get("total_karma", 0),
        "avatar":        u.get("icon_img"),
        "is_premium":    u.get("is_gold", False),
        "is_mod":        u.get("is_mod", False),
        "is_verified":   u.get("verified", False),
        "date_creation": _ts(u.get("created_utc")),
        "url":           f"{_BASE}/user/{username}/",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. POSTS D'UN UTILISATEUR
# ══════════════════════════════════════════════════════════════════════════════

def get_user_posts(
    username: str,
    tri:      str = "new",
    limit:    int = 25,
) -> list[dict]:
    """
    Posts recents d'un utilisateur Reddit.
    tri   : new | hot | top | controversial
    limit : nombre de posts (max 100)
    """
    data  = _get(f"{_BASE}/user/{username}/submitted.json",
                 params={"sort": tri, "limit": min(limit, 100)})
    posts = _children(data, "t3")
    return [_fmt_post(p) for p in posts[:limit]]


# ══════════════════════════════════════════════════════════════════════════════
# 6. SUBREDDITS TENDANCE
# ══════════════════════════════════════════════════════════════════════════════

def trending_subreddits() -> list[dict]:
    """
    Subreddits tendance du moment (endpoint officiel Reddit).
    """
    data = _get(f"{_BASE}/api/trending_subreddits.json")
    noms = data.get("subreddit_names", [])

    results = []
    for nom in noms:
        try:
            about = _get(f"{_BASE}/r/{nom}/about.json")
            info  = about.get("data", {})
            results.append({
                "nom":         info.get("display_name"),
                "titre":       info.get("title"),
                "description": info.get("public_description"),
                "nb_membres":  info.get("subscribers", 0),
                "is_nsfw":     info.get("over18", False),
                "url":         f"{_BASE}/r/{nom}/",
            })
        except Exception:
            results.append({"nom": nom, "url": f"{_BASE}/r/{nom}/"})

    return results