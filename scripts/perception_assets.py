"""Download the official assets atomically, checking their decompressed SHA-256."""
import argparse
import bz2
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def verified(path, asset):
    if not path.is_file() or path.stat().st_size != asset['bytes']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == asset['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'data/perception/models'
    target.mkdir(parents=True, exist_ok=True)
    for asset in json.loads((ROOT / 'services/perception/assets.json').read_text())['assets']:
        destination = target / asset['name']
        if verified(destination, asset):
            print(asset['name'] + ': SHA-256 OK', flush=True)
            continue
        if args.verify_only:
            raise SystemExit(asset['name'] + ': absent ou invalide')
        print('Téléchargement : ' + asset['name'], flush=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target, delete=False) as output:
                temporary = Path(output.name)
                with urllib.request.urlopen(asset['url'], timeout=120) as source:
                    decompressor = bz2.BZ2Decompressor() if asset['compression'] == 'bz2' else None
                    written = 0
                    while chunk := source.read(1024 * 1024):
                        chunk = decompressor.decompress(chunk) if decompressor else chunk
                        written += len(chunk)
                        if written > asset['bytes']:
                            raise ValueError('Taille de ressource inattendue')
                        output.write(chunk)
                if decompressor and not decompressor.eof:
                    raise ValueError('Archive tronquée')
            if not verified(temporary, asset):
                raise ValueError('Empreinte SHA-256 incorrecte : ' + asset['name'])
            temporary.chmod(0o644)
            temporary.replace(destination)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
