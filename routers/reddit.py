"""
Router Reddit  v0.1
===================
Endpoints :
  GET /reddit/posts/search              — recherche de posts
  GET /reddit/posts/{post_id}           — detail post + commentaires
  GET /reddit/r/{subreddit}             — infos + posts d'un subreddit
  GET /reddit/trending                  — subreddits tendance
  GET /reddit/users/{username}          — profil utilisateur
  GET /reddit/users/{username}/posts    — posts d'un utilisateur
"""

from fastapi import APIRouter, HTTPException, Path, Query
from typing import Optional

from exporters import to_csv_response
from services.reddit_service import (
    search_posts, get_subreddit, get_post,
    get_user, get_user_posts, trending_subreddits,
    RedditUnavailable,
)

router = APIRouter(prefix="/reddit", tags=["Reddit"])

FormatQuery = Query("json", alias="format", pattern="^(json|csv)$",
                    description="Format : json (defaut) ou csv")


def _respond(data, fmt: str, filename: str):
    if fmt == "csv":
        rows = data if isinstance(data, list) else [data]
        return to_csv_response(rows, filename)
    return data


# ── 1. Recherche posts ────────────────────────────────────────────────────────

@router.get("/posts/search", summary="Recherche de posts Reddit")
def route_search_posts(
    query:     str           = Query(...,         description="Termes de recherche (ex: python tutorial)"),
    subreddit: Optional[str] = Query(None,         description="Limiter a un subreddit (ex: python)"),
    sort:      str           = Query("relevance",  description="Tri : relevance | hot | new | top | comments"),
    time:      str           = Query("all",        description="Periode : hour | day | week | month | year | all"),
    limit:     int           = Query(25,           ge=1, le=100, description="Nombre de posts"),
    fmt:       str           = FormatQuery,
):
    """Recherche de posts sur Reddit (tout Reddit ou dans un subreddit specifique)."""
    try:
        data = search_posts(query, subreddit or "", sort, time, limit)
        return _respond(data, fmt, "reddit_posts.csv")
    except RedditUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur recherche posts : {e}")


# ── 2. Detail post + commentaires ─────────────────────────────────────────────

@router.get("/posts/{post_id}", summary="Detail d'un post Reddit")
def route_get_post(
    post_id:         str = Path(..., description="ID du post (ex: 1abc2de) ou URL complete",
                                example="1abc2de"),
    nb_commentaires: int = Query(10, ge=1, le=50, description="Nombre de commentaires"),
    fmt:             str = FormatQuery,
):
    """Detail complet d'un post Reddit avec ses commentaires."""
    try:
        data = get_post(post_id, nb_commentaires)
        return _respond(data, fmt, f"reddit_post_{post_id}.csv")
    except RedditUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur detail post : {e}")


# ── 3. Subreddit ──────────────────────────────────────────────────────────────

@router.get("/r/{subreddit}", summary="Infos et posts d'un subreddit")
def route_get_subreddit(
    subreddit: str = Path(..., description="Nom du subreddit (sans r/)", example="python"),
    tri:       str = Query("hot", description="Tri des posts : hot | new | top | rising"),
    limit:     int = Query(25,    ge=1, le=100, description="Nombre de posts"),
    fmt:       str = FormatQuery,
):
    """Informations et posts d'un subreddit Reddit."""
    try:
        data = get_subreddit(subreddit, tri, limit)
        return _respond(data, fmt, f"reddit_r_{subreddit}.csv")
    except RedditUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur subreddit : {e}")


# ── 4. Subreddits tendance ────────────────────────────────────────────────────

@router.get("/trending", summary="Subreddits tendance du moment")
def route_trending(
    fmt: str = FormatQuery,
):
    """Subreddits les plus populaires du moment sur Reddit."""
    try:
        data = trending_subreddits()
        return _respond(data, fmt, "reddit_trending.csv")
    except RedditUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur trending : {e}")


# ── 5. Profil utilisateur ─────────────────────────────────────────────────────

@router.get("/users/{username}", summary="Profil d'un utilisateur Reddit")
def route_get_user(
    username: str = Path(..., description="Nom d'utilisateur Reddit (sans u/)", example="spez"),
    fmt:      str = FormatQuery,
):
    """Profil public d'un utilisateur Reddit."""
    try:
        data = get_user(username)
        return _respond(data, fmt, f"reddit_user_{username}.csv")
    except RedditUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur profil user : {e}")


# ── 6. Posts d'un utilisateur ─────────────────────────────────────────────────

@router.get("/users/{username}/posts", summary="Posts d'un utilisateur Reddit")
def route_get_user_posts(
    username: str = Path(...,    description="Nom d'utilisateur Reddit", example="spez"),
    tri:      str = Query("new", description="Tri : new | hot | top | controversial"),
    limit:    int = Query(25,    ge=1, le=100, description="Nombre de posts"),
    fmt:      str = FormatQuery,
):
    """Posts publics d'un utilisateur Reddit."""
    try:
        data = get_user_posts(username, tri, limit)
        return _respond(data, fmt, f"reddit_user_{username}_posts.csv")
    except RedditUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur posts user : {e}")