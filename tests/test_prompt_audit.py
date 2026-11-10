"""Every model-facing prompt stays free of probe answers and judge-only fields.

Offline. No browser and no network. The live page URL and the task text are
the only places a destination may appear, and these fixtures use neither.
"""

from __future__ import annotations

import json

from bench.arms import SELECTABLE_ARMS, prompt_for
from bench.judge import JUDGE_SYSTEM
from bench.probe import probe_tasks
from bench.script_cache import PATCH_PROMPT, PATCH_TOOL, patch_request
from bench.script_first import (
    ScriptFirstClient,
    format_run_result,
    model_visible_script_result,
    repair_request,
    script_verdict,
)
from bench.stagehand_local import StagehandLocalClient
from loop import planner

# Probe answers and judge-only strings. The task text uses "Ada Lovelace"
# and "heapq" as words. These are the destination path, the selector, and
# the field the judge reads.
FORBIDDEN = (
    "Ada_Lovelace",
    "heapq.html",
    "/library/heapq.html",
    ".titleline",
    "selector_text",
    "answer_equals_selector",
    "On the Ada Lovelace Wikipedia article",
    "On the heapq module documentation page",
    "The title of the first story on the page",
)


def _model_texts() -> list[tuple[str, str]]:
    texts = [(f"prompt:{arm}", prompt_for(arm)) for arm in SELECTABLE_ARMS]
    texts.append(("patch-prompt", PATCH_PROMPT))
    texts.append(("patch-tool", json.dumps(PATCH_TOOL)))
    texts.append(("planner", planner._SYSTEM))
    texts.append(("planner-fast", planner._FAST_SYSTEM))
    texts.append(("judge-system", JUDGE_SYSTEM))
    for tool in ScriptFirstClient().tools_for_claude():
        texts.append(("run_script-tool", json.dumps(tool)))
    for tool in StagehandLocalClient().tools_for_claude():
        texts.append((f"stagehand:{tool['name']}", json.dumps(tool)))
    for task in probe_tasks():
        url = task["start_url"]
        raw = format_run_result(
            ok=True,
            url=url,
            step_count=1,
            title="Start",
            text="The start page is open.",
            selector_text=".titleline a",
            claimed={"answer": "not the finished page"},
        )
        verdict, payload = script_verdict(task["end_markers"], raw, url)
        assert verdict.verdict == "FAIL", task["id"]
        payload["selector_text"] = ".titleline a"
        payload["answer_equals_selector"] = ".titleline a"
        payload["expected_answer"] = task["expected_answer"]
        visible = model_visible_script_result(raw)
        repair = repair_request(url, verdict.reason)
        texts.append((f"repair:{task['id']}", visible + "\n" + repair))
        texts.append(
            (
                f"patch:{task['id']}",
                patch_request(
                    description=task["description"],
                    start_url=url,
                    script='page.goto("https://example.com/")',
                    payload=payload,
                    verdict=verdict,
                ),
            )
        )
    return texts


def test_prompts_repairs_and_patch_turns_omit_probe_answers():
    seen = _model_texts()
    names = [name for name, _text in seen]
    assert any(name.startswith("prompt:") for name in names)
    assert any(name.startswith("repair:") for name in names)
    assert any(name.startswith("patch:") for name in names)
    assert len([name for name in names if name.startswith("prompt:")]) == len(SELECTABLE_ARMS)
    for name, text in seen:
        for secret in FORBIDDEN:
            assert secret not in text, f"{name} contains {secret!r}"
