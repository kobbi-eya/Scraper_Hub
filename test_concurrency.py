"""
test_concurrency.py
====================
Vérifie que le serveur sert plusieurs clients en parallèle sans se geler.

Usage :
    python test_concurrency.py

Principe : on appelle N routes en même temps (via un ThreadPoolExecutor côté
client) et on compare le "temps mur" (wall time) total au temps de la requête
individuelle la plus lente. Si le serveur traite les requêtes en série
(bug de concurrence), le temps mur ≈ somme des temps individuels.
Si le serveur traite en parallèle (comportement attendu), le temps mur ≈
temps de la requête la plus lente (+ une petite marge).
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_URL = "http://127.0.0.1:8000"

# Routes légères qui ne nécessitent pas d'accès réseau externe réel,
# utiles pour valider uniquement l'architecture de concurrence du serveur.
REQUESTS = [
    ("root",           "GET", "/"),
    ("twitter_status",  "GET", "/twitter/auth/status"),
    ("snapchat_docs",   "GET", "/docs"),
    ("reddit_docs",     "GET", "/redoc"),
    ("root_2",          "GET", "/"),
    ("twitter_status_2","GET", "/twitter/auth/status"),
]


def call(name, method, path):
    t0 = time.perf_counter()
    try:
        r = requests.request(method, BASE_URL + path, timeout=30)
        dt = time.perf_counter() - t0
        return name, r.status_code, dt, None
    except Exception as e:
        dt = time.perf_counter() - t0
        return name, None, dt, str(e)


def main():
    print(f"→ Envoi de {len(REQUESTS)} requêtes en parallèle vers {BASE_URL} ...\n")
    t_start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=len(REQUESTS)) as pool:
        futures = [pool.submit(call, *r) for r in REQUESTS]
        for f in as_completed(futures):
            results.append(f.result())
    wall_time = time.perf_counter() - t_start

    results.sort(key=lambda r: r[2])
    for name, status, dt, err in results:
        tag = f"HTTP {status}" if err is None else f"ERREUR: {err}"
        print(f"  {name:<20} {dt:6.3f}s   {tag}")

    slowest = max(r[2] for r in results)
    print(f"\nTemps mur total      : {wall_time:.3f}s")
    print(f"Requête la plus lente : {slowest:.3f}s")

    if wall_time <= slowest * 1.5:
        print("\n✅ Les requêtes semblent traitées EN PARALLÈLE (temps mur ≈ requête la plus lente).")
    else:
        print("\n⚠️  Les requêtes semblent traitées EN SÉRIE (temps mur ≈ somme des requêtes).")
        print("   → il pourrait rester un point de blocage (async def sans threadpool, verrou global, etc.)")


if __name__ == "__main__":
    main()