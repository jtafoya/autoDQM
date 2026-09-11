"""Independent spot checks and conspicuously synthetic rendering QA, no API calls."""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path('/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest')
sys.path.insert(0,str(ROOT/'benchmarks/novel/raw_consistency'))
from common import read, write, canonical, offline
from run_study import make_payload, token_check, validate_citations
from render_signatures import render_trial
from test_raw_consistency import fake_prediction


def main():
    offline()
    bundle=Path(sys.argv[1])
    results=[]
    for run in [1620,1640,1642,1702,1703,2126]:
        d=bundle/f'run{run}'
        inv=read(d/'raw_inventory.json')
        with np.load(d/'raw_detail.npz') as archive:
            detail={k:archive[k] for k in archive.files}
        assert int(detail['rows'].sum())==inv['total_rows']
        records={r['id']:r for r in map(json.loads,(d/'evidence.jsonl').read_text().splitlines())}
        metrics=list(detail['metrics'])
        # Independent direct pandas calculations on first / middle / last raw files.
        for i in sorted({0,len(inv['files'])//2,len(inv['files'])-1}):
            raw=pd.read_csv(inv['files'][i]['path'])
            assert len(raw)==inv['files'][i]['rows']
            for ch in [0,32,33,95]:
                g=raw[raw.channel==ch]
                assert len(g)==detail['rows'][i,ch]
                assert g.event_id.nunique()==detail['channel_events'][i,ch]
                for m,name in enumerate(metrics):
                    v=pd.to_numeric(g[name],errors='raise')
                    v=v[np.isfinite(v)]
                    if len(v):
                        np.testing.assert_allclose(detail['stats'][i,ch,m,1],v.mean(),rtol=1e-12,atol=1e-12)
                        np.testing.assert_allclose(detail['stats'][i,ch,m,6],v.median(),rtol=1e-12,atol=1e-12)
        log=pd.read_csv(d/'anomaly_log.csv')
        assert int(log.anomalous.sum())==records['A-ALL']['anomalous_rows']
        for ch in range(96):
            assert records[f'P-{ch:03}']['present_subruns']==int((detail['rows'][:,ch]>0).sum())
            for m in range(len(metrics)):
                record=records[f'R-{ch:03}-{m:02}']
                assert sum(record['histogram_counts'])==int(np.nansum(detail['stats'][:,ch,m,0]))
        result={'run':run,'files':inv['file_count'],'rows':inv['total_rows'],'raw_bytes':inv['total_bytes'],
            'channels32_33_present_subruns':[records[f'P-{ch:03}']['present_subruns'] for ch in [32,33]],
            'preflight':token_check(make_payload(d,'gpt-5.6-sol'),950000),'independent_checks':'passed'}
        print(json.dumps(result),flush=True)
        results.append(result)
    qa=ROOT/'benchmarks/novel/raw_consistency/validation_artifacts/SYNTHETIC_ONLY_run1640_trial1'
    qa.mkdir(parents=True,exist_ok=True)
    d=bundle/'run1640'
    records=list(map(json.loads,(d/'evidence.jsonl').read_text().splitlines()))
    index={r['id']:r for r in records}
    pred=fake_prediction()
    pred['category']='SYNTHETIC PIPELINE TEST - NOT LLM OUTPUT'
    pred['cause']='No real diagnostic inference; only renderer QA.'
    pred['signatures'][0]['observation']='SYNTHETIC TEST: display actual supplied numerical summaries without diagnosing the run.'
    pred['signatures'][0]['citations']=[{'evidence_id':'R-032-00','field':'mean','value_json':canonical(index['R-032-00']['mean'])},
        {'evidence_id':'P-032','field':'present_subruns','value_json':canonical(index['P-032']['present_subruns'])}]
    write(qa/'diagnosis.json',pred)
    write(qa/'signature_audit.json',validate_citations(pred,records,[]))
    render_trial(qa,d,'1640 [SYNTHETIC TEST - NOT LLM OUTPUT]',1)
    write(qa.parent/'validation_results.json',results)
    print('Synthetic rendering QA: '+str(qa),flush=True)


if __name__=='__main__':main()
