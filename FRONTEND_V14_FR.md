# FlowDocs — amélioration du front V14

Cette version conserve tous les nœuds et le Comparison Agent de la V13 et améliore l’interface générale.

## Mode clair et mode sombre

Un bouton de thème est disponible :

- dans la barre latérale principale ;
- dans la barre supérieure de l’éditeur ;
- sur la page d’accueil ;
- dans la page Settings.

Le choix est sauvegardé dans le navigateur. Le mode clair utilise des fonds blancs et gris très légers, des bordures visibles, un contraste renforcé et des ombres plus discrètes.

## Barre supérieure de l’éditeur

La barre du workflow a été réorganisée :

- nom du workflow modifiable plus lisible ;
- état réel `Saving…` puis `Saved` ;
- compteurs des nœuds, connexions et zoom séparés ;
- outils Snap, Arrange et Fit regroupés ;
- changement de thème accessible directement ;
- bouton Clear accompagné d’une confirmation ;
- bouton Run plus clair avec le nombre de nœuds prêts.

Les nouveaux workflows sont nommés `New workflow`, `New workflow 2`, etc., au lieu de `Untitled Workflow`.

## Lisibilité générale

Le mode clair couvre notamment :

- la navigation principale ;
- la bibliothèque des nœuds ;
- le canvas et sa grille ;
- les cartes des nœuds ;
- le panneau de configuration ;
- l’historique des workflows ;
- la page Documents ;
- le Dashboard ;
- la page Executions ;
- la page d’accueil.

Des styles de focus clavier et une gestion de `prefers-reduced-motion` ont aussi été ajoutés pour l’accessibilité.

## Lancement

Double-cliquer sur `run.bat`. Le lanceur Python fonctionnel des versions précédentes est conservé.
