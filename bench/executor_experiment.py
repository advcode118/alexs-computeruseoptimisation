"""Bounded executor comparison. Reads dev3 only; blocked splits never import.

This is experiment plumbing, not a task-solving mechanism. Use --recover before
--live. Live mode must be launched through the owner's probe_slot.sh.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path('C:/Users/epicd/AppData/Local/Temp/claude/2f9ed140d0fe6502/2f7abe0f-6d7d-45cc-8d42-69d3e8a73575/scratchpad')
LEDGER = Path('C:/Users/epicd/.cu-optimisation/openai-spend-dev-d.json')
OUT = ROOT / 'docs/results/robust_executor_20261114'
BASE = 'bec55ab'


def isolate_tasks():
    # Avoid bench.tasks' eager imports. The experiment has no route to a
    # frozen split, including when probe imports its public task constants.
    for suffix, prefix in [('heldout3_a', 'HELDOUT3A'), ('heldout3_b', 'HELDOUT3B'),
                           ('heldout3_c', 'HELDOUT3C'), ('heldout3_d', 'HELDOUT3D'), ('val3', 'VAL3')]:
        name = 'bench.tasks_' + suffix
        module = types.ModuleType(name)
        setattr(module, prefix + '_TASKS', [])
        setattr(module, prefix + '_TASK_IDS', ())
        sys.modules[name] = module


def rows(path):
    return [r for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip() and (r := json.loads(line)).get('arm') == 'script_first']


def summary(data):
    times = sorted(r['wall_ms'] / 1000 for r in data)
    rank = (len(times) - 1) * .9
    lo = int(rank)
    return dict(n=len(data), first_pass=sum(bool(r['success']) and len(r.get('scripts', [])) == 1 for r in data),
                final_pass=sum(bool(r['success']) for r in data),
                wrong_accepts=sum(r.get('end_state') == 'PASS' and not r['success'] for r in data),
                script_calls=sum(len(r.get('scripts', [])) for r in data),
                model_calls=sum(r.get('model_calls', 0) for r in data),
                mean_s=statistics.mean(times), median_s=statistics.median(times),
                p90_s=times[lo] + (times[min(lo+1, len(times)-1)]-times[lo])*(rank-lo),
                usd=round(sum(r['usd'] for r in data), 6))


def recover():
    from bench.script_first import parse_task_script
    sources = sorted((ROOT/'bench/runs').glob('*.jsonl'))
    sources += sorted((SCRATCH/'base/bench/runs').glob('*.jsonl'))
    sources += sorted((SCRATCH/'base3/bench/runs').glob('*.jsonl'))
    recovered = []
    report = []
    for path in sources:
        data = rows(path)
        if not data:
            continue
        recovered.extend(data)
        report.append({'file': str(path), **summary(data)})
        (OUT / ('recovered_' + path.name)).write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
    ledger = json.loads(LEDGER.read_text())
    # Locate our first saved run by its full token/cost signature, not an
    # assumed reset or another agent's ledger. Refuse an ambiguous boundary.
    first = rows(ROOT/'bench/runs/probe_20261113_210925.jsonl')[0]
    signature = lambda r: (r.get('input_tokens'), r.get('output_tokens'), r.get('usd'))
    hits = [i for i, item in enumerate(ledger['tasks']) if signature(item) == signature(first)]
    assert len(hits) == 1, hits
    start = round(ledger['recorded_extra_usd'] + sum(x['usd'] for x in ledger['tasks'][:hits[0]]), 6)
    budget = dict(original_start=start, recovered_first_signature_index=hits[0],
                  resume_total=ledger['running_total_usd'], ceiling=round(start+1, 6),
                  spent_before_resume=round(ledger['running_total_usd']-start, 6))
    baseline = rows(SCRATCH/'base3/bench/runs/probe_20261113_221300.jsonl')
    parse_results = []
    for row in baseline:
        try:
            steps = parse_task_script(row['scripts'][0])
            parse_results.append({'task_id': row['task_id'], 'parsed': True, 'steps': len(steps)})
        except Exception as exc:
            parse_results.append({'task_id': row['task_id'], 'parsed': False, 'error': str(exc)})
    (OUT/'recovery.json').write_text(json.dumps({'budget': budget, 'runs': report, 'dev3_first_script_parse': parse_results}, indent=2)+'\n')
    print(json.dumps({'budget': budget, 'dev3_baseline': summary(baseline), 'parsed': sum(r['parsed'] for r in parse_results)}, indent=2))


async def offline():
    from playwright.async_api import async_playwright
    from bench.script_first import run_on_page
    import bench.script_resolve as resolver
    cases = [
        ('identical controls', '<button onclick="out.textContent=\'wrong\'">Details</button><button onclick="out.textContent=\'right\'">Details</button>', 'cu.click("Details")', ''),
        ('regex length', '<button onclick="out.textContent=\'wrong\'">Delete</button><button onclick="out.textContent=\'right\'">Delete permanently from every archive and backup</button>', 'cu.click(/Delete/)', ''),
        ('locator ambiguity', '<button onclick="out.textContent=\'wrong\'">Details</button><button onclick="out.textContent=\'right\'">Details</button>', 'page.getByRole("button", {name:"Details", exact:true}).click()', ''),
        ('close partials', '<button onclick="out.textContent=\'wrong\'">Save draft</button><button onclick="out.textContent=\'right\'">Save copy</button>', 'cu.click("Save")', ''),
        ('unique partial', '<button onclick="out.textContent=\'right\'">Save changes</button>', 'cu.click("Save")', 'right'),
        ('exact precedence', '<button onclick="out.textContent=\'wrong\'">Go further</button><button onclick="out.textContent=\'right\'">Go</button>', 'cu.click("Go")', 'right'),
        ('positioned locator', '<button onclick="out.textContent=\'wrong\'">Details</button><button onclick="out.textContent=\'right\'">Details</button>', 'page.getByRole("button", {name:"Details"}).nth(1).click()', 'right'),
        ('hidden duplicate', '<button style="display:none">Save</button><button onclick="out.textContent=\'right\'">Save</button>', 'cu.click("Save")', 'right'),
    ]
    result = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for strict in [False, True]:
                resolver.STRICT_MATCH = strict
                for name, html, code, expected in cases:
                    page = await browser.new_page()
                    await page.set_content(html + '<div id="out"></div>')
                    payload = json.loads((await run_on_page(page, code)).splitlines()[0])
                    observed = await page.locator('#out').text_content()
                    result.append(dict(case=name, variant='strict' if strict else 'fuzzy',
                        code=code, html=html, ok=payload['ok'], observed=observed, expected=expected,
                        correct=observed == expected and bool(payload['ok']) == bool(expected),
                        wrong_accept=payload['ok'] and observed != expected,
                        error=payload.get('error', '')))
                    await page.close()
        finally:
            resolver.STRICT_MATCH = True
            await browser.close()
    # Also prove both in-memory runtimes import and parse the recovered scripts
    # without opening a site or invoking an API.
    compatibility = {}
    baseline = rows(SCRATCH/'base3/bench/runs/probe_20261113_221300.jsonl')
    for arm in ['tip3', 'robust']:
        with variant(arm):
            sf = sys.modules['bench.script_first']
            failures = []
            for row in baseline:
                try:
                    sf.parse_task_script(row['scripts'][0])
                except Exception as exc:
                    failures.append(dict(task_id=row['task_id'], error=str(exc)))
            compatibility[arm] = dict(parsed=len(baseline)-len(failures), failures=failures)
    (OUT/'offline.json').write_text(json.dumps({'cases': result, 'recovered_script_compatibility': compatibility}, indent=2)+'\n')
    print(json.dumps({mode: {'correct':sum(r['correct'] for r in result if r['variant']==mode),
        'wrong_accepts':sum(r['wrong_accept'] for r in result if r['variant']==mode)} for mode in ['fuzzy','strict']}, indent=2))
    print(json.dumps(compatibility, indent=2))


@contextmanager
def variant(name):
    # Import only the four changed runtime modules from the current tip3 tree
    # into memory. No checkout, worktree, or task data is extracted.
    names = ['bench.script_grammar', 'bench.script_helpers', 'bench.script_first', 'bench.arms', 'bench.harness', 'bench.probe']
    saved = {n: sys.modules.get(n) for n in names}
    package = sys.modules['bench']
    attrs = {n: getattr(package, n.split('.')[-1], None) for n in names}
    try:
        for n in reversed(names):
            sys.modules.pop(n, None)
        for n in names:
            if name == 'tip3':
                path = n.replace('.', '/') + '.py'
                source = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT)
                module = types.ModuleType(n)
                module.__file__ = str(ROOT/path)
                module.__package__ = 'bench'
                sys.modules[n] = module
                setattr(package, n.split('.')[-1], module)
                exec(compile(source, f'{BASE}:{path}', 'exec'), module.__dict__)
            else:
                module = importlib.import_module(n)
                setattr(package, n.split('.')[-1], module)
        yield sys.modules['bench.probe']
    finally:
        for n in names:
            if saved[n] is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = saved[n]
            if attrs[n] is None:
                if hasattr(package, n.split('.')[-1]):
                    delattr(package, n.split('.')[-1])
            else:
                setattr(package, n.split('.')[-1], attrs[n])


async def live():
    from bench.tasks_dev3 import DEV3_TASKS
    from bench.openai_spend import OpenAISpendLedger
    budget = json.loads((OUT/'recovery.json').read_text())['budget']
    assert LEDGER.is_file()
    os.environ['CU_OPENAI_SPEND_LEDGER'] = str(LEDGER)
    key = Path('C:/Users/epicd/.cu-optimisation/openai.key').read_text().strip()
    # One preregistered pair, all forty tasks; alternate AB/BA per task.
    # Reserve $0.05 per task and stop well below the original + $1 allowance.
    path = OUT/'paired_dev3.jsonl'
    assert not path.exists(), 'Refuse to overwrite or repeat the comparison'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    with path.open('x', encoding='utf-8') as stream:
        for index, task in enumerate(DEV3_TASKS):
            for arm in (['tip3', 'robust'] if index % 2 == 0 else ['robust', 'tip3']):
                ledger = OpenAISpendLedger.read(LEDGER)
                assert not ledger.aborted and ledger.running_total_usd + .05 < budget['ceiling'], 'Budget reserve exhausted'
                with variant(arm) as probe:
                    row = await probe.run_claude_arm('script_first', task, api_key=key, headless=True,
                        runs_dir=ROOT/'bench/runs', provider='openai', model='gpt-6-luna', effort='medium')
                # run_claude_arm uses the harness's live ledger preflight but
                # the ordinary probe caller records completed task usage here.
                ledger = OpenAISpendLedger.read(LEDGER)
                ledger.record_task(run_id='robust_executor_pair1', task_id=f"script_first:{task['id']}:medium",
                    input_tokens=row['input_tokens'], output_tokens=row['output_tokens'],
                    cached_tokens=row.get('cached_tokens', 0), cache_write_30m_tokens=row.get('cache_write_30m_tokens', 0),
                    cache_write_12h_tokens=row.get('cache_write_12h_tokens', 0), model='gpt-6-luna', effort='medium')
                ledger.save()
                row.update(variant=arm, pair=1, measured_head=head, runtime_base=BASE)
                stream.write(json.dumps(row)+'\n')
                stream.flush()
                print(task['id'], arm, row['success'], round(row['wall_ms']/1000, 2), flush=True)
    data = rows(path)
    report = {arm: summary([r for r in data if r['variant'] == arm]) for arm in ['tip3', 'robust']}
    (OUT/'paired_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--recover', action='store_true')
    args.add_argument('--live', action='store_true')
    args.add_argument('--offline', action='store_true')
    opts = args.parse_args()
    isolate_tasks()
    OUT.mkdir(parents=True, exist_ok=True)
    if opts.recover:
        recover()
    if opts.live:
        asyncio.run(live())
    if opts.offline:
        asyncio.run(offline())


if __name__ == '__main__':
    main()
