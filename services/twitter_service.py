"""
Twitter Service  v7.1
======================
Logique métier pure — aucune dépendance FastAPI.
Contient : TokenPool, QID detection, TwitterClient, cache/checkpoints.
"""

import csv
import hashlib
import io
import json
import logging
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from config import (
    settings, CACHE_DIR, CHECKPOINT_DIR, QID_CACHE_FILE, TWITTER_BEARER
)

log = logging.getLogger("scraper.twitter")

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

BASE_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

QID_FALLBACKS = {
    "UserTweets": ["36rb3Xj3iJ64Q-9wKDjCcQ", "H8OjWhdlk05aShjpugaLZg", "E3opETjZQHKSYcH_bS9hug"],
    "UserByScreenName": ["G3KGOASz96M-Qu0nwmGXNg", "qW5u-DAuXpMEG0zA1F7UGQ", "Ej34j3BFt7LiYl8VB_VLLg"],
    "TweetResultByRestId": ["2Acdg-VztGlHX7MjX67Ysw", "oCon7R-cgWRFy6EfZjaKfg", "nBS-WpgA6ZG3CyFkgVXiRQ"],
    "TweetDetail": ["oCon7R-cgWRFy6EfZjaKfg", "2Acdg-VztGlHX7MjX67Ysw", "nBS-WpgA6ZG3CyFkgVXiRQ", "0hWvDhmW8YQ-S_ib3azIrw"],
    "SearchTimeline": ["Yw6L66Pw54NHKuq4Dp7b4Q", "nK1dw4oV3k4w5TdtcAdSww", "gkjsKepM6gl_HmFWoWKfgg", "lZ3-6O3_FuSChtAEPRfOZA"],
    "CommunitiesFetchOneQuery": ["io5rrN-PO7oNS-ozDHrJyw", "oDtvCBDwsOJFH-6nMFO6tg", "hS7cUMCh2GeP2DRzqRFk0Q"],
    "CommunitiesRankedTimeline": ["dGPLIKm6Fz896eIOXHLcPg"],
    "CommunitiesExploreTimeline": ["FpA1LTcHu3vk4JQjDvp4Tg"],
    "CommunitiesMainDiscoveryModule": ["xm1irSse72yjs3GX_zaUhg"],
    "CommunitiesMembershipsSlice": ["keBi-IFOHQFR59XV8-JCbw"],
    "CommunitiesTimeline": ["lApSvKqRrCFOibjOiGjMtg", "y2tJCE2JyJG5v4oObEgBng"],
    "CommunityQuery": ["oDtvCBDwsOJFH-6nMFO6tg", "hS7cUMCh2GeP2DRzqRFk0Q"],
    "CommunityTweetsRankedLoggedOutTimeline": ["bVBKt-X2qNejkJpl4m5vIQ"],
}

FEATURES_TWEETS = json.dumps({
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_the_sky_enabled": True,
    "standardized_nudges_misinfo": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
})

FEATURES_SEARCH = json.dumps({
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_the_sky_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
    "interactive_text_enabled": True,
    "responsive_web_text_conversations_enabled": False,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
    "responsive_web_twitter_blue_verified_badge_is_enabled": True,
})

FEATURES_TWEET_DETAIL = json.dumps({
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_the_sky_enabled": True,
    "standardized_nudges_misinfo": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    "responsive_web_twitter_article_tweet_consumption_enabled": False,
})


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def extract_community_id(id_or_url: str) -> Optional[str]:
    s = id_or_url.strip().rstrip("/")
    m = re.search(r'communities/(\d{5,25})', s)
    if m:
        return m.group(1)
    if re.match(r'^\d{5,25}$', s):
        return s
    return None


def has_auth() -> bool:
    return bool(settings.auth_token and settings.ct0)


def make_auth_session(username: str = "twitter") -> requests.Session:
    if not has_auth():
        raise RuntimeError(
            "Cookies manquants. Définissez AUTH_TOKEN et CT0 dans .env\n"
            "x.com → F12 → Application → Cookies → .x.com"
        )
    s = requests.Session()
    s.headers.update(BASE_HEADERS)
    s.cookies.set("auth_token", settings.auth_token, domain=".x.com")
    s.cookies.set("ct0",        settings.ct0,        domain=".x.com")
    s.headers.update({
        "Authorization":             f"Bearer {TWITTER_BEARER}",
        "Accept":                    "application/json",
        "Referer":                   f"https://x.com/{username}",
        "x-twitter-active-user":     "yes",
        "x-twitter-client-language": "en",
        "x-csrf-token":              settings.ct0,
    })
    return s


def new_guest_session(username: str = "twitter", timeout: int = 20) -> requests.Session:
    s = requests.Session()
    s.headers.update(BASE_HEADERS)
    try:
        s.get(f"https://x.com/{username}", timeout=timeout,
              headers={"Accept": "text/html,application/xhtml+xml"})
    except Exception:
        pass
    s.headers.update({
        "Authorization":             f"Bearer {TWITTER_BEARER}",
        "Accept":                    "application/json",
        "Referer":                   f"https://x.com/{username}",
        "x-twitter-active-user":     "yes",
        "x-twitter-client-language": "en",
    })
    for attempt in range(5):
        try:
            r = s.post("https://api.x.com/1.1/guest/activate.json", timeout=timeout)
            r.raise_for_status()
            token = r.json().get("guest_token", "")
            if token:
                s.headers["x-guest-token"] = token
                return s
        except Exception as e:
            log.warning(f"Token attempt {attempt+1}/5: {e}")
            time.sleep(settings.backoff_base ** attempt + random.uniform(0, 1))
    raise RuntimeError("Impossible d'obtenir un guest token")


