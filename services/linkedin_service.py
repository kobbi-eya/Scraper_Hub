# """
# LinkedIn Service  v0.3
# ======================
# Endpoints disponibles :
#   - search_jobs()          : recherche d'offres (mode invite)
#   - search_jobs_advanced() : recherche avec filtres avances (type contrat, niveau, secteur)
#   - get_job()              : detail d'une offre
#   - get_company()          : profil d'une entreprise
#   - top_companies()        : top entreprises qui recrutent par secteur
# """

# import json
# import logging
# import re
# import time
# from typing import Optional

# import requests

# log = logging.getLogger("service.linkedin")


# class LinkedInUnavailable(Exception):
#     """Ressource LinkedIn introuvable, supprimee, ou bloquee (anti-bot)."""


# # ══════════════════════════════════════════════════════════════════════════════
# # SESSION HTTP
# # ══════════════════════════════════════════════════════════════════════════════

# _BASE = "https://www.linkedin.com"

# _HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/124.0.0.0 Safari/537.36"
#     ),
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#     "Accept-Language": "en-US,en;q=0.9",
#     "X-Requested-With": "XMLHttpRequest",
# }


# def _get(url: str, params: dict | None = None, timeout: int = 20) -> requests.Response:
#     try:
#         r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
#     except requests.RequestException as e:
#         raise LinkedInUnavailable(f"Erreur reseau LinkedIn : {e}")
#     if r.status_code == 429:
#         raise LinkedInUnavailable("LinkedIn rate limit (429). Reessayez plus tard / via proxy.")
#     if r.status_code in (403, 999):
#         raise LinkedInUnavailable(f"LinkedIn a bloque la requete (HTTP {r.status_code}).")
#     if r.status_code == 404:
#         raise LinkedInUnavailable("Ressource LinkedIn introuvable (404).")
#     if r.status_code != 200:
#         raise LinkedInUnavailable(f"Reponse LinkedIn inattendue (HTTP {r.status_code}).")
#     return r


# # ══════════════════════════════════════════════════════════════════════════════
# # HELPERS
# # ══════════════════════════════════════════════════════════════════════════════

# def _clean(text: Optional[str]) -> Optional[str]:
#     if not text:
#         return None
#     text = re.sub(r"<[^>]+>", " ", text)
#     text = text.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
#     text = re.sub(r"\s+", " ", text).strip()
#     return text or None


# def _attr(block: str, attr: str) -> Optional[str]:
#     m = re.search(rf'{attr}="([^"]+)"', block)
#     return m.group(1) if m else None


# def _between(block: str, pattern_open: str, pattern_close: str) -> Optional[str]:
#     m = re.search(pattern_open + r"(.*?)" + pattern_close, block, re.DOTALL)
#     return m.group(1) if m else None


# def _job_id_from_urn(urn: Optional[str]) -> Optional[str]:
#     if not urn:
#         return None
#     m = re.search(r"(\d{6,})", urn)
#     return m.group(1) if m else None


# def _extract_jsonld(html: str, type_: str = "JobPosting") -> Optional[dict]:
#     for m in re.finditer(
#         r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
#     ):
#         try:
#             data = json.loads(m.group(1))
#         except json.JSONDecodeError:
#             continue
#         items = data if isinstance(data, list) else [data]
#         for it in items:
#             if isinstance(it, dict) and it.get("@type") == type_:
#                 return it
#     return None


# # ══════════════════════════════════════════════════════════════════════════════
# # FILTRES AVANCES — mapping LinkedIn
# # ══════════════════════════════════════════════════════════════════════════════

# # Type de contrat  f_JT
# _TYPE_CONTRAT = {
#     "fulltime":   "F",
#     "parttime":   "P",
#     "contract":   "C",
#     "temporary":  "T",
#     "internship": "I",
#     "volunteer":  "V",
#     "other":      "O",
# }

# # Niveau d'experience  f_E
# _NIVEAU = {
#     "internship":   "1",
#     "entry":        "2",
#     "associate":    "3",
#     "mid-senior":   "4",
#     "director":     "5",
#     "executive":    "6",
# }

# # Mode de travail  f_WT
# _REMOTE = {
#     "onsite":  "1",
#     "remote":  "2",
#     "hybrid":  "3",
# }

# # Secteurs LinkedIn (industry codes) — principaux
# _SECTEURS = {
#     "technology":       "96",
#     "finance":          "43",
#     "healthcare":       "14",
#     "education":        "69",
#     "retail":           "27",
#     "manufacturing":    "25",
#     "consulting":       "104",
#     "media":            "3",
#     "automotive":       "23",
#     "construction":     "48",
#     "hospitality":      "31",
#     "legal":            "9",
#     "marketing":        "80",
#     "real-estate":      "44",
#     "transportation":   "71",
# }


# # ══════════════════════════════════════════════════════════════════════════════
# # PARSING CARTE JOB
# # ══════════════════════════════════════════════════════════════════════════════

