from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
# odoorpc remplacé par JSON-RPC httpx natif (branche feature/web-session-auth)
import os
import json
import httpx
from dotenv import load_dotenv


# Chargement des identifiants
load_dotenv()

# Lecture dynamique des variables d'environnement
_ODOO_URL      = os.getenv("ODOO_URL", "https://odoo.example.com")
_ODOO_DB       = os.getenv("ODOO_DB", "")
_ODOO_USERNAME = os.getenv("ODOO_USERNAME", "utilisateur@example.com")
_ODOO_HOST     = _ODOO_URL.replace("https://", "").replace("http://", "").split('/')[0]

security = HTTPBasic(auto_error=False)

app = FastAPI(
    title="🚀 Capsy-Odoo & KoboToolbox API Bridge",
    description=f"""
## 🌉 Connecteur Universel Capsy - Odoo & KoboToolbox

Cette API est une passerelle complète permettant d'interagir de manière fluide avec l'ERP **Odoo ({_ODOO_HOST})** ainsi qu'avec les bases de données de collecte de données **KoboToolbox**.
Elle est conçue pour être consommée par des services tiers, des applications mobiles ou des agents IA (Capsy AI).

### 🔐 Connexion & Authentification :
* **Instance Odoo** : `{_ODOO_URL}`
* **Base de données** : `{_ODOO_DB}`
* **Authentification Swagger (Cadenas 🔒)** : Vous pouvez cliquer sur le bouton **Authorize 🔒** en haut à droite sur Swagger pour utiliser vos propres identifiants Odoo (email & mot de passe). Si le cadenas n'est pas renseigné, les identifiants du fichier `.env` (`{_ODOO_USERNAME}`) seront utilisés par défaut.
* **KoboToolbox** : Chargé dynamiquement depuis la variable d'environnement `ID_DB_KOBOTOOLBOX` ou passé en paramètre `asset_id`.


### 🛠 Fonctionnalités clés :
* **🔌 Connexion Directe Odoo & KoboToolbox** : Accès sécurisé aux modèles Odoo via OdooRPC et à KoboToolbox via son API REST v2.
* **📖 Opérations CRUD Complètes** : Lecture, Création, Modification et Suppression (`GET`, `POST`, `PUT`).
* **🏗 Structure Normalisée** : Réponses JSON uniformes pour tous les modules.

### 📂 Applications & Modules supportés (28 modules Odoo + KoboToolbox) :
* **Communication & Collaboration** : Discussion, Live Chat, Calendrier, Rendez-vous
* **Gestion de Projets & Formation** : Projets, To-do, eLearning, Sondages, Connaissances, Documents, Feuilles de temps, Planning
* **Commerce & Relation Client** : Contacts, CRM, Ventes, Événements
* **Gestion Financière & Opérationnelle** : Comptabilité, Tableaux de bord, Inventaire, Signature
* **Marketing** : Site Web, Marketing Automation, Email Marketing
* **Ressources Humaines** : Employés, Paie, Congés
* **Collecte de Données Terrain** : 📊 **KoboToolbox** (Soumissions, Asset, CRUD complet)
* **Système** : Apps, Paramètres

***Note :*** *En cas d'erreur 401 ou 403, vérifiez vos identifiants dans le cadenas 🔒 de Swagger ou vos droits d'accès Odoo/KoboToolbox.*

---
### 📚 Documentation & Téléchargement :
Vous pouvez consulter ou télécharger la documentation complète de l'API ici :
* **Version Web HTML** : [Consulter la documentation en ligne](/documentation)
* **Documentation technique** : [Télécharger le fichier (API_DOCUMENTATION.md)](https://capsy-odoo-api.vercel.app/docs/API_DOCUMENTATION.md)
""",
    version="4.0.0-session",
    contact={
        "name": "Support Capsy Services",
        "url": "https://capsy-services.vercel.app",
    }
)

# Configuration CORS pour autoriser le port 3000 (React)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modèles de données ---
class ItemBase(BaseModel):
    data: Dict[str, Any]

