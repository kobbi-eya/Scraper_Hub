# 🕷️ Scraper Hub

API **FastAPI** multi-plateformes pour collecter des données publiques (profils, publications, commentaires, stories…) depuis **YouTube**, **Twitter/X**, **Snapchat**, **Reddit** et **LinkedIn**, avec export en CSV/JSON.

> ⚠️ **Usage responsable** : projet à visée éducative et de recherche. Respectez les conditions d'utilisation de chaque plateforme, la législation sur les données personnelles (RGPD, etc.) et la vie privée des personnes. Ne republiez pas de données scrapées.

## Plateformes supportées

| Plateforme | Préfixe | Statut |
|---|---|---|
| YouTube | `/youtube` | ✅ Opérationnel |
| Twitter/X | `/twitter` | ✅ Opérationnel |
| Snapchat | `/snapchat` | 🔧 En cours |
| LinkedIn | `/linkedin` | 🔧 En cours |
| Reddit | `/reddit` | 🔧 Routeur présent |

## Fonctionnalités

- Une API unique, une route par plateforme, documentation interactive Swagger (`/docs`) et ReDoc (`/redoc`)
- Routes synchrones exécutées dans le threadpool `anyio` (limite portée à 200 threads) pour servir plusieurs clients en parallèle malgré les appels réseau bloquants
- Export des résultats en **CSV** et **JSON** (dossier `exporters/`)
- Configuration par variables d'environnement (`pydantic-settings`)
- CORS ouvert par défaut (à restreindre en production)

## Structure du projet

```
Scraper_Hub/
├── main.py            # Point d'entrée FastAPI, monte les routers (aucune logique métier)
├── config.py          # Configuration, lit le fichier .env
├── routers/           # Endpoints HTTP par plateforme
├── services/          # Logique de scraping par plateforme
├── exporters/         # Export CSV / JSON
├── requirements.txt   # Dépendances
├── .env.example       # Modèle de configuration
└── .gitignore
```

## Installation

**Prérequis** : Python 3.10+ et `pip`.

```bash
git clone https://github.com/kobbi-eya/Scraper_Hub.git
cd Scraper_Hub

python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env             # Windows : copy .env.example .env
```

## Configuration

Renseignez vos valeurs dans `.env` :

| Variable | Description |
|---|---|
| `AUTH_TOKEN` | Cookie `auth_token` d'une session Twitter/X |
| `CT0` | Cookie `ct0` d'une session Twitter/X |
| `TWITTER_BEARER` | Bearer token utilisé pour les requêtes Twitter/X |

> 🔒 Ne commitez jamais `.env`. Utilisez un compte dédié, pas votre compte principal. Si un secret a fuité, révoquez-le.

Récupérer `auth_token` et `ct0` : connectez-vous à x.com → outils de développement → *Application* → *Cookies* → `https://x.com`.

## Lancement

```bash
uvicorn main:app --reload --port 8000
# ou
python main.py
```

- API : http://localhost:8000
- Swagger : http://localhost:8000/docs
- ReDoc : http://localhost:8000/redoc

## Endpoints

### YouTube (`/youtube`)

| Route | Description |
|---|---|
| `GET /youtube/video?url=...` | Infos d'une vidéo |
| `GET /youtube/channel?url=...&limit=10` | Vidéos d'une chaîne |
| `GET /youtube/search?q=...&limit=10` | Recherche |
| `GET /youtube/comments?url=...&limit=20` | Commentaires d'une vidéo |
| `GET /youtube/*/export` | Export CSV |

### Twitter/X (`/twitter`)

| Route | Description |
|---|---|
| `GET /twitter/profile?username=...` | Profil |
| `GET /twitter/user/tweets?username=...` | Tweets d'un utilisateur |
| `GET /twitter/tweet/{id}` | Détail d'un tweet |
| `GET /twitter/transcript/{id}` | Transcription |
| `GET /twitter/community/{id}` | Infos d'une communauté |
| `GET /twitter/community-tweets/{id}` | Tweets d'une communauté |
| `GET /twitter/start-full-scrape?username=...` | Scraping complet d'un compte |
| `GET /twitter/export/csv?username=...` | Export CSV |
| `GET /twitter/export/json?username=...` | Export JSON |

### Snapchat (`/snapchat`) — en cours

| Route | Description |
|---|---|
| `GET /snapchat/profile?username=...` | Profil public |
| `GET /snapchat/stories?username=...` | Stories publiques |
| `GET /snapchat/spotlight?q=...&limit=10` | Recherche Spotlight |

### Exemple

```bash
curl "http://localhost:8000/youtube/search?q=python&limit=5"
```

## Stack technique

FastAPI · Uvicorn · pydantic-settings · requests · yt-dlp · youtube-comment-downloader

## Bonnes pratiques

- Ne versionnez pas les données scrapées (`*.json` de sortie, `cache/`, `checkpoints/`).
- Limitez la cadence des requêtes pour éviter les blocages.
- Restreignez `allow_origins` (CORS) avant tout déploiement public.

## Contribuer

Forkez le dépôt, créez une branche, puis ouvrez une pull request.

 
