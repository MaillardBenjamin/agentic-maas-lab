"""A failed proof endpoint cannot starve monthly ABT billing, and vice versa."""
import asyncio
import httpx
import pytest
from worker import main as worker

@pytest.mark.parametrize('unavailable',['/internal/proofs/dispatch','/internal/abt/billing',None])
def test_dispatcher_keeps_both_jobs_independent_and_cancels_cleanly(monkeypatch,unavailable):
    calls=[];sleeps=[]
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def post(self,url,headers):
            path='/internal/'+url.split('/internal/')[1];calls.append(path)
            request=httpx.Request('POST',url)
            return httpx.Response(503 if path==unavailable else 200,request=request)
    async def sleep(delay):
        sleeps.append(delay)
        if len(sleeps)==2:raise asyncio.CancelledError()
    monkeypatch.setattr(worker.httpx,'AsyncClient',lambda **kw:Client())
    monkeypatch.setattr(worker.asyncio,'sleep',sleep)
    with pytest.raises(asyncio.CancelledError):asyncio.run(worker.dispatch_proof_outbox())
    assert calls==['/internal/proofs/dispatch','/internal/abt/billing']*2
    assert sleeps==[5,5]
