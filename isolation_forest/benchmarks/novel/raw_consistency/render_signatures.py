"""Offline figures from explicitly cited input evidence, never feature attribution."""
from __future__ import annotations
import json
from pathlib import Path
import textwrap
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import read, write

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})


def wrapped(text, width=100):
    return '\n'.join(textwrap.fill(line, width=width) for line in str(text).splitlines())


def save_text_figure(path, title, sections, label):
    content = '\n\n'.join(f'{heading}\n{wrapped(body)}' for heading, body in sections)
    height = max(5., 1.7 + .23 * len(content.splitlines()))
    fig = plt.figure(figsize=(15, height), facecolor='white')
    fig.text(.04, 1-.35/height, title, fontsize=17, color='#17365b', va='top')
    fig.text(.04, 1-1.0/height, content, va='top', fontsize=11, linespacing=1.4)
    fig.text(.04, .25/height, label, fontsize=9, color='#555555')
    fig.savefig(path, dpi=145)
    plt.close(fig)


def plot_record(record, header, path, title, valid):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    fig.suptitle(title + (' [reference check failed]' if not valid else ''), fontsize=14)
    if record['kind'] == 'raw_metric':
        edges = np.asarray(header['histogram_edges_by_metric'][record['metric']], dtype=float)
        counts = np.asarray(record['histogram_counts'])
        axes[0].stairs(counts, edges, color='#24527a', fill=True, alpha=.65)
        axes[0].set_xscale('symlog', linthresh=1)
        axes[0].set_xlabel(record['metric'] + ' (source units; symlog axis)')
        axes[0].set_ylabel('Finite raw rows')
        axes[0].set_title('All-file distribution supplied to LLM')
        values = np.array([np.nan if x is None else x for x in record['time_bin_mean']])
        axes[1].plot(np.arange(1, len(values)+1), values, 'o-', color='#b3541e')
        axes[1].set_ylabel('Finite-row-weighted mean (source units)')
        axes[1].set_title('Ordered subrun-bin means supplied to LLM')
    else:
        q = record['occupancy_quantiles']
        axes[0].plot(np.asarray(header['quantile_probabilities'])*100, q, 'o-', color='#24527a')
        axes[0].set_xlabel('Percentile across all supplied subruns')
        axes[0].set_ylabel('Observed channel events / observed events')
        axes[0].set_ylim(-.02, 1.02)
        axes[0].set_title('Occupancy distribution supplied to LLM')
        values = record['time_bin_occupancy']
        axes[1].plot(np.arange(1, len(values)+1), values, 'o-', color='#b3541e')
        axes[1].set_ylabel('Event-weighted occupancy')
        axes[1].set_ylim(-.02, 1.02)
        axes[1].set_title(f'Presence: {record["present_subruns"]}/{record["total_subruns"]} subruns')
    labels = [f'{a}-{b}' for a, b in header['time_bin_subrun_ranges']]
    axes[1].set_xticks(np.arange(1, len(labels)+1))
    axes[1].set_xticklabels(labels, rotation=35, ha='right')
    axes[1].set_xlabel('Subrun range (not elapsed time)')
    for ax in axes:
        ax.grid(axis='y', color='#dddddd', linewidth=.5)
        for side in ['top', 'right']:
            ax.spines[side].set_visible(False)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def render_trial(directory, inputs, run, trial):
    prediction = read(directory / 'diagnosis.json')
    audit = read(directory / 'signature_audit.json')
    header = read(inputs / 'summary_header.json')
    records = {r['id']: r for r in map(json.loads, (inputs / 'evidence.jsonl').read_text().splitlines())}
    images = directory / 'signature_images'
    images.mkdir(exist_ok=True)
    label = 'LLM-cited evidence and stated links. Reference checks are not causal validation or internal attribution.'
    title = f'Run {run} | Trial {trial}'
    sections = [('Category', prediction['category']), ('Cause', prediction['cause']),
                ('Action', prediction['action']), ('Evidence summary', prediction['reasoning_summary'])]
    signatures = prediction['signatures']
    if not signatures: sections.append(('Signature record', 'No signatures supplied. Evidence explanation unavailable.'))
    sections.append(('Signatures cited', '\n'.join(f'{s["signature_id"]}: {s["observation"]}' for s in signatures)))
    sections.append(('Reference audit', 'All cited IDs and values match the frozen input.' if audit['all_references_valid'] else '\n'.join(audit['issues'])))
    save_text_figure(images / 'diagnosis_and_signatures.png', title, sections, label)
    report = [f'# {title}', '', '## Diagnosis', '', f'Category: {prediction["category"]}', '',
              f'Cause: {prediction["cause"]}', '', f'Action: {prediction["action"]}', '',
              f'Confidence: {prediction["confidence"]}', '', prediction['reasoning_summary'], '',
              '## LLM-cited signatures', '', label, '']
    plotted = []
    for i, signature in enumerate(signatures, 1):
        reference_audit = audit['signatures'][i-1]
        refs = '\n'.join(f'{c["evidence_id"]}.{c["field"]} = {c["value_json"]}' for c in signature['citations'])
        sections = [('Observation stated by LLM', signature['observation']),
                    ('Role', signature['role']), ('Link to cause stated by LLM', signature['cause_link']),
                    ('Link to action stated by LLM', signature['action_link']),
                    ('Exact input references', refs or 'No references supplied'),
                    ('Reference check', 'IDs and values match input; interpretation not automatically verified.' if reference_audit['references_valid'] else '\n'.join(reference_audit['errors']))]
        signature_file = images / f'signature_{i:02}_evidence_links.png'
        save_text_figure(signature_file, title + ' | ' + signature['signature_id'], sections, label)
        report += [f'### {signature["signature_id"]}', '', signature['observation'], '',
                   f'Role: {signature["role"]}', '', f'Cause link: {signature["cause_link"]}', '',
                   f'Action link: {signature["action_link"]}', '', '```text', refs, '```', '',
                   f'![Evidence links](signature_images/{signature_file.name})', '']
        seen = set()
        for citation in signature['citations']:
            rid = citation['evidence_id']
            if rid in seen or rid not in records: continue
            seen.add(rid)
            record = records[rid]
            # All cited R/P records are rendered. Context/KB/anomaly stay as source text.
            if record['kind'] in ('raw_metric', 'raw_presence'):
                if record['kind'] == 'raw_metric' and not record['n']: continue
                filename = f'signature_{i:02}_{rid}.png'
                plot_record(record, header, images / filename, title + f' | {signature["signature_id"]} | {rid}', reference_audit['references_valid'])
                report += [f'![Supplied evidence {rid}](signature_images/{filename})', '']
                plotted.append({'signature_id': signature['signature_id'], 'evidence_id': rid, 'image': str((images / filename).resolve())})
    report += ['## Missing information', ''] + ['- ' + x for x in prediction['missing_information']]
    (directory / 'diagnosis_report.md').write_text('\n'.join(report)+'\n')
    write(directory / 'signature_records.json', {'signatures': signatures, 'reference_audit': audit,
          'input_directory': str(inputs.resolve()), 'evidence_file': str((inputs / 'evidence.jsonl').resolve()),
          'raw_detail': str((inputs / 'raw_detail.npz').resolve()), 'plots': plotted})


def render_study(study):
    config = read(study / 'study_config.json')
    for run in config['runs']:
        for trial in range(1, config['trials']+1):
            directory = study / f'run{run}' / f'trial_{trial}'
            if (directory / 'diagnosis.json').exists() and (directory / 'signature_audit.json').exists():
                render_trial(directory, Path(config['inputs']) / f'run{run}', run, trial)
