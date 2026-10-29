"""Execution-line audit using stdlib only. This is not branch or scenario coverage."""
import json
from pathlib import Path
import sys
import threading
import trace
import pytest
path=str(Path('/app/maas/abt.py').resolve());seen=set()
def observe(frame,event,arg):
    if frame.f_code.co_filename==path:
        if event=='line':seen.add(frame.f_lineno)
        return observe
    return None
sys.settrace(observe);threading.settrace(observe)
try:status=pytest.main(['-q','tests/test_abt.py','tests/test_abt_worker.py'])
finally:sys.settrace(None);threading.settrace(None)
executable={n for n in trace._find_executable_linenos(path) if n > 0}
print(json.dumps({'type':'execution_lines_not_branches','file':'services/api/maas/abt.py','executed':len(executable&seen),'executable':len(executable),'percent':round(100*len(executable&seen)/len(executable),1),'unexecuted_lines':sorted(executable-seen),'test_exit_code':status}))
sys.exit(status)
