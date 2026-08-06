# Correction de l'affichage du document d'entrée

Le panneau **Document Parser** n'affiche plus le champ **Standalone test document**.

Il affiche maintenant un bloc en lecture seule **Input document** contenant :

- le nom du fichier choisi dans le nœud `Document Input` ;
- le nom de la dernière version produite par un nœud intermédiaire après une exécution ;
- le nœud source ayant fourni le document.

La recherche remonte automatiquement la chaîne du workflow. Si aucun fichier n'est configuré, le panneau indique :

`No input document selected`

Le fichier doit être choisi dans le nœud `Document Input`, et non dans le `Document Parser`.