# def _parse_job_card(li_html: str) -> Optional[dict]:
#     urn = _attr(li_html, "data-entity-urn") or _attr(li_html, "data-job-id")
#     job_id = _job_id_from_urn(urn)

#     titre      = _clean(_between(li_html, r'class="[^"]*base-search-card__title[^"]*"[^>]*>',    r"</h3>"))
#     entreprise = _clean(_between(li_html, r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>', r"</h4>"))
#     lieu       = _clean(_between(li_html, r'class="[^"]*job-search-card__location[^"]*"[^>]*>',  r"</span>"))
#     date_pub   = _attr(li_html, "datetime")
#     type_emploi = _clean(_between(li_html, r'class="[^"]*job-search-card__benefits[^"]*"[^>]*>', r"</span>"))
#     easy_apply  = bool(re.search(r'Easy Apply|Candidature simplifiee', li_html, re.IGNORECASE))

#     nb_candidats = None
#     m_c = re.search(r'(\d+)\s*(candidat|applicant)', li_html, re.IGNORECASE)
#     if m_c:
#         nb_candidats = int(m_c.group(1))

#     href = None
#     m_h = re.search(r'href="(https://[^"]*?/jobs/view/[^"]+)"', li_html)
#     if m_h:
#         href = m_h.group(1).split("?")[0]
#     elif job_id:
#         href = f"{_BASE}/jobs/view/{job_id}"

#     if not (job_id or titre):
#         return None

#     return {
#         "job_id":       job_id,
#         "titre":        titre,
#         "entreprise":   entreprise,
#         "lieu":         lieu,
#         "date":         date_pub,
#         "type_emploi":  type_emploi,
#         "easy_apply":   easy_apply,
#         "nb_candidats": nb_candidats,
#         "url":          href,
#     }


# def _fetch_jobs_page(params: dict) -> list[dict]:
#     """Recupere une page de resultats et retourne les jobs parses."""
#     endpoint = f"{_BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search"
#     r = _get(endpoint, params=params)
#     cards = re.findall(r"<li[^>]*>.*?</li>", r.text, re.DOTALL)
#     out = []
#     for li in cards:
#         job = _parse_job_card(li)
#         if job:
#             out.append(job)
#     return out


# def _paginate(params: dict, limit: int, delay: float) -> list[dict]:
#     """Pagination generique sur l'endpoint guest."""
#     out: list[dict] = []
#     seen: set[str] = set()
#     start = 0

#     while len(out) < limit and start < 1000:
#         p = {**params, "start": start}
#         jobs = _fetch_jobs_page(p)
#         if not jobs:
#             break
#         new_here = 0
#         for job in jobs:
#             key = job.get("job_id") or job.get("url") or job.get("titre")
#             if key in seen:
#                 continue
#             seen.add(key)
#             out.append(job)
#             new_here += 1
#             if len(out) >= limit:
#                 break
#         if new_here == 0:
#             break
#         start += 25
#         if len(out) < limit:
#             time.sleep(delay)

#     return out[:limit]


# # ══════════════════════════════════════════════════════════════════════════════
# # 1. RECHERCHE SIMPLE
# # ══════════════════════════════════════════════════════════════════════════════

# def search_jobs(
#     keywords: str,
#     location: str = "",
#     limit: int = 25,
#     remote: bool = False,
#     delay: float = 1.0,
# ) -> list[dict]:
#     """Recherche d'offres d'emploi (mode invite)."""
#     params: dict = {"keywords": keywords, "location": location}
#     if remote:
#         params["f_WT"] = "2"
#     return _paginate(params, limit, delay)


# # ══════════════════════════════════════════════════════════════════════════════
# # 2. RECHERCHE AVANCEE
# # ══════════════════════════════════════════════════════════════════════════════

# def search_jobs_advanced(
#     keywords: str,
#     location: str = "",
#     limit: int = 25,
#     type_contrat: Optional[str] = None,
#     niveau: Optional[str] = None,
#     mode_travail: Optional[str] = None,
#     secteur: Optional[str] = None,
#     date_depuis: Optional[str] = None,
#     delay: float = 1.0,
# ) -> list[dict]:
#     """
#     Recherche avancee avec filtres LinkedIn.

#     type_contrat : fulltime | parttime | contract | temporary | internship | volunteer | other
#     niveau       : internship | entry | associate | mid-senior | director | executive
#     mode_travail : onsite | remote | hybrid
#     secteur      : technology | finance | healthcare | education | retail |
#                    manufacturing | consulting | media | automotive | construction |
#                    hospitality | legal | marketing | real-estate | transportation
#     date_depuis  : r86400 (24h) | r604800 (7j) | r2592000 (30j)
#     """
#     params: dict = {"keywords": keywords, "location": location}

#     if type_contrat:
#         code = _TYPE_CONTRAT.get(type_contrat.lower())
#         if not code:
#             raise ValueError(f"type_contrat invalide : {type_contrat}. "
#                              f"Valeurs : {list(_TYPE_CONTRAT)}")
#         params["f_JT"] = code

