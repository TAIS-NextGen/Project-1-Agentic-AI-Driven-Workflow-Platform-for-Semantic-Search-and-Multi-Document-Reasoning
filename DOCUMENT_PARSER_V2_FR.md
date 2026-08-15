# Document Parser 1.1 — corrections

## 1. Utilisation automatique du dernier document traité

Le parser ne dépend plus uniquement du champ `file_id` ou d'un port nommé exactement `document`.

Pendant l'exécution, le moteur construit maintenant la lignée des sorties provenant de tous les nœuds en amont. Elle est ordonnée du nœud le plus proche au plus éloigné.

Le Document Parser cherche en priorité :

1. le fichier directement connecté à son entrée ;
2. une sortie de fichier utilisant un autre nom de port ;
3. la sortie du nœud de traitement le plus proche (`cleaned_document`, `converted_path`, `image`, `document`, etc.) ;
4. le `file_id` configuré uniquement comme solution de secours pour un test isolé.

Exemple :

```text
Document Input → File Converter → Watermark Remover → Document Parser
```

Le parser utilise la sortie de **Watermark Remover**, et non le document d'origine.

Les anciennes connexions enregistrées avec les ports génériques `input/output` restent également compatibles.

## 2. Parsing complet du document

Le nouveau paramètre **Parse entire document** est activé par défaut.

Lorsqu'il est actif :

- PDF : toutes les pages sont parcourues ;
- DOCX : les paragraphes et tableaux sont extraits dans leur ordre réel ;
- DOCX : les en-têtes et pieds de page peuvent être inclus ;
- XLSX/XLSM : toutes les feuilles et toutes les lignes sont parcourues ;
- CSV : toutes les lignes sont parcourues ;
- TXT/Markdown : tout le fichier est lu.

Le champ **Maximum rows per sheet** n'est utilisé que si le parsing complet est désactivé.

Les métadonnées retournent maintenant :

```json
{
  "parse_entire_document": true,
  "complete": true,
  "truncated": false,
  "selected_source": "nearest_upstream_artifact"
}
```

Pour les PDF contenant des pages sans couche texte, `requires_ocr` est indiqué dans les métadonnées. Dans ce cas, il faut utiliser un nœud OCR.

## 3. Téléchargement des résultats

Après une exécution réussie, le parser crée trois fichiers :

- le texte complet en `.txt` ;
- les données structurées et métadonnées en `.json` ;
- une archive `.zip` contenant les deux fichiers.

Ils sont accessibles dans l'onglet **Outputs** avec les boutons :

- **Download full TXT** ;
- **Download structured JSON** ;
- **Download complete ZIP**.

L'aperçu affiché dans le panneau est limité à 50 000 caractères pour éviter de bloquer le navigateur. Les fichiers téléchargés contiennent bien le résultat complet.

## 4. Validation réalisée

Les tests couvrent :

- la sélection de la version traitée la plus proche ;
- la compatibilité avec une ancienne connexion `output → document` ;
- un classeur Excel de 5 005 lignes intégralement extrait malgré une ancienne limite configurée à 5 ;
- le mode limité et l'indication `truncated` ;
- l'ordre paragraphes/tableaux dans Word ;
- les en-têtes et pieds de page Word ;
- la génération et le contenu des fichiers TXT, JSON et ZIP ;
- l'upload et l'exécution réelle à travers FastAPI.
