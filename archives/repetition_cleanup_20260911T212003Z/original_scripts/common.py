"""Shared deterministic serialization and audit helpers (no API imports)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import socket
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = [1620, 1640, 1642, 1702, 1703, 2126]
RAW_ROOT = Path('/eos/experiment/milliqan/run3_MilliMon/slab')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def read(path):
    return json.loads(Path(path).read_text())


def offline():
    original = socket.socket.connect
    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError('Offline preparation/tests cannot make network connections')
        return original(sock, address)
    socket.socket.connect = connect


def novel_module():
    sys.path.insert(0, str(ROOT / 'benchmarks/novel'))
    import novel_test
    return novel_test


def source_hashes():
    files = list(HERE.glob('*.py')) + [ROOT / p for p in (
        'benchmarks/novel/novel_test.py', 'benchmarks/novel/context_builders.py',
        'benchmarks/novel/context_manifest.yaml', 'benchmarks/novel/novel_manifest.yaml',
        'benchmarks/recognition/recognition_test.py', 'src/llm.py',
        'src/features.py', 'src/run_config.py')]
    return {str(p): sha(p) for p in files if p.is_file()}


def verify_files(mapping):
    for path, expected in mapping.items():
        if sha(path) != expected:
            raise ValueError(f'Frozen file changed: {path}')


def at_path(record, field):
    """Dot-separated dictionary keys / array indices, never eval."""
    value = record
    for part in field.split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value