# ══════════════════════════════════════════════════════════════════════════════
# QID DETECTION
# ══════════════════════════════════════════════════════════════════════════════

_qid_lock  = threading.Lock()
_qid_cache : dict[str, str] = {}


def load_qid_cache() -> dict[str, str]:
    try:
        if QID_CACHE_FILE.exists():
            age = datetime.now() - datetime.fromtimestamp(QID_CACHE_FILE.stat().st_mtime)
            if age < timedelta(hours=settings.qid_cache_hours):
                data = json.loads(QID_CACHE_FILE.read_text())
                log.info(f"[QID] Cache disque chargé : {list(data.keys())}")
                return data
    except Exception:
        pass
    return {}


def save_qid_cache(qids: dict[str, str]) -> None:
    try:
        QID_CACHE_FILE.write_text(json.dumps(qids, ensure_ascii=False))
    except Exception:
        pass


def detect_all_qids(session: requests.Session, username: str = "twitter") -> dict[str, str]:
    operations = [
        "UserTweets", "UserByScreenName", "TweetDetail", "TweetResultByRestId",
        "SearchTimeline", "CommunitiesFetchOneQuery", "CommunitiesRankedTimeline",
        "CommunitiesExploreTimeline", "CommunitiesMainDiscoveryModule",
        "CommunitiesMembershipsSlice", "CommunitiesTimeline", "UserTweetsAndReplies", "Likes",
    ]
    patterns = [
        r'"queryId"\s*:\s*"([A-Za-z0-9_-]{15,})"[^}]{0,120}"operationName"\s*:\s*"({op})"',
        r'"operationName"\s*:\s*"({op})"[^}]{0,120}"queryId"\s*:\s*"([A-Za-z0-9_-]{15,})"',
        r'queryId:"([A-Za-z0-9_-]{15,})",operationName:"({op})"',
        r'operationName:"({op})",queryId:"([A-Za-z0-9_-]{15,})"',
        r'id:\s*"([A-Za-z0-9_-]{15,})"[^}]{0,80}name:\s*"({op})"',
        r'name:\s*"({op})"[^}]{0,80}id:\s*"([A-Za-z0-9_-]{15,})"',
        r'"({op})"\s*,\s*"([A-Za-z0-9_-]{20,})"',
    ]
    found: dict[str, str] = {}
    try:
        r = session.get(f"https://x.com/{username}", timeout=20,
                        headers={"Accept": "text/html,application/xhtml+xml"})
        js_urls  = re.findall(r'src="(https://abs\.twimg\.com/responsive-web/client-web/[^"]+\.js)"', r.text)
        main_urls  = [u for u in js_urls if "main" in u]
        other_urls = [u for u in js_urls if "main" not in u]
        for js_url in (main_urls + other_urls)[:20]:
            if len(found) == len(operations): break
            try:
                js = session.get(js_url, timeout=20).text
                for op in operations:
                    if op in found: continue
                    for pat_tpl in patterns:
                        pat = pat_tpl.replace("{op}", re.escape(op))
                        m   = re.search(pat, js)
                        if m:
                            candidates = [g for g in m.groups() if re.match(r'^[A-Za-z0-9_-]{15,}$', g or "")]
                            if candidates:
                                found[op] = candidates[0]
                                log.info(f"[QID] {op} → {candidates[0]}")
                                break
            except Exception:
                continue
    except Exception as e:
        log.warning(f"[QID] Détection JS échouée: {e}")
    for op, fallback_list in QID_FALLBACKS.items():
        if op not in found:
            found[op] = fallback_list[0]
    return found


def get_qid(op: str, session: Optional[requests.Session] = None) -> str:
    with _qid_lock:
        global _qid_cache
        if op in _qid_cache:
            return _qid_cache[op]
        if not _qid_cache:
            _qid_cache = load_qid_cache()
            if op in _qid_cache:
                return _qid_cache[op]
        if session:
            detected = detect_all_qids(session)
            _qid_cache.update(detected)
            save_qid_cache(_qid_cache)
            if op in _qid_cache:
                return _qid_cache[op]
        fallbacks = QID_FALLBACKS.get(op, [])
        if fallbacks:
            qid = fallbacks[0]
            _qid_cache[op] = qid
            return qid
        raise RuntimeError(f"QID introuvable pour {op}")


def refresh_qid(op: str, session: requests.Session) -> str:
    with _qid_lock:
        global _qid_cache
        detected = detect_all_qids(session)
        _qid_cache.update(detected)
        save_qid_cache(_qid_cache)
        return _qid_cache.get(op, QID_FALLBACKS.get(op, [""])[0])


