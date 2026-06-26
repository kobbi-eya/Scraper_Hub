# """
# Router LinkedIn  v0.3
# =====================
# Endpoints :
#   GET /linkedin/jobs/search               — recherche simple
#   GET /linkedin/jobs/search/advanced      — recherche avec filtres avances
#   GET /linkedin/jobs/{job_id}             — detail d'une offre
#   GET /linkedin/company/{slug}            — profil d'une entreprise
#   GET /linkedin/companies/top             — top entreprises par secteur
# """

# from fastapi import APIRouter, HTTPException, Query
# from typing import Optional

# from exporters import to_csv_response
# from services.linkedin_service import (
#     search_jobs,
#     search_jobs_advanced,
#     get_job,
#     get_company,
#     top_companies,
#     LinkedInUnavailable,
#     _SECTEURS,
#     _TYPE_CONTRAT,
#     _NIVEAU,
#     _REMOTE,
# )

# router = APIRouter(prefix="/linkedin", tags=["LinkedIn"])

# FormatQuery = Query(
#     "json",
#     alias="format",
#     pattern="^(json|csv)$",
#     description="Format de sortie : json (defaut) ou csv",
# )


# def _respond(data, fmt: str, filename: str):
#     if fmt == "csv":
#         rows = data if isinstance(data, list) else [data]
#         return to_csv_response(rows, filename)
#     return data


# # ── 1. Recherche simple ───────────────────────────────────────────────────────

# @router.get("/jobs/search", summary="Recherche simple d'offres d'emploi")
# def route_search_jobs(
#     keywords: str  = Query(...,   description="Mots-cles (ex: python developer)"),
#     location: str  = Query("",    description="Ville ou pays (ex: Paris, France)"),
#     limit:    int  = Query(25,    ge=1, le=200, description="Nombre d'offres"),
#     remote:   bool = Query(False, description="Teletravail uniquement"),
#     fmt:      str  = FormatQuery,
# ):
#     """Recherche d'offres d'emploi LinkedIn (donnees publiques, mode invite)."""
#     try:
#         data = search_jobs(keywords, location, limit, remote)
#         return _respond(data, fmt, "linkedin_jobs.csv")
#     except LinkedInUnavailable as e:
#         raise HTTPException(status_code=502, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Erreur recherche jobs : {e}")


# # ── 2. Recherche avancee ──────────────────────────────────────────────────────

# @router.get("/jobs/search/advanced", summary="Recherche avancee avec filtres")
# def route_search_jobs_advanced(
#     keywords:     str           = Query(...,  description="Mots-cles (ex: data engineer)"),
#     location:     str           = Query("",   description="Ville ou pays"),
#     limit:        int           = Query(25,   ge=1, le=200, description="Nombre d'offres"),
#     type_contrat: Optional[str] = Query(None, description=f"Type contrat : {list(_TYPE_CONTRAT)}"),
#     niveau:       Optional[str] = Query(None, description=f"Niveau : {list(_NIVEAU)}"),
#     mode_travail: Optional[str] = Query(None, description=f"Mode travail : {list(_REMOTE)}"),
#     secteur:      Optional[str] = Query(None, description=f"Secteur : {list(_SECTEURS)}"),
#     date_depuis:  Optional[str] = Query(None, description="Periode : r86400 (24h) | r604800 (7j) | r2592000 (30j)"),
#     fmt:          str           = FormatQuery,
# ):
#     """
#     Recherche avancee avec filtres LinkedIn :
#     type de contrat, niveau d'experience, mode de travail, secteur, date de publication.
#     """
#     try:
#         data = search_jobs_advanced(
#             keywords, location, limit,
#             type_contrat, niveau, mode_travail, secteur, date_depuis,
#         )
#         return _respond(data, fmt, "linkedin_jobs_advanced.csv")
#     except ValueError as e:
#         raise HTTPException(status_code=422, detail=str(e))
#     except LinkedInUnavailable as e:
#         raise HTTPException(status_code=502, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Erreur recherche avancee : {e}")


