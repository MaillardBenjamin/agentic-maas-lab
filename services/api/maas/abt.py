"""Account-based transport entitlements and deterministic simulated monthly billing."""
import calendar
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from maas.db import Record, Session
from maas.domain import digest
from maas.organizations import CATALOG
from maas.security import USERS, access, principal, service


def utc_now():
    return datetime.now(timezone.utc)


def today():
    return utc_now().date()


def month(start, offset):
    index = start.year * 12 + start.month - 1 + offset
    return date(index // 12, index % 12 + 1, min(start.day, calendar.monthrange(index // 12, index % 12 + 1)[1]))


def rows(db, kind):
    return db.scalars(select(Record).where(Record.kind == kind).order_by(Record.id))


def locked(db, rid, kind):
    row = db.scalar(select(Record).where(Record.id == rid, Record.kind == kind).with_for_update().execution_options(populate_existing=True))
    if not row:
        raise HTTPException(404, 'Référence ABT inconnue')
    return row


def owner(user, traveler):
    profile = USERS.get(traveler)
    if not profile or profile['role'] != 'traveler':
        raise HTTPException(422, 'Voyageur inconnu')
    access(user, {'org': profile['org'], 'traveler': traveler})
    return profile


def ensure_account(db, org, traveler):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    aid = 'abt-account-' + org + '-' + traveler
    insert = sqlite_insert if db.bind.dialect.name == 'sqlite' else pg_insert
    db.execute(insert(Record).values(id=aid, kind='abt_account', data={'id': aid, 'org': org, 'traveler': traveler}).on_conflict_do_nothing(index_elements=['id']))
    return aid


def link_known_orders(db):
    for record in list(db.scalars(select(Record).where(Record.kind.in_(['order', 'abt_contract', 'abt_invoice', 'abt_usage'])).order_by(Record.id))):
        order = record.data
        profile = USERS.get(order.get('traveler'))
        if profile and profile['role'] == 'traveler' and profile['org'] == order.get('org'):
            aid = ensure_account(db, order['org'], order['traveler'])
            if order.get('account_id') != aid:
                if record.kind in ('abt_invoice', 'abt_usage'):
                    locked(db, order['contract_id'], 'abt_contract')
                current = locked(db, record.id, record.kind)
                current.data = {**current.data, 'account_id': aid}


def invoice(db, contract, period, due, amount):
    iid = 'abt-invoice-' + digest({'contract': contract['id'], 'period': period})
    if not db.get(Record, iid):
        value = {'id': iid, 'contract_id': contract['id'], 'account_id': contract['account_id'], 'org': contract['org'], 'traveler': contract['traveler'], 'period': period, 'due_date': due, 'amount_cents': amount, 'currency': 'EUR', 'status': 'pending', 'mode': 'simulated_direct_debit'}
        db.add(Record(id=iid, kind='abt_invoice', data=value))
    return iid


def validate(db, row, passage_id, occurred_at):
    c = row.data
    at = occurred_at.astimezone(timezone.utc)
    fingerprint = digest({'passage': passage_id, 'time': at.isoformat()})
    eid = 'abt-usage-' + digest({'contract': c['id'], 'passage': passage_id})
    old = db.get(Record, eid)
    if old:
        if old.data['fingerprint'] != fingerprint:
            raise HTTPException(409, 'Passage déjà associé à un autre contenu')
        return {**old.data, 'duplicate': True}
    if at > utc_now() or not c['start_date'] <= at.date().isoformat() < c['end_date'] or c['status'] != 'active':
        raise HTTPException(409, 'Droit ABT inactif, hors période ou passage futur')
    period = at.strftime('%Y-%m')
    if c['terms']['billing'] == 'postpaid' and db.get(Record, 'abt-invoice-' + digest({'contract': c['id'], 'period': period})):
        raise HTTPException(409, 'Période facturée : rapprochement nécessaire')
    previous = sum(r.data['charge_cents'] for r in rows(db, 'abt_usage') if r.data['contract_id'] == c['id'] and r.data['period'] == period)
    charge = min(c['terms']['ride_cents'], max(0, c['terms']['monthly_cap_cents'] - previous)) if c['terms']['billing'] == 'postpaid' else 0
    value = {'id': eid, 'contract_id': c['id'], 'account_id': c['account_id'], 'org': c['org'], 'traveler': c['traveler'], 'passage_id': passage_id, 'occurred_at': at.isoformat(), 'period': period, 'charge_cents': charge, 'fingerprint': fingerprint, 'source': 'simulated_validator'}
    db.add(Record(id=eid, kind='abt_usage', data=value))
    return {**value, 'duplicate': False}


def collect(db, row, failed=False):
    value = row.data
    if value['status'] == 'paid_simulated':
        return value
    if value['due_date'] > today().isoformat():
        raise HTTPException(409, 'Échéance non encore exigible')
    attempt = {'status': 'failed' if failed else 'paid_simulated', 'at': utc_now().isoformat(), 'mode': 'simulated_direct_debit'}
    row.data = {**value, 'status': attempt['status'], 'last_attempt_at': attempt['at'], 'attempts': [*value.get('attempts', []), attempt]}
    c = locked(db, value['contract_id'], 'abt_contract')
    others = any(r.id != row.id and r.data['contract_id'] == c.id and r.data['status'] == 'failed' for r in rows(db, 'abt_invoice'))
    c.data = {**c.data, 'status': 'expired' if c.data['end_date'] <= today().isoformat() else 'suspended' if failed or others else 'active'}
    return row.data


def billing(db):
    now = today()
    link_known_orders(db)
    for record in list(rows(db, 'abt_contract')):
        row = locked(db, record.id, 'abt_contract')
        c = row.data
        if c['terms']['billing'] == 'postpaid':
            periods = sorted({r.data['period'] for r in rows(db, 'abt_usage') if r.data['contract_id'] == c['id'] and r.data['period'] < now.strftime('%Y-%m')})
            for period in periods:
                amount = sum(r.data['charge_cents'] for r in rows(db, 'abt_usage') if r.data['contract_id'] == c['id'] and r.data['period'] == period)
                invoice(db, c, period, month(date.fromisoformat(period+'-01'), 1).isoformat(), amount)
        for bill in list(rows(db, 'abt_invoice')):
            if bill.data['contract_id'] == c['id'] and bill.data['status'] == 'pending' and bill.data['due_date'] <= now.isoformat():
                collect(db, locked(db, bill.id, 'abt_invoice'))
        if c['end_date'] <= now.isoformat():
            row.data = {**row.data, 'status': 'expired'}


class Subscribe(BaseModel):
    traveler: str
    product: Literal['transport_annual', 'transport_postpaid']
    start_date: date
    consent: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=100)


