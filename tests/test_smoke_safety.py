"""The local security audit must not create cloud credentials or print them."""
import importlib.util
from pathlib import Path
import runpy
import sys
from types import ModuleType
import httpx
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'

def test_audio_response_is_redacted_if_a_smoke_assertion_fails(monkeypatch):
    spec=importlib.util.spec_from_file_location('smoke_safety',SCRIPTS/'smoke.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module.httpx,'request',lambda *a,**kw:httpx.Response(200,json={'value':'SECRET_SHOULD_NEVER_BE_PRINTED'}))
    with pytest.raises(AssertionError) as error:module.call('/api/voice/session',{}, {'consent':True},503)
    assert 'SECRET_SHOULD_NEVER_BE_PRINTED' not in str(error.value)
    assert 'masquée' in str(error.value)


def test_security_smoke_checks_audio_independently_from_agent_provider(monkeypatch):
    calls=[]
    def call(path,headers,body=None,status=200):
        calls.append((path,body,status))
        if path=='/api/orders':return [{'id':'o','state':'fulfilled'}]
        if path=='/api/quotes':return {'id':'q'}
        if path=='/api/budget':return {'reserved_cents':0}
        if path=='/api/integrations':return [{'name':'OpenAI','mode':'unconfigured'},{'name':'Ollama','mode':'configured'},{'name':'Bridge','mode':'configured'}]
        if path=='/api/voice/status':return {'configured':True}
        if path=='/api/voice/session':
            assert body=={'consent':False} and status==422,'Must not create a cloud session during a security check'
        return {}
    module=ModuleType('smoke');module.call=call;module.login=lambda uid:{}
    monkeypatch.setitem(sys.modules,'smoke',module)
    monkeypatch.setattr(sys,'argv',['security_smoke.py'])
    runpy.run_path(str(SCRIPTS/'security_smoke.py'),run_name='__main__')
    assert any(path=='/api/voice/session' for path,_,_ in calls)
