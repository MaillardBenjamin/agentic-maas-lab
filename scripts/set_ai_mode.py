"""Select the text provider without printing or changing any credential."""
import argparse
import os
from pathlib import Path
import re
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["disabled", "openai", "ollama"])
args = parser.parse_args()
path = Path(".env")
if path.is_symlink():
    raise SystemExit("Configuration symbolique refusée")
lines = path.read_text().splitlines() if path.exists() else Path(".env.example").read_text().splitlines()
changes = {"AI_ENABLED": "false" if args.mode == "disabled" else "true", "AGENT_MODE": args.mode}
if args.mode == "ollama":
    existing = {line.split("=", 1)[0] for line in lines if "=" in line}
    for key, value in {"OLLAMA_HOST": "http://host.docker.internal:11434", "OLLAMA_MODEL": "qwen3:14b"}.items():
        if key not in existing:
            changes[key] = value
seen = set()
updated = []
for line in lines:
    match = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=", line)
    key = match.group(1) if match else None
    if key in changes:
        if key not in seen:
            updated.append(key + "=" + changes[key])
        seen.add(key)
    else:
        updated.append(line)
updated += [key + "=" + value for key, value in changes.items() if key not in seen]
fd, temporary = tempfile.mkstemp(dir=".", prefix=".env.tmp.")
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write("\n".join(updated) + "\n")
    os.replace(temporary, path)
finally:
    Path(temporary).unlink(missing_ok=True)
print("Text provider selected: " + args.mode + "; credentials preserved. Recreate api and agents to apply.")
