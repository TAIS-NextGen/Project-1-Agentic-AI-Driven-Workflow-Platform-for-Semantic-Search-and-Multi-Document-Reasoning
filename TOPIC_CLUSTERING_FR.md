# Nœud Topic Clustering — FlowDocs V12

## Objectif

Le workflow recommandé est :

```text
Corpus Input → Topic Clustering
```

**Corpus Input** permet de sélectionner un dossier complet depuis le navigateur. Les fichiers compatibles sont importés ensemble en conservant leur chemin relatif dans le dossier.

**Topic Clustering** parse le contenu de chaque document, regroupe les documents portant sur des thèmes proches et retourne la liste des documents appartenant à chaque cluster.

## Formats pris en charge

- PDF avec couche texte
- DOCX
- XLSX et XLSM
- CSV
- TXT
- Markdown

Un PDF scanné sans couche texte est signalé comme document ignoré. Il doit d'abord passer par un OCR.

## Configuration simplifiée

Le nœud Topic Clustering expose seulement :

- **Number of clusters** : automatique, ou nombre manuel de 2 à 12 ;
- **Create downloadable results** : génération des résultats JSON, CSV et ZIP.

En mode automatique, plusieurs nombres de clusters sont évalués et le meilleur découpage est choisi avec le score de silhouette.

## Sorties

### Topic Clusters

Pour chaque cluster :

- identifiant du cluster ;
- nom généré à partir des mots-clés dominants ;
- mots-clés ;
- nombre de documents ;
- document représentatif ;
- documents du cluster avec leur score de similarité.

### Document Assignments

Une ligne par document avec :

- cluster ;
- nom du thème ;
- nom du fichier ;
- chemin relatif dans le dossier ;
- score de similarité.

### Téléchargements

- JSON complet ;
- CSV des affectations ;
- ZIP contenant les deux fichiers.

## Moteur utilisé

Le traitement est local et utilise :

- les parsers déjà présents dans FlowDocs pour extraire le texte ;
- `TfidfVectorizer` avec mots, expressions et caractères ;
- K-Means ou MiniBatchKMeans selon la taille du corpus ;
- le score de silhouette pour sélectionner automatiquement le nombre de clusters.

Aucune clé API et aucun envoi vers un service cloud ne sont nécessaires.
