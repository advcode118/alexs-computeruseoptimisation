# Shortcut Replay Report

## Summary

- **Total Snapshots**: 5
- **Shortcut Fired**: 2 (40%)
- **Matched Model Action**: 1
- **Mismatched**: 1

## Details

| Task | Step | Shortcut Fired | Tier | Shortcut Action | Model Action | Match |
|------|------|----------------|------|-----------------|--------------|-------|
| wv_arxiv_search | 1 | ✗ | planner | - | fill:S1E5:attention is all you | - |
| fixture_packing_add | 1 | ✗ | planner | - | fill:S1E3:milk | - |
| fixture_packing_add | 2 | ✗ | fast | - | click:S2E4 | - |
| wv_wikipedia_search | 1 | ✓ | html_shortcut | click:S1E1 | fill:S1E3:Ada Lovelace | ✗ |
| wv_wikipedia_search | 2 | ✓ | html_shortcut | click:S2E5 | click:S2E5 | ✓ |
