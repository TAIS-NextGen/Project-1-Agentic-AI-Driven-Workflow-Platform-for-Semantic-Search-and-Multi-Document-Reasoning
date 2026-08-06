# Démarrage rapide de FlowDocs sous Windows

## Méthode recommandée

1. Décompressez complètement l’archive ZIP.
2. Ouvrez le dossier obtenu.
3. Double-cliquez sur `run.bat`.
4. Laissez ouverts les deux terminaux créés par le script.
5. L’application s’ouvre sur `http://localhost:5173`.

Au premier lancement, le script crée automatiquement `.venv` puis installe les dépendances Python et npm. Les lancements suivants sont plus rapides.

## Prérequis

- Python 3.11 ou plus récent ;
- Node.js 20.19 ou plus récent avec npm ;
- une connexion Internet uniquement pour la première installation des dépendances.

## Utilisation corrigée

- **New Workflow** crée maintenant un workflow réellement vide.
- Le menu **Workflows** ouvre l’historique des workflows sauvegardés dans le navigateur.
- La page **Documents** permet un upload local réel, un upload multiple et un import depuis une URL publique directe.
- Dans un nœud **Document Input**, choisissez un fichier déjà importé ou chargez-en un nouveau.
- Une erreur backend n’est plus remplacée par un faux résultat simulé : l’interface affiche l’erreur réelle.

## Import cloud

L’option **Cloud URL** accepte une URL HTTP(S) publique pointant directement vers un fichier. Google Drive et OneDrive nécessitent une configuration OAuth spécifique ; l’interface ne les présente donc plus comme faussement connectés.