#     if niveau:
#         code = _NIVEAU.get(niveau.lower())
#         if not code:
#             raise ValueError(f"niveau invalide : {niveau}. Valeurs : {list(_NIVEAU)}")
#         params["f_E"] = code

#     if mode_travail:
#         code = _REMOTE.get(mode_travail.lower())
#         if not code:
#             raise ValueError(f"mode_travail invalide : {mode_travail}. Valeurs : {list(_REMOTE)}")
#         params["f_WT"] = code

#     if secteur:
#         code = _SECTEURS.get(secteur.lower())
#         if not code:
#             raise ValueError(f"secteur invalide : {secteur}. Valeurs : {list(_SECTEURS)}")
#         params["f_I"] = code

#     if date_depuis:
#         params["f_TPR"] = date_depuis

#     return _paginate(params, limit, delay)


# # ══════════════════════════════════════════════════════════════════════════════
# # 3. DETAIL OFFRE
# # ══════════════════════════════════════════════════════════════════════════════

# def get_job(job_id: str) -> dict:
#     """Detail complet d'une offre via sa page publique /jobs/view/<id>."""
#     jid = _job_id_from_urn(job_id) or job_id.strip()
#     url = f"{_BASE}/jobs/view/{jid}"
#     html = _get(url).text

#     ld      = _extract_jsonld(html) or {}
#     org     = ld.get("hiringOrganization") or {}
#     loc     = ld.get("jobLocation") or {}
#     if isinstance(loc, list):
#         loc = loc[0] if loc else {}
#     address = (loc.get("address") or {}) if isinstance(loc, dict) else {}

#     # Salaire
#     salary = None
#     base = ld.get("baseSalary") or {}
#     if isinstance(base, dict):
#         val = base.get("value") or {}
#         if isinstance(val, dict):
#             lo, hi = val.get("minValue"), val.get("maxValue")
#             if lo or hi:
#                 salary = {
#                     "min":    lo,
#                     "max":    hi,
#                     "unite":  val.get("unitText") or "",
#                     "devise": base.get("currency"),
#                 }

#     titre      = _clean(ld.get("title")) or _clean(_between(html, r'class="[^"]*top-card-layout__title[^"]*"[^>]*>', r"</h1>"))
#     entreprise = _clean(org.get("name")) or _clean(_between(html, r'class="[^"]*topcard__org-name-link[^"]*"[^>]*>', r"</a>"))

#     if not (titre or entreprise):
#         raise LinkedInUnavailable(f"Offre {jid} introuvable ou non publique.")

#     niveau_experience = _clean(_between(html, r'class="[^"]*description__job-criteria-text[^"]*"[^>]*>', r"</span>"))
#     secteur           = _clean(_between(html, r'class="[^"]*job-criteria__text--criteria[^"]*"[^>]*>',   r"</span>"))
#     easy_apply        = bool(re.search(r'Easy Apply|Candidature simplifiee', html, re.IGNORECASE))

#     nb_candidats = None
#     m_c = re.search(r'(\d+)\s*(candidat|applicant)', html, re.IGNORECASE)
#     if m_c:
#         nb_candidats = int(m_c.group(1))

#     taille_entreprise = None
#     nb_emp = org.get("numberOfEmployees")
#     if isinstance(nb_emp, dict):
#         taille_entreprise = str(nb_emp.get("value") or "")
#     elif isinstance(nb_emp, (int, str)):
#         taille_entreprise = str(nb_emp)

#     pays_raw = address.get("addressCountry")
#     pays     = _clean(pays_raw if isinstance(pays_raw, str) else (pays_raw or {}).get("name"))

#     return {
#         "job_id":             jid,
#         "titre":              titre,
#         "entreprise":         entreprise,
#         "site_entreprise":    org.get("url") or org.get("sameAs"),
#         "taille_entreprise":  taille_entreprise,
#         "logo":               org.get("logo"),
#         "lieu":               _clean(address.get("addressLocality")) or _clean(
#                                   ld.get("jobLocation", {}).get("name")
#                                   if isinstance(ld.get("jobLocation"), dict) else None),
#         "pays":               pays,
#         "date_publication":   ld.get("datePosted"),
#         "date_expiration":    ld.get("validThrough"),
#         "type_emploi":        ld.get("employmentType"),
#         "niveau_experience":  niveau_experience,
#         "secteur":            secteur,
#         "salaire":            salary,
#         "easy_apply":         easy_apply,
#         "nb_candidats":       nb_candidats,
#         "description":        _clean(ld.get("description")),
#         "url":                url,
#     }


# # ══════════════════════════════════════════════════════════════════════════════
# # 4. PROFIL ENTREPRISE
# # ══════════════════════════════════════════════════════════════════════════════

# def get_company(company_slug: str) -> dict:
#     """
#     Profil public d'une entreprise LinkedIn.

