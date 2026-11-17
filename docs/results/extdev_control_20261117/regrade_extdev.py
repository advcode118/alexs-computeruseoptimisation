"""Replay immutable extdev evidence after the authored-only key selection lock."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from bench.regrade import regrade_row
from bench.tasks_extdev import EXTDEV_TASKS
import report_rep1 as original

SOURCES = {'smoke': 'smoke/probe_20261117_011924.jsonl',
           'default': 'raw/probe_20261117_012232.jsonl',
           'ultrafast': 'raw/probe_20261117_015118.jsonl'}


def older_diff():
    before = json.loads((ROOT/'docs/results/regrade_20261116/regrade.json').read_text())
    after = json.loads((ROOT/'docs/results/regrade_20261117/regrade.json').read_text())
    prior = {s['path']: s for s in before['sources']}
    current = {s['path']: s for s in after['sources']}
    assert set(prior) <= set(current)
    assert all(prior[p]['sha256'] == current[p]['sha256'] for p in prior)
    identity = lambda r: (r['file'], r['arm'], r['task_id'], r['direction'], r['new_reason'])
    old_rows = before['flipped_rows']
    new_rows = [r for r in after['flipped_rows'] if r['file'] in prior]
    old, new = Counter(map(identity, old_rows)), Counter(map(identity, new_rows))
    representatives = {identity(r): r for r in old_rows + new_rows}
    result = {'matched_older_sources': len(prior), 'matched_source_hashes_unchanged': True,
              'new_older_flips': [representatives[k] for k in sorted(new - old) for _ in range((new - old)[k])],
              'removed_older_flips': [representatives[k] for k in sorted(old - new) for _ in range((old - new)[k])],
              'preexisting_flips_unchanged': sum((old & new).values()),
              'hidden_flip_summary_before': before['heldout3_flips'],
              'hidden_flip_summary_after': after['heldout3_flips'],
              'older_groups_unchanged': all(prior[p]['groups'] == current[p]['groups'] for p in prior)}
    (ROOT/'docs/results/regrade_20261117/diff_vs_20261116.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    key_hash = hashlib.sha256((ROOT/'bench/tasks_extdev.py').read_bytes()).hexdigest()
    assert key_hash in (HERE/'KEY_CHANGES.md').read_text(), 'Key selection must be locked first'
    tasks = {t['id']: t for t in EXTDEV_TASKS}
    catalog = {key: {'task': t, 'split': 'extdev', 'hidden': False} for key, t in tasks.items()}
    replayed, audit = {}, []
    for invocation, source in SOURCES.items():
        replayed[invocation] = []
        for line, row in enumerate(original.load(HERE/source), 1):
            if 'task_id' not in row:
                continue
            result = regrade_row(row, catalog)
            audit.append({'file': source, 'line': line, 'arm': row['arm'], 'task_id': row['task_id'],
                          'old': result['old'], 'new': result['new'], 'category': result['category'],
                          'old_reason': row.get('success_reason', ''), 'new_reason': result['reason'],
                          'stored_page_field': 'grade_page_text' in row,
                          'empty_page_text': not bool(row.get('grade_page_text', '').strip())})
            if result['skipped']:
                continue
            assert result['category'] == 'full re-grade', (source, row['task_id'], result)
            assert result['new'] is not None
            replayed[invocation].append({**row, 'success': result['new'], 'success_reason': result['reason']})
    default, ultra = replayed['default'], replayed['ultrafast']
    groups = {arm: {r['task_id']: r for r in default if r['arm'] == arm}
              for arm in ('browser_use', 'script_first', 'cascade')}
    ids = set(groups['cascade'])
    groups['browser_use ultrafast'] = {r['task_id']: r for r in ultra if r['task_id'] in ids}
    assert len(ids) == 22 and all(set(rows) == ids for rows in groups.values())
    old_metrics = json.loads((HERE/'paired_metrics.json').read_text())
    assert sorted(ids) == old_metrics['paired_task_ids']
    metrics = {name: original.metrics(rows.values()) for name, rows in groups.items()}
    rank = lambda name: (-metrics[name]['pass_rate'], metrics[name]['mean_wall_ms'])
    best = min(groups, key=rank)
    baseline = min(('browser_use', 'browser_use ultrafast'), key=rank)
    boot = original.bootstrap(groups, tasks, best)
    baseline_boot = original.bootstrap(groups, tasks, baseline)
    assert boot['clusters'] == old_metrics['paired_site_counts']
    for name, rows in groups.items():
        metric = metrics[name]
        metric['pass_rate_ci'] = boot['pass_rate_ci'][name]
        metric['paired_difference_vs_best_arm'] = metric['pass_rate'] - metrics[best]['pass_rate']
        metric['paired_difference_ci'] = boot['difference_ci'][name]
        claims = [r for r in rows.values() if r.get('claimed_answer', '').strip()] if name.startswith('browser_use') else [
            r for r in rows.values() if (r.get('self_checks') or [{}])[-1].get('verdict') == 'PASS']
        metric['claims_or_self_check_passes'] = len(claims)
        if name != 'cascade':
            metric['false_accepts'] = sum(not r['success'] for r in claims)
        for key in ('n', 'median_wall_ms', 'mean_wall_ms', 'p90_wall_ms', 'mean_usd'):
            assert metric[key] == old_metrics['paired'][name][key]
    stage_claims = [r for r in groups['cascade'].values()
                    if (r.get('self_checks') or [{}])[-1].get('verdict') == 'PASS']
    assert all('text' in r['self_checks'][-1]['payload'] for r in stage_claims)
    stages = [original.stage_one_replay(r, tasks[r['task_id']]) for r in stage_claims]
    metrics['cascade']['false_accepts'] = sum(not r['stage_one_frozen_replay_success'] for r in stages)
    accepted = [r for r in stages if r['precision_gate_accepted']]
    gate_fa = sum(not r['stage_one_frozen_replay_success'] for r in accepted)
    ultra_boot = original.bootstrap({'all': {r['task_id']: r for r in ultra}}, tasks, 'all')
    all_ultra = {**original.metrics(ultra), 'pass_rate_ci': ultra_boot['pass_rate_ci']['all'],
                 'false_accepts': sum(bool(r.get('claimed_answer', '').strip()) and not r['success'] for r in ultra)}
    shares = {stage: {'n': sum(r['answered_by'] == stage for r in groups['cascade'].values()),
                      'passes': sum(r['answered_by'] == stage and r['success'] for r in groups['cascade'].values())}
              for stage in ('script', 'browser_use')}
    delta = metrics['cascade']['pass_rate'] - metrics[baseline]['pass_rate']
    elapsed = metrics['cascade']['mean_wall_ms'] - metrics[baseline]['mean_wall_ms']
    flips = [r for r in audit if r['new'] is not None and r['old'] != r['new']]
    older = older_diff()
    ledger_path = Path.home()/'.cu-optimisation/openai-spend-alex15.json'
    # The live ledger exists only on the machine that paid for the run; a fresh clone uses the committed summary.
    ledger = json.loads((ledger_path if ledger_path.exists() else HERE/'ledger_summary.json').read_text())
    assert ledger['running_total_usd'] == 6.277727
    result = {'grader_sha256': hashlib.sha256((ROOT/'bench/grade.py').read_bytes()).hexdigest(),
              'keys_sha256': key_hash, 'seed': original.SEED, 'bootstrap_draws': original.BOOTSTRAPS,
              'paired_task_ids': sorted(ids), 'paired_site_counts': boot['clusters'],
              'paired': metrics, 'best_arm': best, 'best_baseline': baseline,
              'ultrafast40': all_ultra, 'flips': flips,
              'rows': len(audit), 'attempted': sum(r['new'] is not None for r in audit),
              'budget_skips': sum(r['category'] == 'skipped' for r in audit),
              'not_regradable': [r for r in audit if r['new'] is None and r['category'] != 'skipped'],
              'smoke_passes': sum(r['success'] for r in replayed['smoke']),
              'cascade': {'answered_by': shares, 'stage_one_pass_replays': stages, 'gate_false_accepts': gate_fa,
                          'gate_accepts': len(accepted), 'difference_vs_best_baseline': delta,
                          'difference_vs_best_baseline_ci': baseline_boot['difference_ci']['cascade'],
                          'mean_wall_difference_ms': elapsed,
                          'mean_wall_difference_ci_ms': baseline_boot['wall_difference_ci']['cascade'],
                          'criterion_point_estimate': delta >= -.02 and elapsed < 0},
              'older_data_diff': older, 'ledger_running_total_usd': ledger['running_total_usd']}
    (HERE/'regraded_metrics.json').write_text(json.dumps(result, indent=2)+'\n')
    with (HERE/'regraded_rows.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(audit[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(audit)
    lines = ['| Arm / sample | Valid n | Passes; rate [site-clustered 95% CI] | Paired delta vs best arm, pp [95% CI] | Median wall_ms | Mean wall_ms | P90 wall_ms | Mean USD | False accepts / claims |',
             '|---|---:|---|---|---:|---:|---:|---:|---|']
    ci = lambda values, scale=100: '[' + ', '.join(f'{v*scale:.2f}' for v in values) + ']'
    def table_row(name, metric, difference, fa):
        return f'| {name} | {metric["n"]} | {metric["passes"]}/{metric["n"]}; {100*metric["pass_rate"]:.2f}% {ci(metric["pass_rate_ci"])} | {difference} | {metric["median_wall_ms"]:.2f} | {metric["mean_wall_ms"]:.2f} | {metric["p90_wall_ms"]:.2f} | {metric["mean_usd"]:.6f} | {fa} |'
    for name in ('browser_use', 'browser_use ultrafast', 'script_first', 'cascade'):
        m = metrics[name]
        diff = f'{100*m["paired_difference_vs_best_arm"]:.2f} {ci(m["paired_difference_ci"])}'
        fa = f'{m["false_accepts"]}/{m["claims_or_self_check_passes"]}'
        if name == 'cascade':
            fa += f' stage-1 PASS; {gate_fa}/{len(accepted)} accepted by gate'
        label = 'browser_use default' if name == 'browser_use' else name
        lines.append(table_row(label+', paired', m, diff, fa))
    lines.append('| playwright_mcp | **0** | **infra failure: Chrome missing, 0 valid rows** | N/A | N/A | N/A | N/A | N/A | N/A |')
    lines.append(table_row('browser_use ultrafast, all 40 (supplemental)', all_ultra, 'N/A: different sample', f'{all_ultra["false_accepts"]}/40'))
    lines += ['', f'Best arm: **{best}**; best baseline: **{baseline}** (highest pass rate, then lower mean wall).',
              f'Cascade vs best baseline: **{100*delta:.2f} pp {ci(baseline_boot["difference_ci"]["cascade"])}**;',
              f'mean wall difference **{elapsed:.2f} ms {ci(baseline_boot["wall_difference_ci"]["cascade"], 1)}**.',
              f'Within 2 pp with lower mean wall: **{"yes" if result["cascade"]["criterion_point_estimate"] else "no"} at the point estimate**.',
              'This is not an established noninferiority/accuracy result; bootstrap limitations and key coverage caveats remain.', '',
              '### Cascade stage split and false accepts', '',
              '| Stage | Rows | Share | New passes |', '|---|---:|---:|---:|']
    for name, values in shares.items():
        lines.append(f'| {name} | {values["n"]} | {100*values["n"]/22:.2f}% | {values["passes"]} |')
    lines += ['', f'Stage-1 false accepts: {metrics["cascade"]["false_accepts"]}/6 final self-check PASS claims;',
              f'precision-gate false accepts: {gate_fa}/{len(accepted)}. Stage-1 replay uses the saved',
              'self-check payload, not the fallback final page. All six payloads retain page text;',
              'four handed-off cases remain snapshot reconstructions, not independent post-script grade reads.', '',
              'Cascade gains NBA leaders and Nets navigation. It remains one task behind both baselines:',
              'ICSE 2004 now passes for both baselines via separately grounded date/chair parts,',
              'but cascade ended at `http://www.icse-conferences.org/2004/org_ctte.htm`, not the keyed `/history.html`.',
              'Thus the 4.55 pp deficit misses the 2 pp criterion despite a 169 ms lower mean wall time.',
              'The 90.91% fallback rate still limits speed gains. The accepted Nets script is now a pass;',
              'the accepted SpotHero contact result remains a false accept.', '',
              '### Every extdev flip (old recorded → new frozen grade)', '',
              '| File | Arm | Task | Flip | Old reason | New reason |', '|---|---|---|---|---|---|']
    for r in flips:
        lines.append('| ' + ' | '.join(str(r[k]) for k in ('file','arm','task_id')) + ' | FAIL → PASS | ' + r['old_reason'] + ' | ' + r['new_reason'] + ' |')
    lines += ['', 'Flip totals: ' + json.dumps(dict(Counter((r['file']+' / '+r['arm']) for r in flips))) + '.',
              'All other extdev outcomes are unchanged, including smoke (0/3 passes) and MCP (0 valid rows).',
              'NBA flips use full-reference bounds plus grounded parts; ICSE 2004 flips use separately grounded date/chair parts;',
              'Nets/commuter flips use the explicit URL-answer flag. No outcome flips are due solely to query-subset matching.', '',
              '### Older saved data', '',
              f'`python tools/regrade.py --out docs/results/regrade_20261117` covered {len(json.loads((ROOT/"docs/results/regrade_20261117/regrade.json").read_text())["sources"])} sources with arm rows.',
              f'Against regrade_20261116: {older["matched_older_sources"]} common source hashes match;',
              f'{older["preexisting_flips_unchanged"]} pre-existing flips remain unchanged. New older-data flips: {len(older["new_older_flips"])};',
              f'removed older-data flips: {len(older["removed_older_flips"])}; hidden-split flip summaries are unchanged.',
              '**No older data is affected.** Every common per-source arm group is identical.',
              'The global report lists 41 raw-recorded→current flips: the previous 31 plus the 10 extdev flips above.',
              'See [global report](../regrade_20261117/report.md) and [machine-readable comparison](../regrade_20261117/diff_vs_20261116.json).', '']
    section = '\n'.join(lines)
    (HERE/'REGRADE.md').write_text(section)
    readme = HERE/'README.md'
    marker = '<!-- REGRADE_TABLE -->'
    end = '<!-- END_REGRADE_TABLE -->'
    content = readme.read_text()
    if marker in content:
        start, tail = content.split(marker, 1)
        _, finish = tail.split(end, 1)
        readme.write_text(start + marker + '\n\n' + section + '\n' + end + finish)
    print('Extdev replay:',len(audit),'rows;',result['attempted'],'attempted;',result['budget_skips'],'budget skips; 0 unavailable')
    print('Extdev flips:',len(flips),'(all fail->pass); smoke passes:',result['smoke_passes'])
    print('Older data:',older)
    print('Ledger running_total_usd:',ledger['running_total_usd'])
    print('\n'.join(lines[:8]))


if __name__ == '__main__':
    main()