# # ── 3. Detail offre ───────────────────────────────────────────────────────────

# @router.get("/jobs/{job_id}", summary="Detail complet d'une offre")
# def route_get_job(
#     job_id: str,
#     fmt:    str = FormatQuery,
# ):
#     """Detail complet d'une offre LinkedIn via son ID numerique."""
#     try:
#         data = get_job(job_id)
#         return _respond(data, fmt, f"linkedin_job_{data['job_id']}.csv")
#     except LinkedInUnavailable as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Erreur detail job : {e}")


# # ── 4. Profil entreprise ──────────────────────────────────────────────────────

# @router.get("/company/{slug}", summary="Profil public d'une entreprise")
# def route_get_company(
#     slug: str,
#     fmt:  str = FormatQuery,
# ):
#     """
#     Profil public d'une entreprise LinkedIn.
#     Le slug est l'identifiant URL visible sur linkedin.com/company/<slug>/
#     Exemple : google, apple, orange, total-energies
#     """
#     try:
#         data = get_company(slug)
#         return _respond(data, fmt, f"linkedin_company_{slug}.csv")
#     except LinkedInUnavailable as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Erreur profil entreprise : {e}")


# # ── 5. Top entreprises par secteur ────────────────────────────────────────────

# @router.get("/companies/top", summary="Top entreprises qui recrutent par secteur")
# def route_top_companies(
#     secteur:  str = Query(...,  description=f"Secteur : {list(_SECTEURS)}"),
#     location: str = Query("",   description="Ville ou pays (optionnel)"),
#     limit:    int = Query(10,   ge=1, le=50, description="Nombre d'entreprises"),
#     fmt:      str = FormatQuery,
# ):
#     """
#     Retourne le classement des entreprises qui publient le plus d'offres
#     dans un secteur donne, avec le nombre d'offres actives.
#     """
#     try:
#         data = top_companies(secteur, location, limit)
#         return _respond(data, fmt, f"linkedin_top_{secteur}.csv")
#     except ValueError as e:
#         raise HTTPException(status_code=422, detail=str(e))
#     except LinkedInUnavailable as e:
#         raise HTTPException(status_code=502, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Erreur top entreprises : {e}")

"""
Router LinkedIn  v0.5  — JOBS + COMPANY (mode invite)
=====================================================
Controller pur : HTTP in, HTTP out. Logique dans linkedin_service.
Chaque endpoint accepte ?format=json (defaut) ou ?format=csv.

Corrections v0.5 :
  - /company/{slug} : 100% LinkedIn (page + offres), plus aucun service tiers
    et la provenance de chaque champ est renvoyee dans la reponse (`sources`).
  - /companies/active-recruiters : renomme (ex /companies/top) car ce n'est PAS
    un classement officiel LinkedIn mais un derive des offres.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from exporters import to_csv_response
from services.linkedin_service import (
    search_jobs, search_jobs_advanced, get_job, get_company, active_recruiters,
    LinkedInUnavailable, _SECTEURS, _TYPE_CONTRAT, _NIVEAU, _REMOTE,
)

router = APIRouter(prefix="/linkedin", tags=["LinkedIn"])

FormatQuery = Query("json", alias="format", pattern="^(json|csv)$",
                    description="Format de sortie : json (defaut) ou csv")


def _respond(data, fmt: str, filename: str):
    if fmt == "csv":
        rows = data if isinstance(data, list) else [data]
        return to_csv_response(rows, filename)
    return data


# -- 1. Recherche simple -------------------------------------------------------

@router.get("/jobs/search", summary="Recherche simple d'offres d'emploi")
def route_search_jobs(
    keywords: str           = Query(...,   description="Mots-cles (ex: python developer)"),
    location: str           = Query("",    description="Ville ou pays (texte)"),
    limit:    int           = Query(25,    ge=1, le=200, description="Nombre d'offres"),
    remote:   bool          = Query(False, description="Teletravail uniquement"),
    fmt:      str           = FormatQuery,
):
    """Recherche simple d'offres LinkedIn (mots-cles + localisation)."""
    try:
        data = search_jobs(keywords, location, limit, remote)
        return _respond(data, fmt, "linkedin_jobs.csv")
    except LinkedInUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur recherche jobs : {e}")