class ItemResponse(BaseModel):
    id: int
    data: Dict[str, Any]

class OdooLoginRequest(BaseModel):
    username: str
    password: str
    db: Optional[str] = None
    url: Optional[str] = None

# ---------------------------------------------------------------------------
# OdooSession — couche JSON-RPC native async (remplace OdooRPC)
# ---------------------------------------------------------------------------
class OdooSession:
    """Client JSON-RPC léger pour Odoo basé sur httpx AsyncClient.
    Utilise /web/session/authenticate pour obtenir un session_id,
    puis /web/dataset/call_kw pour toutes les opérations métier.
    """
    def __init__(self, base_url: str, db: str, uid: int, session_id: str, username: str):
        self.base_url   = base_url.rstrip("/")
        self.db         = db
        self.uid        = uid
        self.session_id = session_id
        self.username   = username
        self._rpc_id    = 10

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Cookie": f"session_id={self.session_id}",
        }

    async def call_kw(self, model: str, method: str, args: list, kwargs: dict) -> Any:
        self._rpc_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": self._rpc_id,
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs,
            },
        }
        url = f"{self.base_url}/web/dataset/call_kw"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json=payload, headers=self._headers())
        data = r.json()
        if "error" in data:
            msg = data["error"].get("data", {}).get("message") or data["error"].get("message", "Erreur Odoo")
            raise Exception(msg)
        return data.get("result")

    # helpers CRUD (tous async)
    async def search(self, model: str, domain: list, limit: int = 10) -> list:
        return await self.call_kw(model, "search", [domain], {"limit": limit})

    async def read(self, model: str, ids: list, fields: Optional[list] = None) -> list:
        kwargs: Dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        return await self.call_kw(model, "read", [ids], kwargs)

    async def search_read(self, model: str, domain: list, fields: Optional[list], limit: int = 10) -> list:
        kwargs: Dict[str, Any] = {"limit": limit}
        if fields:
            kwargs["fields"] = fields
        return await self.call_kw(model, "search_read", [domain], kwargs)

    async def fields_get(self, model: str) -> dict:
        return await self.call_kw(model, "fields_get", [], {"attributes": ["type"]})

    async def create(self, model: str, vals: dict) -> int:
        return await self.call_kw(model, "create", [vals], {})

    async def write(self, model: str, ids: list, vals: dict) -> bool:
        return await self.call_kw(model, "write", [ids, vals], {})


async def _authenticate(username: str, password: str, url: str, db: str) -> OdooSession:
    """Authentifie via /web/session/authenticate et retourne une OdooSession."""
    auth_url = f"{url.rstrip('/')}/web/session/authenticate"
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {"db": db, "login": username, "password": password},
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(auth_url, json=payload, headers={"Content-Type": "application/json"})

    data = r.json()
    if "error" in data:
        msg = data["error"].get("data", {}).get("message") or data["error"].get("message", "Erreur")
        raise HTTPException(status_code=401, detail=f"Odoo Access Denied pour '{username}': {msg}")

    result = data.get("result", {})
    uid = result.get("uid")
    session_id = result.get("session_id") or r.cookies.get("session_id")

    if not uid or not session_id:
        raise HTTPException(status_code=401, detail="Authentification échouée : identifiants invalides ou base de données incorrecte.")

    return OdooSession(
        base_url=url, db=db, uid=uid,
        session_id=session_id, username=username
    )


