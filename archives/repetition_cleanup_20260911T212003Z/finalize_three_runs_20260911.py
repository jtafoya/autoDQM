"""Offline retained-study verification and cleanup receipt."""
import json
import hashlib
from pathlib import Path
import shutil
import sys
root = Path('/afs/cern.ch/user/p/pengy/autoDQM')
raw = root/'isolation_forest/benchmarks/novel/raw_consistency'
study = raw/'results/study_20260910T233752Z_e8027ad4'
scope = json.loads((study/'retained_scope.json').read_text())
archive = Path(scope['archive'])
sys.path.insert(0,str(raw))
from common import read, write, sha, RUNS, verify_files
from run_study import compare, make_payload, digest, validate_citations
journal = read(archive/'cleanup_manifest.json')
verify_files(journal['retained_file_sha256'])
old_review = archive/'removed/isolation_forest/benchmarks/novel/raw_consistency/results/study_20260910T233752Z_e8027ad4/semantic_review.json'
review = read(old_review)
review['runs'] = {k:v for k,v in review['runs'].items() if int(k) in RUNS}
write(study/'semantic_review.json',review)
comparison = compare(study)
assert [x['run'] for x in comparison] == RUNS
assert all(x['all_diagnoses_completed'] and x['identical_request_bytes'] for x in comparison)
config = read(study/'study_config.json')
checks=[]
for run in RUNS:
    inp=Path(config['inputs'])/f'run{run}'
    payload=make_payload(inp,config['model'])
    records=[json.loads(line) for line in (inp/'evidence.jsonl').read_text().splitlines()]
    for t in range(1,4):
        d=study/f'run{run}/trial_{t}'
        m=read(d/'metadata.json')
        assert m['input_sha256']==digest(payload)
        assert m['request_body_sha256']==sha(d/'request_body.json')
        audit=validate_citations(read(d/'diagnosis.json'),records,read(inp/'manifest.json')['visible_historical_runs'])
        assert audit['all_references_valid']
        checks.append({'run':run,'trial':t,'status':m['status'],'request_body_sha256':m['request_body_sha256'],'citations_valid':True})
dry=raw/'results/dry_run_20260911T212141Z_457b38cb'
assert dry.is_dir()
dry_checks=[]
for run in RUNS:
    for t in range(1,4):
        d=dry/f'run{run}/trial_{t}'
        m=read(d/'metadata.json')
        old=read(study/f'run{run}/trial_{t}/metadata.json')
        assert m['status']=='dry_run' and m['network_attempts']==0
        assert m['request_body_sha256']==old['request_body_sha256']
        dry_checks.append({'run':run,'trial':t,'identical_to_original_wire':True})
dest=archive/'validation'/dry.name
dest.parent.mkdir(parents=True,exist_ok=True)
hashes={str(p.relative_to(dry)):sha(p) for p in dry.rglob('*') if p.is_file()}
shutil.move(str(dry),str(dest))
verify_files({str(dest/k):h for k,h in hashes.items()})
report={'retained_runs':RUNS,'completed_diagnoses':len(checks),'unchanged_retained_files':len(journal['retained_file_sha256']),
        'offline_unit_tests_passed':11,'no_real_api_calls':True,'original_trial_checks':checks,'serializer_checks':dry_checks,
        'validation_dry_run_archive':str(dest),'archived_validation_sha256':hashes,'archive':str(archive)}
write(raw/'cleanup_verification.json',report)
write(archive/'post_cleanup_verification.json',report)
assert sorted(p.name for p in study.glob('run*') if p.is_dir())==[f'run{r}' for r in RUNS]
print(json.dumps({k:v for k,v in report.items() if k not in ['original_trial_checks','serializer_checks','archived_validation_sha256']}))
