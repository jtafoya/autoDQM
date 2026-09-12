"""One-off recoverable cleanup, scoped to the repetition study only."""
import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone
import fcntl

root = Path('/afs/cern.ch/user/p/pengy/autoDQM')
raw = root / 'isolation_forest/benchmarks/novel/raw_consistency'
study = raw / 'results/study_20260910T233752Z_e8027ad4'
bundle = raw / 'inputs/bundle_20260910T230921Z'
keep = [1620, 1640, 1642]
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive = root / 'archives' / ('repetition_cleanup_' + stamp)

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def files(p):
    return [p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file())

def save(p, value):
    p.write_text(json.dumps(value, indent=2) + '\n')

with (study / '.resume.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for run in keep:
        for trial in range(1,4):
            folder = study / f'run{run}/trial_{trial}'
            assert json.loads((folder/'metadata.json').read_text())['status'] == 'completed'
            assert (folder/'diagnosis_report.md').is_file()
    before = {str(p): sha(p) for run in keep for parent in [study/f'run{run}', bundle/f'run{run}'] for p in files(parent)}
    archive.mkdir(parents=True, exist_ok=False)
    journal = {'reason': 'User requested three cases only. Recoverable moves, not permanent deletion. Original raw CSVs, KB and unrelated benchmarks are out of scope.',
               'retained_runs': keep, 'retained_file_sha256': before, 'moves': [], 'script_snapshots': {}}
    for p in raw.iterdir():
        if p.is_file() and p.suffix in ('.py', '.md'):
            dest = archive/'original_scripts'/p.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p,dest)
            journal['script_snapshots'][str(p)] = {'copy':str(dest), 'sha256':sha(dest)}
    targets = [study/f'run{r}' for r in [1702,1703,2126]] + [bundle/f'run{r}' for r in [1702,1703,2126]]
    targets += [raw/'results/dry_run_20260910T231741Z_7b484ae2', raw/'results/dry_run_20260910T232003Z_b035e27f',
                raw/'validation_artifacts', raw/'__pycache__', raw/'resume_study.py', raw/'test_resume_study.py', raw/'RECOVERY.md',
                raw/'validation.md', raw/'INPUT_LOCATIONS.md', study/'recovery_attempts', study/'consistency.json', study/'consistency.md', study/'semantic_review.json',
                root/'isolation_forest/benchmarks/novel/randomness']
    for src in targets:
        if not src.exists(): continue
        assert src.is_relative_to(root) and src != root
        dest = archive/'removed'/src.relative_to(root)
        assert not dest.exists()
        hashes = {str(p.relative_to(src)) if p != src else '.':sha(p) for p in files(src)}
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        for rel,h in hashes.items(): assert sha(dest if rel=='.' else dest/rel) == h
        journal['moves'].append({'original':str(src), 'archived':str(dest), 'sha256':hashes})
        save(archive/'cleanup_manifest.json',journal)
    for p,h in before.items(): assert sha(Path(p)) == h
    scope = {'retained_runs':keep, 'trials_per_run':3, 'completed_diagnoses':9, 'archive':str(archive),
             'note':'Historical study_config.json and bundle.json remain unchanged as provenance. Current scripts select only these retained runs. Archived historical-run citations inside frozen prompts are intentionally unchanged.'}
    save(study/'retained_scope.json',scope)
    save(bundle/'retained_scope.json',scope)
    journal['retained_files_unchanged'] = True
    save(archive/'cleanup_manifest.json',journal)
    print(json.dumps({'archive':str(archive),'moved_targets':len(journal['moves']),'moved_files':sum(len(m['sha256']) for m in journal['moves']), 'retained_files_verified':len(before)}))
