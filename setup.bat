@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║        🕷️  Scraper Hub — Setup           ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── Demander le dossier cible ────────────────────────────────────────────────
set /p "TARGET=📁 Dossier d'installation [défaut: scraper_hub] : "
if "!TARGET!"=="" set TARGET=scraper_hub

echo.
echo  ▶ Création de l'architecture dans : !TARGET!\
echo.

:: ── Créer les dossiers ───────────────────────────────────────────────────────
mkdir "!TARGET!"                  2>nul
mkdir "!TARGET!\routers"          2>nul
mkdir "!TARGET!\services"         2>nul
mkdir "!TARGET!\exporters"        2>nul
mkdir "!TARGET!\cache"            2>nul
mkdir "!TARGET!\checkpoints"      2>nul

echo  ✅ Dossiers créés

:: ── Créer les __init__.py vides ──────────────────────────────────────────────
type nul > "!TARGET!\routers\__init__.py"
type nul > "!TARGET!\services\__init__.py"
type nul > "!TARGET!\exporters\__init__.py"

:: ── Créer .env template ──────────────────────────────────────────────────────
(
echo # ── Twitter Auth ^(optionnel, requis pour les Communities^) ────────────
echo AUTH_TOKEN=
echo CT0=
echo.
echo # ── Paramètres optionnels ──────────────────────────────────────────────
echo # TOKEN_POOL_SIZE=6
echo # PAGE_DELAY=0.25
echo # CACHE_TTL_HOURS=12
) > "!TARGET!\.env"

echo  ✅ .env template créé

:: ── Créer .gitignore ─────────────────────────────────────────────────────────
(
echo .env
echo cache/
echo checkpoints/
echo __pycache__/
echo *.pyc
echo .venv/
echo venv/
) > "!TARGET!\.gitignore"

echo  ✅ .gitignore créé

:: ── requirements.txt ─────────────────────────────────────────────────────────
(
echo fastapi^>=0.111.0
echo uvicorn[standard]^>=0.29.0
echo yt-dlp^>=2024.5.1
echo youtube-comment-downloader^>=0.1.68
echo requests^>=2.31.0
echo pydantic-settings^>=2.0.0
) > "!TARGET!\requirements.txt"

echo  ✅ requirements.txt créé

:: ── Fichiers Python vides avec header ────────────────────────────────────────

:: config.py
(
echo # config.py — Settings globaux
echo # Rempli automatiquement depuis le repo ou coller depuis la doc
) > "!TARGET!\config.py"

:: main.py
(
echo # main.py — Point d'entrée FastAPI
echo # Rempli automatiquement depuis le repo ou coller depuis la doc
) > "!TARGET!\main.py"

:: services
(echo # services/youtube_service.py) > "!TARGET!\services\youtube_service.py"
(echo # services/twitter_service.py) > "!TARGET!\services\twitter_service.py"
(echo # services/snapchat_service.py) > "!TARGET!\services\snapchat_service.py"

:: routers
(echo # routers/youtube.py) > "!TARGET!\routers\youtube.py"
(echo # routers/twitter.py) > "!TARGET!\routers\twitter.py"
(echo # routers/snapchat.py) > "!TARGET!\routers\snapchat.py"

:: exporters
(echo # exporters/csv_exporter.py) > "!TARGET!\exporters\csv_exporter.py"
(echo # exporters/__init__.py)     > "!TARGET!\exporters\__init__.py"

echo  ✅ Fichiers Python créés

:: ── Résumé de l'arborescence ─────────────────────────────────────────────────
echo.
echo  📂 Structure créée :
echo.
echo  !TARGET!\
echo  ├── main.py
echo  ├── config.py
echo  ├── requirements.txt
echo  ├── .env
echo  ├── .gitignore
echo  ├── cache\
echo  ├── checkpoints\
echo  ├── routers\
echo  │   ├── __init__.py
echo  │   ├── youtube.py
echo  │   ├── twitter.py
echo  │   └── snapchat.py
echo  ├── services\
echo  │   ├── __init__.py
echo  │   ├── youtube_service.py
echo  │   ├── twitter_service.py
echo  │   └── snapchat_service.py
echo  └── exporters\
echo      ├── __init__.py
echo      └── csv_exporter.py
echo.

:: ── Proposer d'installer les dépendances ─────────────────────────────────────
set /p "INSTALL=📦 Installer les dépendances maintenant ? (o/n) [o] : "
if "!INSTALL!"=="" set INSTALL=o
if /i "!INSTALL!"=="o" (
    echo.
    echo  ▶ Installation des dépendances...
    cd "!TARGET!"
    python -m pip install -r requirements.txt
    cd ..
    echo.
    echo  ✅ Dépendances installées
)

:: ── Instructions finales ─────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  ✅  Architecture prête !                                ║
echo  ║                                                          ║
echo  ║  Prochaines étapes :                                     ║
echo  ║  1. Coller le code dans chaque fichier Python            ║
echo  ║  2. Remplir .env avec AUTH_TOKEN + CT0 si besoin         ║
echo  ║  3. cd !TARGET!                                          ║
echo  ║  4. python main.py                                       ║
echo  ║  5. Ouvrir http://localhost:8000/docs                    ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
pause