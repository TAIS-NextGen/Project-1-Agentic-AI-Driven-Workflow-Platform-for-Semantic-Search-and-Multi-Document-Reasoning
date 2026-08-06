# Amélioration du front-end et nouveaux nœuds

## 1. Améliorations de l’éditeur de workflow

L’éditeur a été modernisé afin d’être plus flexible, interactif et lisible :

- bibliothèque de nœuds avec recherche et filtrage par catégorie ;
- ajout par clic ou glisser-déposer sur le canvas ;
- déplacement des nœuds avec alignement optionnel sur la grille ;
- zoom centré sur le curseur avec `Ctrl + molette` ;
- déplacement du canvas avec la molette ;
- mini-carte interactive ;
- organisation automatique des nœuds ;
- fonction « Fit view » pour recentrer le workflow ;
- panneau latéral repliable ;
- affichage des ports, des types d’entrée/sortie et du statut d’exécution ;
- panneau de configuration enrichi avec chargement de fichier et test réel du nœud ;
- résultats affichés directement : aperçu de l’image, texte extrait, métadonnées et données structurées ;
- quatre workflows de démarrage : Invoice OCR, Image cleanup, Parse documents et RAG Search.

## 2. Nœud Contrast Enhancer

### Contrat

- Type : `contrast-enhancer`
- Entrée : `image`
- Sorties : `image`, `metadata`
- Formats : PNG, JPEG, TIFF, BMP et WebP

### Paramètres

- contraste ;
- luminosité ;
- netteté ;
- contraste automatique ;
- pourcentage de coupure des pixels extrêmes ;
- taille maximale du fichier.

### API/bibliothèque utilisée

Le nœud utilise **Pillow**, une bibliothèque Python locale de traitement d’image :

- `ImageOps.autocontrast` pour étendre automatiquement la plage tonale ;
- `ImageEnhance.Contrast` pour régler le contraste ;
- `ImageEnhance.Brightness` pour régler la luminosité ;
- `ImageEnhance.Sharpness` pour améliorer la netteté ;
- `ImageStat` pour mesurer la luminosité moyenne avant et après le traitement.

### Pourquoi ce choix ?

Pillow est rapide, stable et adapté à ce traitement déterministe. Il fonctionne localement, sans clé API, sans quota et sans envoyer les documents vers un service externe. Cela réduit les coûts, améliore la confidentialité et rend les tests reproductibles. Le résultat est enregistré en PNG afin de fournir une sortie homogène aux nœuds suivants, notamment l’OCR.

## 3. Nœud Document Parser

### Contrat

- Type : `document-parser`
- Entrée : `document`
- Sorties : `text`, `data`, `metadata`
- Formats : PDF, DOCX, XLSX, XLSM, CSV, TXT et Markdown

Les anciens formats binaires `.doc` et `.xls` ne sont pas lus directement. Le nœud renvoie un message demandant une conversion vers DOCX ou XLSX.

### API/bibliothèques utilisées

Le nœud utilise une API locale spécialisée pour chaque format :

- **pypdf** avec `PdfReader` pour extraire le texte page par page des PDF textuels ;
- **python-docx** pour lire les paragraphes et les tableaux Word ;
- **openpyxl** avec `load_workbook(read_only=True, data_only=True)` pour lire les feuilles Excel en limitant l’utilisation mémoire ;
- les modules standards Python `csv` et `pathlib` pour CSV, TXT et Markdown.

### Pourquoi ce choix ?

Une bibliothèque spécialisée par format donne une extraction plus précise et plus structurée qu’un convertisseur générique. Le traitement reste local, gratuit et testable. Le mode lecture seule d’openpyxl permet de gérer des classeurs volumineux, tandis que `data_only=True` retourne les valeurs calculées plutôt que les formules lorsque le classeur les contient.

`pypdf` extrait le texte déjà présent dans un PDF. Un PDF scanné sans couche texte doit d’abord passer par un nœud OCR. Le workflow recommandé est alors :

`Document Input → Contrast Enhancer → OCR → Output`

Pour les documents numériques :

`Document Input → Document Parser → Text Splitter → Output`

## 4. API de test depuis le front-end

Le bouton **Test Node** réutilise l’endpoint backend existant :

`POST /api/workflows/execute`