def try_with_fallbacks(session, op, url_builder, params, timeout=20) -> Optional[requests.Response]:
    tried: set[str] = set()
    try:
        qid = get_qid(op, session)
        if qid not in tried:
            tried.add(qid)
            r = session.get(url_builder(qid), params=params, timeout=timeout)
            if r.status_code == 200:
                return r
    except Exception:
        pass
    for qid in QID_FALLBACKS.get(op, []):
        if qid in tried: continue
        tried.add(qid)
        try:
            r = session.get(url_builder(qid), params=params, timeout=timeout)
            if r.status_code == 200:
                with _qid_lock:
                    _qid_cache[op] = qid
                    save_qid_cache(_qid_cache)
                return r
        except Exception:
            continue
    try:
        qid = refresh_qid(op, session)
        if qid not in tried:
            r = session.get(url_builder(qid), params=params, timeout=timeout)
            if r.status_code == 200:
                return r
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# TOKEN POOL
# ══════════════════════════════════════════════════════════════════════════════

class TokenPool:
    def __init__(self, size: int = 6):
        self._size     = size
        self._sessions : list[requests.Session] = []
        self._lock     = threading.Lock()
        self._idx      = 0
        self._total    = 0
        self._cooldown : dict[int, float] = {}

    def _make_session(self, username: str = "twitter") -> requests.Session:
        s = new_guest_session(username)
        self._total += 1
        return s

    def init(self, username: str, size: Optional[int] = None) -> None:
        n = size or self._size
        def _make(u):
            try: return self._make_session(u)
            except: return None
        with ThreadPoolExecutor(max_workers=min(n, 4)) as ex:
            results = list(ex.map(_make, [username] * n))
        self._sessions = [s for s in results if s is not None]
        log.info(f"[pool] {len(self._sessions)}/{n} tokens actifs")
        if self._sessions:
            get_qid("TweetResultByRestId", self._sessions[0])

    def get(self) -> requests.Session:
        with self._lock:
            if not self._sessions: raise RuntimeError("Pool vide")
            now = time.time()
            for _ in range(len(self._sessions)):
                idx = self._idx % len(self._sessions)
                self._idx += 1
                if now >= self._cooldown.get(idx, 0):
                    return self._sessions[idx]
            next_up = min(self._cooldown.values())
            time.sleep(max(0, next_up - now) + 0.1)
            return self._sessions[0]

    def mark_429(self, session: requests.Session, wait: float = 30.0) -> None:
        with self._lock:
            try:
                idx = self._sessions.index(session)
                self._cooldown[idx] = time.time() + wait
            except ValueError:
                pass

    def replace(self, session: requests.Session, username: str) -> requests.Session:
        with self._lock:
            try:
                idx = self._sessions.index(session)
                try:
                    self._sessions[idx] = self._make_session(username)
                    self._cooldown.pop(idx, None)
                    return self._sessions[idx]
                except Exception:
                    return session
            except ValueError:
                return session

    @property
    def total_used(self) -> int:
        return self._total


# ══════════════════════════════════════════════════════════════════════════════
# CACHE & CHECKPOINTS
# ══════════════════════════════════════════════════════════════════════════════

def cache_path(username: str, max_tweets: int) -> Path:
    key = hashlib.md5(f"{username}_{max_tweets}".encode()).hexdigest()
    return CACHE_DIR / f"{username}_{key}.json"

def load_cache(username: str, max_tweets: int = 0) -> Optional[dict]:
    path = cache_path(username, max_tweets)
    if not path.exists(): return None
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    if age > timedelta(hours=settings.cache_ttl_hours): return None
    return json.loads(path.read_text(encoding="utf-8"))

def save_cache(username: str, max_tweets: int, data: dict) -> None:
    cache_path(username, max_tweets).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")

def clear_cache(username: str) -> int:
    deleted = 0
    for f in CACHE_DIR.glob(f"{username}_*.json"):
        f.unlink(); deleted += 1
    return deleted

def checkpoint_path(username: str, window_key: str) -> Path:
    return CHECKPOINT_DIR / f"{username}_{window_key}.json"

def load_checkpoint(username: str, window_key: str) -> Optional[list]:
    path = checkpoint_path(username, window_key)
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding="utf-8"))
    except: return None

def save_checkpoint(username: str, window_key: str, tweets: list) -> None:
    checkpoint_path(username, window_key).write_text(
        json.dumps(tweets, ensure_ascii=False), encoding="utf-8")

def list_checkpoints(username: str) -> list[str]:
    return sorted(p.stem.replace(f"{username}_", "")
                  for p in CHECKPOINT_DIR.glob(f"{username}_*.json"))

def load_all_checkpoints(username: str) -> list[dict]:
    all_tweets: list[dict] = []
    seen: set[str] = set()
    for wk in list_checkpoints(username):
        for t in (load_checkpoint(username, wk) or []):
            if t.get("id") and t["id"] not in seen:
                seen.add(t["id"]); all_tweets.append(t)
    all_tweets.sort(key=lambda t: t.get("date", ""), reverse=True)
    return all_tweets

