# 🧪 Pharmexam

> Application web de gestion des surveillances d’examens universitaires  
> Développée avec **Django (Python)**

---

## 📖 Description

**Pharmexam** est une application web permettant d’optimiser l’organisation et le suivi des surveillances d’examens.

Elle assure :

- La gestion des années universitaires
- La gestion des sessions d’examens
- La planification des examens
- L’affectation des salles
- L’inscription des surveillants
- Le suivi des heures effectuées
- L’export des données au format Excel

Le système garantit automatiquement :

- ✅ Respect des capacités des salles  
- ✅ Absence de conflits horaires  
- ✅ Respect des quotas de surveillants  
- ✅ Cohérence des responsables pédagogiques  

---

## 🔐 Authentification & Rôles

Le système gère plusieurs types d’utilisateurs :

| Rôle | Description |
|------|------------|
| SCOLARITE | Gestion administrative |
| ENSEIGNANT | Responsable pédagogique |
| MEMBRE_POOL | Surveillant |

Les administrateurs parmis ces utilisateurs disposent de permissions étendues.

---

## 🗓 Organisation Académique

### Année Universitaire
- Une année universitaire active doit être sélectionnée.
- Les sessions d’examens sont rattachées à une année universitaire.

### Session d’Examens
- Création / suppression par un administrateur.
- Contient plusieurs examens.

---

## 📝 Gestion des Examens

### Création (`INITIE`)

Un examen doit obligatoirement comporter :

- Nom
- UP concernée
- UE de rattachement
- Responsable (appartenant aux responsables de l’UE)
- Nombre total d’élèves
- Nombre d’élèves avec tiers temps
- Nombre de surveillants requis
- Date
- Heure de début
- Heure de fin

---

### États d’un examen

| Statut | Condition |
|--------|----------|
| INITIE | Examen créé |
| INCOMPLET | Données ou affectations manquantes |
| COMPLET | Toutes les contraintes respectées |
| TERMINE | Heure de fin dépassée |

Un examen est **COMPLET** lorsque :

- Les salles sont affectées
- Une salle tiers temps est définie (si nécessaire)
- Tous les surveillants requis sont inscrits
- La capacité totale couvre tous les candidats

---

## 🏫 Règles d’Affectation des Salles

- Un examen peut utiliser plusieurs salles
- Capacité totale ≥ nombre total d’étudiants
- Aucune salle ne peut être utilisée sur deux examens simultanément
- Les conflits de planning sont bloqués

---

## 👥 Inscription des Surveillants

Un utilisateur peut s’inscrire si :

- Le quota maximum n’est pas atteint
- Il est disponible sur le créneau

---

## 📊 Suivi des Activités

L’onglet **Suivi** permet d’afficher pour chaque utilisateur :

- Nombre d’examens surveillés
- Nombre total d’heures effectuées

---

## 📤 Export des Données

Export au format **Excel** pour :

- Une session d’examens
- Une année universitaire complète

---