#     company_slug : identifiant URL de l'entreprise (ex: 'google', 'apple', 'orange')
#                    visible dans https://www.linkedin.com/company/<slug>/
#     """
#     slug = company_slug.strip().lower()
#     url  = f"{_BASE}/company/{slug}/"
#     html = _get(url).text

#     ld = _extract_jsonld(html, type_="Organization") or {}

#     # Fallback HTML si JSON-LD incomplet
#     nom = _clean(ld.get("name")) or _clean(
#         _between(html, r'class="[^"]*org-top-card-summary__title[^"]*"[^>]*>', r"</h1>"))

#     if not nom:
#         raise LinkedInUnavailable(f"Entreprise '{slug}' introuvable ou non publique.")

#     description = _clean(ld.get("description")) or _clean(
#         _between(html, r'class="[^"]*org-top-card-summary__tagline[^"]*"[^>]*>', r"</p>"))

#     logo = (ld.get("logo") or {}).get("url") if isinstance(ld.get("logo"), dict) else ld.get("logo")
#     logo = logo or _attr(html, "data-delayed-url") or None

#     site_web = ld.get("url") or ld.get("sameAs") or _clean(
#         _between(html, r'class="[^"]*org-top-card-primary-actions__inner[^"]*".*?href="', r'"'))

#     secteur = _clean(ld.get("industry")) or _clean(
#         _between(html, r'class="[^"]*org-top-card-summary-info-list__info-item[^"]*"[^>]*>', r"</span>"))

#     taille = None
#     nb_emp = ld.get("numberOfEmployees")
#     if isinstance(nb_emp, dict):
#         taille = str(nb_emp.get("value") or "")
#     elif isinstance(nb_emp, (int, str)):
#         taille = str(nb_emp)
#     if not taille:
#         m_t = re.search(r'(\d[\d,\.\s]*)\s*(employ|salarie|employee)', html, re.IGNORECASE)
#         if m_t:
#             taille = m_t.group(1).strip()

#     siege = _clean(ld.get("address", {}).get("addressLocality") if isinstance(ld.get("address"), dict) else None) or \
#             _clean(_between(html, r'class="[^"]*org-top-card-summary-info-list[^"]*".*?<span[^>]*>', r"</span>"))

#     nb_abonnes = None
#     m_ab = re.search(r'([\d,\.]+)\s*(follower|abonn)', html, re.IGNORECASE)
#     if m_ab:
#         nb_abonnes = m_ab.group(1).replace(",", "").replace(".", "")

#     specialites: list[str] = []
#     for m in re.finditer(r'class="[^"]*speciality[^"]*"[^>]*>([^<]+)<', html, re.IGNORECASE):
#         val = _clean(m.group(1))
#         if val:
#             specialites.append(val)

#     return {
#         "slug":         slug,
#         "nom":          nom,
#         "description":  description,
#         "logo":         logo,
#         "site_web":     site_web,
#         "secteur":      secteur,
#         "taille":       taille,
#         "siege":        siege,
#         "nb_abonnes":   nb_abonnes,
#         "specialites":  specialites or None,
#         "url":          url,
#     }


# # ══════════════════════════════════════════════════════════════════════════════
# # 5. TOP ENTREPRISES PAR SECTEUR
# # ══════════════════════════════════════════════════════════════════════════════

# def top_companies(
#     secteur: str,
#     location: str = "",
#     limit: int = 10,
# ) -> list[dict]:
#     """
#     Top entreprises qui recrutent le plus dans un secteur donne.

#     Strategie : recherche d'offres filtrees par secteur, puis agregation
#     par entreprise pour identifier celles qui publient le plus d'offres.

#     secteur  : technology | finance | healthcare | education | retail |
#                manufacturing | consulting | media | automotive | construction |
#                hospitality | legal | marketing | real-estate | transportation
#     location : ville ou pays (optionnel)
#     limit    : nombre d'entreprises a retourner
#     """
#     code = _SECTEURS.get(secteur.lower())
#     if not code:
#         raise ValueError(f"secteur invalide : '{secteur}'. Valeurs : {list(_SECTEURS)}")

#     # On recupere un max d'offres pour avoir un bon echantillon
#     sample_limit = min(limit * 10, 100)
#     params: dict = {"keywords": "", "location": location, "f_I": code}
#     jobs = _paginate(params, sample_limit, delay=0.5)

#     # Agregation par entreprise
#     from collections import Counter, defaultdict
#     compteur: Counter = Counter()
#     meta: dict = defaultdict(dict)

#     for job in jobs:
#         ent = job.get("entreprise")
#         if not ent:
#             continue
#         compteur[ent] += 1
#         if ent not in meta or not meta[ent].get("lieu"):
#             meta[ent] = {
#                 "entreprise": ent,
#                 "lieu":       job.get("lieu"),
#                 "exemple_url": job.get("url"),
#             }

#     resultats = []
#     for ent, nb_offres in compteur.most_common(limit):
#         resultats.append({
#             "rang":       len(resultats) + 1,
#             "entreprise": ent,
#             "nb_offres":  nb_offres,
#             "lieu":       meta[ent].get("lieu"),
#             "exemple_offre": meta[ent].get("exemple_url"),
#         })