def generate_windows(created_year: int) -> list[tuple[str, str, str]]:
    windows = []
    today_str    = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().year
    for year in range(created_year, current_year + 1):
        if year >= 2019:
            for since, until in [
                (f"{year}-01-01", f"{year}-07-01"),
                (f"{year}-07-01", f"{year+1}-01-01" if year < current_year else today_str),
            ]:
                if since >= today_str: break
                windows.append((f"{since[:7]}_to_{until[:7]}", since, until))
        else:
            windows.append((f"{year}", f"{year}-01-01", f"{year+1}-01-01"))
    return windows


# ══════════════════════════════════════════════════════════════════════════════
# TWITTER CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class TwitterClient:

    def __init__(self, timeout: int = 20):
        self.timeout     = timeout
        self._pool       = TokenPool(settings.token_pool_size)
        self._search_qid = ""
        self._username   = ""
        self._session    = requests.Session()

    def _init(self, username: str) -> None:
        self._username = username
        self._pool.init(username)
        self._session = self._pool.get()
        try:
            self._search_qid = get_qid("SearchTimeline", self._session)
        except Exception as e:
            log.error(f"SearchTimeline QID: {e}")

    def _get(self, url: str, params: dict,
             session: Optional[requests.Session] = None) -> Optional[requests.Response]:
        sess    = session or self._pool.get()
        backoff = settings.backoff_base
        for attempt in range(settings.max_retries):
            try:
                r = sess.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    wait = backoff ** attempt * 10 + random.uniform(2, 5)
                    self._pool.mark_429(sess, wait)
                    time.sleep(min(wait, 30))
                    sess = self._pool.get()
                    continue
                if r.status_code in (401, 403):
                    sess = self._pool.replace(sess, self._username)
                    time.sleep(settings.rotate_delay)
                    continue
                if r.status_code == 404: return None
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(backoff ** attempt * 3); continue
                r.raise_for_status()
                return r
            except requests.exceptions.Timeout:
                time.sleep(backoff ** attempt * 2)
            except Exception as e:
                log.error(f"GET error: {e}"); break
        return None

    # ── Profile ───────────────────────────────────────────────────────────────

    def get_profile(self, username: str) -> tuple[dict, str, int]:
        self._init(username)
        variables = json.dumps({
            "screen_name": username,
            "withSafetyModeUserFields": True,
            "withSuperFollowsUserFields": True,
        })
        features = json.dumps({
            "hidden_profile_likes_enabled": False,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
        })
        r = try_with_fallbacks(
            self._session, "UserByScreenName",
            lambda qid: f"https://x.com/i/api/graphql/{qid}/UserByScreenName",
            {"variables": variables, "features": features}, self.timeout
        )
        if r is None: raise RuntimeError(f"Profil @{username} inaccessible")
        result = r.json().get("data", {}).get("user", {}).get("result", {})
        if not result: raise ValueError(f"Profil introuvable: @{username}")
        legacy  = result.get("legacy", {})
        user_id = result.get("rest_id") or legacy.get("id_str", "")
        try:
            created_year = datetime.strptime(legacy.get("created_at", ""), "%a %b %d %H:%M:%S +0000 %Y").year
        except Exception:
            created_year = 2006
        urls    = legacy.get("entities", {}).get("url", {}).get("urls", [])
        website = urls[0].get("expanded_url", "N/A") if urls else "N/A"
        profile = {
            "username": username, "user_id": user_id,
            "name": legacy.get("name", "N/A"), "bio": legacy.get("description", "N/A"),
            "location": legacy.get("location", "N/A"), "website": website,
            "avatar_url": legacy.get("profile_image_url_https", "N/A"),
            "banner_url": legacy.get("profile_banner_url", "N/A"),
            "verified": legacy.get("verified", False),
            "blue_verified": result.get("is_blue_verified", False),
            "followers_count": legacy.get("followers_count", 0),
            "following_count": legacy.get("friends_count", 0),
            "tweet_count": legacy.get("statuses_count", 0),
            "likes_count": legacy.get("favourites_count", 0),
            "media_count": legacy.get("media_count", 0),
            "listed_count": legacy.get("listed_count", 0),
            "created_at": legacy.get("created_at", ""),
            "created_year": created_year,
            "withheld_in": legacy.get("withheld_in_countries", []),
            "profile_url": f"https://twitter.com/{username}",
        }
        log.info(f"✅ @{username} | créé {created_year} | {profile['tweet_count']:,} tweets")
        return profile, user_id, created_year

    # ── Tweet Detail ──────────────────────────────────────────────────────────

    def get_tweet_detail(self, tweet_id: str) -> dict:
        if not re.match(r"^\d{5,25}$", tweet_id):
            return {"error": f"ID tweet invalide : '{tweet_id}'"}
        variables = json.dumps({
            "tweetId": tweet_id, "withCommunity": True,
            "includePromotedContent": False, "withVoice": True,
        })
        r = try_with_fallbacks(
            self._session, "TweetResultByRestId",
            lambda qid: f"https://x.com/i/api/graphql/{qid}/TweetResultByRestId",
            {"variables": variables, "features": FEATURES_TWEET_DETAIL}, self.timeout
        )
        if r is None: return {"error": f"Tweet {tweet_id} inaccessible"}
        try: data = r.json()
        except Exception: return {"error": "Réponse non-JSON"}
        result = data.get("data", {}).get("tweetResult", {}).get("result", {})
        if not result: return {"error": f"Tweet {tweet_id} non trouvé"}
        tweet = self._build_tweet(result, "")
        if not tweet: return {"error": "Parse du tweet échoué"}
        return {"tweet": tweet, "thread": [], "replies": [], "reply_count": 0}

    # ── Transcript ────────────────────────────────────────────────────────────

    def get_transcript(self, tweet_id: str) -> dict:
        detail = self.get_tweet_detail(tweet_id)
        if "error" in detail: return detail
        main   = detail["tweet"]
        author = main["url"].split("/")[3]
        parts  = sorted([main] + [t for t in detail["thread"]
                        if t["url"].split("/")[3].lower() == author.lower()],
                        key=lambda x: x.get("date", ""))
        return {
            "tweet_id": tweet_id, "author": author,
            "thread_len": len(parts),
            "transcript": "\n\n".join(f"[{i+1}/{len(parts)}] {t['text']}" for i, t in enumerate(parts)),
            "parts": parts,
            "total_likes": sum(t.get("likes", 0) for t in parts),
            "total_rt":    sum(t.get("retweets", 0) for t in parts),
        }

    # ── Community ─────────────────────────────────────────────────────────────

    def get_community(self, community_id: str) -> dict:
        cid = extract_community_id(community_id)
        if not cid: return {"error": f"ID ou URL invalide : '{community_id}'"}
        sess = make_auth_session() if has_auth() else self._session
        variables = json.dumps({"communityId": cid, "withDmMuting": False, "withSafetyModeUserFields": True})
        r = try_with_fallbacks(
            sess, "CommunitiesFetchOneQuery",
            lambda qid: f"https://x.com/i/api/graphql/{qid}/CommunitiesFetchOneQuery",
            {"variables": variables}, self.timeout
        )
        if r:
            try:
                data   = r.json()
                result = (
                    data.get("data", {}).get("communityResults", {}).get("result", {})
                    or data.get("data", {}).get("community_results_by_rest_id", {}).get("result", {})
                )
                if result and result.get("name"):
                    return self._build_community(cid, result)
            except Exception as e:
                log.warning(f"[Community] FetchOne parse échoué: {e}")
        return {"error": f"Community {cid} inaccessible. " + ("" if has_auth() else "Ajoutez AUTH_TOKEN + CT0 dans .env")}

    def _build_community(self, community_id: str, result: dict) -> dict:
        admin_name = "N/A"
        try:
            admin_name = result.get("admin_results", {}).get("result", {}).get("legacy", {}).get("screen_name", "N/A")
        except Exception:
            pass
        return {
            "id": community_id, "name": result.get("name", "N/A"),
            "description": result.get("description", "N/A"),
            "member_count": result.get("member_count", 0),
            "moderator_count": result.get("moderator_count", 0),
            "created_at": result.get("created_at", "N/A"),
            "rules": [r_.get("name", "") for r_ in result.get("rules", [])],
            "is_nsfw": result.get("is_nsfw", False),
            "role": result.get("role", "NonMember"),
            "admin": admin_name, "auth_used": has_auth(),
            "url": f"https://x.com/i/communities/{community_id}",
        }

    def get_community_tweets(self, community_id: str, max_tweets: int = 100) -> dict:
        cid = extract_community_id(community_id)
        if not cid: return {"error": f"ID ou URL invalide : '{community_id}'"}
        sess   = make_auth_session() if has_auth() else self._session
        tweets : list[dict] = []
        seen   : set[str]   = set()
        endpoints = [
            ("CommunityTweetsRankedLoggedOutTimeline", "CommunityTweetsRankedLoggedOutTimeline"),
            ("CommunitiesRankedTimeline", "CommunitiesRankedTimeline"),
            ("CommunitiesTimeline",       "CommunitiesTimeline"),
        ]
        working_op = working_name = cursor = None
        for op, name in endpoints:
            variables = json.dumps({
                "communityId": cid, "count": 20, "withCommunity": True,
                "includePromotedContent": False, "rankingMode": "Recency",
            })
            r = try_with_fallbacks(
                sess, op,
                lambda qid, n=name: f"https://x.com/i/api/graphql/{qid}/{n}",
                {"variables": variables, "features": FEATURES_TWEETS}, self.timeout
            )
            if r is None: continue
            try:
                instructions = self._extract_community_instructions(r.json())
                if instructions is None: continue
                batch, next_cursor = self._parse_community_instructions(instructions, cursor)
                for t in batch:
                    if t.get("id") and t["id"] not in seen:
                        seen.add(t["id"]); tweets.append(t)
                working_op = op; working_name = name; cursor = next_cursor
                break
            except Exception as e:
                log.warning(f"[CommunityTweets] {op} échoué: {e}")
        if not working_op:
            return {"community_id": cid, "count": 0, "auth_used": has_auth(),
                    "tweets": [], "error": "Aucun endpoint fonctionnel"}
        page = 1
        consecutive_empty = 0
        while cursor and len(tweets) < max_tweets and page < 50:
            page += 1
            variables = json.dumps({
                "communityId": cid, "count": 20, "cursor": cursor,
                "withCommunity": True, "includePromotedContent": False, "rankingMode": "Recency",
            })
            r = try_with_fallbacks(
                sess, working_op,
                lambda qid, n=working_name: f"https://x.com/i/api/graphql/{qid}/{n}",
                {"variables": variables, "features": FEATURES_TWEETS}, self.timeout
            )
            if r is None: break
            try:
                instructions = self._extract_community_instructions(r.json())
                if not instructions: break
                batch, next_cursor = self._parse_community_instructions(instructions, cursor)
                new_here = 0
                for t in batch:
                    if t.get("id") and t["id"] not in seen:
                        seen.add(t["id"]); tweets.append(t); new_here += 1
                if new_here == 0:
                    consecutive_empty += 1
                    if consecutive_empty >= 2: break
                else:
                    consecutive_empty = 0
                if not next_cursor or next_cursor == cursor: break
                cursor = next_cursor
            except Exception as e:
                log.warning(f"[CommunityTweets] Page {page}: {e}"); break
            time.sleep(settings.page_delay)
        return {"community_id": cid, "count": len(tweets), "auth_used": has_auth(),
                "endpoint_used": working_op, "tweets": tweets[:max_tweets]}

    def _extract_community_instructions(self, data: dict) -> Optional[list]:
        d = data.get("data", {})
        paths = [
            lambda: d["communityResults"]["result"]["ranked_community_timeline"]["timeline"]["instructions"],
            lambda: d["community_timeline"]["timeline"]["instructions"],
            lambda: d["communityResults"]["result"]["timeline"]["timeline"]["instructions"],
            lambda: d["communityResults"]["result"]["timeline"]["instructions"],
        ]
        for fn in paths:
            try:
                result = fn()
                if result: return result
            except (KeyError, TypeError):
                continue
        return None

    def _parse_community_instructions(self, instructions: list,
                                      current_cursor: Optional[str]) -> tuple[list[dict], Optional[str]]:
        tweets: list[dict] = []
        next_cursor: Optional[str] = None
        for inst in instructions:
            if inst.get("type") == "TimelineTerminateTimeline": continue
            for entry in inst.get("entries", []):
                eid     = entry.get("entryId", "")
                content = entry.get("content", {})
                is_cursor = (
                    "cursor" in eid.lower()
                    or "Cursor" in (content.get("entryType", "") or content.get("__typename", ""))
                    or content.get("cursorType")
                )
                if is_cursor:
                    cursor_type = content.get("cursorType") or content.get("itemContent", {}).get("cursorType", "")
                    if cursor_type == "Bottom" or (not next_cursor and cursor_type != "Top"):
                        val = content.get("value") or content.get("itemContent", {}).get("value")
                        if val and val != current_cursor:
                            next_cursor = val
                    continue
                t = self._parse_entry(entry, "")
                if t: tweets.append(t); continue
                for item in (content.get("items", []) or content.get("moduleItems", [])):
                    t = self._parse_item(item, "")
                    if t: tweets.append(t)
        return tweets, next_cursor

    # ── Pipeline A ────────────────────────────────────────────────────────────

    def pipeline_a(self, user_id: str) -> list[dict]:
        log.info("━━ Pipeline A : UserTweets ━━")
        tweets = []; cursor = None; page = 0
        empty_streak = 0; last_cursor = None; same_streak = 0
        while True:
            if page > 0 and page % settings.rotate_every == 0:
                time.sleep(settings.rotate_delay)
            batch, next_cursor = self._fetch_user_tweets_page(user_id, cursor)
            page += 1
            if not batch:
                empty_streak += 1
                if empty_streak >= settings.max_empty_pages: break
                time.sleep(1.0); continue
            empty_streak = 0
            tweets.extend(batch)
            if not next_cursor: break
            if next_cursor == last_cursor:
                same_streak += 1
                if same_streak >= 3: break
            else: same_streak = 0
            last_cursor = next_cursor; cursor = next_cursor
            time.sleep(settings.page_delay)
        log.info(f"[A] {len(tweets)} tweets")
        return tweets

    def _fetch_user_tweets_page(self, user_id: str,
                                cursor: Optional[str]) -> tuple[list[dict], Optional[str]]:
        variables: dict = {
            "userId": user_id, "count": 100,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": False,
            "withVoice": True, "withV2Timeline": True,
        }
        if cursor: variables["cursor"] = cursor
        r = try_with_fallbacks(
            self._session, "UserTweets",
            lambda qid: f"https://x.com/i/api/graphql/{qid}/UserTweets",
            {"variables": json.dumps(variables), "features": FEATURES_TWEETS}, self.timeout
        )
        if r is None: return [], None
        instructions = (
            r.json().get("data", {}).get("user", {}).get("result", {})
                    .get("timeline", {}).get("timeline", {}).get("instructions", [])
        )
        return self._parse_instructions(instructions, cursor, self._username)

    # ── Pipeline C ────────────────────────────────────────────────────────────

    def pipeline_c(self, username: str, created_year: int, progress_callback=None) -> list[dict]:
        if not self._search_qid: return []
        log.info(f"━━ Pipeline C : fenêtres depuis {created_year} ━━")
        windows  = generate_windows(created_year)
        done_cks = set(list_checkpoints(username))
        pending  = [(wk, si, un) for wk, si, un in windows if wk not in done_cks]
        all_tweets: list[dict] = []
        seen: set[str] = set()
        for wk in done_cks:
            for t in (load_checkpoint(username, wk) or []):
                if t.get("id") and t["id"] not in seen:
                    seen.add(t["id"]); all_tweets.append(t)
        done_count = len(done_cks); total = len(windows)
        lock = threading.Lock()
        def scrape_one(args):
            wk, since, until = args
            result = self._scrape_window(username, since, until)
            save_checkpoint(username, wk, result)
            return wk, result
        with ThreadPoolExecutor(max_workers=settings.parallel_windows) as ex:
            futures = {ex.submit(scrape_one, w): w for w in pending}
            for fut in as_completed(futures):
                try:
                    wk, window_tweets = fut.result()
                    with lock:
                        done_count += 1
                        new_here = []
                        for t in window_tweets:
                            if t.get("id") and t["id"] not in seen:
                                seen.add(t["id"]); all_tweets.append(t); new_here.append(t)
                        if progress_callback:
                            progress_callback(done_count, total, wk, len(all_tweets))
                except Exception as e:
                    log.warning(f"[C] Fenêtre échouée: {e}")
        all_tweets.sort(key=lambda t: t.get("date", ""), reverse=True)
        return all_tweets

    def _scrape_window(self, username: str, since: str, until: str) -> list[dict]:
        query = f"from:{username} since:{since} until:{until}"
        tweets = []; cursor = None; empty_streak = 0; last_cursor = None; same_streak = 0; page = 0
        try: sess = new_guest_session(username, self.timeout)
        except Exception as e:
            log.warning(f"[C] Session échouée: {e}"); return []
        while True:
            if page > 0 and page % settings.rotate_every == 0:
                try: sess = new_guest_session(username, self.timeout)
                except Exception: pass
                time.sleep(settings.rotate_delay)
            batch, next_cursor = self._fetch_search_page(sess, username, query, cursor)
            page += 1
            if not batch:
                empty_streak += 1
                if empty_streak >= settings.max_empty_pages: break
                try: sess = new_guest_session(username, self.timeout)
                except Exception: pass
                time.sleep(1.0); continue
            empty_streak = 0; tweets.extend(batch)
            if not next_cursor: break
            if next_cursor == last_cursor:
                same_streak += 1
                if same_streak >= 3: break
            else: same_streak = 0
            last_cursor = next_cursor; cursor = next_cursor
            time.sleep(settings.page_delay)
        return tweets

    def _fetch_search_page(self, session, username, query, cursor) -> tuple[list[dict], Optional[str]]:
        variables: dict = {
            "rawQuery": query, "count": settings.max_per_page,
            "querySource": "typed_query", "product": "Latest",
            "includePromotedContent": False,
        }
        if cursor: variables["cursor"] = cursor
        params  = {"variables": json.dumps(variables), "features": FEATURES_SEARCH}
        backoff = settings.backoff_base
        r       = None
        for attempt in range(settings.max_retries):
            try:
                qid = get_qid("SearchTimeline")
                r   = session.get(
                    f"https://twitter.com/i/api/graphql/{qid}/SearchTimeline",
                    params=params, timeout=self.timeout)
                if r.status_code == 429:
                    time.sleep(min(backoff ** attempt * 8 + random.uniform(2, 5), 60)); continue
                if r.status_code == 404:
                    refresh_qid("SearchTimeline", session); continue
                if r.status_code in (401, 403, 500, 502, 503):
                    time.sleep(backoff ** attempt * 3); continue
                r.raise_for_status(); break
            except Exception as e:
                log.warning(f"[C] fetch: {e}"); time.sleep(backoff ** attempt * 2)
        else: return [], None
        try: data = r.json()
        except Exception: return [], None
        instructions = (
            data.get("data", {}).get("search_by_raw_query", {})
                .get("search_timeline", {}).get("timeline", {}).get("instructions", [])
        )
        return self._parse_instructions(instructions, cursor, username)

    def get_tweets_full(self, user_id: str, username: str, created_year: int,
                        progress_callback=None) -> list[dict]:
        tweets_a = self.pipeline_a(user_id)
        seen     = {t["id"] for t in tweets_a if t.get("id")}
        tweets_c = self.pipeline_c(username, created_year, progress_callback)
        all_tweets = list(tweets_a)
        for t in tweets_c:
            if t.get("id") and t["id"] not in seen:
                seen.add(t["id"]); all_tweets.append(t)
        all_tweets.sort(key=lambda t: t.get("date", ""), reverse=True)
        return all_tweets

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_instructions(self, instructions: list, current_cursor: Optional[str],
                            username: str) -> tuple[list[dict], Optional[str]]:
        tweets: list[dict] = []; next_cursor: Optional[str] = None
        for inst in instructions:
            for entry in inst.get("entries", []):
                eid     = entry.get("entryId", "")
                content = entry.get("content", {})
                if "cursor-bottom" in eid or "cursor-showMoreThreads" in eid:
                    val = content.get("value") or content.get("itemContent", {}).get("value")
                    if val and val != current_cursor: next_cursor = val
                    continue
                if content.get("entryType") == "TimelineTimelineCursor":
                    if content.get("cursorType") == "Bottom":
                        val = content.get("value")
                        if val and val != current_cursor: next_cursor = val
                    continue
                item_content = content.get("itemContent", {})
                if item_content.get("itemType") == "TimelineTimelineCursor":
                    if item_content.get("cursorType") == "Bottom":
                        val = item_content.get("value")
                        if val and val != current_cursor: next_cursor = val
                    continue
                t = self._parse_entry(entry, username)
                if t: tweets.append(t); continue
                for item in (content.get("items", []) or content.get("moduleItems", [])):
                    t = self._parse_item(item, username)
                    if t: tweets.append(t)
        return tweets, next_cursor

    def _parse_entry(self, entry: dict, username: str) -> Optional[dict]:
        try:
            result = entry["content"]["itemContent"]["tweet_results"]["result"]
            return self._build_tweet(result, username)
        except (KeyError, TypeError): return None

    def _parse_item(self, item: dict, username: str) -> Optional[dict]:
        try:
            result = (
                item.get("item", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                or item.get("itemContent", {}).get("tweet_results", {}).get("result", {})
            )
            return self._build_tweet(result, username) if result else None
        except (KeyError, TypeError): return None

    def _build_tweet(self, result: dict, username: str) -> Optional[dict]:
        try:
            if result.get("__typename") in ("TweetTombstone", "TweetUnavailable"): return None
            if "tweet" in result: result = result["tweet"]
            legacy = result.get("legacy", {})
            text   = legacy.get("full_text") or legacy.get("text", "")
            if not text: return None
            author = (
                result.get("core", {}).get("user_results", {})
                      .get("result", {}).get("legacy", {}).get("screen_name", username)
            )
            tid = legacy.get("id_str", "")
            media_items = [
                {"type": m.get("type", ""), "url": m.get("media_url_https", ""), "alt": m.get("ext_alt_text", "")}
                for m in legacy.get("entities", {}).get("media", [])
            ]
            return {
                "id": tid, "text": text, "date": legacy.get("created_at", "N/A"),
                "likes": legacy.get("favorite_count", 0), "retweets": legacy.get("retweet_count", 0),
                "replies": legacy.get("reply_count", 0), "quotes": legacy.get("quote_count", 0),
                "views": int(result.get("views", {}).get("count", 0) or 0),
                "bookmarks": legacy.get("bookmark_count", 0),
                "is_rt": text.startswith("RT @"), "has_media": bool(media_items), "media": media_items,
                "urls": [u.get("expanded_url", "") for u in legacy.get("entities", {}).get("urls", [])],
                "lang": legacy.get("lang", ""), "reply_to": legacy.get("in_reply_to_screen_name", None),
                "reply_to_id": legacy.get("in_reply_to_status_id_str", None),
                "quoted_id": legacy.get("quoted_status_id_str", None),
                "author": author, "url": f"https://twitter.com/{author}/status/{tid}",
            }
        except (KeyError, TypeError, ValueError): return None


# ══════════════════════════════════════════════════════════════════════════════
# QUICK SCRAPE (utilisé par les endpoints simples)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_quick(username: str, max_tweets: int = 0) -> tuple[dict, int]:
    cached = load_cache(username, max_tweets)
    if cached: return cached, cached.get("_tokens_used", 0)
    client  = TwitterClient()
    profile, user_id, created_year = client.get_profile(username)
    existing = load_all_checkpoints(username)
    tweets   = existing if existing else client.pipeline_a(user_id)
    data = {"profile": profile, "tweets": tweets,
            "_tokens_used": client._pool.total_used, "_created_year": created_year}
    save_cache(username, max_tweets, data)
    return data, client._pool.total_used


_running_jobs: dict[str, dict] = {}

def run_full_scrape_background(username: str) -> None:
    job = _running_jobs.setdefault(username, {
        "status": "running", "progress": 0, "total_windows": 0,
        "current_window": "", "tweets_found": 0,
        "started_at": datetime.now().isoformat(),
    })
    def cb(idx, total, wk, found):
        job["progress"] = idx; job["total_windows"] = total
        job["current_window"] = wk; job["tweets_found"] = found
    try:
        client  = TwitterClient()
        profile, user_id, created_year = client.get_profile(username)
        job["total_windows"] = len(generate_windows(created_year))
        tweets = client.get_tweets_full(user_id, username, created_year, cb)
        data   = {"profile": profile, "tweets": tweets,
                  "_tokens_used": client._pool.total_used, "_created_year": created_year}
        save_cache(username, 0, data)
        job.update({"status": "done", "tweets_found": len(tweets),
                    "finished_at": datetime.now().isoformat()})
    except Exception as e:
        job.update({"status": "error", "error": str(e)})
        log.exception(f"[bg] Erreur @{username}")