"""Download the dataset from Zenodo and verify its checksums (standard library only)."""
import hashlib
import json
import urllib.request
from pathlib import Path

# Zenodo record of the dataset (the numeric id in zenodo.org/records/<id>).
ZENODO_RECORD = 24014974      # https://doi.org/10.5281/zenodo.24014974
DEFAULT_DIR = Path('data') / 'volve-mlready-v1.0.0'

# Files a user can skip to save space (everything needed by the notebooks is kept).
OPTIONAL = {'vp_st10010_native_depth.npy', 'vp_st10010_native_depth.json',
            'pp_poststack_st0202_time.npy', 'pp_poststack_st0202_time.json',
            'source_files.zip', 'code.zip'}


def _digest(path, algo, chunk=8 << 20):
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def download(dest=DEFAULT_DIR, record=None, minimal=False):
    """Download every file of the Zenodo record into `dest` (skips files already complete).

    minimal=True skips the native-grid arrays, the source files and the code snapshot
    (about 2.5 GB instead of 3.2 GB).
    """
    record = record or ZENODO_RECORD
    if record is None:
        raise RuntimeError('The Zenodo record id is not set yet. Download the files manually '
                           'and pass their folder to VolveMLReady(...).')
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    meta = json.load(urllib.request.urlopen(f'https://zenodo.org/api/records/{record}', timeout=60))
    for f in meta['files']:
        name, size = f['key'], f['size']
        if minimal and name in OPTIONAL:
            continue
        out = dest / name
        if out.exists() and out.stat().st_size == size:
            print(f'skip {name}')
            continue
        print(f'get  {name} ({size / 1e6:,.0f} MB)', flush=True)
        tmp = out.with_suffix(out.suffix + '.part')
        urllib.request.urlretrieve(f['links']['self'], tmp)
        algo, want = f['checksum'].split(':', 1)
        if _digest(tmp, algo) != want:
            raise RuntimeError(f'{name}: {algo} checksum mismatch')
        tmp.rename(out)
    return dest


def verify(root=DEFAULT_DIR):
    """Check every file listed in SHA256SUMS.txt that is present. Returns {name: ok/missing/BAD}."""
    root = Path(root)
    status = {}
    for line in (root / 'SHA256SUMS.txt').read_text().splitlines():
        want, name = line.split(None, 1)
        p = root / name.strip()
        status[name.strip()] = ('missing' if not p.exists()
                                else 'ok' if _digest(p, 'sha256') == want else 'BAD')
    return status
