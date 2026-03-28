# EmbryoTempoFormer Code Review Template

Use this template for PRs, branch reviews, or pre-merge checks in this repository.
Prioritize correctness, reproducibility, data-split hygiene, and statistical validity over style-only comments.

## Review Metadata

| Field | Value |
| --- | --- |
| Review target | |
| Branch / PR | |
| Commit / tag | |
| Reviewer | |
| Date | |
| Review type | PR / local branch / release / hotfix |

## Change Summary

- What changed?
- Why was it changed?
- Which pipeline stage is affected?
  `src/` model code / `analysis/` Python pipeline / `scripts/` shell entrypoints / split or data utilities / figures or summaries

## Findings

List findings in severity order. Use file references and explain the concrete risk.

| Severity | File / area | Finding | Why it matters | Requested change |
| --- | --- | --- | --- | --- |
| P0 | | | blocks correctness or reproducibility | |
| P1 | | | likely bug / invalid conclusion / data leak risk | |
| P2 | | | maintainability / robustness / portability risk | |
| P3 | | | minor issue or follow-up | |

Severity guide:
- `P0`: invalid results, broken pipeline, train/test leakage, destructive output changes
- `P1`: likely scientific or engineering bug, wrong metric, wrong aggregation, hidden regression
- `P2`: robustness, clarity, portability, or performance risk
- `P3`: optional cleanup or follow-up

## Project-Specific Checklist

Mark each item `Yes`, `No`, or `N/A`.

### 1. Reproducibility and Environment

- [ ] No machine-specific absolute paths were introduced outside local `.env`
- [ ] New environment variables are reflected in `.env.example` and documented if needed
- [ ] Changes keep outputs under `runs/` rather than hard-coded external locations
- [ ] Commands still work from repo-root-relative paths
- [ ] Dependency changes are reflected in `requirements.txt`, `environment.yml`, or both

### 2. Data Integrity and Split Hygiene

- [ ] Train / val / test boundaries remain intact
- [ ] Embryo IDs are preserved consistently across preprocessing, split loading, inference, and aggregation
- [ ] Split JSON assumptions still match `split/README.md`
- [ ] Optional external-domain `S-BIAD840` logic stays isolated from the main paper pipeline unless explicitly intended
- [ ] No processed data, checkpoints, or `runs/` artifacts were accidentally staged for commit

### 3. Time-Axis and Biological Assumptions

- [ ] `DT_H`, `T0_HPF`, `CLIP_LEN`, `IMG_SIZE`, `EXPECT_T`, and `STRIDE` remain internally consistent
- [ ] Any change to time-axis assumptions is propagated to downstream analysis and documentation
- [ ] Checkpoint assumptions still match processed array shape and inference settings
- [ ] Any change in anchor or staging logic is justified and reflected in summaries / figures

### 4. Statistical Validity

- [ ] Inference claims remain embryo-level, not point-level pseudo-replication
- [ ] Aggregation still separates `points.csv`, `embryo.csv`, and `summary.json` correctly
- [ ] Bootstrap / CI / power calculations still operate on the intended unit of analysis
- [ ] Metric changes are scientifically interpretable and do not silently change the paper claim

### 5. Model / Inference Correctness

- [ ] CLI behavior remains consistent for `preprocess`, `make_split`, `train`, `eval`, and `infer`
- [ ] EMA / AMP / device / batch-size logic still has sane defaults
- [ ] Memory-profile changes do not silently alter semantics
- [ ] JSON output schema remains backward compatible, or breaking changes are documented

### 6. Pipeline Orchestration

- [ ] `scripts/` wrappers and `analysis/run_reproduction_pipeline.py` remain in sync
- [ ] Optional flags such as `RUN_CONTINUOUS_POWER`, `RUN_CLIPLEN_SENSITIVITY`, and `RUN_SALIENCY` still behave as documented
- [ ] Step ordering still matches the expected reproduction flow
- [ ] Fail-fast behavior is preserved for missing env vars, missing files, or subprocess errors

### 7. Figures, Tables, and Output Contracts

- [ ] Output filenames and folder layout remain stable unless intentionally versioned
- [ ] Downstream figure or summary scripts still find the expected upstream files
- [ ] Any renamed output is reflected in README or release instructions
- [ ] Generated artifacts needed only for local inspection are not committed

## Verification Performed

Record what was actually run, not what should have been run.

| Check | Command / method | Result |
| --- | --- | --- |
| Environment sanity | `bash scripts/00_check_env.sh` | |
| Targeted script | | |
| Targeted Python module | | |
| Smoke test on changed path | | |
| Full reproduction rerun | | |

## Reviewer Notes

### Open Questions

- 

### Risk Summary

- Scientific risk:
- Reproducibility risk:
- Engineering risk:

## Recommendation

- [ ] Approve
- [ ] Request changes
- [ ] Comment only

## Short Review Summary

Write a 3 to 6 line summary covering:
- whether the change is safe to merge
- the highest-severity issue, if any
- what was verified directly
- any remaining uncertainty
