"""Conservative source scan. Reports locations only, never matched values."""
import re
from pathlib import Path

patterns = [re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{35,}\b"), re.compile(r"sandbox_secret_[A-Za-z0-9]{30,}")]
skip = {".git", ".venv", "node_modules", "dist", "out", "cache", "__pycache__", ".pytest_cache", "artifacts", "data", "target"}
found = []
for path in Path(".").rglob("*"):
    if not path.is_file() or path.name == ".env" or any(p in skip for p in path.parts):
        continue
    try:
        lines = path.read_text().splitlines()
    except (UnicodeDecodeError, OSError):
        continue
    for i, line in enumerate(lines, 1):
        if any(pattern.search(line) for pattern in patterns):
            found.append(f"{path}:{i}")
if found:
    raise SystemExit("Possible secrets in source at: " + ", ".join(found))
print("Source scan passed: no matching OpenAI or Bridge secrets. Local .env intentionally excluded.")
