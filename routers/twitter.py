"""
Router Twitter/X
=================
Controller pur : HTTP in, HTTP out. Toute la logique est dans twitter_service.
"""

import io
import json
import re
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query
from fastapi import Path as FPath
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from exporters import to_csv_response, to_json_response
from services.twitter_service import (
    TwitterClient,
    _running_jobs,
    clear_cache,
    detect_all_qids,
    generate_windows,
    has_auth,
    list_checkpoints,
    load_all_checkpoints,
    load_cache,
    load_checkpoint,
    new_guest_session,
    run_full_scrape_background,
    save_checkpoint,
    scrape_quick,
    QID_FALLBACKS,
    QID_CACHE_FILE,
    _qid_cache,
    _qid_lock,
    save_qid_cache,
    make_auth_session,
    try_with_fallbacks,
    FEATURES_TWEETS,
    extract_community_id,
)

router = APIRouter(prefix="/twitter", tags=["Twitter/X"])


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.get("/auth/status")
async def auth_status():
    return {
        "authenticated": has_auth(),
        "message": (
            "Cookies configurés — Communities accessibles."
            if has_auth()
            else "Mode guest. Ajoutez AUTH_TOKEN et CT0 dans .env pour les Communities."
        ),
    }


# ── QIDs ──────────────────────────────────────────────────────────────────────

@router.get("/qids")
async def get_qids(refresh: bool = Query(False)):
    if refresh or not _qid_cache:
        try:
            sess     = new_guest_session()
            detected = detect_all_qids(sess)
            with _qid_lock:
                _qid_cache.update(detected)
                save_qid_cache(_qid_cache)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    age_s = None
    if QID_CACHE_FILE.exists():
        age_s = int((datetime.now() - datetime.fromtimestamp(QID_CACHE_FILE.stat().st_mtime)).total_seconds())
    return {"qids": _qid_cache, "cache_age_seconds": age_s, "fallbacks": QID_FALLBACKS}


# ── Profil ────────────────────────────────────────────────────────────────────

@router.get("/profile")
async def get_profile(username: str = Query(...)):
    try:
        client = TwitterClient()
        profile, user_id, created_year = client.get_profile(username)
        return {"success": True, "profile": profile, "tokens_used": client._pool.total_used}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── User tweets ───────────────────────────────────────────────────────────────

@router.get("/user/tweets")
async def get_user_tweets(
    username:   str  = Query(...),
    max_tweets: int  = Query(800),
    refresh:    bool = Query(False),
):
    try:
        if refresh: clear_cache(username)
        existing = load_all_checkpoints(username)
        if existing and not refresh:
            return {"success": True, "username": username, "source": "checkpoints",
                    "count": len(existing),
                    "tweets": existing[:max_tweets] if max_tweets else existing}
        client = TwitterClient()
        profile, user_id, _ = client.get_profile(username)
        tweets = client.pipeline_a(user_id)
        return {"success": True, "username": username, "source": "pipeline_a",
                "count": len(tweets),
                "tweets": tweets[:max_tweets] if max_tweets else tweets,
                "tokens_used": client._pool.total_used}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Tweet detail ──────────────────────────────────────────────────────────────

@router.get("/tweet/{tweet_id}")
async def get_tweet(tweet_id: str = FPath(..., description="ID numérique du tweet")):
    if not re.match(r"^\d{5,25}$", tweet_id):
        raise HTTPException(status_code=400, detail=f"ID invalide : '{tweet_id}'")
    try:
        client = TwitterClient()
        client._init("twitter")
        detail = client.get_tweet_detail(tweet_id)
        if "error" in detail:
            raise HTTPException(status_code=404, detail=detail["error"])
        return {"success": True, **detail, "tokens_used": client._pool.total_used}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Transcript ────────────────────────────────────────────────────────────────

