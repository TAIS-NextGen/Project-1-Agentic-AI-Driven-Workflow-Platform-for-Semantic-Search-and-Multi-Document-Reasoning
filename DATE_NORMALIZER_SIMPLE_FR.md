# Date Normalizer — configuration simplifiée

## Utilité

Le nœud détecte les dates présentes dans une entrée, puis les convertit dans un format uniforme choisi par l’utilisateur.

Il accepte directement :

- un texte produit par un nœud précédent, par exemple **Document Parser**, **OCR** ou **Text Cleaner** ;
- un document PDF, qui est parsé automatiquement avant la détection des dates ;
- les autres documents déjà pris en charge par le Document Parser, notamment DOCX, XLSX, CSV, TXT et Markdown.

## Configuration visible

Le panneau contient seulement deux paramètres :

1. **Date format**
   - `YYYY-MM-DD`
   - `DD/MM/YYYY`
   - `MM/DD/YYYY`
2. **Replace dates in returned text**
   - activé : le texte est retourné avec les dates remplacées ;
   - désactivé : le texte reste inchangé et seule la liste structurée des dates est retournée.

Lorsqu’une heure est présente, elle est conservée automatiquement.

## Source d’entrée affichée

Le bloc de test autonome a été supprimé.

Le panneau affiche désormais l’entrée réellement connectée :

- pour un document : le nom du fichier et le nœud qui l’a fourni ;
- pour un texte : le nom du nœud qui a produit le texte et le nom de sa sortie.

Exemple :

```text
Input text
Produced by Document Parser · Raw Text
Document Parser
```

Cette présentation de la source est également utilisée pour les autres nœuds du workflow.

## PDF sans couche texte

Un PDF textuel est parsé directement. Pour un PDF scanné ne contenant pas de couche texte, le nœud demande de connecter un nœud OCR avant Date Normalizer.