Le front construit temporairement un workflow contenant uniquement le nœud sélectionné et sa configuration. Cette approche évite de créer une seconde logique d’exécution et garantit que le test utilise exactement le même moteur que le workflow complet.

Les fichiers sont envoyés par :

`POST /api/documents/upload`

Le `file_id` retourné est injecté dans la configuration du nœud avant le test.

## 5. Tests ajoutés

Tests unitaires :

```bash
pytest -q \
  backend/tests/nodes/preprocessing/test_contrast_enhancer.py \
  backend/tests/nodes/ingestion/test_document_parser.py
```

Tests autonomes :

```bash
python backend/test_contrast_enhancer_e2e.py
python backend/test_document_parser_e2e.py
```

Les tests couvrent notamment :

- amélioration et génération d’une image PNG ;
- conservation de la transparence ;
- validation des formats et de la taille ;
- extraction DOCX avec tableau ;
- extraction XLSX avec données structurées ;
- extraction PDF textuel ;
- rejet explicite des anciens formats non pris en charge.

## 6. Dépendances ajoutées

```toml
Pillow>=10.0.0
pypdf>=5.0.0
python-docx>=1.1.0
openpyxl>=3.1.0
```

Installation backend :

```bash
cd backend
pip install -e ".[dev]"
```

Lancement backend :

```bash
uvicorn backend.main:app --reload
```

Lancement front-end :

```bash
cd frontend
npm install
npm run dev
```

## 7. Correctifs workflow et documents

### Nouveau workflow vide

Le store du canvas démarre maintenant avec `nodes: []` et `edges: []`. Le bouton **New Workflow** :

1. remet le canvas à zéro ;
2. crée une nouvelle entrée persistante ;
3. ouvre l’éditeur vide.

Les workflows d’exemple restent disponibles dans la bibliothèque, mais ils ne sont chargés que lorsque l’utilisateur clique explicitement sur un modèle.

### Historique réel des workflows

Les workflows sont sauvegardés dans le `localStorage` avec Zustand Persist. Chaque entrée conserve :

- le nom ;
- les nœuds et leur configuration ;
- les connexions ;
- la position et le zoom du canvas ;
- la date de création et de modification ;
- le nombre d’exécutions.

La page **Workflow history** permet de rechercher, ouvrir, dupliquer et supprimer les workflows. Cet historique est propre au navigateur utilisé.

### Bibliothèque de documents fonctionnelle

Endpoints ajoutés :

```text
GET    /api/documents
POST   /api/documents/upload
POST   /api/documents/upload/batch
POST   /api/documents/import-url
GET    /api/documents/{file_id}
GET    /api/documents/{file_id}/download
DELETE /api/documents/{file_id}
```

Les métadonnées sont conservées dans `data/uploads/.documents-index.json`. Le nœud `Document Input` utilise le `file_id` réel renvoyé par le backend et peut donc fournir le document aux nœuds suivants pendant l’exécution.

L’import cloud disponible immédiatement utilise une URL HTTP(S) publique directe. Les adresses privées et locales sont bloquées. Google Drive et OneDrive ne sont plus affichés comme connectés sans authentification : une intégration complète demanderait OAuth.

### Exécution sans faux résultat

L’ancien fallback simulé du front-end a été supprimé. Lorsque le backend est indisponible ou qu’un nœud échoue, l’exécution est marquée en erreur et le message réel est affiché. Aucun résultat fictif n’est généré.

### Démarrage Windows

Le fichier `run.bat` à la racine :

- vérifie Python et Node.js ;
- crée `.venv` ;
- installe `backend/requirements.txt` si nécessaire ;
- installe les dépendances npm si Vite manque ;
- configure l’URL du backend ;
- lance le backend et le front-end dans deux terminaux.

## 8. Validation des correctifs

Commande exécutée :

```bash
pytest -q \
  backend/tests/api/test_documents_api.py \
  backend/tests/nodes/ingestion/test_document_upload.py \
  backend/tests/nodes/ingestion/test_document_parser.py \
  backend/tests/nodes/preprocessing/test_contrast_enhancer.py
```

Résultat : **20 tests réussis**. Les tests couvrent l’upload local, l’upload multiple, le rejet d’une URL privée, l’import cloud simulé, la liste, le téléchargement, la suppression et l’exécution du nœud Document Upload avec un vrai `file_id`.
