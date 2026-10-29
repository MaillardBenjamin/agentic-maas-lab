"""Conservative AI reservation ceiling: real advisory lock, isolated PostgreSQL schema."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import uuid
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema,DropSchema
from maas import budget
from maas.db import Base,Record,engine as source
schema='budget_test_'+uuid.uuid4().hex
with source.begin() as conn:conn.execute(CreateSchema(schema))
engine=create_engine(source.url,execution_options={'schema_translate_map':{None:schema}})
try:
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    with patch.object(budget,'Session',factory),patch.dict('os.environ',{'AI_MONTHLY_BUDGET_EUR':'1.00'}):
        def reserve(_):
            try:budget.reserve(30);return 'accepted'
            except HTTPException as e:
                assert e.status_code==429;return 'refused'
        with ThreadPoolExecutor(10) as pool:results=list(pool.map(reserve,range(10)))
        assert results.count('accepted')==3 and results.count('refused')==7
        assert budget.reserve(10)['reserved_cents']==100
        try:budget.reserve(1);raise AssertionError('Ceiling exceeded')
        except HTTPException as e:assert e.status_code==429
        with factory() as db:
            rows=list(db.scalars(select(Record).where(Record.kind=='budget')))
            assert len(rows)==1 and rows[0].data['reserved_cents']==100
    print(json.dumps({'status':'passed','database':'PostgreSQL isolated schema','concurrent_requests':10,'accepted_30_cents':3,'refused':7,'exact_ceiling_allowed':100,'excess_rejected_without_increment':True}))
finally:
    engine.dispose()
    with source.begin() as conn:conn.execute(DropSchema(schema,cascade=True))
