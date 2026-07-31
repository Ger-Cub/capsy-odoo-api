# 🚀 Capsy-Odoo API - Documentation Complète

## 📜 1. Qu'est-ce que l'API Capsy-Odoo ?

L'API Capsy-Odoo est une interface middleware haute performance développée avec le framework **FastAPI (Python)**. Elle sert de pont de communication bidirectionnel entre l'écosystème **Capsy**, vos formulaires **KoboToolbox** et votre ERP **Odoo**.

Son rôle principal est de simplifier, sécuriser et automatiser les échanges de données sans avoir à manipuler la complexité technique native d'Odoo (protocoles XML-RPC/JSON-RPC) ou de KoboToolbox v2 REST API.

---

## 🔐 2. Configuration de connexion

Les paramètres de connexion sont chargés **dynamiquement** depuis le fichier `.env` au démarrage du serveur. La documentation interactive (Swagger `/docs`) affiche automatiquement les valeurs actives.

| Variable | Description | Exemple |
| :--- | :--- | :--- |
| `ODOO_URL` | URL complète de l'instance Odoo | `https://testjack.odoo.com` |
| `ODOO_DB` | Nom de la base de données Odoo | `testjack` |
| `ODOO_USERNAME` | Email de l'utilisateur Odoo | `utilisateur@example.com` |
| `ODOO_PASSWORD` | Mot de passe ou clé API Odoo | `****` |
| `ID_DB_KOBOTOOLBOX` | Identifiant de l'Asset KoboToolbox par défaut | `votre_id_kobotoolbox` |
| `KOBOTOOLBOX_URL` | URL de base de KoboToolbox | `https://kf.kobotoolbox.org` |
| `KOBOTOOLBOX_TOKEN` | Token d'API KoboToolbox (optionnel si public) | `****` |

> ⚠️ **Ne jamais commiter le fichier `.env`**. Il est exclu du dépôt via `.gitignore`.

---

## 🚀 3. Commandes pour lancer le projet API

### ⚡ A. Utilisation Quotidienne (Chaque fois que vous travaillez)
Vous **n'avez pas** besoin de relancer `pip install` à chaque fois. Il suffit d'exécuter :

```bash
# 1. Activer l'environnement virtuel
source venv/bin/activate

# 2. Lancer le serveur API
python main.py
```
*(Le serveur est accessible sur **`http://localhost:8000`**)*

---

### 🛠️ B. Installation Initiale (Une seule fois au début)
La commande `pip install -r requirements.txt` est à exécuter **une seule fois** lors de l'installation du projet ou si de nouvelles dépendances sont ajoutées.

```bash
# 1. Accéder au projet
cd capsy-odoo-api

# 2. Créer et activer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 3. Installer les dépendances (Une seule fois)
pip install -r requirements.txt

# 4. Démarrer le serveur API
python main.py
# (ou avec hot-reload : uvicorn main:app --reload --host 0.0.0.0 --port 8000)
```

### 🌐 Liens Utiles
* 🌐 **Swagger UI Interactif (avec Cadenas 🔒)** : [http://localhost:8000/docs](http://localhost:8000/docs)
* 📖 **Documentation HTML Capsy** : [http://localhost:8000/documentation](http://localhost:8000/documentation)

---



## 🎯 4. À quoi ça sert ? (Cas d'usage)

### 🔓 Libérer la donnée Odoo & KoboToolbox

Grâce à cette API, vous pouvez extraire vos informations Odoo (Projets, eLearning, Sondages, Live Chat, Contacts, Devis, Stocks, Employés) ainsi que vos collectes de données terrain **KoboToolbox** pour les afficher dans n'importe quel autre outil (site web personnalisé, application mobile, ou chatbot IA Capsy).

### ⚡ Automatisation des Processus

* **Synchronisation en temps réel** : Automatisez la création de projets, cours eLearning, sondages, sessions live chat, ou la remontée des formulaires KoboToolbox.
* **Gestion simplifiée** : Permettez à des services tiers d'effectuer des opérations de lecture, création et modification (`GET`, `POST`, `PUT`).

---

## 📂 5. Structure des Méthodes (Odoo & KoboToolbox)

Pour chaque application (28 modules Odoo disponibles + KoboToolbox), l'API implémente trois types d'actions :

| Action | Méthode HTTP | Description |
| :--- | :--- | :--- |
| **Lire** | `GET` | Récupère la liste des éléments ou un élément précis. |
| **Écrire** | `POST` | Crée un nouvel enregistrement dans Odoo ou KoboToolbox. |
| **Modifier** | `PUT` | Met à jour les champs d'un enregistrement existant. |

---

## 📊 6. Endpoints KoboToolbox (`/kobotoolbox`)

L'API fournit une gestion complète sur les bases de données KoboToolbox :

* `GET /kobotoolbox/` : Lire les soumissions (supporte pagination `limit` & `start`, et `asset_id` personnalisé).
* `GET /kobotoolbox/asset` : Récupérer les métadonnées de la base de données / questionnaire KoboToolbox.
* `GET /kobotoolbox/{submission_id}` : Obtenir une soumission spécifique par son identifiant.
* `POST /kobotoolbox/` : Soumettre / ajouter une nouvelle ligne de données dans KoboToolbox.
* `PUT /kobotoolbox/{submission_id}` : Mettre à jour une soumission existante.


---

## 🔐 7. Authentification & Connexion des Utilisateurs (`/login`)

L'API fournit un endpoint universel permettant aux utilisateurs Odoo de Capsy de s'authentifier de manière dynamique :

*   **Endpoint** : `/login`
*   **Méthode** : `POST`
*   **Payload** :
    ```json
    {
      "username": "email@example.com",
      "password": "mot_de_passe_ou_cle_api",
      "db": "testjack",
      "url": "https://testjack.odoo.com"
    }
    ```

---

## 🚑 8. Aide au dépannage (Troubleshooting)

Si vous recevez une erreur **500 (Internal Server Error)** :

* **Authentification** : Vérifiez vos identifiants dans le fichier `.env` ou via le cadenas 🔒 de Swagger.
* **Droits d'accès** : L'utilisateur Odoo défini dans `ODOO_USERNAME` doit avoir les droits de lecture/écriture/suppression sur les modules concernés (Projets, eLearning, Sondages, Live Chat, etc.).
* **KoboToolbox** : Assurez-vous que l'Asset ID `ID_DB_KOBOTOOLBOX` est valide et accessible.


