# 🚀 Capsy-Odoo API - Documentation Complète

## 📜 1. Qu'est-ce que l'API Capsy-Odoo ?

L'API Capsy-Odoo est une interface middleware haute performance développée avec le framework **FastAPI (Python)**. Elle sert de pont de communication bidirectionnel entre l'écosystème **Capsy** et votre ERP **Odoo**.

Son rôle principal est de simplifier, sécuriser et automatiser les échanges de données sans avoir à manipuler la complexité technique native d'Odoo (protocoles XML-RPC/JSON-RPC).

---

## 🔐 2. Configuration de connexion

Les paramètres de connexion sont chargés **dynamiquement** depuis le fichier `.env` au démarrage du serveur. La documentation interactive (Swagger `/docs`) affiche automatiquement les valeurs actives.

| Variable | Description | Exemple |
| :--- | :--- | :--- |
| `ODOO_URL` | URL complète de l'instance Odoo | `https://capsy1-test-gerard.odoo.com` |
| `ODOO_DB` | Nom de la base de données Odoo | `capsy1-test-gerard` |
| `ODOO_USERNAME` | Email de l'utilisateur Odoo | `gerardcubakabisimwa@gmail.com` |
| `ODOO_PASSWORD` | Mot de passe ou clé API Odoo | `****` |

> ⚠️ **Ne jamais commiter le fichier `.env`**. Il est exclu du dépôt via `.gitignore`.  
> Créez un fichier `.env.example` avec des valeurs fictives pour documenter la structure.

---

## 🎯 3. À quoi ça sert ? (Cas d'usage)

### 🔓 Libérer la donnée Odoo

Grâce à cette API, vous pouvez extraire vos informations Odoo (Clients, Devis, Stocks, Employés) pour les afficher dans n'importe quel autre outil (un site web personnalisé, une application mobile, ou un chatbot IA comme Capsy).

### ⚡ Automatisation des Processus

* **Synchronisation en temps réel** : Automatisez la création de contacts ou de pistes (leads) depuis vos formulaires externes.
* **Gestion simplifiée** : Permettez à des services tiers de modifier des enregistrements (ex: mise à jour d'une feuille de temps ou validation de congés).

### 🤖 Intelligence Artificielle (Capsy Integration)

Cette API est le "système nerveux" qui permet à **Capsy AI** d'interagir avec votre entreprise. L'IA peut lire les données pour répondre aux questions des employés ou écrire dans Odoo pour exécuter des tâches administratives.

---

## 🛠️ 4. Fonctionnement Technique

L'API repose sur trois piliers :

1. **FastAPI** : Fournit une documentation interactive (Swagger) et des performances asynchrones exceptionnelles.
2. **OdooRPC** : Une couche de communication robuste qui utilise le protocole JSON-RPC de manière sécurisée (SSL).
3. **Mapping Dynamique** : Chaque endpoint (ex: `/sales/`) est dynamiquement lié à son équivalent technique dans Odoo (ex: `sale.order`).

---

## 📂 5. Structure des Méthodes

Pour chaque application (24 modules disponibles), l'API implémente trois types d'actions :

| Action | Méthode HTTP | Description |
| :--- | :--- | :--- |
| **Lire** | `GET` | Récupère la liste des éléments ou un élément précis. Supporte la pagination. |
| **Écrire** | `POST` | Crée un nouvel enregistrement dans Odoo (ex: nouveau contact). |
| **Modifier** | `PUT` | Met à jour les champs d'un enregistrement existant. |

---

## 🔐 6. Authentification & Connexion des Utilisateurs (`/login`)

L'API fournit un endpoint universel permettant aux utilisateurs Odoo de Capsy de s'authentifier de manière dynamique :

*   **Endpoint** : `/login`
*   **Méthode** : `POST`
*   **Payload** :
    ```json
    {
      "username": "email@example.com",
      "password": "mot_de_passe_ou_cle_api",
      "db": "capsy1-test-gerard", // Optionnel (prend la valeur du .env par défaut)
      "url": "https://capsy1-test-gerard.odoo.com" // Optionnel (prend la valeur du .env par défaut)
    }
    ```
*   **Réponse en cas de succès (`200 OK`)** :
    ```json
    {
      "status": "success",
      "message": "Connexion réussie à l'instance Odoo",
      "uid": 2,
      "username": "email@example.com",
      "name": "Nom de l'utilisateur",
      "company": "Nom de l'entreprise",
      "instance": "https://capsy1-test-gerard.odoo.com",
      "database": "capsy1-test-gerard"
    }
    ```

---

## 🚑 7. Aide au dépannage (Troubleshooting)

Si vous recevez une erreur **500 (Internal Server Error)** :

* **Authentification** : Vérifiez vos identifiants dans le fichier `.env`. L'instance active et l'utilisateur sont affichés dans la description de `/docs`.
* **Droits d'accès** : L'utilisateur Odoo défini dans `ODOO_USERNAME` doit avoir les droits de lecture/écriture sur les modules concernés (Contacts, CRM, etc.).
* **Modules installés** : L'API essaie d'accéder à des modèles (ex: `hr.employee`). Si le module "Employés" n'est pas installé sur l'instance définie dans `ODOO_URL`, Odoo renverra une erreur.

---

## 🔒 8. Sécurité

L'API utilise un fichier `.env` pour ne jamais exposer vos secrets dans le code source. Dans un environnement de production, il est recommandé d'ajouter une couche d'authentification (OAuth2 ou API Key) entre Capsy et cette API.
