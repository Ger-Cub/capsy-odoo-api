from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import odoorpc
import os
from dotenv import load_dotenv

# Chargement des identifiants
load_dotenv()

app = FastAPI(
    title="🚀 Capsy-Odoo API Bridge",
    description="""
## 🌉 Connecteur Universel Odoo - Capsy

Cette API permet d'interagir de manière fluide avec l'instance Odoo **essaiek3.odoo.com**. 
Elle est conçue pour être utilisée par des services tiers, des applications mobiles ou des agents IA.

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

***Note :*** *Les erreurs 500 indiquent généralement un manque de permissions sur l'utilisateur Odoo ou un module non installé sur l'instance.*
""",
    version="3.1.0",
    contact={
        "name": "Support Capsy Services",
        "url": "https://capsy.services",
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

# --- Gestion de la connexion Odoo ---
def get_odoo():
    try:
        url = os.getenv("ODOO_URL", "https://essaiek3.odoo.com")
        host = url.replace("https://", "").replace("http://", "").split('/')[0]
        
        odoo = odoorpc.ODOO(host, protocol="jsonrpc+ssl", port=443)
        odoo.login(
            os.getenv("ODOO_DB"), 
            os.getenv("ODOO_USERNAME"), 
            os.getenv("ODOO_PASSWORD")
        )
        return odoo
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Odoo : {str(e)}")

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

# --- Générateur de Routes ---
def add_module_endpoints(app_instance, module_id, config):
    model_name = config["model"]
    tag = config["label"]
    prefix = f"/{module_id}"

    @app_instance.get(f"{prefix}/", response_model=List[ItemResponse], tags=[tag], summary=f"Lire {tag}")
    async def read_items(limit: int = 10, odoo_client=Depends(get_odoo)):
        try:
            ids = odoo_client.env[model_name].search([], limit=limit)
            records = odoo_client.env[model_name].read(ids)
            return [{"id": r["id"], "data": r} for r in records]
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Erreur de lecture {tag}: {str(e)}")

    @app_instance.post(f"{prefix}/", response_model=ItemResponse, tags=[tag], summary=f"Écrire (Créer) {tag}")
    async def create_item(item: ItemBase, odoo_client=Depends(get_odoo)):
        try:
            new_id = odoo_client.env[model_name].create(item.data)
            return {"id": new_id, "data": item.data}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erreur de création {tag}: {str(e)}")

    @app_instance.put(f"{prefix}/{{item_id}}", response_model=ItemResponse, tags=[tag], summary=f"Modifier {tag}")
    async def update_item(item_id: int, item: ItemBase, odoo_client=Depends(get_odoo)):
        try:
            odoo_client.env[model_name].write([item_id], item.data)
            return {"id": item_id, "data": item.data}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erreur de modification {tag}: {str(e)}")

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
