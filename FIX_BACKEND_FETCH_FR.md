# Correction « Backend error: Failed to fetch »

La ligne backend `GET /api/documents HTTP/1.1 200 OK` prouve que l'API répond.
Le bandeau pouvait néanmoins rester visible lorsqu'une première requête échouait pendant le démarrage, puis qu'une seconde réussissait.

Corrections incluses :

- les réponses obsolètes des requêtes concurrentes sont ignorées dans la page Documents ;
- une réussite efface explicitement l'ancienne erreur ;
- `run.bat` attend `/health` avant de démarrer le frontend ;
- `run.bat` attend aussi Vite avant d'ouvrir le navigateur ;
- CORS accepte `localhost` et `127.0.0.1` sur les ports 5173 et 3000.

## Démarrage

Fermez les anciennes fenêtres Backend et Frontend, puis double-cliquez sur `run.bat`.
Le script ne doit ouvrir le navigateur qu'une fois les deux services prêts.