@router.get("/transcript/{tweet_id}")
async def get_transcript(
    tweet_id: str = FPath(...),
    format:   str = Query("json", description="json | text"),
):
    if not re.match(r"^\d{5,25}$", tweet_id):
        raise HTTPException(status_code=400, detail=f"ID invalide : '{tweet_id}'")
    try:
        client = TwitterClient()
        client._init("twitter")
        result = client.get_transcript(tweet_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        if format == "text":
            return StreamingResponse(iter([result["transcript"]]),
                                     media_type="text/plain; charset=utf-8")
        return {"success": True, **result, "tokens_used": client._pool.total_used}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Community ─────────────────────────────────────────────────────────────────

@router.get("/community/{community_id:path}")
async def get_community(community_id: str = FPath(...)):
    if community_id.endswith("/tweets"):
        community_id = community_id[:-7]
    cid = extract_community_id(community_id)
    if not cid:
        raise HTTPException(status_code=400, detail=f"ID ou URL invalide : '{community_id}'")
    try:
        client = TwitterClient()
        client._init("twitter")
        data = client.get_community(cid)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        return {"success": True, **data, "tokens_used": client._pool.total_used}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/community-tweets/{community_id:path}")
async def get_community_tweets(
    community_id: str = FPath(...),
    max_tweets:   int = Query(100),
):
    cid = extract_community_id(community_id)
    if not cid:
        raise HTTPException(status_code=400, detail=f"ID ou URL invalide : '{community_id}'")
    try:
        client = TwitterClient()
        client._init("twitter")
        data = client.get_community_tweets(cid, min(max_tweets, 400))
        return {"success": True, **data, "tokens_used": client._pool.total_used}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Scrape full ───────────────────────────────────────────────────────────────

@router.get("/start-full-scrape")
async def start_full_scrape(
    background_tasks: BackgroundTasks,
    username: str  = Query(...),
    force:    bool = Query(False),
):
    job = _running_jobs.get(username, {})
    if job.get("status") == "running" and not force:
        return {"message": f"Déjà en cours @{username}", "job": job}
    _running_jobs[username] = {
        "status": "running", "progress": 0, "total_windows": 0,
        "current_window": "init", "tweets_found": 0,
        "started_at": datetime.now().isoformat(),
    }
    background_tasks.add_task(run_full_scrape_background, username)
    return {"message": f"Extraction lancée @{username}",
            "status_url": f"/twitter/status?username={username}"}


@router.get("/status")
async def scrape_status(username: str = Query(...)):
    job = _running_jobs.get(username)
    if not job:
        return {"status": "no_job", "checkpoints": len(list_checkpoints(username)),
                "tweets": len(load_all_checkpoints(username))}
    return job


# ── Checkpoints ───────────────────────────────────────────────────────────────

@router.get("/checkpoints")
async def list_ckpts(username: str = Query(...)):
    result = [{"window": wk, "tweets": len(load_checkpoint(username, wk) or [])}
              for wk in list_checkpoints(username)]
    return {"username": username, "windows": result, "total": sum(r["tweets"] for r in result)}


@router.delete("/checkpoints")
async def delete_checkpoints(username: str = Query(...)):
    from pathlib import Path
    from config import CHECKPOINT_DIR
    deleted = 0
    for p in CHECKPOINT_DIR.glob(f"{username}_*.json"):
        p.unlink(); deleted += 1
    clear_cache(username); _running_jobs.pop(username, None)
    return {"username": username, "deleted": deleted}


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/export/csv")
async def export_csv(username: str = Query(...)):
    tweets = load_all_checkpoints(username)
    if not tweets:
        data, _ = scrape_quick(username); tweets = data["tweets"]
    if not tweets:
        raise HTTPException(status_code=404, detail="Aucun tweet")
    fname = f"{username}_tweets_{datetime.now().strftime('%Y%m%d')}.csv"
    return to_csv_response(tweets, fname)


@router.get("/export/json")
async def export_json(username: str = Query(...)):
    tweets = load_all_checkpoints(username)
    if not tweets:
        data, _ = scrape_quick(username); tweets = data["tweets"]
    fname = f"{username}_tweets_{datetime.now().strftime('%Y%m%d')}.json"
    return to_json_response({"tweets": tweets, "count": len(tweets)}, fname)


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/ingest/json")
async def ingest_json(username: str = Query(...), payload: dict = Body(...)):
    tweets_raw = payload if isinstance(payload, list) else payload.get("tweets", [])
    tweets = []; seen: set[str] = set()
    for t in tweets_raw:
        tid  = t.get("id_str") or str(t.get("id", ""))
        text = t.get("full_text") or t.get("text", "")
        if tid and text and tid not in seen:
            seen.add(tid); tweets.append(t)
    if not tweets:
        raise HTTPException(status_code=400, detail="Aucun tweet valide")
    wk = f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    save_checkpoint(username, wk, tweets)
    return {"success": True, "imported": len(tweets), "window_key": wk}


# ── Cache ─────────────────────────────────────────────────────────────────────

@router.delete("/cache")
async def cache_clear(username: str = Query(...)):
    return {"deleted": clear_cache(username)}


# ── Debug ─────────────────────────────────────────────────────────────────────

@router.get("/debug/community/{community_id}")
async def debug_community(community_id: str):
    cid = extract_community_id(community_id)
    if not cid:
        raise HTTPException(status_code=400, detail="ID invalide")
    client = TwitterClient(); client._init("twitter")
    s = make_auth_session() if has_auth() else client._session
    results = {}
    for op, name in [
        ("CommunitiesRankedTimeline", "CommunitiesRankedTimeline"),
        ("CommunitiesTimeline",       "CommunitiesTimeline"),
    ]:
        variables = json.dumps({
            "communityId": cid, "count": 5, "withCommunity": True,
            "includePromotedContent": False, "rankingMode": "Recency",
        })
        try:
            r = try_with_fallbacks(
                s, op, lambda qid, n=name: f"https://x.com/i/api/graphql/{qid}/{n}",
                {"variables": variables, "features": FEATURES_TWEETS}, 20
            )
            if r:
                raw = r.json()
                results[op] = {"http_status": r.status_code,
                               "data_keys": list(raw.get("data", {}).keys()),
                               "raw_truncated": json.dumps(raw, ensure_ascii=False)[:2000]}
            else:
                results[op] = {"error": "pas de réponse"}
        except Exception as e:
            results[op] = {"error": str(e)}
    return {"community_id": cid, "auth_used": has_auth(), "endpoints_tested": results}