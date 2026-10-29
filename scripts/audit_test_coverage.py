"""Local line-execution inventory, not a completeness or branch-coverage claim."""
from collections import defaultdict
import json
from pathlib import Path
import sys
import threading
import trace
import pytest
roots=('/app/maas/','/app/worker/');seen=defaultdict(set)
def observe(frame,event,arg):
    filename=frame.f_code.co_filename
    if filename.startswith(roots):
        if event=='line':seen[filename].add(frame.f_lineno)
        return observe
    return None
sys.settrace(observe);threading.settrace(observe)
try:status=pytest.main(['-q','tests','--junitxml=/evidence/api-tests.xml'])
finally:sys.settrace(None);threading.settrace(None)
modules=[]
for root in roots:
    for source in sorted(Path(root).glob('*.py')):
        if source.name=='__init__.py':continue
        lines={n for n in trace._find_executable_linenos(str(source)) if n>0}
        hit=seen.get(str(source),set())&lines
        modules.append({'file':str(source).removeprefix('/app/'),'executed':len(hit),'executable':len(lines),'percent':round(100*len(hit)/len(lines),1) if lines else None,'not_executed':sorted(lines-hit)})
result={'scope':'pytest suite, execution lines only, excludes standalone integration scripts, agent runtime and frontend','exit_code':status,'modules':modules}
Path('/evidence/unit-line-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps([{k:v for k,v in m.items() if k!='not_executed'} for m in modules]))
sys.exit(status)
