"""Document key choices using authored data only, before any arm-answer replay."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bench.tasks_extdev import EXTDEV_TASKS

HERE = Path(__file__).resolve().parent
NOT_KEYED = {
    'greatamerica_thrill': 'Individual ride names: no authored page-verbatim list; only category heading is available.',
    'frontiercity_family': 'Individual ride names: no authored page-verbatim list; only category heading is available.',
    'dota_dlc_cart': 'Other DLC names and proof that every cartable DLC was added; reproducer supplies UI actions, not more page-verbatim answer values.',
    'booking_times_square': 'Four-star label and location wording have no authored page-verbatim answer part; existing URL key is unchanged.',
    'airbnb_europe_mansions': 'Europe wording is not an authored page-verbatim part; existing URL key remains unchanged.',
    'ronaldo_world_cup_stats': 'Individual statistics and years are not authored page-verbatim parts; URL navigation is explicitly allowed for this find-statistics-page task.',
    'fiestatexas_events': 'Individual event names/dates are unavailable; heading only. No URL-answer flag: asks to show all events, not merely find a page.',
    'spothero_marketing': 'Other openings, if any, are unavailable; one authored role only. Find-openings page navigation is allowed.',
    'steam_daily_players': 'Game names/player counts are unavailable; tab heading only. No URL-answer flag: asks for the daily-player view, whose tab state is not encoded by the URL.',
    'amazon_puppy_food': 'Individual products, puppy-food wording and four-star page label are unavailable; only sort heading is authored.',
    'green_xbox_controller': 'Four-star page label is unavailable; existing URL marker remains unchanged.',
    'tiny_home_dates': 'Individual property names, adult/pet counts and dates have no authored page-verbatim parts; existing URL key is unchanged.',
    'sf_exercise_dates': 'Individual event names and date labels are unavailable; existing date-query URL key is unchanged.',
    'castles_europe_week': 'Individual property names and price/duration/date labels are unavailable; existing URL key is unchanged.',
    'rovio_anniversary': 'Authored fragment names the third Angry Birds Movie installment, whereas original source_key.answer names Mystery Island. Preserve the already-authored page fragment, document conflict; do not invent or substitute a title.',
    'pirate_treasures': 'Authored character fragments come from another article and are not guaranteed to coexist on the final page. No additional characters or inferred treasure names added.',
    'ironhide_historical_games': 'April 2023 authored source says free-game promotion, not a new release. No invented release claim/date part.',
    'ironhide_arcade_gdc': 'GDC fragment comes from another page; coexistence on final page is unverified.',
    'icse_2002_chairs': 'Original multiline chair marker is retained as one part; conjunction/paraphrase matching is not introduced.',
    'booking_la_filters': 'Original multiline review-filter marker is retained; no inferred additional filters.',
    'spothero_contact': 'Unchanged: contacting support is an action, not merely opening a URL; no URL-answer flag.',
    'dream_blast_revenue': 'Single requested game name is already the complete authored value; year/revenue context is not a requested answer part.',
    'inclusive_strategy_role': 'Single requested named role is already complete in the marker; alternate wording and document title are context, not extra requested answer parts.',
}


def main():
    lines = ['# Extdev key changes — authored-data-only selection', '',
             '**Key selection was completed before reading any saved arm answers for this step.**',
             'No arm returned answer was consulted to choose parts, full answers or URL flags.',
             'Only descriptions, existing marker/unchecked_fragments, reproducer constants,',
             'and original candidate source_key/provenance were inspected.', '',
             'The old marker, URL keys, key_scope and unchecked_fragments remain unchanged.',
             'For multipart requests the reference is marker + authored unchecked_fragments,',
             'joined with `; `. Constraints with no authored page-verbatim value are not invented.',
             'Source references are bench/tasks_extdev.py fields and, by source/source_id,',
             'docs/results/ext_sample_20261116/{candidates_extdev,authoring_extdev}.jsonl.',
             'Page-verbatim authorship is not proof that all parts coexist on the final page:',
             'multi-source tasks may still fail grounding. Synthetic 40/40 is logical compatibility only.', '',
             'URL flags are conservative: five find/browse-page tasks only. No value task',
             'has a URL flag. Contact-support, all-events and daily-player-view tasks do not.', '',
             '## Frozen key-selection snapshot', '',
             '`bench/tasks_extdev.py` SHA256: `' + hashlib.sha256((ROOT/'bench/tasks_extdev.py').read_bytes()).hexdigest() + '`.', '']
    changed = 0
    for t in EXTDEV_TASKS:
        if not any(k in t for k in ('full_answer', 'answer_parts', 'url_answer_ok')):
            continue
        changed += 1
        name = t['id'].split('_', 2)[2]
        lines += ['## ' + t['id'], '', '- Description: ' + t['description'],
                  '- Provenance: ' + t['source'] + ' / `' + t['source_id'] + '`.',
                  '- Old marker (unchanged): `' + json.dumps(t['expected_answer'], ensure_ascii=False) + '`.',
                  '- New full_answer: `' + json.dumps(t.get('full_answer'), ensure_ascii=False) + '`.',
                  '- New answer_parts: `' + json.dumps(t.get('answer_parts'), ensure_ascii=False) + '`.',
                  '- url_answer_ok: `' + json.dumps(t.get('url_answer_ok', False)) + '`.']
        for i, part in enumerate(t.get('answer_parts', [])):
            origin = 'expected_answer / end_markers.answer_in_text' if i == 0 else f'unchecked_fragments[{i-1}]'
            lines.append(f'  - Part {i+1} source: `{origin}` = `{json.dumps(part, ensure_ascii=False)}`.')
        lines += ['- Not keyed / limitation: ' + NOT_KEYED.get(name, 'No additional requested authored fact omitted; literal strings are not paraphrase matching.'), '']
    lines += ['## Unchanged action-task note', '', NOT_KEYED['spothero_contact'], '',
              f'Changed tasks: {changed}; parts mode: {sum("answer_parts" in t for t in EXTDEV_TASKS)}; URL flags: {sum(t.get("url_answer_ok", False) for t in EXTDEV_TASKS)}.', '']
    (HERE/'KEY_CHANGES.md').write_text('\n'.join(lines))
    print(lines[-2])
    print('Key choices locked without consulting arm answers.')


if __name__ == '__main__':
    main()