class Passage(BaseModel):
    passage_id: str = Field(min_length=1, max_length=100)
    occurred_at: datetime


class Debit(BaseModel):
    failed: bool = False


def register(app):
    @app.get('/api/abt')
    def account(traveler: str | None = None, user=Depends(principal)):
        uid = traveler or (user['id'] if user['role'] == 'traveler' else None)
        owner(user, uid)
        with Session() as db:
            def scoped(kind):
                return [r.data for r in rows(db, kind) if r.data['org'] == user['org'] and r.data['traveler'] == uid]
            orders = [{'id': r.id, 'account_id': r.data.get('account_id'), 'state': r.data['state'], 'created_at': r.data['created_at'], 'products': [l['name'] for l in r.data['quote']['lines']], 'total_cents': r.data['quote']['total_cents']} for r in rows(db, 'order') if r.data['traveler'] == uid and r.data['org'] == user['org']]
            return {'id': 'abt-account-' + user['org'] + '-' + uid, 'orders': orders, 'traveler': uid, 'contracts': scoped('abt_contract'), 'invoices': sorted(scoped('abt_invoice'), key=lambda i: (i['due_date'], i['id'])), 'usages': scoped('abt_usage'), 'offers': CATALOG['abt_products'], 'mode': 'simulation', 'note': 'Droits conservés sur votre compte. Prélèvements simulés, aucun débit bancaire.'}

    @app.get('/api/assistant/abt')
    def assistant_account(user=Depends(principal), x_maas_coordination: str = Header(default='')):
        from maas.history import selected_traveler
        return account(selected_traveler(user, x_maas_coordination), user)

    @app.post('/api/abt/subscriptions')
    def subscribe(body: Subscribe, user=Depends(principal)):
        owner(user, body.traveler)
        cid = 'abt-' + digest({'org': user['org'], 'actor': user['id'], 'key': body.idempotency_key})
        fingerprint = digest(body.model_dump(mode='json'))
        try:
            with Session.begin() as db:
                # Serialize subscriptions for a traveler across all sellers and products.
                aid = ensure_account(db, user['org'], body.traveler)
                locked(db, aid, 'abt_account')
                old = db.get(Record, cid)
                if old:
                    if old.data['request_digest'] != fingerprint:
                        raise HTTPException(409, 'Clé déjà utilisée pour une autre souscription')
                    return old.data
                if body.start_date < today():
                    raise HTTPException(422, 'La souscription ne peut pas être rétroactive')
                end = month(body.start_date, 12)
                for r in rows(db, 'abt_contract'):
                    c = r.data
                    if c['org'] == user['org'] and c['traveler'] == body.traveler and c['start_date'] < end.isoformat() and c['end_date'] > body.start_date.isoformat():
                        raise HTTPException(409, 'Un titre ABT transport couvre déjà cette période')
                terms = dict(next(p for p in CATALOG['abt_products'] if p['id'] == body.product))
                value = {'id': cid, 'org': user['org'], 'traveler': body.traveler, 'account_id': aid, 'product': body.product, 'terms': terms, 'start_date': body.start_date.isoformat(), 'end_date': end.isoformat(), 'status': 'active', 'request_digest': fingerprint, 'mandate': {'mode': 'simulated', 'consented_at': utc_now().isoformat(), 'actor': user['id']}, 'created_at': utc_now().isoformat()}
                db.add(Record(id=cid, kind='abt_contract', data=value))
                if terms['billing'] == 'annual_monthly':
                    for i in range(12):
                        invoice(db, value, str(i+1), month(body.start_date, i).isoformat(), terms['monthly_cents'])
                return value
        except IntegrityError:
            # First account creation may race. Re-submit unchanged; no partial contract persists.
            raise HTTPException(409, 'Souscription concurrente : réessayez avec la même clé')

    @app.post('/api/demo/abt/{cid}/validate')
    def passage(cid: str, body: Passage, user=Depends(principal)):
        if body.occurred_at.tzinfo is None:
            raise HTTPException(422, 'Fuseau horaire requis')
        with Session.begin() as db:
            row = locked(db, cid, 'abt_contract'); access(user, row.data)
            return validate(db, row, body.passage_id, body.occurred_at)

    @app.post('/api/demo/abt/invoices/{iid}/collect')
    def debit(iid: str, body: Debit, user=Depends(principal)):
        with Session.begin() as db:
            # Same lock order as billing: contract, then invoice.
            ref = db.get(Record, iid)
            if not ref or ref.kind != 'abt_invoice':
                raise HTTPException(404, 'Échéance inconnue')
            access(user, ref.data)
            locked(db, ref.data['contract_id'], 'abt_contract')
            return collect(db, locked(db, iid, 'abt_invoice'), body.failed)

    @app.post('/internal/abt/billing', dependencies=[Depends(service)])
    def run_billing():
        with Session.begin() as db:
            billing(db)
        return {'mode': 'simulated_direct_debit', 'status': 'processed'}
