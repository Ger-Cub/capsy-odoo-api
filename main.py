from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
# odoorpc remplacé par JSON-RPC httpx natif (branche feature/web-session-auth)
import os
import re
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
    allow_origins=[
        "https://capsy-services.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include external routers (formations) ---
import sys
from pathlib import Path
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from routers.formations import router as formations_router
    app.include_router(formations_router)
except Exception as _e:
    print(f"[WARN] formations router not included: {_e}")

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


class SessionCallRequest(BaseModel):
    session_id: str
    uid: int
    username: str
    model: str
    method: str
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
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

        # If the endpoint returned a non-200, surface the status and body for debugging
        if r.status_code != 200:
            text = None
            try:
                text = r.text
            except Exception:
                text = '<no response body>'
            raise Exception(f"HTTP {r.status_code}: {text}")

        # Parse JSON safely
        try:
            data = r.json()
        except Exception as exc:
            raise Exception(f"Invalid JSON response from Odoo RPC endpoint: {str(exc)} - raw: {r.text}")

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
    
    partner_id = None
    avatar_url = None
    name = credentials.username
    company = ""

    try:
        user_data = await session.read("res.users", [session.uid], ["name", "company_id", "partner_id", "avatar_128", "image_128"])
        if user_data:
            u = user_data[0]
            name = u.get("name") or credentials.username
            company = (u.get("company_id") or [None, ""])[1]
            p_id = u.get("partner_id")
            partner_id = p_id[0] if isinstance(p_id, list) else p_id
            avatar_b64 = u.get("avatar_128") or u.get("image_128") or False

            if not avatar_b64 and partner_id:
                partner_data = await session.read("res.partner", [partner_id], ["avatar_128", "image_128"])
                if partner_data:
                    avatar_b64 = partner_data[0].get("avatar_128") or partner_data[0].get("image_128") or False

            if avatar_b64:
                avatar_url = f"data:image/png;base64,{avatar_b64}"
    except Exception:
        pass

    return {
        "status":     "success",
        "message":    "Connexion réussie à l'instance Odoo",
        "uid":        session.uid,
        "username":   credentials.username,
        "name":       name,
        "company":    company,
        "partner_id": partner_id,
        "avatar":     avatar_url,
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


class AppointmentCreate(BaseModel):
    serviceTitle: str
    clientName: str
    clientEmail: Optional[str] = None
    clientPhone: Optional[str] = None
    clientNotes: Optional[str] = None
    date: str
    timeSlot: str
    preferredTherapist: Optional[str] = None
    format: Optional[str] = "presentiel"   # 'presentiel' | 'en_ligne'
    appointmentTypeId: Optional[int] = None  # calendar.appointment.type id si connu


class CreateAppointmentRequest(BaseModel):
    appointment: AppointmentCreate
    loggedInPartnerId: Optional[int] = None
    loggedInUserId: Optional[int] = None
    loggedInSessionId: Optional[str] = None


# --- Modèle Mot de passe oublié ---
class OdooResetPasswordRequest(BaseModel):
    login: str       # email
    db: Optional[str] = None
    url: Optional[str] = None


# --- Endpoint Inscription (Signup) ---
# --- Endpoint Inscription (Signup) ---
@app.post(
    "/signup",
    tags=["🔐 Connexion"],
    summary="Créer un nouveau compte utilisateur Odoo",
    description="""
Crée un nouveau compte utilisateur portail sur l'instance Odoo.
"""
)
async def signup_odoo(request: OdooSignupRequest):
    url_to_use = request.url or _ODOO_URL
    db_to_use  = request.db  or _ODOO_DB

    # Authentifier une session administrateur pour les opérations de création
    admin_user = os.getenv("ODOO_USERNAME")
    admin_pass = os.getenv("ODOO_PASSWORD")

    try:
        admin_session = await _authenticate(admin_user, admin_pass, url_to_use, db_to_use)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'authentification admin Odoo : {str(e)}")

    login_clean = request.login.strip().lower()

    try:
        # 1. Vérifier si l'utilisateur existe déjà
        existing_users = await admin_session.search('res.users', [['login', '=ilike', login_clean]], limit=1)
        if existing_users:
            raise HTTPException(status_code=400, detail="Un compte avec cette adresse email existe déjà. Veuillez vous connecter.")

        # 2. Trouver ou créer le contact res.partner
        existing_partners = await admin_session.search('res.partner', [['email', '=ilike', login_clean]], limit=1)
        partner_id = None
        if existing_partners:
            partner_id = existing_partners[0]
            await admin_session.write('res.partner', [partner_id], {'name': request.name})
        else:
            partner_id = await admin_session.create('res.partner', {
                'name': request.name,
                'email': login_clean,
                'comment': 'Client créé via le formulaire d\'inscription Capsy Services',
            })

        # 3. Trouver le groupe Portail dans Odoo (support Odoo 19 & versions antérieures)
        portal_group_id = None
        try:
            ir_data = await admin_session.search_read(
                'ir.model.data',
                [['module', '=', 'base'], ['name', '=', 'group_portal']],
                ['res_id'],
                limit=1
            )
            if ir_data and ir_data[0].get('res_id'):
                portal_group_id = ir_data[0]['res_id']
        except Exception:
            pass

        if not portal_group_id:
            try:
                groups = await admin_session.search_read(
                    'res.groups',
                    [['name', 'ilike', 'Portal']],
                    ['id'],
                    limit=1
                )
                if groups:
                    portal_group_id = groups[0]['id']
            except Exception:
                pass

        # 4. Création du compte res.users (avec support group_ids Odoo 19+ / groups_id)
        user_vals = {
            'name': request.name,
            'login': login_clean,
            'email': login_clean,
            'password': request.password,
            'partner_id': partner_id,
        }

        if portal_group_id:
            user_vals['group_ids'] = [(6, 0, [portal_group_id])]

        try:
            await admin_session.create('res.users', user_vals)
        except Exception as create_err:
            if 'group_ids' in str(create_err) and portal_group_id:
                del user_vals['group_ids']
                user_vals['groups_id'] = [(6, 0, [portal_group_id])]
                await admin_session.create('res.users', user_vals)
            else:
                raise create_err

        # 5. Authentifier le nouvel utilisateur pour retourner sa session
        user_session = await _authenticate(login_clean, request.password, url_to_use, db_to_use)

        return {
            "status":     "success",
            "message":    "Compte créé avec succès. Bienvenue sur CAPSY !",
            "uid":        user_session.uid,
            "username":   login_clean,
            "name":       request.name,
            "partner_id": partner_id,
            "instance":   url_to_use,
            "database":   db_to_use,
            "session_id": user_session.session_id,
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


# ---------------------------------------------------------------------------
# Sous-tâches cliniques standardisées pour le projet Accompagnement individuel
# ---------------------------------------------------------------------------
CLINICAL_SUBTASKS = [
    "Enregistrer et vérifier la demande",
    "Réaliser l'admission",
    "Effectuer le triage clinique",
    "Attribuer le dossier",
    "Réaliser l'évaluation clinique",
    "Élaborer le plan thérapeutique",
    "Assurer la prise en charge thérapeutique",
    "Assurer la supervision ou le référencement",
    "Préparer la clôture du dossier",
    "Archiver le dossier",
]

# Nom du projet cible dans Odoo
PROJET_ACCOMPAGNEMENT = "Accompagnement individuel"


async def get_available_therapists_helper(
    session: OdooSession,
    start_time: str,
    stop_time: str,
    service_title: Optional[str] = None
) -> dict:
    """
    Vérifie la disponibilité réelle des thérapeutes dans Odoo pour un créneau [start_time, stop_time].
    Si service_title est spécifié, restreint la recherche aux seuls thérapeutes autorisés pour ce service (staff_user_ids).
    Consulte calendar.event pour détecter les conflits d'horaires.
    """
    therapists = []
    allowed_uids: list = []

    if service_title:
        try:
            clean_title = service_title.split('/')[0].strip()
            appt_types = await session.search_read(
                'appointment.type',
                [['name', 'ilike', clean_title]],
                ['id', 'name', 'staff_user_ids'],
                limit=1
            )
            if appt_types and appt_types[0].get('staff_user_ids'):
                allowed_uids = appt_types[0]['staff_user_ids']
        except Exception as e:
            print(f"[WARN] Erreur lors de la recherche des therapeutes du service '{service_title}': {e}")

    try:
        domain = [['active', '=', True], ['share', '=', False]]
        if allowed_uids:
            domain.append(['id', 'in', allowed_uids])

        user_records = await session.search_read(
            'res.users',
            domain,
            ['id', 'name', 'partner_id'],
            limit=50
        )
        for u in user_records:
            pid = u.get('partner_id')
            partner_id = pid[0] if isinstance(pid, list) else pid
            therapists.append({
                'id': u['id'],
                'name': u['name'],
                'partner_id': partner_id
            })
    except Exception as e:
        print(f"[WARN] Erreur lors de la récupération des thérapeutes : {e}")

    busy_user_ids = set()
    busy_partner_ids = set()

    try:
        overlapping_events = await session.search_read(
            'calendar.event',
            [['start', '<', stop_time], ['stop', '>', start_time]],
            ['id', 'user_id', 'partner_ids']
        )
        for ev in overlapping_events:
            uid_field = ev.get('user_id')
            if uid_field:
                uid_val = uid_field[0] if isinstance(uid_field, list) else uid_field
                busy_user_ids.add(uid_val)
            
            pids_field = ev.get('partner_ids', [])
            for pid in pids_field:
                busy_partner_ids.add(pid)
    except Exception as e:
        print(f"[WARN] Erreur lors de la vérification des conflits de RDV : {e}")

    available = []
    busy = []

    for t in therapists:
        if t['id'] in busy_user_ids or t['partner_id'] in busy_partner_ids:
            busy.append(t)
        else:
            available.append(t)

    return {
        'available': available,
        'busy': busy,
        'total': len(therapists)
    }


@app.get('/therapists/availability', tags=["Thérapeutes"], summary="Vérifier la disponibilité des thérapeutes pour un créneau")
async def check_therapists_availability(
    date: str,
    timeSlot: str,
    service_title: Optional[str] = None,
    session: OdooSession = Depends(get_odoo),
):
    times = timeSlot.split(' - ')
    start_str = times[0].strip().replace('h', ':') + ':00'
    end_str   = times[1].strip().replace('h', ':') + ':00' if len(times) > 1 else start_str
    start = f"{date} {start_str}"
    stop  = f"{date} {end_str}"
    
    return await get_available_therapists_helper(session, start, stop, service_title)


@app.post('/appointments', tags=["Rendez-vous"], include_in_schema=False)
@app.post('/appointments/', tags=["Rendez-vous"], include_in_schema=False)
@app.post('/appointments/create', tags=["Rendez-vous"], summary="Créer un rendez-vous complet (contact + calendrier + dossier clinique)")
async def create_appointment(req: CreateAppointmentRequest, session: OdooSession = Depends(get_odoo)):
    """
    Flux complet de création d'un rendez-vous CAPSY :

    1. **Contact & Utilisateur Portail** – Crée ou retrouve le partenaire client et son compte portail dans Odoo.
    2. **Disponibilité Thérapeute** – Vérifie et assigne un praticien réellement disponible ("Premier disponible").
    3. **Calendrier** – Crée un `calendar.event` dans les agendas du client et du thérapeute.
    4. **Dossier clinique** – Crée une tâche principale dans le projet « Accompagnement individuel » avec sous-tâches.
    """
    appt = req.appointment
    
    # Utiliser la session admin pour contourner les restrictions ACL Odoo lors de la création d'événements et de tâches
    admin_user = os.getenv("ODOO_USERNAME")
    admin_pass = os.getenv("ODOO_PASSWORD")
    try:
        write_session = await _authenticate(admin_user, admin_pass, _ODOO_URL, _ODOO_DB)
    except Exception:
        write_session = session

    try:
        # ------------------------------------------------------------------ #
        # 1) Résoudre ou créer le partenaire client + compte portail
        # ------------------------------------------------------------------ #
        clean_email = appt.clientEmail.strip().lower() if appt.clientEmail else None
        search_domain: list = []
        if clean_email:
            search_domain = [['email', '=ilike', clean_email]]
        elif appt.clientPhone:
            search_domain = [['phone', '=', appt.clientPhone]]

        partner_ids = await write_session.search('res.partner', search_domain, limit=1) if search_domain else []
        partner_id: Optional[int] = None
        if partner_ids:
            partner_id = partner_ids[0]
        else:
            partner_id = await write_session.create('res.partner', {
                'name': appt.clientName,
                'email': clean_email or False,
                'phone': appt.clientPhone or False,
                'comment': 'Créé via site web Capsy (réservation en ligne)',
            })

        # Si réservation publique (non connecté), créer automatiquement le compte portail pour lier les données
        if not req.loggedInUserId and clean_email:
            try:
                user_ids = await write_session.search('res.users', [['login', '=ilike', clean_email]], limit=1)
                if not user_ids:
                    portal_gid = None
                    try:
                        ir_data = await write_session.search_read('ir.model.data', [['module', '=', 'base'], ['name', '=', 'group_portal']], ['res_id'], limit=1)
                        if ir_data and ir_data[0].get('res_id'):
                            portal_gid = ir_data[0]['res_id']
                    except Exception:
                        pass

                    user_vals = {
                        'name': appt.clientName,
                        'login': clean_email,
                        'email': clean_email,
                        'password': f"Capsy@{partner_id}#2026",
                        'partner_id': partner_id,
                    }
                    if portal_gid:
                        user_vals['group_ids'] = [(6, 0, [portal_gid])]

                    try:
                        await write_session.create('res.users', user_vals)
                    except Exception as create_err:
                        if 'group_ids' in str(create_err) and portal_gid:
                            del user_vals['group_ids']
                            user_vals['groups_id'] = [(6, 0, [portal_gid])]
                            await write_session.create('res.users', user_vals)
            except Exception as u_err:
                print(f"[WARN] Impossible de créer le compte utilisateur portail automatique: {u_err}")

        # ------------------------------------------------------------------ #
        # 2) Trouver le type de rendez-vous Odoo par correspondance de titre
        # ------------------------------------------------------------------ #
        appointment_type_id: Optional[int] = appt.appointmentTypeId
        if not appointment_type_id:
            service_clean_name = appt.serviceTitle.split('/')[0].strip()
            for model_name in ['appointment.type', 'calendar.appointment.type']:
                try:
                    appt_type_ids = await write_session.search(
                        model_name,
                        [['name', 'ilike', service_clean_name]],
                        limit=1,
                    )
                    if appt_type_ids:
                        appointment_type_id = appt_type_ids[0]
                        break
                except Exception:
                    continue

        # ------------------------------------------------------------------ #
        # 3) Heures & Vérification de la disponibilité réelle du thérapeute
        # ------------------------------------------------------------------ #
        times = appt.timeSlot.split(' - ')
        start_str = times[0].strip().replace('h', ':') + ':00'
        end_str   = times[1].strip().replace('h', ':') + ':00' if len(times) > 1 else start_str
        start = f"{appt.date} {start_str}"
        stop  = f"{appt.date} {end_str}"

        availability_data = await get_available_therapists_helper(write_session, start, stop, appt.serviceTitle)
        available_therapists = availability_data.get('available', [])

        therapist_user_id: Optional[int] = None
        therapist_partner_id: Optional[int] = None
        organizer_name = appt.preferredTherapist or 'Capsy Services'

        if not appt.preferredTherapist or appt.preferredTherapist in ('Premier disponible', ''):
            if available_therapists:
                chosen = available_therapists[0]
                therapist_user_id = chosen['id']
                therapist_partner_id = chosen['partner_id']
                organizer_name = chosen['name']
            else:
                all_therapists = availability_data.get('available', []) + availability_data.get('busy', [])
                if all_therapists:
                    chosen = all_therapists[0]
                    therapist_user_id = chosen['id']
                    therapist_partner_id = chosen['partner_id']
                    organizer_name = chosen['name']
        else:
            try:
                user_recs = await write_session.search_read(
                    'res.users',
                    [['name', 'ilike', appt.preferredTherapist]],
                    ['id', 'name', 'partner_id'],
                    limit=1
                )
                if user_recs:
                    therapist_user_id = user_recs[0]['id']
                    pid = user_recs[0].get('partner_id')
                    therapist_partner_id = pid[0] if isinstance(pid, list) else pid
                    organizer_name = user_recs[0]['name']
            except Exception:
                pass

        # ------------------------------------------------------------------ #
        # 4) Description HTML du rendez-vous
        # ------------------------------------------------------------------ #
        phone_display  = appt.clientPhone or ''
        email_display  = clean_email or ''
        notes_display  = appt.clientNotes or 'Aucun détail supplémentaire'
        format_display = 'Au bureau CAPSY - Goma' if (appt.format or 'presentiel') == 'presentiel' else 'Séance en ligne'

        description_html = (
            f"<div>"
            f"Client: {appt.clientName}\n"
            f"Email: {email_display}\n"
            f"Phone: {phone_display}\n"
            f"Notes: {notes_display}\n"
            f"Therapist: {organizer_name}"
            f"<br><strong>Organisé par</strong><br>"
            f"{appt.clientName}<br>"
            f"<a href=\"mailto:{email_display}\">{email_display}</a><br>"
            f"<a href=\"tel:{phone_display.replace(' ', '%20')}\">{phone_display}</a>"
            f"</div>"
        )

        # ------------------------------------------------------------------ #
        # 5) Créer l'événement dans le calendrier du thérapeute ET du client
        # ------------------------------------------------------------------ #
        attendee_partner_ids = [partner_id]
        if therapist_partner_id and therapist_partner_id not in attendee_partner_ids:
            attendee_partner_ids.append(therapist_partner_id)
        if req.loggedInPartnerId and req.loggedInPartnerId not in attendee_partner_ids:
            attendee_partner_ids.append(req.loggedInPartnerId)

        event_vals: dict = {
            'name': f"RDV: {appt.serviceTitle}",
            'start': start,
            'stop': stop,
            'allday': False,
            'description': description_html,
            'show_as': 'busy',
            'privacy': 'public',
            'partner_ids': [[6, 0, attendee_partner_ids]],
            'location': format_display,
            'videocall_source': 'discuss' if (appt.format or 'presentiel') == 'en_ligne' else 'custom',
        }

        if therapist_user_id:
            event_vals['user_id'] = therapist_user_id

        if appointment_type_id:
            event_vals['appointment_type_id'] = appointment_type_id
            event_vals['appointment_status'] = 'booked'
            event_vals['appointment_type_schedule_based_on'] = 'users'

        event_id: int = await write_session.create('calendar.event', event_vals)

        # ------------------------------------------------------------------ #
        # 6) Créer le dossier clinique dans le projet « Accompagnement individuel »
        # ------------------------------------------------------------------ #
        task_id: Optional[int] = None
        subtask_ids: list = []
        project_id: Optional[int] = None

        try:
            proj_ids = await write_session.search('project.project', [['name', '=', PROJET_ACCOMPAGNEMENT]], limit=1)
            if not proj_ids:
                proj_ids = await write_session.search('project.project', [['name', 'ilike', 'Accompagnement']], limit=1)
            if proj_ids:
                project_id = proj_ids[0]

            dossier_description = (
                f"<p><strong>Dossier client :</strong> {appt.clientName}</p>"
                f"<p><strong>Service :</strong> {appt.serviceTitle}</p>"
                f"<p><strong>Email :</strong> {email_display or 'N/A'}</p>"
                f"<p><strong>Téléphone :</strong> {phone_display or 'N/A'}</p>"
                f"<p><strong>Date RDV :</strong> {appt.date} ({appt.timeSlot})</p>"
                f"<p><strong>Thérapeute :</strong> {organizer_name}</p>"
                f"<p><strong>Format :</strong> {format_display}</p>"
                f"<p><strong>Notes :</strong> {notes_display}</p>"
                f"<p><em>Dossier créé automatiquement via le site Capsy — event Odoo #{event_id}</em></p>"
            )

            prefix = "SC-IND"
            title_lower = appt.serviceTitle.lower()
            if "famil" in title_lower:
                prefix = "SC-FAM"
            elif "enfant" in title_lower or "ado" in title_lower:
                prefix = "SC-ENF"
            elif "adulte" in title_lower:
                prefix = "SC-ADU"

            import datetime
            current_year = datetime.datetime.now().year

            client_parts = [p.strip() for p in appt.clientName.split() if p.strip()]
            initials_list = [p[0].upper() for p in client_parts if p[0].isalpha()]
            initials_str = ".".join(initials_list) if initials_list else "C.L"

            seq_num = 1
            try:
                search_domain = [['name', 'ilike', f"Dossier : {prefix}-{current_year}"]]
                if project_id:
                    search_domain.append(['project_id', '=', project_id])
                existing_tasks = await write_session.search('project.task', search_domain, limit=9999)
                seq_num = len(existing_tasks) + 1
            except Exception:
                seq_num = 1

            seq_str = f"{seq_num:04d}"
            confidential_task_name = f"Dossier : {prefix}-{current_year} — {seq_str}-{initials_str}"

            task_vals: dict = {
                'name': confidential_task_name,
                'partner_id': partner_id,
                'date_deadline': appt.date,
                'description': dossier_description,
                'tag_ids': [],
            }
            if project_id:
                task_vals['project_id'] = project_id
            if therapist_user_id:
                task_vals['user_ids'] = [[6, 0, [therapist_user_id]]]

            task_id = await write_session.create('project.task', task_vals)

            for i, subtask_name in enumerate(CLINICAL_SUBTASKS, start=1):
                subtask_vals: dict = {
                    'name': f"{i:02d}. {subtask_name}",
                    'parent_id': task_id,
                    'partner_id': partner_id,
                    'description': f"Étape {i}/10 du suivi clinique — Dossier {appt.clientName}",
                }
                if project_id:
                    subtask_vals['project_id'] = project_id
                if therapist_user_id:
                    subtask_vals['user_ids'] = [[6, 0, [therapist_user_id]]]
                try:
                    sub_id = await write_session.create('project.task', subtask_vals)
                    subtask_ids.append(sub_id)
                except Exception as sub_err:
                    print(f"[WARN] Sous-tâche '{subtask_name}' non créée : {sub_err}")

        except Exception as proj_err:
            print(f"[WARN] Dossier clinique non créé : {proj_err}")

        return {
            'status': 'success',
            'message': 'Rendez-vous créé avec succès dans Odoo',
            'event_id': event_id,
            'appointment_type_id': appointment_type_id,
            'partner_id': partner_id,
            'assigned_therapist': organizer_name,
            'project_id': project_id,
            'task_id': task_id,
            'subtask_ids': subtask_ids,
            'subtasks_created': len(subtask_ids),
        }

    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur de création Rendez-vous: {str(exc)}")


# ---------------------------------------------------------------------------
# Champs retournés pour la liste des rendez-vous
# ---------------------------------------------------------------------------
APPT_FIELDS = [
    'id', 'display_name', 'name', 'description',
    'start', 'stop', 'allday', 'duration',
    'location', 'show_as', 'privacy', 'effective_privacy',
    'user_id', 'partner_id',
    'videocall_location', 'videocall_source', 'access_token',
    'current_attendee', 'current_status', 'attendees_count',
    'accepted_count', 'declined_count', 'tentative_count', 'awaiting_count',
    'appointment_status', 'appointment_type_id',
    'appointment_type_schedule_based_on', 'appointment_booker_id',
    'recurrency', 'recurrence_id',
    'create_uid', 'create_date', 'write_uid', 'write_date',
    'active', 'display_time',
]


@app.get('/appointments', tags=["Rendez-vous"], include_in_schema=False)
@app.get(
    '/appointments/',
    tags=["Rendez-vous"],
    summary="Lister les rendez-vous de l'utilisateur ou filtrés",
    description="""
Retourne la liste des `calendar.event` filtrés pour l'utilisateur connecté (ses propres RDV si mine_only=true).
"""
)
async def list_appointments(
    limit: int = 100,
    future_only: bool = False,
    mine_only: bool = False,
    partner_id: Optional[int] = None,
    session: OdooSession = Depends(get_odoo),
):
    try:
        from datetime import datetime, timezone

        admin_user = os.getenv("ODOO_USERNAME")
        admin_pass = os.getenv("ODOO_PASSWORD")
        try:
            read_session = await _authenticate(admin_user, admin_pass, _ODOO_URL, _ODOO_DB)
        except Exception:
            read_session = session

        domain: list = []

        # Obtenir le partner_id rattaché à session.uid
        user_partner_id = partner_id
        if not user_partner_id and session.uid:
            try:
                user_rec = await read_session.read('res.users', [session.uid], ['partner_id'])
                if user_rec and user_rec[0].get('partner_id'):
                    p = user_rec[0]['partner_id']
                    user_partner_id = p[0] if isinstance(p, list) else p
            except Exception:
                pass

        if mine_only or user_partner_id:
            sub_domains = []
            if session.uid:
                sub_domains.append(['user_id', '=', session.uid])
            if user_partner_id:
                sub_domains.append(['partner_ids', 'in', [user_partner_id]])

            if len(sub_domains) == 2:
                domain = ['|', sub_domains[0], sub_domains[1]]
            elif len(sub_domains) == 1:
                domain = [sub_domains[0]]

        if future_only:
            now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            date_filter = ['start', '>=', now_str]
            if domain:
                domain = ['&', date_filter] + domain
            else:
                domain = [date_filter]

        clean_fields = [
            'id', 'display_name', 'name', 'description',
            'start', 'stop', 'allday', 'duration',
            'location', 'show_as', 'privacy',
            'user_id', 'partner_ids',
            'videocall_location', 'videocall_source',
            'appointment_status', 'appointment_type_id',
            'active', 'display_time',
        ]

        records = await read_session.search_read(
            'calendar.event',
            domain,
            clean_fields,
            limit=limit,
        )
        return [{"id": r["id"], "data": r} for r in records]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur lecture rendez-vous: {str(exc)}")



# ---------------------------------------------------------------------------
# Lister les types de rendez-vous Odoo (module Rendez-vous / Appointments)
# ---------------------------------------------------------------------------
APPT_TYPE_FIELDS = [
    'id', 'name', 'active', 'category',
    'appointment_duration', 'appointment_duration_unit',
    'schedule_based_on', 'location_id', 'location',
    'staff_user_ids',
    'appointment_count', 'appointment_count_report',
]

@app.get(
    '/appointments/types/',
    tags=["Rendez-vous"],
    summary="Lister les types de rendez-vous Odoo (module Rendez-vous)",
    description="""
Retourne les types de rendez-vous (`appointment.type` ou `calendar.appointment.type`) publiés,
équivalent à la page `https://testjack.odoo.com/odoo/appointments`.
"""
)
async def list_appointment_types(
    limit: int = 50,
    session: OdooSession = Depends(get_odoo),
):
    """Retourne les types de rendez-vous publiés."""
    model_names = ['appointment.type', 'calendar.appointment.type']
    last_error = None

    for model in model_names:
        try:
            # Récupérer les champs valides disponibles sur ce modèle Odoo
            available_fields = await session.fields_get(model)
            fields_to_read = [f for f in APPT_TYPE_FIELDS if f in available_fields]

            records = await session.search_read(
                model,
                [['active', '=', True]],
                fields_to_read,
                limit=limit,
            )
            return [{"id": r["id"], "data": r, "model": model} for r in records]
        except Exception as exc:
            last_error = exc
            continue

    raise HTTPException(status_code=400, detail=f"Erreur lecture types de rendez-vous: {str(last_error)}")


@app.get(
    '/therapists/',
    tags=["Thérapeutes"],
    summary="Lister les thérapeutes/psychologues Odoo avec leurs photos de profil",
    description="""
Retourne la liste des psychologues/thérapeutes de l'instance Odoo avec leurs photos de profil (format data-URI base64).
Si `appointment_type_id` ou `service_title` est fourni, seuls les thérapeutes rattachés (`staff_user_ids`) à ce type de rendez-vous seront retournés.
"""
)
async def list_therapists(
    appointment_type_id: Optional[int] = None,
    service_title: Optional[str] = None,
    session: OdooSession = Depends(get_odoo),
):
    """Retourne les thérapeutes Odoo avec leurs images d'avatar (filtrés par type de rendez-vous si spécifié)."""
    try:
        allowed_user_ids: Optional[list] = None

        # Si appointment_type_id ou service_title est spécifié, récupérer staff_user_ids sur Odoo
        target_type_id = appointment_type_id
        if not target_type_id and service_title:
            # Supprimer les suffixes de prix comme '/55 USD', '/120USD', '- 30 USD', '/ 70USD'
            # mais NE PAS couper 'enfants/ados' (le mot après / ne commence pas par un chiffre)
            clean_title = re.sub(r'\s*/\s*\d+.*$|\s+-\s*\d+.*$', '', service_title).strip()
            # Nettoyer les traits d'union résiduels (ex: 'enfants/ados -20...' → 'enfants/ados')
            clean_title = re.sub(r'\s+-.*$', '', clean_title).strip()

            for model_name in ['appointment.type', 'calendar.appointment.type']:
                try:
                    types = await session.search_read(
                        model_name,
                        [['name', 'ilike', clean_title]],
                        ['id', 'name', 'staff_user_ids'],
                        limit=1
                    )
                    if types:
                        target_type_id = types[0]['id']
                        allowed_user_ids = types[0].get('staff_user_ids') or []
                        break
                except Exception:
                    continue

            # Fallback : si toujours pas trouvé, essayer avec les 3 premiers mots significatifs
            if target_type_id is None and len(clean_title) > 10:
                keywords = ' '.join(clean_title.split()[:3])
                for model_name in ['appointment.type', 'calendar.appointment.type']:
                    try:
                        types = await session.search_read(
                            model_name,
                            [['name', 'ilike', keywords]],
                            ['id', 'name', 'staff_user_ids'],
                            limit=1
                        )
                        if types:
                            target_type_id = types[0]['id']
                            allowed_user_ids = types[0].get('staff_user_ids') or []
                            break
                    except Exception:
                        continue
        elif target_type_id:
            for model_name in ['appointment.type', 'calendar.appointment.type']:
                try:
                    types = await session.read(model_name, [target_type_id], ['staff_user_ids'])
                    if types:
                        allowed_user_ids = types[0].get('staff_user_ids') or []
                        break
                except Exception:
                    continue

        # Domaine de recherche sur res.users
        domain = [['share', '=', False], ['active', '=', True]]
        if allowed_user_ids is not None:
            if not allowed_user_ids:
                return []
            domain.append(['id', 'in', allowed_user_ids])

        users = await session.search_read(
            'res.users',
            domain,
            ['id', 'name', 'login', 'email', 'partner_id', 'avatar_128', 'image_128'],
            limit=50,
        )

        IGNORED_PATTERNS = ['odoobot', 'automated process', 'centre d\'assistance', 'capsy sarl', 'capsy services']

        therapists = []
        for u in users:
            name = u.get('name') or ''
            if any(ign in name.lower() for ign in IGNORED_PATTERNS):
                continue
            avatar_b64 = u.get('avatar_128') or u.get('image_128') or False
            avatar_url = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else None
            p_id = u.get('partner_id')
            partner_id = p_id[0] if isinstance(p_id, list) else p_id

            therapists.append({
                'id': u['id'],
                'partner_id': partner_id,
                'name': name,
                'email': u.get('email') or u.get('login'),
                'avatar': avatar_url,
            })
        return therapists
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erreur lecture thérapeutes: {str(exc)}")
    """Teste l'authentification et un appel simple `fields_get`/`search_read` pour diagnostiquer 404/erreurs.
    Retourne le résultat ou l'erreur détaillée.
    """
    try:
        # essayer un fields_get sur res.partner
        try:
            fg = await session.fields_get('res.partner')
        except Exception as e:
            return {"status": "error", "stage": "fields_get", "detail": str(e)}

        # essayer un search_read simple
        try:
            res = await session.search_read('res.partner', [], ['id', 'name'], limit=1)
            return {"status": "ok", "fields_get_sample_keys": list(fg.keys())[:5], "sample": res}
        except Exception as e:
            return {"status": "error", "stage": "search_read", "detail": str(e)}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Debug Odoo failed: {str(exc)}")

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


@app.post('/session/call', tags=["🔐 Session"], summary="Appel JSON-RPC via session_id (proxy)")
async def session_call(req: SessionCallRequest):
    """Permet à un client front (ayant un `session_id` et `uid`) d'invoquer `call_kw` via la session existante.
    Utile pour déléguer des actions Odoo sans transmettre le mot de passe.
    """
    url_to_use = req.url or _ODOO_URL
    db_to_use = req.db or _ODOO_DB
    if not req.session_id or not req.uid:
        raise HTTPException(status_code=400, detail="session_id et uid requis")

    session = OdooSession(base_url=url_to_use, db=db_to_use, uid=req.uid, session_id=req.session_id, username=req.username)
    try:
        args = req.args or []
        kwargs = req.kwargs or {}
        result = await session.call_kw(req.model, req.method, args, kwargs)
        return {"result": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur Odoo via session: {str(exc)}")

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
    "vent": {"model": "product.product", "label": "Ventes - Produits"},
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
async def resolve_model_name(odoo_client, model_name):
    fallbacks = {
        "mail.channel": ["discuss.channel", "mail.channel"],
        "im_livechat.channel": ["im_livechat.channel", "discuss.channel"],
    }
    if model_name in fallbacks:
        for fb in fallbacks[model_name]:
            try:
                # Vérification via fields_get (JSON-RPC safe)
                fields = await odoo_client.fields_get(fb)
                if fields:
                    return fb
            except Exception:
                continue
    return model_name

# Cache pour stocker les champs sûrs par modèle
FIELDS_CACHE: Dict[str, list] = {}

async def get_safe_fields(session: OdooSession, model_name: str) -> list:
    if model_name not in FIELDS_CACHE:
        try:
            fields_info = await session.fields_get(model_name)
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
            resolved_model = await resolve_model_name(session, model_name)
            fields_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else await get_safe_fields(session, resolved_model)
            try:
                records = await session.search_read(resolved_model, [], fields_list or None, limit=limit)
            except Exception:
                records = await session.search_read(resolved_model, [], ["id", "display_name"], limit=limit)
            return [{"id": r["id"], "data": r} for r in records]
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "Access Denied" in error_msg or "n'êtes pas autorisé" in error_msg:
                raise HTTPException(status_code=403, detail=f"Accès refusé pour '{tag}' : droits insuffisants sur ce modèle.")
            raise HTTPException(status_code=404, detail=f"Erreur de lecture {tag}: {error_msg}")

    @app_instance.post(f"{prefix}/", response_model=ItemResponse, tags=[tag], summary=f"Écrire (Créer) {tag}")
    async def create_item(item: ItemBase, session: OdooSession = Depends(get_odoo)):
        try:
            resolved_model = await resolve_model_name(session, model_name)
            new_id = await session.create(resolved_model, item.data)
            return {"id": new_id, "data": item.data}
        except Exception as e:
            error_msg = str(e)
            if "AccessError" in error_msg or "Access Denied" in error_msg:
                raise HTTPException(status_code=403, detail=f"Accès refusé pour '{tag}' : droits insuffisants (création).")
            raise HTTPException(status_code=400, detail=f"Erreur de création {tag}: {error_msg}")

    @app_instance.put(f"{prefix}/{{item_id}}", response_model=ItemResponse, tags=[tag], summary=f"Modifier {tag}")
    async def update_item(item_id: int, item: ItemBase, session: OdooSession = Depends(get_odoo)):
        try:
            resolved_model = await resolve_model_name(session, model_name)
            await session.write(resolved_model, [item_id], item.data)
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

