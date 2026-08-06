# FlowDocs — Comparison Agent V13

## Objectif

Le nœud **Comparison Agent** compare deux documents complets et affiche :

- les contenus ajoutés ;
- les contenus supprimés ;
- les contenus modifiés ;
- le pourcentage de similarité ;
- les lignes ou paragraphes concernés dans chaque document.

Le workflow recommandé est :

```text
Document Input (version originale) ─┐
                                    ├─→ Comparison Agent
Document Input (nouvelle version) ──┘
```

Le premier document connecté devient **Original Document**. Le deuxième devient **Document to Compare**. Un workflow de démarrage **Compare documents** est également disponible dans l’éditeur.

## Formats pris en charge

- PDF avec couche texte ;
- DOCX ;
- XLSX et XLSM ;
- CSV ;
- TXT ;
- Markdown.

Un PDF scanné sans couche texte doit d’abord passer par un OCR.

## Configuration

La configuration reste volontairement simple :

### Comparison detail

- **Line by line** : comparaison ligne par ligne, recommandée dans la majorité des cas ;
- **Paragraph by paragraph** : regroupe les différences par blocs de texte.

### Ignore spacing differences

Ignore les différences produites uniquement par l’indentation, les espaces multiples ou les retours de mise en forme.

### Ignore upper/lower case

Considère par exemple `Document` et `document` comme identiques.

### Create downloadable reports

Génère quatre sorties téléchargeables :

- JSON structuré ;
- diff texte standard ;
- rapport HTML côte à côte ;
- archive ZIP contenant tous les rapports.

## Sorties

```text
Comparison Result
Comparison Summary
Unified Diff
Downloadable Reports
Metadata
```

Le résultat structuré contient notamment :

```json
{
  "summary": {
    "similarity_percent": 84.5,
    "change_block_count": 3,
    "added_units": 1,
    "removed_units": 1,
    "modified_units": 2,
    "unchanged_units": 18
  },
  "changes": [
    {
      "type": "modified",
      "original_start": 4,
      "revised_start": 4,
      "original_text": "Durée : 12 mois",
      "revised_text": "Durée : 24 mois"
    }
  ]
}
```

## Moteur utilisé

Le nœud utilise le module Python standard `difflib` :

- `SequenceMatcher` pour identifier les blocs communs et différents ;
- `unified_diff` pour produire un rapport texte standard ;
- `HtmlDiff` pour générer le rapport côte à côte.

Aucune API cloud, clé ou abonnement n’est nécessaire. Les documents restent sur la machine qui exécute FlowDocs.

L’extraction du contenu réutilise le **Document Parser** existant : pypdf pour PDF, python-docx pour Word, openpyxl pour Excel et le module CSV de Python.

## Limite importante

La comparaison porte sur le **contenu textuel extrait**. Elle détecte correctement les changements de texte et de données, mais elle n’est pas destinée à comparer pixel par pixel la mise en page, les couleurs, les images ou les polices.

## Tests

Les validations ajoutées couvrent :

- les deux entrées document obligatoires ;
- les ajouts, suppressions et modifications ;
- l’ignorance des espaces et de la casse ;
- la création des rapports JSON, diff, HTML et ZIP ;
- le cas où un des deux documents manque ;
- la découverte automatique du nœud par le backend.