async def get_odoo(auth: Optional[HTTPBasicCredentials] = Depends(security)) -> OdooSession:
    """Dependency FastAPI — retourne une OdooSession authentifiée."""
    username = auth.username if (auth and auth.username) else os.getenv("ODOO_USERNAME")
    password = auth.password if (auth and auth.password) else os.getenv("ODOO_PASSWORD")

    if not username or not password:
        raise HTTPException(
            status_code=401,
            detail="Identifiants Odoo requis. Cliquez sur le cadenas 🔒 (Authorize) dans Swagger pour saisir votre email et mot de passe.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return await _authenticate(username, password, _ODOO_URL, _ODOO_DB)


# --- Endpoint de Connexion ---
@app.post("/login", tags=["🔐 Connexion"], summary="Connexion d'un utilisateur Odoo (retourne session_id)")
async def login_odoo(credentials: OdooLoginRequest):
    url_to_use = credentials.url or _ODOO_URL
    db_to_use  = credentials.db  or _ODOO_DB
    session = await _authenticate(credentials.username, credentials.password, url_to_use, db_to_use)
    # Lire le nom complet et la société via call_kw (async)
    try:
        user_data = await session.read("res.users", [session.uid], ["name", "company_id"])
        name    = user_data[0].get("name") if user_data else credentials.username
        company = (user_data[0].get("company_id") or [None, ""])[1] if user_data else ""
    except Exception:

        name, company = credentials.username, ""

    return {
        "status":     "success",
        "message":    "Connexion réussie à l'instance Odoo",
        "uid":        session.uid,
        "username":   credentials.username,
        "name":       name,
        "company":    company,
        "instance":   url_to_use,
        "database":   db_to_use,
        "session_id": session.session_id,
    }


# --- Modèle Signup ---
class OdooSignupRequest(BaseModel):
    name: str
    login: str       # email
    password: str
    db: Optional[str] = None
    url: Optional[str] = None


# --- Modèle Mot de passe oublié ---
class OdooResetPasswordRequest(BaseModel):
    login: str       # email
    db: Optional[str] = None
    url: Optional[str] = None


# --- Endpoint Inscription (Signup) ---
@app.post(
    "/signup",
    tags=["🔐 Connexion"],
    summary="Créer un nouveau compte utilisateur Odoo",
    description="""
Crée un nouveau compte utilisateur sur l'instance Odoo via le mécanisme `web/signup`.

**Paramètres requis :**
- `name` : Nom complet de l'utilisateur
- `login` : Adresse email (identifiant de connexion)
- `password` : Mot de passe (minimum 8 caractères recommandé)

**Note :** L'inscription doit être activée sur l'instance Odoo cible (*Configuration → Général → Permettre l'inscription*).
"""
)
async def signup_odoo(request: OdooSignupRequest):
    url_to_use = request.url or _ODOO_URL
    db_to_use  = request.db  or _ODOO_DB
    signup_url = f"{url_to_use.rstrip('/')}/web/signup"

    payload = {
        "jsonrpc": "2.0",
        "method":  "call",
        "id":      1,
        "params": {
            "db":       db_to_use,
            "login":    request.login,
            "password": request.password,
            "name":     request.name,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                signup_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        data = r.json()

        # Odoo renvoie une erreur JSON-RPC en cas d'échec
        if "error" in data:
            err_data = data["error"].get("data", {})
            msg = err_data.get("message") or data["error"].get("message", "Erreur lors de l'inscription.")
            raise HTTPException(status_code=400, detail=msg)

        result = data.get("result", {})

        # Après inscription réussie, on authentifie pour retourner le session_id
        try:
            session = await _authenticate(request.login, request.password, url_to_use, db_to_use)
            user_data = await session.read("res.users", [session.uid], ["name", "company_id"])
            name    = user_data[0].get("name") if user_data else request.name
            company = (user_data[0].get("company_id") or [None, ""])[1] if user_data else ""
        except Exception:
            name, company, session = request.name, "", None

        return {
            "status":     "success",
            "message":    "Compte créé avec succès.",
            "uid":        session.uid if session else None,
            "username":   request.login,
            "name":       name,
            "company":    company,
            "instance":   url_to_use,
            "database":   db_to_use,
            "session_id": session.session_id if session else None,
        }

    except HTTPException:
        raise
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur de connexion à Odoo : {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur inattendue lors de l'inscription : {str(exc)}")


# --- Endpoint Mot de passe oublié (Reset Password) ---
@app.post(
    "/forgot-password",
    tags=["🔐 Connexion"],
    summary="Demander la réinitialisation du mot de passe",
    description="""
Envoie un email de réinitialisation de mot de passe à l'adresse indiquée via Odoo.

**Paramètre requis :**
- `login` : Adresse email du compte Odoo

**Comportement :**  
Pour des raisons de sécurité, la réponse est identique que l'email existe ou non (prévention de l'énumération de comptes).
L'email de réinitialisation est envoyé directement par Odoo et contient un lien sécurisé valable 24h.
"""
)
async def forgot_password_odoo(request: OdooResetPasswordRequest):
    url_to_use = request.url or _ODOO_URL
    db_to_use  = request.db  or _ODOO_DB
    reset_url  = f"{url_to_use.rstrip('/')}/web/reset_password"

    payload = {
        "jsonrpc": "2.0",
        "method":  "call",
        "id":      2,
        "params": {
            "db":    db_to_use,
            "login": request.login,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                reset_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        data = r.json()

        # On ne lève pas d'erreur si l'email n'existe pas (sécurité anti-énumération)
        if "error" in data:
            err_data = data["error"].get("data", {})
            msg = err_data.get("message") or data["error"].get("message", "")
            # Si c'est une vraie erreur technique on la remonte, sinon réponse générique
            if "SMTP" in msg or "mail" in msg.lower() or "smtp" in msg.lower():
                raise HTTPException(
                    status_code=502,
                    detail="Erreur d'envoi d'email. Veuillez contacter l'administrateur."
                )

        return {
            "status":  "success",
            "message": "Si un compte existe pour cet email, un lien de réinitialisation a été envoyé.",
            "login":   request.login,
        }

    except HTTPException:
        raise
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur de connexion à Odoo : {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur inattendue : {str(exc)}")

# --- Endpoint de la Documentation HTML ---
@app.get("/documentation", response_class=HTMLResponse, tags=["📖 Documentation"], summary="Afficher la documentation complète en HTML")
async def get_documentation():
    try:
        doc_path = os.path.join(os.path.dirname(__file__), "docs", "API_DOCUMENTATION.md")
        with open(doc_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
    except Exception:
        markdown_content = "# Documentation indisponible pour le moment."

    # Code HTML avec un style premium vert (CAPSY Services)
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Documentation API Capsy-Odoo</title>
        <!-- Tailwind CSS -->
        <script src="https://cdn.tailwindcss.com"></script>
        <!-- Google Fonts Outfit -->
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <!-- Marked.js -->
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <!-- FontAwesome -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <!-- Github Markdown CSS -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <style>
            body {{
                font-family: 'Outfit', sans-serif;
                background-color: #f8fafc;
            }}
            .markdown-body {{
                background-color: transparent !important;
                font-family: 'Outfit', sans-serif !important;
            }}
            .markdown-body h1, .markdown-body h2, .markdown-body h3 {{
                border-bottom: 1px solid #e2e8f0 !important;
                font-family: 'Outfit', sans-serif !important;
                font-weight: 800 !important;
                color: #003600 !important;
                padding-bottom: 8px !important;
            }}
            .markdown-body pre {{
                background-color: #0f172a !important;
                border-radius: 12px !important;
                border: 1px solid #1e293b !important;
                padding: 16px !important;
            }}
            .markdown-body code {{
                font-family: monospace !important;
                color: #0f172a;
            }}
            .markdown-body pre code {{
                color: #f8fafc !important;
            }}
            .glass {{
                background: rgba(255, 255, 255, 0.85);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
        </style>
    </head>
    <body class="min-h-screen text-slate-800">
        <!-- Navigation -->
        <nav class="sticky top-0 z-50 glass border-b border-slate-200/50 px-6 py-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="h-10 w-10 rounded-xl bg-gradient-to-tr from-[#003600] to-[#00a847] flex items-center justify-center text-white shadow-md">
                    <i class="fa-solid fa-network-wired fa-lg"></i>
                </div>
                <div>
                    <span class="font-extrabold text-[#003600] tracking-tight text-lg">CAPSY</span><span class="font-bold text-slate-500 text-lg">-ODOO</span>
                    <p class="text-[10px] text-slate-400 font-semibold tracking-wider uppercase">Bridge API</p>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <a href="/docs" class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[#008738] to-[#00a847] text-white rounded-xl text-sm font-bold shadow-md hover:shadow-lg transition-all hover:-translate-y-0.5">
                    <i class="fa-solid fa-code"></i>
                    <span>Interactive Swagger Docs</span>
                </a>
            </div>
        </nav>

        <!-- Contenu principal -->
        <div class="max-w-5xl mx-auto px-4 py-10 sm:px-6 lg:px-8">
            <div class="bg-white rounded-3xl shadow-xl border border-slate-100 p-6 sm:p-12">
                <div id="content" class="markdown-body">
                    <div class="flex justify-center items-center py-20">
                        <i class="fa-solid fa-circle-notch fa-spin fa-2xl text-[#008738]"></i>
                    </div>
                </div>
            </div>
        </div>

        <script>
            document.addEventListener('DOMContentLoaded', () => {{
                const rawMarkdown = {json.dumps(markdown_content)};
                document.getElementById('content').innerHTML = marked.parse(rawMarkdown);
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- Configuration des Modules ---
MODULES_CONFIG = {
    "discussion": {"model": "mail.channel", "label": "Discussion"},
    "calendar": {"model": "calendar.event", "label": "Calendrier"},
    "appointments": {"model": "calendar.appointment.type", "label": "Rendez-vous"},
    "todo": {"model": "project.task", "label": "To-do"},
    "projects": {"model": "project.project", "label": "Projets"},
    "elearning": {"model": "slide.channel", "label": "eLearning"},
    "surveys": {"model": "survey.survey", "label": "Sondages"},
    "livechat": {"model": "im_livechat.channel", "label": "Live Chat"},
    "knowledge": {"model": "knowledge.article", "label": "Connaissances"},
    "contacts": {"model": "res.partner", "label": "Contacts"},
    "crm": {"model": "crm.lead", "label": "CRM"},
    "sales": {"model": "sale.order", "label": "Ventes"},
    "dashboards": {"model": "spreadsheet.dashboard", "label": "Tableaux de bord"},
    "accounting": {"model": "account.move", "label": "Comptabilité"},
    "documents": {"model": "documents.document", "label": "Documents"},
    "timesheets": {"model": "account.analytic.line", "label": "Feuilles de temps"},
    "planning": {"model": "planning.slot", "label": "Planning"},
    "website": {"model": "website", "label": "Site Web"},
    "marketing-automation": {"model": "marketing.campaign", "label": "Marketing Automation"},
    "email-marketing": {"model": "mailing.mailing", "label": "Email Marketing"},
    "events": {"model": "event.event", "label": "Événements"},
    "inventory": {"model": "stock.picking", "label": "Inventaire"},
    "signature": {"model": "sign.request", "label": "Signature"},
    "employees": {"model": "hr.employee", "label": "Employés"},
    "payroll": {"model": "hr.payslip", "label": "Paie"},
    "leave": {"model": "hr.leave", "label": "Congés"},
    "apps": {"model": "ir.module.module", "label": "Apps"},
    "settings": {"model": "res.config.settings", "label": "Paramètres"},
}

# --- Résolution Dynamique des Modèles (Odoo v16 vs v17+) ---
def resolve_model_name(odoo_client, model_name):
    fallbacks = {
        "mail.channel": ["discuss.channel", "mail.channel"],
        "im_livechat.channel": ["im_livechat.channel", "discuss.channel"],
    }
    if model_name in fallbacks:
        for fb in fallbacks[model_name]:
            try:
                # Vérification via fields_get (JSON-RPC safe)
                if session.fields_get(fb):
                    return fb
            except Exception:
                continue
    return model_name

# Cache pour stocker les champs sûrs par modèle
FIELDS_CACHE: Dict[str, list] = {}

def get_safe_fields(session: OdooSession, model_name: str) -> list:
    if model_name not in FIELDS_CACHE:
        try:
            fields_info = session.fields_get(model_name)
            safe_types = {'boolean', 'integer', 'float', 'char', 'text', 'html', 'date', 'datetime', 'selection', 'many2one'}
            FIELDS_CACHE[model_name] = [field for field, info in fields_info.items() if info.get('type') in safe_types]
        except Exception:
            return []
    return FIELDS_CACHE[model_name]

# --- Générateur de Routes ---
def add_module_endpoints(app_instance, module_id, config):
    model_name = config["model"]
    tag = config["label"]
    prefix = f"/{module_id}"

    @app_instance.get(f"{prefix}/", response_model=List[ItemResponse], tags=[tag], summary=f"Lire {tag}")
    async def read_items(limit: int = 10, fields: Optional[str] = None, session: OdooSession = Depends(get_odoo)):
        try:
            resolved_model = resolve_model_name(session, model_name)
            fields_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else get_safe_fields(session, resolved_model)
            try:
                records = session.search_read(resolved_model, [], fields_list or None, limit=limit)
            except Exception:
                records = session.search_read(resolved_model, [], ["id", "display_name"], limit=limit)
            return [{"id": r["id"], "data": r} for r in records]
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "Access Denied" in error_msg or "n'êtes pas autorisé" in error_msg:
                raise HTTPException(status_code=403, detail=f"Accès refusé pour '{tag}' : droits insuffisants sur ce modèle.")
            raise HTTPException(status_code=404, detail=f"Erreur de lecture {tag}: {error_msg}")

    @app_instance.post(f"{prefix}/", response_model=ItemResponse, tags=[tag], summary=f"Écrire (Créer) {tag}")
    async def create_item(item: ItemBase, session: OdooSession = Depends(get_odoo)):
        try:
            resolved_model = resolve_model_name(session, model_name)
            new_id = session.create(resolved_model, item.data)
            return {"id": new_id, "data": item.data}
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "Access Denied" in error_msg:
                raise HTTPException(status_code=403, detail=f"Accès refusé pour '{tag}' : droits insuffisants (création).")
            raise HTTPException(status_code=400, detail=f"Erreur de création {tag}: {error_msg}")

    @app_instance.put(f"{prefix}/{{item_id}}", response_model=ItemResponse, tags=[tag], summary=f"Modifier {tag}")
    async def update_item(item_id: int, item: ItemBase, session: OdooSession = Depends(get_odoo)):
        try:
            resolved_model = resolve_model_name(session, model_name)
            session.write(resolved_model, [item_id], item.data)
            return {"id": item_id, "data": item.data}
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "Access Denied" in error_msg:
                raise HTTPException(status_code=403, detail=f"Accès refusé pour '{tag}' : droits insuffisants (modification).")
            raise HTTPException(status_code=400, detail=f"Erreur de modification {tag}: {error_msg}")


# Application de la génération pour chaque module
for mod_id, mod_cfg in MODULES_CONFIG.items():
    add_module_endpoints(app, mod_id, mod_cfg)



# --- Endpoints KoboToolbox (CRUD) ---
KOBO_BASE_URL = os.getenv("KOBOTOOLBOX_URL", "https://kf.kobotoolbox.org").rstrip("/")
KOBO_TOKEN = os.getenv("KOBOTOOLBOX_TOKEN", "")

def get_kobo_headers():
    headers = {"User-Agent": "Capsy-Odoo-API-Bridge/1.0"}
    token = os.getenv("KOBOTOOLBOX_TOKEN", KOBO_TOKEN)
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers

def resolve_kobo_asset_id(asset_id: Optional[str] = None) -> str:
    target = asset_id or os.getenv("ID_DB_KOBOTOOLBOX")
    if not target:
        raise HTTPException(
            status_code=400,
            detail="Asset ID KoboToolbox non spécifié. Veuillez le fournir via le paramètre 'asset_id' ou le définir dans le fichier .env (ID_DB_KOBOTOOLBOX)."
        )
    return target

class KoboItemBase(BaseModel):
    data: Dict[str, Any]

@app.get("/kobotoolbox/", tags=["📊 KoboToolbox"], summary="Lire les données KoboToolbox (Liste)")
async def get_kobo_data(
    asset_id: Optional[str] = None,
    limit: int = 100,
    start: int = 0
):
    target_asset = resolve_kobo_asset_id(asset_id)
    url = f"{KOBO_BASE_URL}/api/v2/assets/{target_asset}/data.json"
    params = {}
    if limit:
        params["limit"] = limit
    if start:
        params["start"] = start

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=get_kobo_headers(), params=params, timeout=15.0)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erreur KoboToolbox ({response.status_code}): {response.text}"
                )
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Erreur de connexion à KoboToolbox: {str(exc)}")

@app.get("/kobotoolbox/asset", tags=["📊 KoboToolbox"], summary="Obtenir les informations de l'asset KoboToolbox")
async def get_kobo_asset_info(asset_id: Optional[str] = None):
    target_asset = resolve_kobo_asset_id(asset_id)
    url = f"{KOBO_BASE_URL}/api/v2/assets/{target_asset}.json"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=get_kobo_headers(), timeout=15.0)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erreur KoboToolbox ({response.status_code}): {response.text}"
                )
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Erreur de connexion à KoboToolbox: {str(exc)}")

@app.get("/kobotoolbox/{submission_id}", tags=["📊 KoboToolbox"], summary="Lire une soumission KoboToolbox par ID")
async def get_kobo_submission(submission_id: int, asset_id: Optional[str] = None):
    target_asset = resolve_kobo_asset_id(asset_id)
    url = f"{KOBO_BASE_URL}/api/v2/assets/{target_asset}/data/{submission_id}.json"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=get_kobo_headers(), timeout=15.0)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Soumission #{submission_id} introuvable dans KoboToolbox.")
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erreur KoboToolbox ({response.status_code}): {response.text}"
                )
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Erreur de connexion à KoboToolbox: {str(exc)}")

@app.post("/kobotoolbox/", tags=["📊 KoboToolbox"], summary="Créer / Ajouter une soumission dans KoboToolbox")
async def create_kobo_submission(item: KoboItemBase, asset_id: Optional[str] = None):
    target_asset = resolve_kobo_asset_id(asset_id)
    url = f"{KOBO_BASE_URL}/api/v2/assets/{target_asset}/data/"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=item.data, headers=get_kobo_headers(), timeout=15.0)
            if response.status_code not in (200, 201):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erreur lors de la création dans KoboToolbox ({response.status_code}): {response.text}"
                )
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Erreur de connexion à KoboToolbox: {str(exc)}")

@app.put("/kobotoolbox/{submission_id}", tags=["📊 KoboToolbox"], summary="Modifier une soumission KoboToolbox")
async def update_kobo_submission(submission_id: int, item: KoboItemBase, asset_id: Optional[str] = None):
    target_asset = resolve_kobo_asset_id(asset_id)
    url = f"{KOBO_BASE_URL}/api/v2/assets/{target_asset}/data/{submission_id}/"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.patch(url, json=item.data, headers=get_kobo_headers(), timeout=15.0)
            if response.status_code not in (200, 201, 202):
                response = await client.put(url, json=item.data, headers=get_kobo_headers(), timeout=15.0)
            if response.status_code not in (200, 201, 202):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erreur lors de la modification KoboToolbox ({response.status_code}): {response.text}"
                )
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Erreur de connexion à KoboToolbox: {str(exc)}")

@app.get("/favicon.ico", include_in_schema=False)

async def favicon():
    return Response(status_code=204)

@app.get("/", tags=["🏠 Accueil"])
async def root():
    kobo_asset_configured = bool(os.getenv("ID_DB_KOBOTOOLBOX"))
    return {
        "message": "Bienvenue sur l'API Capsy-Odoo LIVE",
        "documentation": "/docs",
        "modules_actifs": len(MODULES_CONFIG),
        "kobotoolbox_actif": kobo_asset_configured
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