#     return resultats


"""
LinkedIn Service  v0.4
======================
Endpoints disponibles :
  - search_jobs()          : recherche d'offres (mode invite)
  - search_jobs_advanced() : recherche avec filtres avances (type contrat, niveau, secteur)
  - get_job()              : detail d'une offre
  - get_company()          : profil d'une entreprise
  - top_companies()        : top entreprises qui recrutent par secteur
"""

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("service.linkedin")


class LinkedInUnavailable(Exception):
    """Ressource LinkedIn introuvable, supprimee, ou bloquee (anti-bot)."""


# ══════════════════════════════════════════════════════════════════════════════
# SESSION HTTP
# ══════════════════════════════════════════════════════════════════════════════

_BASE = "https://www.linkedin.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


def _get(url: str, params: dict | None = None, timeout: int = 20) -> requests.Response:
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
    except requests.RequestException as e:
        raise LinkedInUnavailable(f"Erreur reseau LinkedIn : {e}")
    if r.status_code == 429:
        raise LinkedInUnavailable("LinkedIn rate limit (429). Reessayez plus tard / via proxy.")
    if r.status_code in (403, 999):
        raise LinkedInUnavailable(f"LinkedIn a bloque la requete (HTTP {r.status_code}).")
    if r.status_code == 404:
        raise LinkedInUnavailable("Ressource LinkedIn introuvable (404).")
    if r.status_code != 200:
        raise LinkedInUnavailable(f"Reponse LinkedIn inattendue (HTTP {r.status_code}).")
    return r


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _clean(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _attr(block: str, attr: str) -> Optional[str]:
    m = re.search(rf'{attr}="([^"]+)"', block)
    return m.group(1) if m else None


def _between(block: str, pattern_open: str, pattern_close: str) -> Optional[str]:
    m = re.search(pattern_open + r"(.*?)" + pattern_close, block, re.DOTALL)
    return m.group(1) if m else None


def _job_id_from_urn(urn: Optional[str]) -> Optional[str]:
    if not urn:
        return None
    m = re.search(r"(\d{6,})", urn)
    return m.group(1) if m else None


def _extract_jsonld(html: str, type_: str = "JobPosting") -> Optional[dict]:
    for m in re.finditer(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    ):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") == type_:
                return it
    return None


def _date_to_linkedin_tpr(date_str: Optional[str]) -> Optional[str]:
    """
    Convertit une date normale (YYYY-MM-DD) en parametre f_TPR LinkedIn.

    LinkedIn accepte uniquement des intervalles relatifs :
      r86400   = dernières 24h
      r604800  = dernière semaine
      r2592000 = dernier mois

    On choisit automatiquement le bon intervalle selon l'ecart avec aujourd'hui :
      <= 1 jour  -> r86400
      <= 7 jours -> r604800
      <= 30 jours -> r2592000
      > 30 jours  -> r2592000 (meilleur effort)

    Leve ValueError si le format est invalide.
    """
    if not date_str:
        return None

    try:
        d = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"Format de date invalide : '{date_str}'. "
            f"Utilisez le format YYYY-MM-DD (ex: 2026-01-15)."
        )

    aujourd_hui = datetime.now(timezone.utc).date()
    delta = (aujourd_hui - d).days

    if delta < 0:
        raise ValueError(
            f"La date '{date_str}' est dans le futur. "
            f"Entrez une date passee (ex: {aujourd_hui})."
        )

    if delta <= 1:
        return "r86400"
    elif delta <= 7:
        return "r604800"
    else:
        return "r2592000"


# ══════════════════════════════════════════════════════════════════════════════
# FILTRES AVANCES — mapping LinkedIn
# ══════════════════════════════════════════════════════════════════════════════

_TYPE_CONTRAT = {
    "fulltime":   "F",
    "parttime":   "P",
    "contract":   "C",
    "temporary":  "T",
    "internship": "I",
    "volunteer":  "V",
    "other":      "O",
}

_NIVEAU = {
    "internship": "1",
    "entry":      "2",
    "associate":  "3",
    "mid-senior": "4",
    "director":   "5",
    "executive":  "6",
}

_REMOTE = {
    "onsite": "1",
    "remote": "2",
    "hybrid": "3",
}

_SECTEURS = {
    "technology":     "96",
    "finance":        "43",
    "healthcare":     "14",
    "education":      "69",
    "retail":         "27",
    "manufacturing":  "25",
    "consulting":     "104",
    "media":          "3",
    "automotive":     "23",
    "construction":   "48",
    "hospitality":    "31",
    "legal":          "9",
    "marketing":      "80",
    "real-estate":    "44",
    "transportation": "71",
}


# ══════════════════════════════════════════════════════════════════════════════
# PARSING CARTE JOB
# ══════════════════════════════════════════════════════════════════════════════