# -- 2. Recherche avancee ------------------------------------------------------

@router.get("/jobs/search/advanced", summary="Recherche avancee avec filtres")
def route_search_jobs_advanced(
    keywords:     str           = Query(...,  description="Mots-cles (ex: data engineer)"),
    location:     str           = Query("",   description="Ville ou pays (texte)"),
    limit:        int           = Query(25,   ge=1, le=200, description="Nombre d'offres"),
    type_contrat: Optional[str] = Query(None, description=f"Type contrat : {list(_TYPE_CONTRAT)}"),
    niveau:       Optional[str] = Query(None, description=f"Niveau : {list(_NIVEAU)}"),
    mode_travail: Optional[str] = Query(None, description=f"Mode travail : {list(_REMOTE)}"),
    secteur:      Optional[str] = Query(None, description=f"Secteur : {list(_SECTEURS)}"),
    date_depuis:  Optional[str] = Query(None, description="Date YYYY-MM-DD (convertie en intervalle)"),
    fmt:          str           = FormatQuery,
):
    """Recherche avancee : contrat, niveau, mode de travail, secteur, date."""
    try:
        data = search_jobs_advanced(keywords, location, limit, type_contrat, niveau,
                                    mode_travail, secteur, date_depuis)
        return _respond(data, fmt, "linkedin_jobs_advanced.csv")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LinkedInUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur recherche avancee : {e}")


# -- 3. Detail offre -----------------------------------------------------------

@router.get("/jobs/{job_id}", summary="Detail complet d'une offre")
def route_get_job(job_id: str, fmt: str = FormatQuery):
    """Detail complet d'une offre LinkedIn via son ID numerique."""
    try:
        data = get_job(job_id)
        return _respond(data, fmt, f"linkedin_job_{data['job_id']}.csv")
    except LinkedInUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur detail job : {e}")


# -- 4. Profil entreprise (100% LinkedIn) ----------------------------------

@router.get("/company/{slug}", summary="Profil entreprise (100% LinkedIn)")
def route_get_company(
    slug: str = ...,
    fmt:  str = FormatQuery,
):
    """
    Profil d'entreprise base uniquement sur LinkedIn (page publique + offres).
    Aucun service tiers. Le champ `sources` indique l'origine de chaque valeur.
    """
    try:
        data = get_company(slug)
        return _respond(data, fmt, f"linkedin_company_{data['slug']}.csv")
    except LinkedInUnavailable as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur profil entreprise : {e}")


# -- 5. Entreprises les plus actives en recrutement (derive des offres) --------

@router.get("/companies/active-recruiters",
            summary="Entreprises les plus actives en recrutement (derive des offres)")
def route_active_recruiters(
    secteur:  str = Query(...,  description=f"Secteur : {list(_SECTEURS)}"),
    location: str = Query("",   description="Ville ou pays (optionnel)"),
    limit:    int = Query(10,   ge=1, le=50, description="Nombre d'entreprises"),
    fmt:      str = FormatQuery,
):
    """
    Classement des entreprises qui publient le plus d'offres dans un secteur.
    NON officiel : derive du volume d'offres publiques (voir champ `source`).
    """
    try:
        data = active_recruiters(secteur, location, limit)
        # en CSV on exporte le classement (liste), pas l'enveloppe
        if fmt == "csv":
            return to_csv_response(data["classement"], f"linkedin_recruiters_{secteur}.csv")
        return data
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LinkedInUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur recruteurs actifs : {e}")
