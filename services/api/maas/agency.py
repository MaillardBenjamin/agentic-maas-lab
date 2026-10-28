"""Local agency/CRC contact cases, separate from financial effects."""
from datetime import datetime, timezone
from typing import Literal
import uuid

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from maas.db import Record, Session
from maas.domain import digest
from maas.security import USERS, principal


def advisor(user=Depends(principal)):
    if user['role'] not in ('clerk', 'supervisor'):
        raise HTTPException(403, 'Poste réservé aux conseillers et superviseurs')
    return user


class Contact(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    traveler: str = Field(max_length=80)
    order_id: str | None = Field(default=None, max_length=80)
    channel: Literal['station', 'phone', 'email']
    motive: Literal['information', 'sale', 'payment', 'delivery', 'parking', 'bike', 'other']
    summary: str = Field(min_length=5, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    revision: int = Field(ge=1, strict=True)
    status: Literal['open', 'pending', 'resolved'] | None = None
    note: str = Field(default='', max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')

    @model_validator(mode='after')
    def meaningful(self):
        if not self.note and self.status is None:
            raise ValueError('Note ou changement de statut requis')
        if self.status == 'resolved' and len(self.note) < 5:
            raise ValueError('Précisez la réponse apportée avant de clôturer le dossier')
        return self


def now():
    return datetime.now(timezone.utc).isoformat()


def case(db, cid, user, lock=False):
    query = select(Record).where(Record.id == cid, Record.kind == 'agency_case')
    record = db.scalar(query.with_for_update() if lock else query)
    if not record or record.data['org'] != user['org']:
        raise HTTPException(404, 'Dossier introuvable')
    return record


def register(app, log):
    @app.get('/api/agency/cases')
    def listing(user=Depends(advisor)):
        with Session() as db:
            values = db.scalars(select(Record).where(Record.kind == 'agency_case').order_by(Record.created_at.desc()))
            return [{k: v for k, v in r.data.items() if k not in ('notes', 'request_digest')} for r in values if r.data['org'] == user['org']][:100]

    @app.get('/api/agency/cases/{cid}')
    def read(cid: str, user=Depends(advisor)):
        with Session() as db:
            return case(db, cid, user).data

    @app.post('/api/agency/cases')
    def create(body: Contact, user=Depends(advisor)):
        customer = USERS.get(body.traveler)
        if not customer or customer['role'] != 'traveler' or customer['org'] != user['org']:
            raise HTTPException(422, 'Voyageur de démonstration inconnu')
        cid = 'contact-' + digest({'org': user['org'], 'actor': user['id'], 'key': body.idempotency_key})[:32]
        fingerprint = digest(body.model_dump())
        try:
            with Session.begin() as db:
                existing = db.get(Record, cid)
                if existing:
                    if existing.data['request_digest'] != fingerprint:
                        raise HTTPException(409, 'Clé déjà associée à un autre contact')
                    return existing.data
                if body.order_id:
                    order = db.get(Record, body.order_id)
                    if not order or order.kind != 'order' or order.data['org'] != user['org']:
                        raise HTTPException(404, 'Commande introuvable')
                    if order.data['traveler'] != body.traveler:
                        raise HTTPException(422, 'La commande appartient à un autre voyageur')
                timestamp = now()
                value = {'id': cid, 'org': user['org'], 'traveler': body.traveler, 'order_id': body.order_id, 'channel': body.channel, 'motive': body.motive, 'summary': body.summary, 'status': 'open', 'revision': 1, 'assigned_to': user['id'], 'created_at': timestamp, 'updated_at': timestamp, 'request_digest': fingerprint, 'notes': [{'id': uuid.uuid4().hex, 'at': timestamp, 'author': user['id'], 'text': body.summary, 'status': 'open'}]}
                db.add(Record(id=cid, kind='agency_case', data=value))
                log(db, 'agency.case.created', {'case_id': cid, 'order_id': body.order_id, 'org': user['org'], 'principal': user['id']})
                return value
        except IntegrityError:
            with Session() as db:
                existing = case(db, cid, user).data
                if existing['request_digest'] != fingerprint:
                    raise HTTPException(409, 'Clé déjà associée à un autre contact')
                return existing

    @app.post('/api/agency/cases/{cid}/updates')
    def update(cid: str, body: ContactUpdate, user=Depends(advisor)):
        uid = 'contact-update-' + digest({'case': cid, 'key': body.idempotency_key})
        fingerprint = digest(body.model_dump())
        with Session.begin() as db:
            rec = case(db, cid, user, lock=True)
            previous = db.get(Record, uid)
            if previous:
                if previous.data['request_digest'] != fingerprint:
                    raise HTTPException(409, 'Clé de mise à jour déjà utilisée')
                return rec.data
            value = rec.data
            if value['revision'] != body.revision:
                raise HTTPException(409, 'Le dossier a été modifié. Actualisez-le avant de reprendre votre note.')
            if len(value['notes']) >= 100:
                raise HTTPException(409, 'Historique du dossier plein pour ce démonstrateur')
            timestamp, status = now(), body.status or value['status']
            entry = {'id': uuid.uuid4().hex, 'at': timestamp, 'author': user['id'], 'text': body.note, 'status': status}
            result = {**value, 'status': status, 'revision': value['revision'] + 1, 'updated_at': timestamp, 'notes': [*value['notes'], entry]}
            rec.data = result
            db.add(Record(id=uid, kind='agency_update', data={'request_digest': fingerprint, 'case_id': cid}))
            log(db, 'agency.case.updated', {'case_id': cid, 'order_id': value['order_id'], 'org': user['org'], 'principal': user['id'], 'status': status})
            return result
