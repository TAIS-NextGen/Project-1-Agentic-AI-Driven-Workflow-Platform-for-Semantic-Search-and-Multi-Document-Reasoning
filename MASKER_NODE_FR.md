# Nœud Masker — FlowDocs V11

## Objectif

Le nœud **Masker** reçoit un document dans le workflow, détecte les données sensibles et produit un **nouveau PDF anonymisé**. Le fichier original n’est jamais modifié.

Entrées acceptées :

- un PDF provenant de `Document Input` ou `File Converter` ;
- la sortie texte d’un nœud comme `Document Parser`, à condition que le document source soit encore présent dans la chaîne amont.

Sorties :

- `Masked PDF` : document PDF anonymisé, utilisable par les nœuds suivants ;
- `Masking Report` : nombre d’éléments masqués par catégorie, sans recopier les valeurs sensibles ;
- `Metadata` : informations sur le fichier source, le fichier produit et les pages traitées.

## Configuration du front

La configuration reste volontairement simple :

- Emails ;
- Numéros de téléphone ;
- Identifiants : CIN, passeport, SSN, matricule et ID libellés ;
- Adresses postales ;
- Données financières : IBAN et numéros de carte valides ;
- Adresses IP ;
- Apparence du masque : rectangles noirs ou blancs.

Il n’existe aucun bloc de fichier de test autonome. Le panneau affiche automatiquement le nom du document reçu ou le nom du nœud qui a fourni le texte.

## Fonctionnement PDF

Le traitement utilise **PyMuPDF** :

1. extraction des mots et de leurs coordonnées sur chaque page ;
2. détection locale des catégories activées ;
3. ajout de véritables zones de redaction ;
4. suppression permanente du texte situé sous ces zones ;
5. suppression des métadonnées PDF courantes ;
6. enregistrement d’un nouveau PDF téléchargeable.

Le masque n’est donc pas une simple forme dessinée au-dessus du texte.

## Exemples de workflow

```text
Document Input → Masker → Document Parser
```

```text
Document Input → Document Parser → Masker
```

Dans le second cas, le nœud récupère automatiquement le PDF source depuis la chaîne du workflow et utilise la sortie du parser comme source affichée dans le front.

## PDF scannés

Un PDF scanné sans couche texte ne fournit pas les coordonnées nécessaires. Le nœud affiche alors une erreur claire demandant un traitement OCR qui conserve les positions des mots.

## Test autonome

Depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe backend\test_masker_e2e.py
```
