from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import odoorpc
import os
import json
from dotenv import load_dotenv

# Chargement des identifiants
load_dotenv()

# Lecture dynamique des variables d'environnement
_ODOO_URL      = os.getenv("ODOO_URL", "https://odoo.example.com")
_ODOO_DB       = os.getenv("ODOO_DB", "")
_ODOO_USERNAME = os.getenv("ODOO_USERNAME", "utilisateur@example.com")
_ODOO_HOST     = _ODOO_URL.replace("https://", "").replace("http://", "").split('/')[0]

app = FastAPI(
    title="🚀 Capsy-Odoo API Bridge",
    description=f"""
## 🌉 Connecteur Universel Odoo - Capsy

Cette API permet d'interagir de manière fluide avec l'instance Odoo **{_ODOO_HOST}**.
Elle est conçue pour être utilisée par des services tiers, des applications mobiles ou des agents IA.

### 🔐 Connexion active :
*   **Instance** : `{_ODOO_URL}`
*   **Base de données** : `{_ODOO_DB}`
*   **Utilisateur** : `{_ODOO_USERNAME}`

### 🛠 Fonctionnalités clés :
*   **🔌 Connexion Directe** : Accès sécurisé aux modèles Odoo via OdooRPC.
*   **📖 Opérations CRUD** : Lecture, Création et Modification sur plus de 20 modules.
*   **🏗 Structure Normalisée** : Réponses JSON uniformes pour tous les modules.

### 📂 Applications supportées (24 modules) :
L'API est configurée pour interagir avec les modules suivants de votre instance Odoo :
*   **Communication** : Discussion, Calendrier, Rendez-vous
*   **Productivité** : To-do, Connaissances, Documents, Feuilles de temps, Planning
*   **Commerce** : Contacts, CRM, Ventes, Événements
*   **Gestion** : Comptabilité, Tableaux de bord, Inventaire, Signature
*   **Marketing** : Site Web, Marketing Automation, Email Marketing
*   **Ressources Humaines** : Employés, Paie, Congés
*   **Système** : Apps, Paramètres

***Note :*** *Les erreurs 500 indiquent généralement un manque de permissions sur l'utilisateur `{_ODOO_USERNAME}` ou un module non installé sur l'instance `{_ODOO_HOST}`.*

---
### 📚 Documentation & Téléchargement :
Vous pouvez consulter ou télécharger la documentation complète de l'API ici :
*   **Version Web HTML** : [Consulter la documentation en ligne](/documentation)
*   **Documentation technique** : [Télécharger le fichier (API_DOCUMENTATION.md)](https://capsy-odoo-api.vercel.app/docs/API_DOCUMENTATION.md)
""",
    version="3.1.0",
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

# --- Gestion de la connexion Odoo ---
def get_odoo():
    try:
        odoo = odoorpc.ODOO(_ODOO_HOST, protocol="jsonrpc+ssl", port=443)
        odoo.login(
            _ODOO_DB,
            _ODOO_USERNAME,
            os.getenv("ODOO_PASSWORD")
        )
        return odoo
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Odoo : {str(e)}")

# --- Endpoint de Connexion ---
@app.post("/login", tags=["🔐 Connexion"], summary="Connexion d'un utilisateur Odoo")
async def login_odoo(credentials: OdooLoginRequest):
    try:
        url_to_use = credentials.url or _ODOO_URL
        db_to_use = credentials.db or _ODOO_DB
        host = url_to_use.replace("https://", "").replace("http://", "").split('/')[0]
        
        odoo = odoorpc.ODOO(host, protocol="jsonrpc+ssl", port=443)
        odoo.login(db_to_use, credentials.username, credentials.password)
        
        # Récupération des informations de l'utilisateur connecté
        user_info = odoo.env['res.users'].browse(odoo.env.uid)
        
        return {
            "status": "success",
            "message": "Connexion réussie à l'instance Odoo",
            "uid": odoo.env.uid,
            "username": credentials.username,
            "name": user_info.name,
            "company": user_info.company_id.name if hasattr(user_info, 'company_id') else None,
            "instance": url_to_use,
            "database": db_to_use
        }
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Échec de l'authentification Odoo : {str(e)}"
        )

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
    }
    if model_name in fallbacks:
        for fb in fallbacks[model_name]:
            try:
                # Tente d'accéder au modèle pour voir s'il existe dans le registre d'Odoo
                if odoo_client.env[fb]:
                    return fb
            except Exception:
                continue
    return model_name

