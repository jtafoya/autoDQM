"""One-time recoverable archive of explicitly identified legacy result directories."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

REMOTE = Path('/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/benchmarks/novel/randomness')
LOCAL = Path('/Users/branchinpyjamas/Documents/AutoFLAME/artifacts')
NAMES = {
    'remote': ['dry_run_20260905T001936Z_b0469e00', 'dry_run_20260905T002507Z_fc2cc95c',
               'study_20260906T044011Z_7ac63c5a', 'feature_matrix'],
    'local': ['feature_matrix', 'phase1_feature_matrix'],
}


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def main():
    mode=sys.argv[1]
    if mode not in NAMES: raise ValueError('Expected remote or local')
    root=REMOTE if mode=='remote' else LOCAL
    destination=root/'archive_summary_only_20260910'
    if destination.exists(): raise ValueError('Archive already exists; refusing overwrite')
    sources=[root/name for name in NAMES[mode]]
    for source in sources:
        if not source.is_dir() or source.is_symlink(): raise ValueError(f'Unexpected archive target: {source}')
    hashes={str(p.relative_to(root)):sha(p) for source in sources for p in source.rglob('*') if p.is_file()}
    destination.mkdir()
    manifest={'reason':'Superseded summary-only experiment and post-hoc visualizations; not expanded-raw-input evidence. Preserved for audit, not erased.',
              'moves':[{ 'original':str(s), 'archived':str(destination/s.name)} for s in sources], 'sha256':hashes}
    (destination/'archive_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for source in sources: shutil.move(str(source),str(destination/source.name))
    for rel,h in hashes.items():
        if sha(destination/rel)!=h: raise ValueError(f'Archive verification failed: {rel}')
    print(json.dumps({'archive':str(destination),'files_preserved':len(hashes),'hashes_verified':True}))


if __name__=='__main__': main()
