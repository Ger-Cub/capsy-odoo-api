# 🚀 Capsy-Odoo & KoboToolbox API Bridge

Passerelle middleware haute performance basée sur **FastAPI** permettant d'interagir avec votre ERP **Odoo** et vos bases de données **KoboToolbox**.

---

## ⚡ 1. Utilisation Quotidienne (Chaque fois que vous travaillez)

À chaque fois que vous souhaitez lancer le projet en local, il vous suffit d'exécuter :

```bash
# 1. Activer l'environnement virtuel
source venv/bin/activate

# 2. Démarrer le serveur API
python main.py
```
*(Le serveur sera disponible sur **`http://localhost:8000`**)*

---

## 🛠️ 2. Installation Initiale (Une seule fois au début)

Vous n'avez besoin d'exécuter `pip install -r requirements.txt` que **la première fois** ou si de nouvelles dépendances sont ajoutées.

### 1. Accéder au projet
```bash
cd capsy-odoo-api
```

### 2. Créer et activer l'environnement virtuel
```bash
# Sur Linux / macOS :
python3 -m venv venv
source venv/bin/activate

# Sur Windows (PowerShell) :
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances (*Une seule fois*)
```bash
pip install -r requirements.txt
```

### 4. Configurer le fichier d'environnement (`.env`)
```env
ODOO_URL=https://testjack.odoo.com
ODOO_DB=testjack
ODOO_USERNAME=votre_email@example.com
ODOO_PASSWORD=votre_mot_de_passe
ID_DB_KOBOTOOLBOX=votre_id_kobotoolbox
```

### 5. Démarrer le serveur API
```bash
python main.py
# ou avec hot-reload :
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Tester les endpoints
```bash
python test_api.py
```


---

## 📚 Documentation & Liens
* 🌐 **Swagger UI Interactif (avec Cadenas 🔒 pour identifiants)** : [http://localhost:8000/docs](http://localhost:8000/docs)
* 📖 **Documentation Web HTML** : [http://localhost:8000/documentation](http://localhost:8000/documentation)
* 📄 **Documentation Markdown détaillée** : [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)
