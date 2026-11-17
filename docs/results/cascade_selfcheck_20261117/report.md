# Cascade self-check precision

| Unit | Mode | TP | FP | FN | TN | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| script | plain | 86 | 19 | 1 | 164 | 81.9% | 98.9% |
| script | precision | 85 | 5 | 2 | 178 | 94.4% | 97.7% |
| final | plain | 86 | 19 | 1 | 25 | 81.9% | 98.9% |
| final | precision | 85 | 5 | 2 | 39 | 94.4% | 97.7% |

Rules were tuned on these dev/validation rows, not an independent claim set.
Wilson 95% intervals and per-rule false accepts caught / true passes lost are in precision.json.
Remaining false accepts are wrong-value-on-right-page cases structural checks cannot see.