def _parse_job_card(li_html: str) -> Optional[dict]:
    urn    = _attr(li_html, "data-entity-urn") or _attr(li_html, "data-job-id")
    job_id = _job_id_from_urn(urn)

    titre       = _clean(_between(li_html, r'class="[^"]*base-search-card__title[^"]*"[^>]*>',    r"</h3>"))
    entreprise  = _clean(_between(li_html, r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>', r"</h4>"))
    lieu        = _clean(_between(li_html, r'class="[^"]*job-search-card__location[^"]*"[^>]*>',  r"</span>"))
    date_pub    = _attr(li_html, "datetime")
    type_emploi = _clean(_between(li_html, r'class="[^"]*job-search-card__benefits[^"]*"[^>]*>',  r"</span>"))
    easy_apply  = bool(re.search(r'Easy Apply|Candidature simplifiee', li_html, re.IGNORECASE))

    nb_candidats = None
    m_c = re.search(r'(\d+)\s*(candidat|applicant)', li_html, re.IGNORECASE)
    if m_c:
        nb_candidats = int(m_c.group(1))

    href  = None
    m_h   = re.search(r'href="(https://[^"]*?/jobs/view/[^"]+)"', li_html)
    if m_h:
        href = m_h.group(1).split("?")[0]
    elif job_id:
        href = f"{_BASE}/jobs/view/{job_id}"

    if not (job_id or titre):
        return None

    return {
        "job_id":       job_id,
        "titre":        titre,
        "entreprise":   entreprise,
        "lieu":         lieu,
        "date":         date_pub,
        "type_emploi":  type_emploi,
        "easy_apply":   easy_apply,
        "nb_candidats": nb_candidats,
        "url":          href,
    }


def _fetch_jobs_page(params: dict) -> list[dict]:
    endpoint = f"{_BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search"
    r        = _get(endpoint, params=params)
    cards    = re.findall(r"<li[^>]*>.*?</li>", r.text, re.DOTALL)
    out = []
    for li in cards:
        job = _parse_job_card(li)
        if job:
            out.append(job)
    return out


def _paginate(params: dict, limit: int, delay: float) -> list[dict]:
    out:  list[dict] = []
    seen: set[str]   = set()
    start = 0

    while len(out) < limit and start < 1000:
        p    = {**params, "start": start}
        jobs = _fetch_jobs_page(p)
        if not jobs:
            break
        new_here = 0
        for job in jobs:
            key = job.get("job_id") or job.get("url") or job.get("titre")
            if key in seen:
                continue
            seen.add(key)
            out.append(job)
            new_here += 1
            if len(out) >= limit:
                break
        if new_here == 0:
            break
        start += 25
        if len(out) < limit:
            time.sleep(delay)

    return out[:limit]


# ══════════════════════════════════════════════════════════════════════════════
# 1. RECHERCHE SIMPLE
# ══════════════════════════════════════════════════════════════════════════════

def search_jobs(
    keywords: str,
    location: str  = "",
    limit:    int  = 25,
    remote:   bool = False,
    delay:    float = 1.0,
) -> list[dict]:
    params: dict = {"keywords": keywords, "location": location}
    if remote:
        params["f_WT"] = "2"
    return _paginate(params, limit, delay)


# ══════════════════════════════════════════════════════════════════════════════
# 2. RECHERCHE AVANCEE
# ══════════════════════════════════════════════════════════════════════════════

def search_jobs_advanced(
    keywords:     str,
    location:     str           = "",
    limit:        int           = 25,
    type_contrat: Optional[str] = None,
    niveau:       Optional[str] = None,
    mode_travail: Optional[str] = None,
    secteur:      Optional[str] = None,
    date_depuis:  Optional[str] = None,   # format YYYY-MM-DD
    delay:        float         = 1.0,
) -> list[dict]:
    """
    Recherche avancee avec filtres LinkedIn.

    date_depuis : date au format YYYY-MM-DD (ex: 2026-05-01)
                  LinkedIn ne supporte pas les dates exactes, on convertit
                  automatiquement en intervalle (24h / 7j / 30j).
    """
    params: dict = {"keywords": keywords, "location": location}

    if type_contrat:
        code = _TYPE_CONTRAT.get(type_contrat.lower())
        if not code:
            raise ValueError(f"type_contrat invalide : '{type_contrat}'. Valeurs : {list(_TYPE_CONTRAT)}")
        params["f_JT"] = code

    if niveau:
        code = _NIVEAU.get(niveau.lower())
        if not code:
            raise ValueError(f"niveau invalide : '{niveau}'. Valeurs : {list(_NIVEAU)}")
        params["f_E"] = code

    if mode_travail:
        code = _REMOTE.get(mode_travail.lower())
        if not code:
            raise ValueError(f"mode_travail invalide : '{mode_travail}'. Valeurs : {list(_REMOTE)}")
        params["f_WT"] = code

    if secteur:
        code = _SECTEURS.get(secteur.lower())
        if not code:
            raise ValueError(f"secteur invalide : '{secteur}'. Valeurs : {list(_SECTEURS)}")
        params["f_I"] = code

    if date_depuis:
        params["f_TPR"] = _date_to_linkedin_tpr(date_depuis)

    return _paginate(params, limit, delay)


# ══════════════════════════════════════════════════════════════════════════════
# 3. DETAIL OFFRE
# ══════════════════════════════════════════════════════════════════════════════

def get_job(job_id: str) -> dict:
    jid  = _job_id_from_urn(job_id) or job_id.strip()
    url  = f"{_BASE}/jobs/view/{jid}"
    html = _get(url).text

    ld      = _extract_jsonld(html) or {}
    org     = ld.get("hiringOrganization") or {}
    loc     = ld.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    address = (loc.get("address") or {}) if isinstance(loc, dict) else {}

    salary = None
    base   = ld.get("baseSalary") or {}
    if isinstance(base, dict):
        val = base.get("value") or {}
        if isinstance(val, dict):
            lo, hi = val.get("minValue"), val.get("maxValue")
            if lo or hi:
                salary = {
                    "min":    lo,
                    "max":    hi,
                    "unite":  val.get("unitText") or "",
                    "devise": base.get("currency"),
                }

    titre      = _clean(ld.get("title")) or _clean(_between(html, r'class="[^"]*top-card-layout__title[^"]*"[^>]*>', r"</h1>"))
    entreprise = _clean(org.get("name")) or _clean(_between(html, r'class="[^"]*topcard__org-name-link[^"]*"[^>]*>', r"</a>"))

    if not (titre or entreprise):
        raise LinkedInUnavailable(f"Offre {jid} introuvable ou non publique.")

    niveau_experience = _clean(_between(html, r'class="[^"]*description__job-criteria-text[^"]*"[^>]*>', r"</span>"))
    secteur           = _clean(_between(html, r'class="[^"]*job-criteria__text--criteria[^"]*"[^>]*>',   r"</span>"))
    easy_apply        = bool(re.search(r'Easy Apply|Candidature simplifiee', html, re.IGNORECASE))

    nb_candidats = None
    m_c = re.search(r'(\d+)\s*(candidat|applicant)', html, re.IGNORECASE)
    if m_c:
        nb_candidats = int(m_c.group(1))

    taille_entreprise = None
    nb_emp = org.get("numberOfEmployees")
    if isinstance(nb_emp, dict):
        taille_entreprise = str(nb_emp.get("value") or "")
    elif isinstance(nb_emp, (int, str)):
        taille_entreprise = str(nb_emp)

    pays_raw = address.get("addressCountry")
    pays     = _clean(pays_raw if isinstance(pays_raw, str) else (pays_raw or {}).get("name"))

    return {
        "job_id":             jid,
        "titre":              titre,
        "entreprise":         entreprise,
        "site_entreprise":    org.get("url") or org.get("sameAs"),
        "taille_entreprise":  taille_entreprise,
        "logo":               org.get("logo"),
        "lieu":               _clean(address.get("addressLocality")) or _clean(
                                  ld.get("jobLocation", {}).get("name")
                                  if isinstance(ld.get("jobLocation"), dict) else None),
        "pays":               pays,
        "date_publication":   ld.get("datePosted"),
        "date_expiration":    ld.get("validThrough"),
        "type_emploi":        ld.get("employmentType"),
        "niveau_experience":  niveau_experience,
        "secteur":            secteur,
        "salaire":            salary,
        "easy_apply":         easy_apply,
        "nb_candidats":       nb_candidats,
        "description":        _clean(ld.get("description")),
        "url":                url,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. PROFIL ENTREPRISE
# ══════════════════════════════════════════════════════════════════════════════

def get_company(company_slug: str) -> dict:
    """
    Profil d'une entreprise via ses offres d'emploi publiques (mode invite).
    Enrichi via Clearbit (logo, site) et Wikipedia (description, taille).

    company_slug : slug (ex: 'apple') ou URL LinkedIn complète.
    """
    from collections import Counter

    raw   = company_slug.strip()
    m_url = re.search(r'linkedin\.com/company/([^/?&#]+)', raw, re.IGNORECASE)
    slug  = m_url.group(1).lower() if m_url else raw.lower()
    nom_recherche = slug.replace("-", " ")

    endpoint = f"{_BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search"

    # ── Collecte toutes les offres (pagination jusqu'à 75) ─────────────────
    offres: list[dict] = []
    seen:   set[str]   = set()

    for start in range(0, 75, 25):
        params = {"keywords": nom_recherche, "location": "", "start": start}
        try:
            r     = _get(endpoint, params=params)
            cards = re.findall(r"<li[^>]*>.*?</li>", r.text, re.DOTALL)
        except LinkedInUnavailable:
            break
        new_here = 0
        for li in cards:
            job = _parse_job_card(li)
            if not job:
                continue
            ent = (job.get("entreprise") or "").lower()
            # Filtre souple : accepte si le slug OU le nom de recherche est contenu
            if slug not in ent and nom_recherche not in ent:
                continue
            key = job.get("job_id") or job.get("url")
            if key in seen:
                continue
            seen.add(key)
            offres.append(job)
            new_here += 1
        if new_here == 0:
            break
        time.sleep(0.5)

    if not offres:
        raise LinkedInUnavailable(
            f"Aucune offre publique trouvee pour '{slug}'. "
            f"Verifiez le nom ou utilisez /jobs/search?keywords={slug}."
        )

    # Nom officiel = le plus frequent dans les offres
    noms    = [j.get("entreprise") for j in offres if j.get("entreprise")]
    nom_off = Counter(noms).most_common(1)[0][0] if noms else slug.title()

    # Lieux uniques
    lieux = list({j.get("lieu") for j in offres if j.get("lieu")})

    # Detail JSON-LD de la premiere offre (logo, taille, site)
    detail: dict = {}
    for offre in offres[:3]:
        if offre.get("job_id"):
            try:
                detail = get_job(offre["job_id"])
                if detail.get("logo") or detail.get("site_entreprise"):
                    break
            except Exception:
                continue

    # ── Clearbit : logo + site web ─────────────────────────────────────────
    logo     = detail.get("logo")
    site_web = detail.get("site_entreprise")
    taille   = detail.get("taille_entreprise")

    if not logo or not site_web:
        try:
            cb_url  = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={requests.utils.quote(nom_off)}"
            cb_r    = requests.get(cb_url, timeout=5)
            if cb_r.status_code == 200:
                cb_data = cb_r.json()
                if cb_data:
                    logo     = logo     or cb_data[0].get("logo")
                    domain   = cb_data[0].get("domain")
                    site_web = site_web or (f"https://{domain}" if domain else None)
        except Exception:
            pass

    # ── Wikipedia : description + taille ──────────────────────────────────
    description = None
    # Recherche "Apple Inc." plutôt que "Apple" pour eviter la confusion
    wiki_query = nom_off if len(nom_off) > 5 else f"{nom_off} Inc."
    try:
        wiki_url = (
            f"https://en.wikipedia.org/api/rest_v1/page/summary/"
            f"{requests.utils.quote(wiki_query)}"
        )
        wiki_r = requests.get(wiki_url, timeout=5,
                              headers={"User-Agent": "scraper-hub/0.1"})
        if wiki_r.status_code == 200:
            wiki     = wiki_r.json()
            wiki_type = wiki.get("type", "")
            # On accepte uniquement les pages de type "standard" (entreprise, organisation)
            # et on rejette les pages de desambiguation ou trop generiques
            if wiki_type == "standard" and wiki.get("extract"):
                extract = wiki["extract"]
                # Verifie que c'est bien une page d'entreprise/organisation
                is_company = re.search(
                    r'(company|corporation|multinational|founded|headquartered|Inc\.|Ltd\.|LLC|entreprise)',
                    extract, re.IGNORECASE
                )
                if is_company:
                    description = extract
                    if not taille:
                        m_t = re.search(
                            r"([\d,]+(?:\+)?\s*(?:employees|workers|staff))",
                            extract, re.IGNORECASE
                        )
                        if m_t:
                            taille = m_t.group(1).strip()
    except Exception:
        pass

    return {
        "slug":              slug,
        "nom":               nom_off,
        "description":       description,
        "logo":              logo,
        "site_entreprise":   site_web,
        "taille":            taille,
        "lieux":             lieux,
        "nb_offres_actives": len(offres),
        "exemple_offres":    [j.get("url") for j in offres[:3]],
        "url_linkedin":      f"{_BASE}/company/{slug}/",
    }

# ══════════════════════════════════════════════════════════════════════════════
# 5. TOP ENTREPRISES PAR SECTEUR
# ══════════════════════════════════════════════════════════════════════════════

def top_companies(
    secteur:  str,
    location: str = "",
    limit:    int = 10,
) -> list[dict]:
    code = _SECTEURS.get(secteur.lower())
    if not code:
        raise ValueError(f"secteur invalide : '{secteur}'. Valeurs : {list(_SECTEURS)}")

    sample_limit = min(limit * 10, 100)
    params: dict = {"keywords": "", "location": location, "f_I": code}
    jobs = _paginate(params, sample_limit, delay=0.5)

    from collections import Counter, defaultdict
    compteur: Counter      = Counter()
    meta:     dict         = defaultdict(dict)

    for job in jobs:
        ent = job.get("entreprise")
        if not ent:
            continue
        compteur[ent] += 1
        if ent not in meta or not meta[ent].get("lieu"):
            meta[ent] = {
                "entreprise":  ent,
                "lieu":        job.get("lieu"),
                "exemple_url": job.get("url"),
            }

    resultats = []
    for ent, nb_offres in compteur.most_common(limit):
        resultats.append({
            "rang":          len(resultats) + 1,
            "entreprise":    ent,
            "nb_offres":     nb_offres,
            "lieu":          meta[ent].get("lieu"),
            "exemple_offre": meta[ent].get("exemple_url"),
        })

    return resultats