# Cache pour stocker les champs sûrs par modèle
FIELDS_CACHE = {}

def get_safe_fields(odoo_client, model_name):
    if model_name not in FIELDS_CACHE:
        try:
            fields_info = odoo_client.env[model_name].fields_get(attributes=['type'])
            # On ignore les champs one2many / many2many pour éviter les erreurs de droits d'accès
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
    async def read_items(limit: int = 10, fields: Optional[str] = None, odoo_client=Depends(get_odoo)):
        try:
            resolved_model = resolve_model_name(odoo_client, model_name)
            
            # Détermination des champs à lire
            if fields:
                fields_list = [f.strip() for f in fields.split(",") if f.strip()]
            else:
                fields_list = get_safe_fields(odoo_client, resolved_model)
                
            ids = odoo_client.env[resolved_model].search([], limit=limit)
            
            # Tente de lire les champs spécifiés ou les champs sûrs
            try:
                if fields_list:
                    records = odoo_client.env[resolved_model].read(ids, fields_list)
                else:
                    records = odoo_client.env[resolved_model].read(ids)
            except Exception as read_error:
                # Si la lecture échoue (ex: règle d'accès sur un champ spécifique),
                # on se replie sur des champs ultra-basiques et universels
                try:
                    records = odoo_client.env[resolved_model].read(ids, ['id', 'display_name'])
                except Exception:
                    raise read_error # Si même le fallback échoue, on propage l'erreur d'origine
                
            return [{"id": r["id"], "data": r} for r in records]
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "n'êtes pas autorisé" in error_msg or "Permission denied" in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail=f"Accès refusé pour le module '{tag}' : L'utilisateur Odoo n'a pas les droits nécessaires (lecture) sur ce modèle ou ses enregistrements."
                )
            raise HTTPException(status_code=404, detail=f"Erreur de lecture {tag}: {error_msg}")

    @app_instance.post(f"{prefix}/", response_model=ItemResponse, tags=[tag], summary=f"Écrire (Créer) {tag}")
    async def create_item(item: ItemBase, odoo_client=Depends(get_odoo)):
        try:
            resolved_model = resolve_model_name(odoo_client, model_name)
            new_id = odoo_client.env[resolved_model].create(item.data)
            return {"id": new_id, "data": item.data}
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "n'êtes pas autorisé" in error_msg or "Permission denied" in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail=f"Accès refusé pour le module '{tag}' : L'utilisateur Odoo n'a pas les droits nécessaires (écriture/création) sur ce modèle."
                )
            raise HTTPException(status_code=400, detail=f"Erreur de création {tag}: {error_msg}")

    @app_instance.put(f"{prefix}/{{item_id}}", response_model=ItemResponse, tags=[tag], summary=f"Modifier {tag}")
    async def update_item(item_id: int, item: ItemBase, odoo_client=Depends(get_odoo)):
        try:
            resolved_model = resolve_model_name(odoo_client, model_name)
            odoo_client.env[resolved_model].write([item_id], item.data)
            return {"id": item_id, "data": item.data}
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "n'êtes pas autorisé" in error_msg or "Permission denied" in error_msg:
                raise HTTPException(
                    status_code=403,
                    detail=f"Accès refusé pour le module '{tag}' : L'utilisateur Odoo n'a pas les droits nécessaires (modification) sur ce modèle ou cet enregistrement."
                )
            raise HTTPException(status_code=400, detail=f"Erreur de modification {tag}: {error_msg}")

# Application de la génération pour chaque module
for mod_id, mod_cfg in MODULES_CONFIG.items():
    add_module_endpoints(app, mod_id, mod_cfg)

@app.get("/", tags=["🏠 Accueil"])
async def root():
    return {
        "message": "Bienvenue sur l'API Capsy-Odoo LIVE",
        "documentation": "/docs",
        "modules_actifs": len(MODULES_CONFIG)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
