# 🕷️ Scraper Hub

**API FastAPI unique pour scraper YouTube, Twitter/X, Reddit et Snapchat — sans clé API officielle, sans configuration compliquée.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-brightgreen)]()

Scraper Hub regroupe dans **une seule API REST** plusieurs scrapers qui, d'habitude, sont dispersés dans des dizaines de scripts différents : vidéos et commentaires YouTube, profils et tweets Twitter/X, posts Reddit, et (bientôt) Snapchat et LinkedIn. Un seul serveur, une doc Swagger interactive, et des exports CSV/JSON prêts à l'emploi.

## Pourquoi ce projet ?

La plupart des scrapers open source ne couvrent qu'**une seule plateforme** et obligent à jongler entre plusieurs outils, formats de sortie et dépendances. Scraper Hub part d'un constat simple : si tu dois croiser des données YouTube + Twitter + Reddit pour une veille, une étude ou un dataset, tu ne devrais pas avoir besoin de 3 projets différents.

## Fonctionnalités

| Plateforme | Statut | Ce que tu peux récupérer |
|---|---|---|
| **YouTube** | ✅ Stable | Vidéo, chaîne, recherche, commentaires, export CSV |
| **Twitter / X** | ✅ Stable | Profil, tweets, thread, transcript, communautés, scrape complet, export CSV/JSON |
| **Reddit** | ✅ Stable | Posts et threads |
| **Snapchat** | 🚧 En cours | Profil, stories, spotlight |
| **LinkedIn** | 🚧 En cours | — |

## Démarrage rapide

```bash
git clone https://github.com/kobbi-eya/Scraper_Hub.git
cd Scraper_Hub
pip install -r requirements.txt
python main.py
```

L'API tourne alors sur `http://localhost:8000`. Documentation interactive disponible sur :
- Swagger UI : `http://localhost:8000/docs`
- ReDoc : `http://localhost:8000/redoc`

### Windows

Un script `setup.bat` est fourni pour installer les dépendances automatiquement.

## Exemples d'utilisation

```bash
# Récupérer les infos d'une vidéo YouTube
curl "http://localhost:8000/youtube/video?url=https://youtube.com/watch?v=XXXX"

# Récupérer les commentaires (20 derniers)
curl "http://localhost:8000/youtube/comments?url=https://youtube.com/watch?v=XXXX&limit=20"

# Profil Twitter/X
curl "http://localhost:8000/twitter/profile?username=elonmusk"

# Export CSV des tweets d'un compte
curl "http://localhost:8000/twitter/export/csv?username=elonmusk" -o tweets.csv
```

## Endpoints principaux

<details>
<summary><b>YouTube</b></summary>

- `GET /youtube/video?url=...`
- `GET /youtube/channel?url=...&limit=10`
- `GET /youtube/search?q=...&limit=10`
- `GET /youtube/comments?url=...&limit=20`
- `GET /youtube/*/export` (CSV)
</details>

<details>
<summary><b>Twitter / X</b></summary>

- `GET /twitter/profile?username=...`
- `GET /twitter/user/tweets?username=...`
- `GET /twitter/tweet/{id}`
- `GET /twitter/transcript/{id}`
- `GET /twitter/community/{id}`
- `GET /twitter/community-tweets/{id}`
- `GET /twitter/start-full-scrape?username=...`
- `GET /twitter/export/csv?username=...`
- `GET /twitter/export/json?username=...`
</details>

<details>
<summary><b>Snapchat (WIP)</b></summary>

- `GET /snapchat/profile?username=...`
- `GET /snapchat/stories?username=...`
- `GET /snapchat/spotlight?q=...&limit=10`
</details>

## Stack technique

- **FastAPI** — framework API, léger et rapide
- **yt-dlp** — extraction YouTube
- **youtube-comment-downloader** — commentaires YouTube
- **anyio** — exécution concurrente des scrapers (jusqu'à 200 threads simultanés)

## Configuration

Le projet utilise `pydantic-settings` : toute configuration sensible (clés, tokens, cookies) doit être placée dans un fichier `.env` à la racine, **jamais commitée**. Voir `.env.example` *(à ajouter)* pour la liste des variables attendues.

## Roadmap

- [ ] Finaliser le scraper Snapchat
- [ ] Ajouter le scraper LinkedIn
- [ ] Authentification par clé API pour l'usage public
- [ ] Rate limiting configurable
- [ ] Dockerfile + docker-compose
- [ ] Tests automatisés (pytest)

## Contribuer

Les PR sont bienvenues. Pour les gros changements, ouvre d'abord une issue pour en discuter.

```bash
git checkout -b feature/ma-fonctionnalite
git commit -m "Ajout: ma fonctionnalité"
git push origin feature/ma-fonctionnalite
```

## Avertissement légal

Ce projet interroge des données publiques de plateformes tierces. L'utilisateur est seul responsable du respect des conditions d'utilisation de chaque plateforme (YouTube, X, Reddit, Snapchat, LinkedIn) et des réglementations applicables (RGPD notamment) dans son usage de l'API.

## Licence

MIT — voir [LICENSE](LICENSE).

## Soutenir le projet

Si Scraper Hub te fait gagner du temps, une ⭐ sur le repo aide énormément à sa visibilité. Pour soutenir le développement continu : [GitHub Sponsors](https://github.com/sponsors/kobbi-eya) *(à activer)*.
