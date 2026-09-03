import os
import sys
from typing import List, Optional, Dict, Any
import xmlrpc.client

from fastapi import APIRouter, HTTPException, status

# Ensure the package root (capsy-odoo-api) is on sys.path so we can import schemas
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from schemas.formations import (
    FormationSchema,
    SignataireSchema,
    ParticipantSchema,
)

import json
from pathlib import Path

# path to seed data
DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
SEED_FILE = DATA_DIR / 'formations_seed.json'


def _load_seed() -> List[Dict[str, Any]]:
    if not SEED_FILE.exists():
        return []
    try:
        with open(SEED_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            if not isinstance(data, list):
                return []

            # normalize entries to match expected API schema
            normalized: List[Dict[str, Any]] = []
            for rec in data:
                if not isinstance(rec, dict):
                    continue
                r = dict(rec)

                # partners: allow comma-separated string in seed -> list
                p = r.get('x_studio_partenaires')
                if isinstance(p, str):
                    r['x_studio_partenaires'] = [s.strip() for s in p.split(',') if s.strip()]

                # normalize description field name differences
                if 'x_studio_description_1' in r and 'x_studio_description' not in r:
                    r['x_studio_description'] = r.pop('x_studio_description_1')

                # ensure competences is a list of strings
                comps = r.get('x_studio_competences_visees') or []
                if isinstance(comps, list):
                    r['x_studio_competences_visees'] = [str(c) for c in comps]
                else:
                    r['x_studio_competences_visees'] = [s.strip() for s in str(comps).split(',') if s.strip()]

                # signataires: ensure list of dicts with x_name/x_studio_role
                signs = r.get('x_studio_signataires') or []
                if isinstance(signs, list):
                    normalized_signs = []
                    for s in signs:
                        if isinstance(s, dict):
                            normalized_signs.append(s)
                    r['x_studio_signataires'] = normalized_signs
                else:
                    r['x_studio_signataires'] = []

                # participants: ensure list of dicts
                parts = r.get('x_studio_participant_ids') or []
                if isinstance(parts, list):
                    normalized_parts = []
                    for p in parts:
                        if isinstance(p, dict):
                            normalized_parts.append(p)
                    r['x_studio_participant_ids'] = normalized_parts
                else:
                    r['x_studio_participant_ids'] = []

                normalized.append(r)

            return normalized
    except Exception:
        return []


def _get_odoo_connection():
    url = os.getenv("ODOO_URL", "http://localhost:8069")
    db = os.getenv("ODOO_DB", "odoo")
    username = os.getenv("ODOO_USERNAME", "admin")
    password = os.getenv("ODOO_PASSWORD", "admin")

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return models, uid, db, password


router = APIRouter(prefix="/formations", tags=["Formations"])


def _search_read(models, uid, db, password, model, domain, fields):
    return models.execute_kw(db, uid, password, model, 'search_read', [domain], {'fields': fields})


def _available_fields(models, uid, db, password, model) -> set:
    try:
        res = models.execute_kw(db, uid, password, model, 'fields_get', [], {'attributes': ['type']})
        return set(res.keys())
    except Exception:
        return set()


def _search(models, uid, db, password, model, domain):
    return models.execute_kw(db, uid, password, model, 'search', [domain])


def _create(models, uid, db, password, model, vals):
    return models.execute_kw(db, uid, password, model, 'create', [vals])


def _write(models, uid, db, password, model, ids, vals):
    return models.execute_kw(db, uid, password, model, 'write', [ids, vals])


def _unlink(models, uid, db, password, model, ids):
    return models.execute_kw(db, uid, password, model, 'unlink', [ids])


def _build_formation_response(record: Dict[str, Any], comps_map, sign_map, part_map) -> Dict[str, Any]:
    # record contains Odoo keys already (x_name, x_studio_identifiant_code, ...)
    partners_raw = record.get('x_studio_partenaires') or ''
    partners = [p.strip() for p in partners_raw.split(',') if p.strip()]

    comp_ids = record.get('x_studio_competences_visees') or []
    competences = [comps_map.get(cid, {}).get('x_name') for cid in comp_ids if cid in comps_map]

    sign_ids = record.get('x_studio_signataires') or []
    signataires = [
        {
            'x_name': sign_map[sid]['x_name'],
            'x_studio_role': sign_map[sid].get('x_studio_role', '')
        }
        for sid in sign_ids
        if sid in sign_map
    ]

    part_ids = record.get('x_studio_participant_ids') or []
    participants = [
        {
            'x_studio_numero_de_certificat': part_map[pid].get('x_studio_numero_de_certificat', ''),
            'x_name': part_map[pid].get('x_name', ''),
            'x_studio_titre_professionnel': part_map[pid].get('x_studio_titre_professionnel', ''),
        }
        for pid in part_ids
        if pid in part_map
    ]

    payload = {
        'x_studio_identifiant_code': record.get('x_studio_identifiant_code'),
        'x_name': record.get('x_name'),
        'x_studio_titre_court': record.get('x_studio_titre_court'),
        'x_studio_statut': record.get('x_studio_statut'),
        'x_studio_dates_texte': record.get('x_studio_dates_texte'),
        'x_studio_duree': record.get('x_studio_duree'),
        'x_studio_lieu': record.get('x_studio_lieu'),
        'x_studio_prefixe_certificat': record.get('x_studio_prefixe_certificat'),
        'x_studio_description': record.get('x_studio_description'),
        'x_studio_partenaires': partners,
        'x_studio_competences_visees': competences,
        'x_studio_signataires': signataires,
        'x_studio_participant_ids': participants,
    }
    return payload


@router.get('/', response_model=List[FormationSchema])
def list_formations():
    models, uid, db, password = _get_odoo_connection()
    requested_fields = [
        'x_studio_identifiant_code', 'x_name', 'x_studio_titre_court', 'x_studio_statut',
        'x_studio_dates_texte', 'x_studio_duree', 'x_studio_lieu', 'x_studio_prefixe_certificat',
        'x_studio_description', 'x_studio_partenaires', 'x_studio_competences_visees',
        'x_studio_signataires', 'x_studio_participant_ids'
    ]

    avail = _available_fields(models, uid, db, password, 'x_formation')
    fields = [f for f in requested_fields if f in avail]
    # always request id
    if 'id' not in fields:
        fields.insert(0, 'id')
    # fallback minimal fields if none of the requested ones exist
    if len(fields) <= 1:
        fields = ['id', 'name', 'display_name']

    records = _search_read(models, uid, db, password, 'x_formation', [], fields)

    # collect related ids
    comp_ids = set()
    sign_ids = set()
    part_ids = set()
    for r in records:
        comp_ids.update(r.get('x_studio_competences_visees') or [])
        sign_ids.update(r.get('x_studio_signataires') or [])
        part_ids.update(r.get('x_studio_participant_ids') or [])

    comps_map = {}
    if comp_ids:
        comp_avail = _available_fields(models, uid, db, password, 'x_competence')
        comp_fields = ['id'] + (['x_name'] if 'x_name' in comp_avail else [])
        comps = _search_read(models, uid, db, password, 'x_competence', [['id', 'in', list(comp_ids)]], comp_fields)
        comps_map = {c['id']: c for c in comps}

    sign_map = {}
    if sign_ids:
        sign_avail = _available_fields(models, uid, db, password, 'x_signataire')
        sign_fields = ['id']
        if 'x_name' in sign_avail:
            sign_fields.append('x_name')
        if 'x_studio_role' in sign_avail:
            sign_fields.append('x_studio_role')
        signs = _search_read(models, uid, db, password, 'x_signataire', [['id', 'in', list(sign_ids)]], sign_fields)
        sign_map = {s['id']: s for s in signs}

    part_map = {}
    if part_ids:
        part_avail = _available_fields(models, uid, db, password, 'x_participant')
        part_fields = ['id']
        for f in ['x_name', 'x_studio_numero_de_certificat', 'x_studio_titre_professionnel']:
            if f in part_avail:
                part_fields.append(f)
        parts = _search_read(models, uid, db, password, 'x_participant', [['id', 'in', list(part_ids)]], part_fields)
        part_map = {p['id']: p for p in parts}

    results = []
    for r in records:
        payload = _build_formation_response(r, comps_map, sign_map, part_map)
        results.append(payload)

    # If Odoo returned no records, fallback to seed file located in data/
    if not results:
        seed = _load_seed()
        if seed:
            # seed already follows the expected Odoo-like field names
            return seed

    return results


@router.get('/{code_id}', response_model=FormationSchema)
def get_formation(code_id: str):
    models, uid, db, password = _get_odoo_connection()
    requested_fields = [
        'x_studio_identifiant_code', 'x_name', 'x_studio_titre_court', 'x_studio_statut',
        'x_studio_dates_texte', 'x_studio_duree', 'x_studio_lieu', 'x_studio_prefixe_certificat',
        'x_studio_description', 'x_studio_partenaires', 'x_studio_competences_visees',
        'x_studio_signataires', 'x_studio_participant_ids'
    ]

    avail = _available_fields(models, uid, db, password, 'x_formation')
    fields = [f for f in requested_fields if f in avail]
    if 'id' not in fields:
        fields.insert(0, 'id')
    if len(fields) <= 1:
        fields = ['id', 'name', 'display_name']

    records = _search_read(models, uid, db, password, 'x_formation', [['x_studio_identifiant_code', '=', code_id]], fields)
    if not records:
        # fallback to seed file
        seed_rec = _get_from_seed_by_code(code_id)
        if seed_rec:
            return seed_rec
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formation not found")
    record = records[0]

    # fetch related records similarly
    comp_ids = set(record.get('x_studio_competences_visees') or [])
    sign_ids = set(record.get('x_studio_signataires') or [])
    part_ids = set(record.get('x_studio_participant_ids') or [])

    comps_map = {}
    if comp_ids:
        comps = _search_read(models, uid, db, password, 'x_competence', [['id', 'in', list(comp_ids)]], ['id', 'x_name'])
        comps_map = {c['id']: c for c in comps}

    sign_map = {}
    if sign_ids:
        signs = _search_read(models, uid, db, password, 'x_signataire', [['id', 'in', list(sign_ids)]], ['id', 'x_name', 'x_studio_role'])
        sign_map = {s['id']: s for s in signs}

    part_map = {}
    if part_ids:
        parts = _search_read(models, uid, db, password, 'x_participant', [['id', 'in', list(part_ids)]], ['id', 'x_name', 'x_studio_numero_de_certificat', 'x_studio_titre_professionnel'])
        part_map = {p['id']: p for p in parts}

    payload = _build_formation_response(record, comps_map, sign_map, part_map)
    return payload


def _get_from_seed_by_code(code_id: str) -> Optional[Dict[str, Any]]:
    seed = _load_seed()
    for r in seed:
        if r.get('x_studio_identifiant_code') == code_id or r.get('x_studio_identifiant_code') == code_id:
            return r
    return None

    # If not found in Odoo, try seed file fallback



@router.post('/', response_model=FormationSchema, status_code=status.HTTP_201_CREATED)
def create_formation(payload: FormationSchema):
    models, uid, db, password = _get_odoo_connection()

    # 1. Competences: ensure exist and collect ids
    comp_ids = []
    for name in payload.competences:
        found = _search(models, uid, db, password, 'x_competence', [['x_name', '=', name]])
        if found:
            comp_ids.append(found[0])
        else:
            cid = _create(models, uid, db, password, 'x_competence', {'x_name': name})
            comp_ids.append(cid)

    # 2. Signataires
    sign_ids = []
    for s in payload.signataires:
        domain = [['x_name', '=', s.name], ['x_studio_role', '=', s.role]]
        found = _search(models, uid, db, password, 'x_signataire', domain)
        if found:
            sign_ids.append(found[0])
        else:
            sid = _create(models, uid, db, password, 'x_signataire', {'x_name': s.name, 'x_studio_role': s.role})
            sign_ids.append(sid)

    # 3. Create formation
    vals = {
        'x_studio_identifiant_code': payload.id,
        'x_name': payload.title,
        'x_studio_titre_court': payload.shortTitle,
        'x_studio_statut': payload.status,
        'x_studio_dates_texte': payload.dateRange,
        'x_studio_duree': payload.duration,
        'x_studio_lieu': payload.location,
        'x_studio_prefixe_certificat': payload.certifNumPrefix,
        'x_studio_description': payload.description,
        'x_studio_partenaires': ', '.join(payload.partners) if payload.partners else '',
        'x_studio_competences_visees': [(6, 0, comp_ids)],
        'x_studio_signataires': [(6, 0, sign_ids)],
    }
    formation_id = _create(models, uid, db, password, 'x_formation', vals)

    # 4. Participants: attach to formation
    for p in payload.participants:
        p_vals = {
            'x_name': p.name,
            'x_studio_numero_de_certificat': p.id,
            'x_studio_titre_professionnel': p.title,
            'x_studio_formation_id': formation_id,
        }
        _create(models, uid, db, password, 'x_participant', p_vals)

    # return created formation (use provided code_id from payload)
    try:
        return get_formation(payload.id)
    except Exception:
        # fallback: attempt to fetch by internal id
        recs = _search_read(models, uid, db, password, 'x_formation', [['id', '=', formation_id]], ['id'])
        if recs:
            code = recs[0].get('x_studio_identifiant_code') or None
            if code:
                return get_formation(code)
        # If all fails, return minimal representation
        return {
            'x_studio_identifiant_code': payload.id,
            'x_name': payload.title,
            'x_studio_partenaires': payload.partners,
            'x_studio_competences_visees': payload.competences,
            'x_studio_signataires': [s.dict(by_alias=True) for s in payload.signataires],
            'x_studio_participant_ids': [p.dict(by_alias=True) for p in payload.participants],
        }


@router.put('/{code_id}', response_model=FormationSchema)
def update_formation(code_id: str, payload: FormationSchema):
    models, uid, db, password = _get_odoo_connection()
    recs = _search_read(models, uid, db, password, 'x_formation', [['x_studio_identifiant_code', '=', code_id]], ['id'])
    if not recs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formation not found")
    formation_id = recs[0]['id']

    # update competences and signataires similarly to create
    comp_ids = []
    for name in payload.competences:
        found = _search(models, uid, db, password, 'x_competence', [['x_name', '=', name]])
        if found:
            comp_ids.append(found[0])
        else:
            cid = _create(models, uid, db, password, 'x_competence', {'x_name': name})
            comp_ids.append(cid)

    sign_ids = []
    for s in payload.signataires:
        domain = [['x_name', '=', s.name], ['x_studio_role', '=', s.role]]
        found = _search(models, uid, db, password, 'x_signataire', domain)
        if found:
            sign_ids.append(found[0])
        else:
            sid = _create(models, uid, db, password, 'x_signataire', {'x_name': s.name, 'x_studio_role': s.role})
            sign_ids.append(sid)

    vals = {
        'x_name': payload.title,
        'x_studio_titre_court': payload.shortTitle,
        'x_studio_statut': payload.status,
        'x_studio_dates_texte': payload.dateRange,
        'x_studio_duree': payload.duration,
        'x_studio_lieu': payload.location,
        'x_studio_prefixe_certificat': payload.certifNumPrefix,
        'x_studio_description': payload.description,
        'x_studio_partenaires': ', '.join(payload.partners) if payload.partners else '',
        'x_studio_competences_visees': [(6, 0, comp_ids)],
        'x_studio_signataires': [(6, 0, sign_ids)],
    }
    _write(models, uid, db, password, 'x_formation', formation_id, vals)

    # participants: remove existing and recreate to match payload
    existing_parts = _search(models, uid, db, password, 'x_participant', [['x_studio_formation_id', '=', formation_id]])
    if existing_parts:
        _unlink(models, uid, db, password, 'x_participant', existing_parts)

    for p in payload.participants:
        p_vals = {
            'x_name': p.name,
            'x_studio_numero_de_certificat': p.id,
            'x_studio_titre_professionnel': p.title,
            'x_studio_formation_id': formation_id,
        }
        _create(models, uid, db, password, 'x_participant', p_vals)

    return get_formation(payload.id)


@router.delete('/{code_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_formation(code_id: str):
    models, uid, db, password = _get_odoo_connection()
    recs = _search_read(models, uid, db, password, 'x_formation', [['x_studio_identifiant_code', '=', code_id]], ['id', 'x_studio_participant_ids'])
    if not recs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formation not found")
    formation = recs[0]
    formation_id = formation['id']

    # delete participants first
    part_ids = formation.get('x_studio_participant_ids') or []
    if part_ids:
        _unlink(models, uid, db, password, 'x_participant', part_ids)

    _unlink(models, uid, db, password, 'x_formation', [formation_id])
    return None
