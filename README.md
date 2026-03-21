# EmbryoTempoFormer (ETF, S-BIAD531)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18318139.svg)](https://doi.org/10.5281/zenodo.18318139)

EmbryoTempoFormer (ETF) is a **paper-grade reproducible pipeline** for:
- **clip-based developmental time prediction** from zebrafish brightfield time-lapse microscopy, and
- **embryo-level developmental tempo estimation** (anchored slope `m_anchor` + stability diagnostics) for cross-condition comparison (e.g., temperature shift).

**Links**
- **Code repo:** https://github.com/LijiayuDeng/s-biad531-embryo-tempoformer
- **Zenodo reproducibility bundle (FULL processed + checkpoints + splits):** https://doi.org/10.5281/zenodo.18318139
- **Optional Princeton processed bundle (external-domain `S-BIAD840` import):** https://doi.org/10.5281/zenodo.18979476
  Extract it as `data/sbiad840_aligned_4p5/` inside this repo.
- **Docker image (ready-to-use pipeline environment):** https://hub.docker.com/r/lijiayudeng/embryo-tempoformer
- **Raw data source:** BioImage Archive accession **S-BIAD531**
  https://www.ebi.ac.uk/bioimage-archive/galleries/S-BIAD531.html

**Design principles**
- Machine-specific absolute paths live in a local `.env` (**never commit**).
- Scripts run end-to-end and produce **JSON/CSV summaries + publication figures** under `runs/`.
- Sliding-window predictions are correlated within embryo; inferential comparisons are performed at the **embryo level** (avoid pseudo-replication).

---

<details open>
<summary>English (click to collapse)</summary>

## Contents
- [Quickstart (Option B, recommended)](#quickstart-option-b-recommended)
- [Expected outputs](#expected-outputs)
- [Optional: SmoothGrad saliency](#optional-smoothgrad-saliency)
- [Metrics notes (external 25C)](#metrics-notes-external-25c)
- [Optional: Training specification (EXP4; from checkpoint cfg)](#optional-training-specification-exp4-from-checkpoint-cfg)
- [Optional: Option A (preprocess from raw OME-TIFF)](#optional-option-a-preprocess-from-raw-ome-tiff)
- [ETF CLI quick reference](#etf-cli-quick-reference)
- [Representative Hardware / Runtime](#representative-hardware--runtime)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Quickstart (Option B, recommended)

**Goal:** reproduce paper quantitative results and figures using the Zenodo bundle (**no re-training required**).

### Requirements
- A **bash** environment (Linux / macOS / WSL).
- Python 3.9+ recommended.
- `pip` (or conda).

### Step 1 — Download and extract the data bundles

For the main paper reproduction, download:
- `embryo-tempoformer_release_v1_full.tar.gz`
  https://doi.org/10.5281/zenodo.18318139

Extract:
```bash
tar -xzf embryo-tempoformer_release_v1_full.tar.gz
```

Expected layout:
```text
embryo-tempoformer_release_v1/
├── processed_28C5/
├── processed_25C/
├── splits/
├── checkpoints/
│   ├── cnn_single_best.pt
│   ├── meanpool_best.pt
│   ├── nocons_best.pt
│   └── full_best.pt
├── MANIFEST.json
└── SHA256SUMS.txt
```

If you also want to reproduce the Princeton external-domain analyses (`Comment 8`),
extract the optional processed Princeton bundle **inside this repository** so that
it becomes:

- `sbiad840_aligned_4p5.tar.gz`
  https://doi.org/10.5281/zenodo.18979476

```text
s-biad531-embryo-tempoformer/
└── data/
    └── sbiad840_aligned_4p5/
        ├── processed_28C5_sbiad840/
        ├── processed_25C_sbiad840/
        └── splits/
```

For example, from the repo root:

```bash
mkdir -p data
tar -xzf sbiad840_aligned_4p5.tar.gz -C data
```

This second bundle is **not required** for the main paper reproduction pipeline;
it is only needed for the optional Princeton cross-site evaluation and low-shot
adaptation workflows.

(Optional) checksum verification:
```bash
cd embryo-tempoformer_release_v1
sha256sum -c SHA256SUMS.txt
cd ..
```

### Step 2 — Clone the repo and install dependencies

**Option 2A: Docker (Easiest, no clone required)**
Skip Python installation entirely!
1. Pull the pre-built image:
```bash
docker pull lijiayudeng/embryo-tempoformer:latest
```
2. Start an interactive container, mounting your extracted Zenodo data to `/data` inside the container:
```bash
# Replace /path/to/embryo-tempoformer_release_v1 with your actual absolute path
docker run -it -v /path/to/embryo-tempoformer_release_v1:/data lijiayudeng/embryo-tempoformer:latest /bin/bash
```
3. Once inside the container (you will be in `/app`), proceed directly to **Step 3**, but use `/data/...` as the base for all absolute paths in your `.env`. Be sure to set `RUNS_DIR=/data/runs` so that the generated figures and CSVs are saved back to your host machine!

**Option 2B: Local pip installation**
```bash
git clone https://github.com/LijiayuDeng/s-biad531-embryo-tempoformer.git
cd s-biad531-embryo-tempoformer
pip install -r requirements.txt
```

(Optional) conda:
```bash
conda env create -f environment.yml
conda activate embryo-tempoformer
```

### Step 3 — Configure `.env`
Create your local `.env`:
```bash
cp .env.example .env
```

Open `.env` and set paths to your extracted Zenodo folder. Replace `/ABS/PATH/TO` with your actual absolute path:

**Required variables (checked by `scripts/00_check_env.sh`):**
```text
PROC_28C5=/ABS/PATH/TO/embryo-tempoformer_release_v1/processed_28C5
PROC_25C=/ABS/PATH/TO/embryo-tempoformer_release_v1/processed_25C
SPLIT_28C5=/ABS/PATH/TO/embryo-tempoformer_release_v1/splits/28C5.json
SPLIT_25C=/ABS/PATH/TO/embryo-tempoformer_release_v1/splits/25C.json

CKPT_CNN_SINGLE=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/cnn_single_best.pt
CKPT_MEANPOOL=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/meanpool_best.pt
CKPT_NOCONS=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/nocons_best.pt
CKPT_FULL=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/full_best.pt
```

**Optional runtime knobs (keep defaults unless needed):**
```text
# External-domain processed npy dirs / splits (either generated by
# scripts/34_preprocess_sbiad840.sh or extracted from the optional
# sbiad840_aligned_4p5 bundle under ./data/)
PROC_28C5_SBIAD840=./data/sbiad840_aligned_4p5/processed_28C5_sbiad840
PROC_25C_SBIAD840=./data/sbiad840_aligned_4p5/processed_25C_sbiad840
SPLIT_28C5_SBIAD840=./data/sbiad840_aligned_4p5/splits/28C5_sbiad840_test.json
SPLIT_25C_SBIAD840=./data/sbiad840_aligned_4p5/splits/25C_sbiad840_test.json

# Output root directory
# IMPORTANT: keep RUNS_DIR=./runs because scripts/reproduce_all.sh assumes ./runs
RUNS_DIR=./runs

# Optional interpreter override for shell entrypoints.
# If PYTHON_BIN is unset in the current shell, scripts/* bootstrap it from .env
# before loading the remaining environment variables.
PYTHON_BIN=python3

# Time-axis constants used by aggregation scripts
DT_H=0.25
T0_HPF=4.5

# Inference windowing / preprocessing assumptions (must match processed arrays and checkpoints)
CLIP_LEN=24
IMG_SIZE=384
EXPECT_T=192
STRIDE=8

# Runtime (inference)
DEVICE=auto
AMP=1
USE_EMA=1
BATCH_SIZE=64
```

### Step 4 — Validate environment paths
```bash
bash scripts/00_check_env.sh
```

If you also want to validate the external S-BIAD840 processed dataset paths:
```bash
WITH_OPTIONAL=sbiad840 bash scripts/00_check_env.sh
```

### Step 5 — One-command reproduction (infer → aggregate → CI/power → figures)
```bash
bash scripts/reproduce_all.sh
```

**What this script does (in order):**
1. `scripts/00_check_env.sh` — sanity-check required `.env` variables and paths
2. `scripts/10_infer_all.sh` — runs inference for 4 models (`cnn_single`, `meanpool`, `nocons`, `full`) on 2 test sets (`ID28C5_TEST`, `EXT25C_TEST`); produces per-embryo JSON under `.../<TAG>/<model>/json/*.json`; writes `OUTROOT/OUTROOT.txt`
3. `scripts/20_aggregate_all.sh <OUTROOT>` — aggregates JSON into `points.csv`, `embryo.csv`, `summary.json`
4. `scripts/30_ci_power_all.sh <OUTROOT>` — computes embryo-bootstrap CI and power curves
5. `scripts/31_power_curve_continuous.sh <OUTROOT> <OUTROOT>/continuous_power` — continuous effect-size planning curves (`E80/E90/E95`)
6. `scripts/11_cliplen_sensitivity.sh <OUTROOT>/cliplen_sensitivity` — fixed-checkpoint clip-length sensitivity (`L=4/12/24` by default)
7. `scripts/12_cliplen_context_fit.sh <OUTROOT> <OUTROOT>/cliplen_sensitivity <OUTROOT>/cliplen_sensitivity/context_fit` — compact `0h/1h/3h/6h` context ladder and descriptive ETF-full fits
8. `scripts/32_stage_error_bins.sh <OUTROOT> <OUTROOT>/stage_error/stage_error_by_bin.csv` — stage-stratified point-level error summary
9. `scripts/33_anchor_sensitivity.sh <OUTROOT> <OUTROOT>/anchor_sensitivity` — T0 anchor sensitivity re-aggregation summary
10. `scripts/44_stage_tempo_dependence.sh <OUTROOT> <OUTROOT>/stage_tempo` — direct stage-dependent tempo analysis (piecewise slopes + local interval derivatives)
11. `scripts/40_make_figures.sh <OUTROOT>` — generates publication figures (PNG + PDF)
12. (optional) `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>` if `RUN_SALIENCY=1`

Output root directory (OUTROOT):
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

Default optional-analysis behavior in `reproduce_all.sh`:
- `RUN_CONTINUOUS_POWER=1`
- `RUN_CLIPLEN_SENSITIVITY=1`
- `RUN_STAGE_ERROR_BINS=1`
- `RUN_ANCHOR_SENSITIVITY=1`
- `RUN_SALIENCY=0`

To skip the extra revision analyses:
```bash
RUN_CONTINUOUS_POWER=0 RUN_CLIPLEN_SENSITIVITY=0 RUN_STAGE_ERROR_BINS=0 RUN_ANCHOR_SENSITIVITY=0 bash scripts/reproduce_all.sh
```

Thin-shell note:
- `scripts/reproduce_all.sh` is now only a wrapper around `analysis/run_reproduction_pipeline.py`
- matrix traversal and optional-stage branching live in Python, not shell

---

## Expected outputs

Under `runs/paper_eval_YYYYMMDD_HHMMSS/`:

**Per-embryo inference**
- `ID28C5_TEST/<model>/json/*.json` — per-embryo inference JSON (one file per embryo)
- `EXT25C_TEST/<model>/json/*.json` — per-embryo inference JSON (external set)

**Aggregated tables and summaries**
- `ID28C5_TEST/<model>/points.csv` — point-level (per sliding window) predictions
- `ID28C5_TEST/<model>/embryo.csv` — embryo-level aggregated metrics
- `ID28C5_TEST/<model>/summary.json` — summary statistics
- `EXT25C_TEST/<model>/points.csv` — external set point-level
- `EXT25C_TEST/<model>/embryo.csv` — external set embryo-level
- `EXT25C_TEST/<model>/summary.json` — external set summary

**Uncertainty and sample-efficiency**
- `CI_<model>_m_anchor.json` — embryo-bootstrap 95% CI for delta-m (computed from `embryo.csv`)
- `power_<model>_m_anchor.csv` — power curve data
- `power_<model>_m_anchor.png` — power curve figure
- `continuous_power/continuous_power_by_model.csv` — continuous effect-size power surface (optional)
- `continuous_power/continuous_thresholds_by_model.csv` — E80/E90/E95 threshold curves over `|delta m|`
- `continuous_power/continuous_E80_by_model.svg` — all-model E80 curve
- `continuous_power/continuous_full_E80_E90_E95.svg` — full-model E80/E90/E95 curves
- `cliplen_sensitivity/cliplen_summary.csv` — fixed-checkpoint clip-length sensitivity summary (optional)
- `cliplen_sensitivity/context_fit/context_ladder.csv` — 0h/1h/3h/6h context ladder summary (optional)
- `cliplen_sensitivity/context_fit/full_context_fit.csv` — descriptive ETF-full 1/3/6h linear fits (optional)
- `stage_error/stage_error_by_bin.csv` — stage-stratified point-level error summary (optional)
- `anchor_sensitivity/anchor_sensitivity_summary.csv` — T0 anchor sensitivity summary (optional)
- `stage_tempo/piecewise_stage_slopes.csv` — Kimmel-period piecewise tempo slopes (optional)
- `stage_tempo/local_slope_by_interval.csv` — local interval slopes from stage-averaged trajectories (optional)
- `stage_tempo/stage_tempo_full_summary.md` — compact ETF-full stage-dependent summary table (optional)
- `stage_tempo/full_local_slope_by_interval.svg` — ETF-full local-slope figure (optional)

**Figures**
- `figures_jobs/` — publication figures (PNG + PDF)

**Meta**
- `OUTROOT.txt` — records OUTROOT path (written by `scripts/10_infer_all.sh`)

Models (`<model>`): `cnn_single`, `meanpool`, `nocons`, `full`.

Thin-shell note:
- shell entrypoints under `scripts/` are orchestration wrappers only
- if `PYTHON_BIN` is unset in the current shell, these wrappers bootstrap it from `.env` before loading the remaining variables
- dataset/model enumeration, per-embryo scheduling, env checking, aggregation, CI/power matrix traversal, and top-level pipeline branching now live in Python (`analysis/check_env.py`, `analysis/run_infer_matrix.py`, `analysis/aggregate_matrix.py`, `analysis/run_ci_power_matrix.py`, `analysis/run_cliplen_sensitivity.py`, `analysis/select_best_embryo.py`, `analysis/run_reproduction_pipeline.py`)

Common overrides for `scripts/10_infer_all.sh`:
```bash
OUTROOT=./runs/paper_eval_manual \
DATASETS=ID28C5_TEST \
MODELS=full \
FORCE=1 \
bash scripts/10_infer_all.sh
```

Notes:
- `FORCE=1` re-runs the requested per-embryo inference JSONs in-place. Leave it at `0` only if you intentionally want to reuse existing JSON under the same `OUTROOT`.

---

## Optional: Continuous effect-size planning curve

This extends sample-efficiency analysis from discrete effect bins to a continuous range.
It is already run by default inside `scripts/reproduce_all.sh` unless `RUN_CONTINUOUS_POWER=0`.

Default dense setup used for revision:
- `|delta m| = 0.00 .. 0.10` with step `0.002`
- Targets: `E80` / `E90` / `E95`
- Shape constraints (enabled by default):
  - power should be non-decreasing with larger `E`
  - required `E` should be non-increasing with larger `|delta m|`

Statistical definition:
- `delta m = mean(m_anchor, A) - mean(m_anchor, B)`
- default `A=EXT25C_TEST`, `B=ID28C5_TEST`
- detection rule: embryo-bootstrap 95% CI excludes 0

Preferred shell entrypoint:
```bash
bash scripts/31_power_curve_continuous.sh \
  runs/paper_eval_20260225_232506 \
  runs/paper_eval_20260225_232506/continuous_power
```

Useful environment overrides:
```bash
MODELS=cnn_single,meanpool,nocons,full \
DELTA_MAX=0.10 DELTA_STEP=0.002 \
R_OUTER=1200 B_BOOT=800 SEED=20260310 \
bash scripts/31_power_curve_continuous.sh
```

Direct Python invocation remains available if needed:
```bash
python analysis/power_curve_continuous.py \
  --outroot runs/paper_eval_20260225_232506 \
  --out_dir runs/paper_eval_20260225_232506/continuous_power \
  --models cnn_single,meanpool,nocons,full \
  --E_list 2,3,4,6,8,10,12,14,16,18,20,22 \
  --delta_max 0.10 \
  --delta_step 0.002 \
  --R 1200 \
  --B_boot 800 \
  --seed 20260310 \
  --y_min_plot 0 \
  --y_max_plot 23 \
  --y_tick_step 1 \
  --enforce_monotone_power_e 1 \
  --enforce_monotone_threshold_delta 1
```

Outputs under `--out_dir`:
- `continuous_power_by_model.csv` — full power surface (`power` + `power_raw`)
- `continuous_thresholds_by_model.csv` — threshold curves (`E80/E90/E95`)
- `continuous_E80_by_model.svg` — all-model E80 curve
- `continuous_full_E80_E90_E95.svg` — full-model E80/E90/E95 curves

Plot notes:
- Curves are drawn with monotone cubic smoothing for readability.
- Markers remain the actual grid-point values.
- Axis display can start at 0, but inferentially valid designs still follow `E_list` (typically `E>=2`).
- Near-zero `|delta m|` may show `>max(E_list)` (rendered as gaps).

---

## Optional: Clip-length sensitivity and context ladder

This analysis answers a different question from the power curve:
- hold the underlying acquisition interval fixed at `15 min`
- vary only the inference clip length (`L=4/12/24` by default)
- summarize the practical context ladder as `0h` (`cnn_single`) vs `1h/3h/6h` (`ETF-full`)

This is also run by default inside `scripts/reproduce_all.sh` unless `RUN_CLIPLEN_SENSITIVITY=0`.

### Step 1: Run fixed-checkpoint clip-length sensitivity
Preferred shell entrypoint:
```bash
bash scripts/11_cliplen_sensitivity.sh
```

Write to a fixed directory:
```bash
bash scripts/11_cliplen_sensitivity.sh runs/cliplen_sensitivity_main
```

Common overrides:
```bash
DATASETS=ID28C5_TEST,EXT25C_TEST \
MODELS=full \
CLIP_LENS=4,12,24 \
FORCE=1 \
bash scripts/11_cliplen_sensitivity.sh
```

Notes:
- `FORCE=1` re-runs both inference and aggregation; with `FORCE=0`, existing JSON and completed summaries may be reused when compatible.

Main outputs:
- `<OUTROOT>/cliplen_summary.csv`
- `<OUTROOT>/L04/...`, `<OUTROOT>/L12/...`, `<OUTROOT>/L24/...`

### Step 2: Summarize as a compact 0h/1h/3h/6h context ladder
Preferred shell entrypoint:
```bash
bash scripts/12_cliplen_context_fit.sh \
  runs/paper_eval_20260225_232506 \
  runs/cliplen_sensitivity_20260311_030252
```

This writes:
- `<CLIPLEN_OUTROOT>/context_fit/context_ladder.csv`
- `<CLIPLEN_OUTROOT>/context_fit/full_context_fit.csv`

Direct Python invocation remains available:
```bash
python analysis/cliplen_context_fit.py \
  --main_outroot runs/paper_eval_20260225_232506 \
  --cliplen_csv runs/cliplen_sensitivity_20260311_030252/cliplen_summary.csv \
  --out_dir runs/cliplen_sensitivity_20260311_030252/context_fit
```

Interpretation notes:
- `cnn_single` is the `0h` image-only reference and is not mixed into ETF-full linear fits.
- ETF-full fits are descriptive only and use the `1h/3h/6h` ladder (`L=4/12/24`).
- This is fixed-checkpoint sensitivity (`24-frame-trained -> shorter-context inference`), not dedicated `4-train-4-test` or `12-train-12-test` retraining.

---

## Optional: Stage-stratified error bins

This summarizes where point-level errors concentrate along the nominal timeline.
It is already run by default inside `scripts/reproduce_all.sh` unless `RUN_STAGE_ERROR_BINS=0`.

Preferred shell entrypoint:
```bash
bash scripts/32_stage_error_bins.sh \
  runs/paper_eval_20260225_232506 \
  runs/paper_eval_20260225_232506/stage_error/stage_error_by_bin.csv
```

Common overrides:
```bash
DATASETS=ID28C5_TEST,EXT25C_TEST \
MODELS=cnn_single,full \
SCHEME=kimmel_start \
bash scripts/32_stage_error_bins.sh
```

Use fixed custom edges only if you explicitly want non-Kimmel bins:
```bash
DATASETS=ID28C5_TEST,EXT25C_TEST \
MODELS=cnn_single,full \
SCHEME=fixed \
BINS=4.5,12.5,20.5,28.5,36.5,46.5 \
bash scripts/32_stage_error_bins.sh
```

Direct Python invocation remains available:
```bash
python analysis/stage_error_bins.py \
  --outroot runs/paper_eval_20260225_232506 \
  --datasets ID28C5_TEST,EXT25C_TEST \
  --models cnn_single,full \
  --scheme kimmel_start \
  --out_csv runs/paper_eval_20260225_232506/stage_error/stage_error_by_bin.csv
```

Output:
- `stage_error/stage_error_by_bin.csv`

Interpretation note:
- This is descriptive point-level stratification from `points.csv`; inferential claims should still remain embryo-level.
- By default, bins follow broad Kimmel periods and are indexed by nominal clip *start* time (`x_true`), not clip end time.
- Therefore the latest nominal time in the table is the latest available clip start (for the main benchmark, `46.5 hpf`), even though the last `L=24` windows still contain imagery extending to approximately `52.25 hpf`.

---

## Optional: T0 anchor sensitivity

This re-aggregates existing per-embryo inference JSONs under alternative `T0`
anchors without retraining, to quantify how anchored tempo summaries change when
the acquisition-defined start time is shifted.
It is already run by default inside `scripts/reproduce_all.sh` unless
`RUN_ANCHOR_SENSITIVITY=0`.

Preferred shell entrypoint:
```bash
bash scripts/33_anchor_sensitivity.sh \
  runs/paper_eval_20260225_232506 \
  runs/paper_eval_20260225_232506/anchor_sensitivity
```

Common overrides:
```bash
DATASETS=ID28C5_TEST,EXT25C_TEST \
MODELS=cnn_single,meanpool,nocons,full \
T0_LIST=4.0,4.5,5.0 \
bash scripts/33_anchor_sensitivity.sh
```

Direct Python summary remains available after aggregation:
```bash
python analysis/anchor_sensitivity.py \
  --outdir runs/paper_eval_20260225_232506/anchor_sensitivity \
  --datasets ID28C5_TEST,EXT25C_TEST \
  --models cnn_single,meanpool,nocons,full \
  --out_csv runs/paper_eval_20260225_232506/anchor_sensitivity/anchor_sensitivity_summary.csv
```

Output:
- `anchor_sensitivity/anchor_sensitivity_summary.csv`

Interpretation note:
- This is an analysis-time sensitivity study only; model weights are unchanged.
- In this project, `T0=4.5 hpf` is the acquisition-defined dataset start, not a claim that `4.5 hpf` is a uniquely optimal biological anchor for all datasets.

---

## Optional: Direct Stage-Dependent Tempo Analysis

This analysis directly tests whether the inferred tempo shift is uniform across
development or concentrated in specific windows.

Preferred shell entrypoint:
```bash
bash scripts/44_stage_tempo_dependence.sh \
  runs/paper_eval_20260225_232506 \
  runs/paper_eval_20260225_232506/stage_tempo
```

Common environment overrides:
```bash
DATASETS=ID28C5_TEST,EXT25C_TEST \
MODELS=cnn_single,meanpool,nocons,full \
N_BOOT=3000 \
SEED=42 \
bash scripts/44_stage_tempo_dependence.sh
```

Direct Python remains available:
```bash
python analysis/stage_tempo_dependence.py \
  --outroot runs/paper_eval_20260225_232506 \
  --datasets ID28C5_TEST,EXT25C_TEST \
  --models cnn_single,meanpool,nocons,full \
  --out_dir runs/paper_eval_20260225_232506/stage_tempo
```

Outputs:
- `stage_tempo/piecewise_stage_slopes.csv`
- `stage_tempo/local_slope_by_interval.csv`
- `stage_tempo/stage_delta_contrasts.csv`
- `stage_tempo/stage_tempo_full_summary.md`
- `stage_tempo/full_local_slope_by_interval.svg`

Interpretation:
- `stage_tempo_full_summary.md` and `full_local_slope_by_interval.svg` are only emitted when the requested run includes `MODEL=full` and both `ID28C5_TEST` and `EXT25C_TEST`. Subset runs still write the CSV outputs.
- `piecewise_stage_slopes.csv` is the primary inferential output for Comment 11: stagewise OLS slopes with embryo-bootstrap CIs.
- `local_slope_by_interval.csv` is a descriptive companion view only.
- The global anchored-fit summary remains the native ETF readout; stagewise slopes are used to test only modest stage dependence on top of that near-linear trend.

Notes:
- Stagewise piecewise slopes are fit by ordinary least squares within each
  Kimmel broad period.
- Uncertainty for the stagewise slopes is quantified by embryo-bootstrap
  resampling over `eid`, so the resulting 95% CIs respect embryo-level rather
  than window-level independence.
- The local interval-slope view remains descriptive and is intended as a
  consistency check rather than the primary inferential test.

---

## Optional: SmoothGrad saliency

SmoothGrad is **qualitative** and slower; it is not required for paper quantitative reproduction.

### Run within the full pipeline
```bash
RUN_SALIENCY=1 bash scripts/reproduce_all.sh
```

Choose model (default `full`):
```bash
RUN_SALIENCY=1 SALIENCY_MODEL=full bash scripts/reproduce_all.sh
```

Also supports: `nocons` / `meanpool` / `cnn_single`.

### What saliency does (implementation details)
When enabled, `scripts/reproduce_all.sh` calls:
- `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>`

This script:
- Selects the "best" embryo on `ID28C5_TEST/<model>/embryo.csv` by minimal `rmse_resid` (tie-breaker: `max_abs_resid`)
- Runs SmoothGrad saliency for **five clips** (starts: `0 / 42 / 84 / 126 / 168`) using `analysis/vis_clip_saliency.py`
- Writes outputs under: `runs/.../vis_best_<EID>_<MODEL>_smoothgrad_five/`
- Key output file: `saliency_time_overlay.png`

### Optional saliency visualization knobs (environment variables)
All optional; defaults shown:
- `SAL_AMP=0` — enable AMP during saliency (default off)
- `SAL_SG_N=20` — SmoothGrad samples
- `SAL_SG_SIGMA=0.01` — noise sigma
- `SAL_HM_LO=90` — heatmap low percentile
- `SAL_HM_HI=99.5` — heatmap high percentile
- `SAL_HM_GAMMA=0.55` — heatmap gamma
- `SAL_BLUR_K=9` — blur kernel size
- `SAL_ALPHA_THR=0.25` — overlay alpha threshold
- `SAL_ALPHA_MAX=0.98` — overlay alpha max

---

## Metrics notes (external 25C)

### In-distribution (28.5C)
Pointwise MAE/RMSE/R² over sliding windows can be interpreted as descriptive accuracy metrics.

### External domain (25C)
Under a temperature-induced tempo shift, the nominal mapping:
- `t(s) = T0 + DT*s`

(i.e., the "y=x" axis when plotting predicted vs nominal time) is **not** a ground-truth developmental clock at 25C.

Therefore:
- `MAE_vs_nominal` / `RMSE_vs_nominal` / `R2_vs_nominal` quantify **deviation from the nominal axis** and are reported for descriptive comparison only (not external-domain accuracy).

**Recommended primary external readouts (embryo-level):**
- `m_anchor` — anchored tempo slope (`m<1` indicates slowdown)
- `rmse_resid` — anchored-fit residual scatter (lower is more stable)
- `max_abs_resid` — worst-case outliers / long tails

### Optional start-time offset diagnostic (`t0_final`)
Per-embryo inference JSON also includes an intercept-like diagnostic:
- For each start `s`: `t0_hat(s) = t_hat(s) - DT*s`
- Aggregated as a trimmed mean (`trim=0.2`) to obtain `t0_final`

This is a **descriptive QC diagnostic** (e.g., effective time-zero uncertainty) and is not used for inferential comparisons.

---

## Optional: Training specification (EXP4; from checkpoint cfg)

Reproducing paper results does **not** require re-training (Option B uses released checkpoints).

Each released checkpoint (`*_best.pt`) stores the full training configuration under `ckpt["cfg"]`. Paper numbers correspond to the released checkpoints and their stored `cfg` (which may differ from CLI defaults).

### Shared EXP4 hyperparameters (from `cfg`)
The list below matches the released `EXP4_full` checkpoint cfg:

**Data / sampling**
- `clip_len=24`
- `img_size=384`
- `expect_t=192`
- `samples_per_embryo=32`
- `jitter=2`
- `cache_items=16`

**Optimization / schedule**
- `epochs=300`
- `batch_size=32`
- `val_batch_size=64`
- `num_workers=8`
- `lr=6e-4`
- `weight_decay=0.01`
- `warmup_ratio=0.01`
- `lr_min_ratio=0.05`
- `max_grad_norm=1.0`
- `grad_accum=1`
- `amp=true`

**Model (Transformer variants)**
- `model_dim=128`
- `model_depth=4`
- `model_heads=4`
- `model_mlp_ratio=2.0`
- `temporal_mode=transformer`
- `temporal_drop_p=0.05`
- `drop=0.1`
- `attn_drop=0.0`

**CNN frame encoder**
- `cnn_base=32`
- `cnn_expand=2`
- `cnn_se_reduction=4`

**Loss**
- `abs_loss_type=l1`
- `lambda_abs=1.0`
- `cons_ramp_ratio=0.2`
- `lambda_diff` — depends on ablation (see below)

**EMA**
- `ema_decay=0.99`
- `ema_eval=true`
- `ema_start_ratio=0.0`

**Repro / engineering**
- `seed=42`
- `mem_profile=lowmem`

Machine-specific fields (examples): `out_dir`, `proc_dir`, `split_json`.

### Ablation differences (verify per checkpoint cfg)
- `cnn_single`: `temporal_mode=identity`, `model_depth=0`, `temporal_drop_p=0.0`, `lambda_diff=0.0`
- `meanpool`: `temporal_mode=meanpool`, `model_depth=0`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `nocons`: `temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `full`: `temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=1.0`

### Print the exact cfg stored in a checkpoint
```bash
python3 -c "import torch,json; print(json.dumps(torch.load('path/to/best.pt',map_location='cpu')['cfg'],indent=2,sort_keys=True))"
```

---

## Optional: Option A (preprocess from raw OME-TIFF)

```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir /ABS/PATH/raw_ome_tiffs \
  --proc_dir /ABS/PATH/processed \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 \
  --p_hi 99 \
  --max_pages 0
```

**Preprocessing summary:**
- Percentile clip + normalize (default `p_lo=1`, `p_hi=99`)
- Resize to `384x384` (PIL bilinear)
- Pad/trim time axis to `192` frames
- Store one `.npy` per embryo

## Optional: Import S-BIAD840 Princeton PNG export

`S-BIAD840` is not laid out as one stack file per embryo. Instead, each time point
is a directory (`Dataset_C/<time_hpf>/`, `Dataset_D/<time_hpf>/`) containing 96
PNG frames, one per embryo. To make this external dataset compatible with the ETF
release pipeline, we first reassemble one time-ordered stack per embryo and then
apply the **same** ETF preprocessing steps (`p_lo=1`, `p_hi=99`, resize to
`384x384`, and optionally pad/trim toward release-style `192`-frame tensors).

For compatibility with the released checkpoints, the helper below aligns both
conditions to `4.5 hpf` before preprocessing. This means:

- `Dataset_C` (28.5C) drops the first 4 frames (`3.5 -> 4.25 hpf`)
- `Dataset_D` (25C) drops the first 8 frames (`2.5 -> 4.25 hpf`)
- both then keep `168` real frames (`4.5 -> 46.25 hpf`)

By default, this external-domain import **does not** pad to `192` frames. This
is intentional: ETF inference only requires `T >= clip_len`, so keeping the
native aligned length avoids injecting synthetic repeated-tail windows into a
cross-domain test set. If you explicitly want release-style fixed-length arrays,
set `PAD_TO_EXPECT=1`.

If you already downloaded a prepacked Princeton processed bundle
(`sbiad840_aligned_4p5.tar.gz` or equivalent), you do **not** need to rerun
`scripts/34_preprocess_sbiad840.sh`; simply extract that bundle into:

```text
./data/sbiad840_aligned_4p5
```

and proceed directly to inference / aggregation / summarization.

Run:

```bash
bash scripts/34_preprocess_sbiad840.sh
bash scripts/34_preprocess_sbiad840.sh ./data/sbiad840_aligned_4p5
```

Key environment overrides:

```bash
SBIAD840_SRC_ROOT=/ABS/PATH/TO/s-biad840/Files/Princeton_Data
SBIAD840_OUT_ROOT=./data/sbiad840_aligned_4p5
ALIGN_START_HPF=4.5
PAD_TO_EXPECT=0
LIMIT=0
```

Outputs:

- `processed_28C5_sbiad840/*.npy`
- `processed_25C_sbiad840/*.npy`
- `splits/28C5_sbiad840_test.json`
- `splits/25C_sbiad840_test.json`

External-domain evaluation on the processed Princeton set:

```bash
bash scripts/10_infer_all.sh runs/sbiad840_eval_20260311_4models
bash scripts/35_aggregate_sbiad840.sh runs/sbiad840_eval_20260311_4models
bash scripts/36_summarize_sbiad840.sh runs/sbiad840_eval_20260311_4models
```

Summary outputs:

- `runs/.../sbiad840_external_summary.csv`
- `runs/.../sbiad840_external_summary.md`

For a denser KimmelNet-style `cnn_single` external check:

```bash
bash scripts/37_infer_sbiad840_cnn_dense.sh runs/sbiad840_eval_dense_cnn_single
bash scripts/35_aggregate_sbiad840.sh runs/sbiad840_eval_dense_cnn_single
bash scripts/36_summarize_sbiad840.sh runs/sbiad840_eval_dense_cnn_single
bash scripts/38_compare_sbiad840_kimmelnet.sh \
  runs/sbiad840_eval_zero_shot \
  runs/sbiad840_eval_dense_cnn_single
```

Comparison outputs:

- `runs/.../sbiad840_vs_kimmelnet.csv`
- `runs/.../sbiad840_vs_kimmelnet.md`

## Optional: Low-shot S-BIAD840 fine-tuning

If zero-shot Princeton calibration is insufficient, the repository now supports
**fresh fine-tuning from released checkpoints** without inheriting optimizer or
scheduler state. This is intended for site-specific adaptation rather than
continuing the original Crick training run.

1. Create low-shot `28.5C` fine-tune splits from the external Princeton pool:

```bash
bash scripts/39_make_sbiad840_finetune_splits.sh
```

Default outputs:

- `data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft12_v12_seed42.json`
- `data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft24_v12_seed42.json`
- `data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_manifest_seed42.json`

By default, these correspond to:

- `12 train / 12 val / 72 test`
- `24 train / 12 val / 60 test`

2. Fine-tune from a released checkpoint with a stage-specific freeze policy:

```bash
bash scripts/41_finetune_sbiad840.sh
```

The helper automatically rebuilds the model architecture from the selected
checkpoint cfg (`cnn_base`, `model_dim`, `mem_profile`, etc.), so low-shot runs
stay checkpoint-compatible by default rather than silently falling back to the
generic train CLI defaults.

Key environment overrides:

```bash
MODEL=cnn_single
STAGE=head_only
SPLIT_JSON=./data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft12_v12_seed42.json
PROC_DIR=./data/sbiad840_aligned_4p5/processed_28C5_sbiad840
OUT_DIR=./runs/finetune_cnn_single_head_only
EPOCHS=30
LR=3e-4
```

Supported `STAGE` values:

- `head_only`: freeze the entire frame encoder and temporal module; keep only the final regression head trainable
- `proj_head`: same as `head_only`, but also unfreeze the frame projection layer (`frame_enc.proj`)
- `frame_tail1`: same as `head_only`, but also unfreeze the frame projection layer and the last CNN block
- `frame_tail2`: same as `head_only`, but also unfreeze the frame projection layer and the last two CNN blocks
- `temporal_last1`: freeze the frame encoder and temporal module first, then re-enable the final temporal block plus the transformer readout path (`cls_token` and `norm`)
- `temporal_last2`: same as `temporal_last1`, but re-enable the last two temporal blocks plus `cls_token` and `norm`
- `temporal_head`: freeze only the frame encoder; allow the full temporal stack plus the regression head to adapt
- `full_trainable`: no freezing; full low-shot fine-tuning

Notes:

- `frame_tail*` stages test whether adapting high-level frame semantics is already sufficient.
- `temporal_last*` / `temporal_head` are intended for models with an actual temporal stack (for example `full` and `nocons`).
- `analysis/run_sbiad840_finetune.py` now rejects `temporal_last*` / `temporal_head` for non-transformer checkpoints such as `cnn_single` and `meanpool`, instead of silently leaving the temporal blocks inactive.

Recommended order:

1. Start with `MODEL=cnn_single STAGE=head_only`
2. If calibration remains poor, try `MODEL=cnn_single STAGE=frame_tail1`
3. For the clip-based main model, then move to `MODEL=full STAGE=head_only`
4. Next test a localized temporal update such as `MODEL=full STAGE=temporal_last1`
5. Only move to broader updates (`frame_tail2`, `temporal_last2`, `temporal_head`, or `full_trainable`) if the lighter stages are insufficient

The Princeton `25C` subset is typically best kept as **external validation** in
the first round, so the initial fine-tune splits are generated only from
`SBIAD840_28C5_TEST`.

3. Summarize multiple zero-shot and fine-tuned Princeton runs into one table:

```bash
bash scripts/42_summarize_sbiad840_finetune.sh
```

Required environment overrides (example paths only):

```bash
CNN_RUN_DIR=./runs/finetune_cnn_single_ft12_frame_tail1_20260311_211714
CNN_EVAL28_OUTROOT=./runs/sbiad840_ft12_frame_tail1_eval
CNN_EVAL25_OUTROOT=./runs/sbiad840_ft12_25c_eval
FULL_RUN_DIR=./runs/finetune_full_ft12_temporal_last1_20260311_224924
FULL_EVAL28_OUTROOT=./runs/sbiad840_ft12_full_temporal_last1_eval
FULL_EVAL25_OUTROOT=./runs/sbiad840_ft12_25c_eval
bash scripts/42_summarize_sbiad840_finetune.sh
```

Notes:

- The dated run directories above are examples, not canonical required names.
- `42` is a thin wrapper around `analysis/run_sbiad840_finetune_summary.py`; experiment definitions are passed explicitly rather than hardcoded in shell.
- The held-out `28.5C` fine-tune comparison in the rebuttal package is based on the fine-tune split test subset (`28C5_sbiad840_ft12_v12_seed42.json`), whereas the `25C` evaluation remains on the full external test split.
- Override output locations with `OUT_DIR`, `OUT_CSV`, and `OUT_MD` if needed.

Default outputs:

- `runs/sbiad840_finetune_compare/sbiad840_finetune_compare.csv`
- `runs/sbiad840_finetune_compare/sbiad840_finetune_compare.md`

4. Evaluate a fine-tuned checkpoint on held-out Princeton `28.5C` / `25C`:

```bash
bash scripts/43_eval_sbiad840_finetuned.sh
```

Typical environment overrides:

```bash
FT_CKPT=./runs/finetune_full_ft12_temporal_last1_20260311_224924/best.pt
MODEL=full
OUTROOT=./runs/sbiad840_ft12_full_temporal_last1_eval
DATASETS=SBIAD840_28C5_TEST,SBIAD840_25C_TEST
PROC_28C5_SBIAD840=./data/sbiad840_aligned_4p5/processed_28C5_sbiad840
PROC_25C_SBIAD840=./data/sbiad840_aligned_4p5/processed_25C_sbiad840
SPLIT_28C5_SBIAD840=./data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft12_v12_seed42.json
SPLIT_25C_SBIAD840=./data/sbiad840_aligned_4p5/splits/25C_sbiad840_test.json
bash scripts/43_eval_sbiad840_finetuned.sh
```

Notes:

- `43` is a thin wrapper around `analysis/eval_sbiad840_finetuned.py`.
- `FT_CKPT` is required for this workflow. The fine-tuned evaluator no longer falls back to the released `CKPT_*` zero-shot checkpoints.
- Dataset paths can be passed explicitly as above or resolved from `.env` by the Python helper.
- `FORCE_INFER=1` is the default and is recommended when reusing an existing `OUTROOT`, because it avoids silently re-aggregating stale per-embryo JSON from an older checkpoint or inference configuration. Set `FORCE_INFER=0` only when you explicitly want to reuse the existing JSON cache.
- Use the fine-tune split JSON for `SPLIT_28C5_SBIAD840` if you want the held-out `28.5C` numbers to match the rebuttal tables; use `28C5_sbiad840_test.json` only when evaluating on the full Princeton `28.5C` pool.
- Default outputs are:
  - `<OUTROOT>/SBIAD840_*/<MODEL>/{json,points.csv,embryo.csv,summary.json}`
  - `<OUTROOT>/sbiad840_external_summary.csv`
  - `<OUTROOT>/sbiad840_external_summary.md`
- Native ETF metrics in these outputs are `m_anchor`, `rmse_resid`, and `max_abs_resid`; auxiliary comparison-only metrics are `m_origin`, through-origin residuals, and through-origin line-fit `R2`.

Princeton script matrix:

| Script | Purpose | Required inputs | Default outputs |
|---|---|---|---|
| `38_compare_sbiad840_kimmelnet.sh <BASE_OUTROOT> <DENSE_OUTROOT>` | compare ETF Princeton results against KimmelNet Table 1/2 using through-origin `y = mx` quantities | summarized zero-shot outroot; summarized dense `cnn_single` outroot | `<BASE_OUTROOT>/sbiad840_vs_kimmelnet.{csv,md}` |
| `42_summarize_sbiad840_finetune.sh [OUT_DIR]` | summarize multiple Princeton fine-tune runs into one comparison table | `CNN_RUN_DIR`, `CNN_EVAL28_OUTROOT`, `CNN_EVAL25_OUTROOT`, `FULL_RUN_DIR`, `FULL_EVAL28_OUTROOT`, `FULL_EVAL25_OUTROOT` | `<OUT_DIR>/sbiad840_finetune_compare.{csv,md}` |
| `43_eval_sbiad840_finetuned.sh [OUTROOT]` | evaluate one fine-tuned checkpoint on held-out Princeton datasets | `FT_CKPT`, `MODEL`; optional explicit Princeton proc/split paths; optional `FORCE_INFER={0,1}` | `<OUTROOT>/SBIAD840_*/<MODEL>/{json,points.csv,embryo.csv,summary.json}`, plus `<OUTROOT>/sbiad840_external_summary.{csv,md}` |
| `44_stage_tempo_dependence.sh [OUTROOT] [OUT_DIR]` | stage-dependent tempo analysis with embryo-bootstrap stagewise slopes | aggregated ETF outroot; optional dataset/model/bootstrap overrides | `<OUT_DIR>/piecewise_stage_slopes.csv`, `local_slope_by_interval.csv`, `stage_delta_contrasts.csv`; the ETF-full markdown/svg companions are emitted only when `models` include `full` and `datasets` include both `ID28C5_TEST` and `EXT25C_TEST` |

---

## ETF CLI quick reference

```bash
python3 src/EmbryoTempoFormer.py -h
python3 src/EmbryoTempoFormer.py preprocess -h
python3 src/EmbryoTempoFormer.py make_split -h
python3 src/EmbryoTempoFormer.py train -h
python3 src/EmbryoTempoFormer.py eval -h
python3 src/EmbryoTempoFormer.py infer -h
```

---

## Representative Hardware / Runtime

The released checkpoints are sufficient for paper reproduction; retraining is
not required for the main ETF results. For practical accessibility, the table
below reports representative single-machine runs used in this revision.

Original released checkpoint training was performed under a substantially
heavier setup than the single-GPU examples below:

| Context | Hardware / memory profile |
|---|---|
| Original released checkpoint training | `4 × RTX 3090` with DDP; the released checkpoints themselves were trained under `mem_profile=lowmem`, and in the original runs per-GPU memory usage was typically around `13-15 GB`; higher-memory profiles were not practical at the original batch/clip settings |
| Princeton inference / low-shot adaptation reported in this revision | single `RTX 4060 Laptop GPU` (`8188 MiB`) using `AMP=1` and `mem_profile=lowmem` |

| Task | Representative configuration | Runtime | Peak GPU memory |
|---|---|---:|---:|
| Princeton zero-shot external inference | `2` datasets × `4` models × `96` embryos = `768` embryo-model jobs | `50.5 min` total (`3.95 s/job`) | single-GPU inference on `RTX 4060 Laptop (8188 MiB)` |
| Low-shot fine-tuning: `cnn_single + ft12 + frame_tail1` | `batch_size=32`, `val_batch_size=64`, `clip_len=24`, `AMP=1`, `mem_profile=lowmem` | `73.7 s/epoch` | `3.66 GB` |
| Low-shot fine-tuning: `full + ft12 + temporal_last1` | `batch_size=16`, `val_batch_size=32`, `clip_len=24`, `AMP=1`, `mem_profile=lowmem` | `135.7 s/epoch` | `5.15 GB` |

Representative hardware used for the above measurements:

- GPU: `NVIDIA GeForce RTX 4060 Laptop GPU` (`8188 MiB`)
- CPU: `13th Gen Intel Core i7-13650HX` (`20` logical CPUs; `10` cores / `20` threads)
- RAM: `15 GiB`

`lowmem` is not a vague label; in code it specifically changes the memory
profile from the default balanced path as follows:

| Setting | `balanced` | `lowmem` | Effect |
|---|---:|---:|---|
| `frame_chunk` | `8` | `4` | fewer frames encoded per CNN call |
| `ckpt_frame` | `False` | `True` | checkpoint the **whole frame encoder per chunk** |
| `ckpt_cnn` | `True` | `False` | rely on whole-frame checkpointing rather than additional intra-CNN checkpoint segmentation |
| `ckpt_segments` | `2` | `1` | simplified low-memory checkpoint path |

Under the same `full + temporal_last1` low-shot fine-tuning setup, the memory
profiles behaved as follows on the `RTX 4060 Laptop GPU`:

| Memory profile | Runtime / epoch | Peak GPU memory | Practical note |
|---|---:|---:|---|
| `ultra` | `142.9 s` | `2.31 GB` | lowest memory, most aggressive compute-for-memory tradeoff |
| `lowmem` | `145.5 s` | `5.12 GB` | practical compromise; this is the released training profile |
| `balanced` | `251.7 s` | `8.80 GB` | nearly saturates an `8 GB`-class laptop GPU |
| `fast` | no completed representative epoch on the `8 GB` laptop probe | effectively at/near device limit | not practical on this class of hardware for the matched configuration |

These values are intended as concrete reference points rather than strict
requirements; exact timings will vary across hardware, storage, and software
stacks.

---

## Troubleshooting

- **Windows:** workflow scripts are `bash` scripts; use WSL (recommended) or Linux/macOS.
- **`bash: command not found`:** run inside a bash shell.
- **`sha256sum: command not found` (macOS):** install coreutils (`brew install coreutils`) or skip verification.
- **Import/module errors:** ensure dependencies installed (`pip install -r requirements.txt`).
- **PyTorch GPU/CUDA:** `pip install -r requirements.txt` typically installs CPU build; for GPU, follow official PyTorch instructions for your platform.
- **GPU/CUDA numeric variability:** exact determinism not guaranteed across hardware/software stacks.
- **`RUNS_DIR` confusion:** keep `RUNS_DIR=./runs` unless you intentionally want outputs elsewhere; `scripts/reproduce_all.sh` now passes the chosen `OUTROOT` through Python orchestration rather than scanning `./runs/paper_eval_*`.
- **Out-of-memory (OOM) during training:** paper reproduction does not require training; if training needed, use `mem_profile=lowmem` as in released checkpoints.

---

## License

MIT (see LICENSE).

</details>

---

<details>
<summary>中文（点击展开/收起）</summary>

## 目录
- 快速开始（Option B，推荐）
- 你应该看到哪些输出
- 可选：SmoothGrad 热图
- 指标说明（外域 25C）
- 可选：训练规格（EXP4；以 checkpoint cfg 为准）
- 可选：Option A（从原始 OME-TIFF 预处理）
- ETF CLI 速查
- 代表性硬件 / 耗时
- 常见问题
- 许可证

---

## 快速开始（Option B，推荐）

**目标：**使用 Zenodo 发布包复现论文定量结果与图表（**无需重新训练**）。

### 环境要求
- **bash** 环境（Linux / macOS / WSL）
- Python 3.9+
- `pip`（或 conda）

### Step 1 — 下载并解压数据包

用于主论文复现，下载：
- `embryo-tempoformer_release_v1_full.tar.gz`
  https://doi.org/10.5281/zenodo.18318139

解压：
```bash
tar -xzf embryo-tempoformer_release_v1_full.tar.gz
```

目录结构：
```text
embryo-tempoformer_release_v1/
├── processed_28C5/
├── processed_25C/
├── splits/
├── checkpoints/
│   ├── cnn_single_best.pt
│   ├── meanpool_best.pt
│   ├── nocons_best.pt
│   └── full_best.pt
├── MANIFEST.json
└── SHA256SUMS.txt
```

如果你还希望复现 Princeton 外部域分析（`Comment 8`），则把可选的
Princeton 处理后数据包也解压到**仓库内部**，使其目录结构变成：

- `sbiad840_aligned_4p5.tar.gz`
  https://doi.org/10.5281/zenodo.18979476

```text
s-biad531-embryo-tempoformer/
└── data/
    └── sbiad840_aligned_4p5/
        ├── processed_28C5_sbiad840/
        ├── processed_25C_sbiad840/
        └── splits/
```

例如，在仓库根目录执行：

```bash
mkdir -p data
tar -xzf sbiad840_aligned_4p5.tar.gz -C data
```

第二个包**不是**主论文复现所必需的；只有当你要运行 Princeton
跨站点评估和低样本站点微调时才需要。

（可选）校验：
```bash
cd embryo-tempoformer_release_v1
sha256sum -c SHA256SUMS.txt
cd ..
```

### Step 2 — 克隆仓库并安装依赖

**选项 2A: 使用 Docker (最省心，无需 clone 代码)**
你可以完全跳过 Python 和 CUDA 的复杂安装：
1. 拉取打包好的 Docker 镜像：
```bash
docker pull lijiayudeng/embryo-tempoformer:latest
```
2. 启动交互式容器，并使用 `-v` 将你解压好的 Zenodo 数据挂载到容器内的 `/data` 目录：
```bash
# 请将 /path/to/embryo-tempoformer_release_v1 替换为你实际的绝对路径
docker run -it -v /path/to/embryo-tempoformer_release_v1:/data lijiayudeng/embryo-tempoformer:latest /bin/bash
```
3. 进入容器后（你将位于 `/app` 目录），请直接跳至 **Step 3** 继续。在配置 `.env` 文件时，请将所有绝对路径都指向 `/data/...`。同时**务必设置 `RUNS_DIR=/data/runs`**，这样跑出来的图表和结果才能保存回你自己的电脑上！

**选项 2B: 本地 pip 安装**
```bash
git clone https://github.com/LijiayuDeng/s-biad531-embryo-tempoformer.git
cd s-biad531-embryo-tempoformer
pip install -r requirements.txt
```

（可选）conda：
```bash
conda env create -f environment.yml
conda activate embryo-tempoformer
```

### Step 3 — 配置 `.env`
生成本地 `.env`：
```bash
cp .env.example .env
```

打开 `.env`，把 `/ABS/PATH/TO` 替换为你的实际绝对路径：

**必需变量（`scripts/00_check_env.sh` 会检查）：**
```text
PROC_28C5=/ABS/PATH/TO/embryo-tempoformer_release_v1/processed_28C5
PROC_25C=/ABS/PATH/TO/embryo-tempoformer_release_v1/processed_25C
SPLIT_28C5=/ABS/PATH/TO/embryo-tempoformer_release_v1/splits/28C5.json
SPLIT_25C=/ABS/PATH/TO/embryo-tempoformer_release_v1/splits/25C.json

CKPT_CNN_SINGLE=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/cnn_single_best.pt
CKPT_MEANPOOL=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/meanpool_best.pt
CKPT_NOCONS=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/nocons_best.pt
CKPT_FULL=/ABS/PATH/TO/embryo-tempoformer_release_v1/checkpoints/full_best.pt
```

**可选运行参数（建议保持默认）：**
```text
# 外部域 processed npy 和 split（两种来源都可以：
# 1) 运行 scripts/34_preprocess_sbiad840.sh 生成；
# 2) 直接解压可选的 sbiad840_aligned_4p5 数据包到 ./data/）
PROC_28C5_SBIAD840=./data/sbiad840_aligned_4p5/processed_28C5_sbiad840
PROC_25C_SBIAD840=./data/sbiad840_aligned_4p5/processed_25C_sbiad840
SPLIT_28C5_SBIAD840=./data/sbiad840_aligned_4p5/splits/28C5_sbiad840_test.json
SPLIT_25C_SBIAD840=./data/sbiad840_aligned_4p5/splits/25C_sbiad840_test.json

# 输出根目录
# 重要：保持 RUNS_DIR=./runs，因为 scripts/reproduce_all.sh 假定使用 ./runs
RUNS_DIR=./runs

# shell 入口脚本可选的解释器覆盖。
# 如果当前 shell 里没有显式设置 PYTHON_BIN，scripts/* 会先从 .env 读取它，
# 再继续加载其余环境变量。
PYTHON_BIN=python3

# 聚合脚本使用的时间轴常数
DT_H=0.25
T0_HPF=4.5

# 推理滑窗/预处理假设（必须与 processed 数组及 checkpoint 一致）
CLIP_LEN=24
IMG_SIZE=384
EXPECT_T=192
STRIDE=8

# 推理运行参数
DEVICE=auto
AMP=1
USE_EMA=1
BATCH_SIZE=64
```

### Step 4 — 检查环境与路径
```bash
bash scripts/00_check_env.sh
```

### Step 5 — 一键复现（推理 → 汇总 → CI/power → 作图）
```bash
bash scripts/reproduce_all.sh
```

**脚本执行顺序：**
1. `scripts/00_check_env.sh` — 检查 `.env` 必需变量与路径
2. `scripts/10_infer_all.sh` — 对 4 个模型（`cnn_single`, `meanpool`, `nocons`, `full`）在 2 个测试集（`ID28C5_TEST`, `EXT25C_TEST`）上运行推理；输出 per-embryo JSON 到 `.../<TAG>/<model>/json/*.json`；写入 `OUTROOT/OUTROOT.txt`
3. `scripts/20_aggregate_all.sh <OUTROOT>` — 聚合 JSON 为 `points.csv`, `embryo.csv`, `summary.json`
4. `scripts/30_ci_power_all.sh <OUTROOT>` — 计算胚胎 bootstrap CI 与 power 曲线
5. `scripts/31_power_curve_continuous.sh <OUTROOT> <OUTROOT>/continuous_power` — 连续效应量规划曲线（`E80/E90/E95`）
6. `scripts/11_cliplen_sensitivity.sh <OUTROOT>/cliplen_sensitivity` — 固定 checkpoint 的 clip 长度敏感性
7. `scripts/12_cliplen_context_fit.sh <OUTROOT> <OUTROOT>/cliplen_sensitivity <OUTROOT>/cliplen_sensitivity/context_fit` — `0h/1h/3h/6h` context ladder 与 ETF-full 描述性拟合
8. `scripts/32_stage_error_bins.sh <OUTROOT> <OUTROOT>/stage_error/stage_error_by_bin.csv` — 分期误差汇总
9. `scripts/33_anchor_sensitivity.sh <OUTROOT> <OUTROOT>/anchor_sensitivity` — T0 锚点敏感性汇总
10. `scripts/44_stage_tempo_dependence.sh <OUTROOT> <OUTROOT>/stage_tempo` — 直接的阶段依赖 tempo 分析（分段斜率 + 局部导数）
11. `scripts/40_make_figures.sh <OUTROOT>` — 生成论文图（PNG + PDF）
12. （可选）若 `RUN_SALIENCY=1`，运行 `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>`

输出根目录（OUTROOT）：
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

说明：
- `scripts/reproduce_all.sh` 现在只是 `analysis/run_reproduction_pipeline.py` 的薄包装层
- 流程分支、可选分析开关和 OUTROOT 传递已经收敛到 Python 侧

`reproduce_all.sh` 默认会启用的可选分析：
- `RUN_CONTINUOUS_POWER=1`
- `RUN_CLIPLEN_SENSITIVITY=1`
- `RUN_STAGE_ERROR_BINS=1`
- `RUN_ANCHOR_SENSITIVITY=1`
- `RUN_SALIENCY=0`

如需跳过本轮修回新增分析：
```bash
RUN_CONTINUOUS_POWER=0 RUN_CLIPLEN_SENSITIVITY=0 RUN_STAGE_ERROR_BINS=0 RUN_ANCHOR_SENSITIVITY=0 bash scripts/reproduce_all.sh
```

---

## 你应该看到哪些输出

在 `runs/paper_eval_YYYYMMDD_HHMMSS/` 下：

**按胚胎推理输出**
- `ID28C5_TEST/<model>/json/*.json` — 每胚胎一个推理 JSON
- `EXT25C_TEST/<model>/json/*.json` — 外域（25C）每胚胎推理 JSON

**聚合表与汇总**
- `ID28C5_TEST/<model>/points.csv` — 点级（每滑动窗口）预测
- `ID28C5_TEST/<model>/embryo.csv` — 胚胎级聚合指标
- `ID28C5_TEST/<model>/summary.json` — 汇总统计
- `EXT25C_TEST/<model>/points.csv` — 外域点级
- `EXT25C_TEST/<model>/embryo.csv` — 外域胚胎级
- `EXT25C_TEST/<model>/summary.json` — 外域汇总

**不确定性与样本效率**
- `CI_<model>_m_anchor.json` — delta-m 的胚胎 bootstrap 95% 置信区间（由 `embryo.csv` 计算）
- `power_<model>_m_anchor.csv` — power 曲线数据
- `power_<model>_m_anchor.png` — power 曲线图
- `continuous_power/continuous_power_by_model.csv` — 连续效应量功效面（可选）
- `continuous_power/continuous_thresholds_by_model.csv` — `|delta m|` 上的 E80/E90/E95 阈值曲线（可选）
- `continuous_power/continuous_E80_by_model.svg` — 全模型 E80 曲线（可选）
- `continuous_power/continuous_full_E80_E90_E95.svg` — `full` 模型 E80/E90/E95 曲线（可选）
- `cliplen_sensitivity/cliplen_summary.csv` — 固定 checkpoint 的 clip 长度敏感性汇总（可选）
- `cliplen_sensitivity/context_fit/context_ladder.csv` — `0h/1h/3h/6h` context ladder 汇总（可选）
- `cliplen_sensitivity/context_fit/full_context_fit.csv` — ETF-full 在 `1/3/6h` 上的描述性直线拟合（可选）
- `stage_error/stage_error_by_bin.csv` — 按 Kimmel 分期的点级误差汇总（可选）
- `anchor_sensitivity/anchor_sensitivity_summary.csv` — T0 锚点敏感性汇总（可选）
- `stage_tempo/piecewise_stage_slopes.csv` — Kimmel 分期下的分段 tempo 斜率（可选）
- `stage_tempo/local_slope_by_interval.csv` — 基于平均轨迹的局部 interval slope（可选）
- `stage_tempo/stage_tempo_full_summary.md` — ETF-full 的阶段依赖摘要表（可选）
- `stage_tempo/full_local_slope_by_interval.svg` — ETF-full 的局部斜率图（可选）

**论文图**
- `figures_jobs/` — 论文图（PNG + PDF）

**元信息**
- `OUTROOT.txt` — 记录 OUTROOT 路径（由 `scripts/10_infer_all.sh` 写入）

模型（`<model>`）：`cnn_single`, `meanpool`, `nocons`, `full`。

Thin-shell 说明：
- `scripts/` 下的 shell 入口只负责环境加载、默认参数和一键编排
- 如果当前 shell 里没有显式设置 `PYTHON_BIN`，这些 wrapper 会先从 `.env` 启动它，再加载其余环境变量
- dataset/model 矩阵遍历、胚胎级调度、环境检查、aggregation、CI/power 批处理、以及顶层 pipeline 分支控制已经收敛到 Python：
  - `analysis/check_env.py`
  - `analysis/run_infer_matrix.py`
  - `analysis/aggregate_matrix.py`
  - `analysis/run_ci_power_matrix.py`
  - `analysis/run_cliplen_sensitivity.py`
  - `analysis/select_best_embryo.py`
  - `analysis/run_reproduction_pipeline.py`

`scripts/10_infer_all.sh` 常用覆盖参数：
```bash
OUTROOT=./runs/paper_eval_manual \
DATASETS=ID28C5_TEST \
MODELS=full \
FORCE=1 \
bash scripts/10_infer_all.sh
```

说明：
- `FORCE=1` 会原地重跑本次请求范围内的 per-embryo JSON。只有当你明确想复用同一个 `OUTROOT` 下已有 JSON 时，才保留 `FORCE=0`。

---

## 可选：Clip 长度敏感性与 context ladder

这个分析回答的问题和 power curve 不同：
- 保持底层采样间隔固定为 `15 min`
- 只改变推理时使用的 clip 长度（默认 `L=4/12/24`）
- 把结果整理成 `0h`（`cnn_single`）对比 `1h/3h/6h`（`ETF-full`）的 context ladder

默认情况下，这个分析也会在 `scripts/reproduce_all.sh` 中运行，除非设置 `RUN_CLIPLEN_SENSITIVITY=0`。

### Step 1：运行固定 checkpoint 的 clip-length sensitivity
推荐 shell 入口：
```bash
bash scripts/11_cliplen_sensitivity.sh
```

写到固定目录：
```bash
bash scripts/11_cliplen_sensitivity.sh runs/cliplen_sensitivity_main
```

常用覆盖参数：
```bash
DATASETS=ID28C5_TEST,EXT25C_TEST \
MODELS=full \
CLIP_LENS=4,12,24 \
FORCE=1 \
bash scripts/11_cliplen_sensitivity.sh
```

说明：
- `FORCE=1` 会同时重跑推理和聚合；当 `FORCE=0` 时，如果已有 JSON 和 summary 与当前请求兼容，脚本会复用已有结果。

主要输出：
- `<OUTROOT>/cliplen_summary.csv`
- `<OUTROOT>/L04/...`、`<OUTROOT>/L12/...`、`<OUTROOT>/L24/...`

### Step 2：整理成紧凑的 `0h/1h/3h/6h` context ladder
推荐 shell 入口：
```bash
bash scripts/12_cliplen_context_fit.sh \
  runs/paper_eval_20260225_232506 \
  runs/cliplen_sensitivity_20260311_030252
```

也可以直接调用 Python：
```bash
python analysis/cliplen_context_fit.py \
  --main_outroot runs/paper_eval_20260225_232506 \
  --cliplen_csv runs/cliplen_sensitivity_20260311_030252/cliplen_summary.csv \
  --out_dir runs/cliplen_sensitivity_20260311_030252/context_fit
```

输出：
- `context_fit/context_ladder.csv`
- `context_fit/full_context_fit.csv`

---

## 可选：直接的阶段依赖 Tempo 分析

这个分析直接回答：温度导致的 tempo 变化是否在发育过程中近似均匀，还是集中在某些阶段窗口。

推荐的 shell 入口：
```bash
bash scripts/44_stage_tempo_dependence.sh \
  runs/paper_eval_20260225_232506 \
  runs/paper_eval_20260225_232506/stage_tempo
```

常用环境变量：
```bash
DATASETS=ID28C5_TEST,EXT25C_TEST \
MODELS=cnn_single,meanpool,nocons,full \
N_BOOT=3000 \
SEED=42 \
bash scripts/44_stage_tempo_dependence.sh
```

也可以直接运行 Python：
```bash
python analysis/stage_tempo_dependence.py \
  --outroot runs/paper_eval_20260225_232506 \
  --datasets ID28C5_TEST,EXT25C_TEST \
  --models cnn_single,meanpool,nocons,full \
  --out_dir runs/paper_eval_20260225_232506/stage_tempo
```

输出：
- `stage_tempo/piecewise_stage_slopes.csv`
- `stage_tempo/local_slope_by_interval.csv`
- `stage_tempo/stage_delta_contrasts.csv`
- `stage_tempo/stage_tempo_full_summary.md`
- `stage_tempo/full_local_slope_by_interval.svg`

说明：
- 如果 `--models` 不包含 `full`，或者 `--datasets` 没有同时包含 `ID28C5_TEST` 和 `EXT25C_TEST`，脚本仍会正常写出 CSV，但会跳过 `ETF-full` 专用的 markdown 摘要和 SVG 图。
- `piecewise_stage_slopes.csv` 按 Kimmel broad periods（blastula / gastrula / segmentation / pharyngula）分别拟合局部线性斜率。
- 这些分段斜率的 95% CI 是按 embryo (`eid`) 做 bootstrap 得到的，因此遵循 embryo-level 而不是 window-level 独立性。
- `stage_delta_contrasts.csv` 给出不同阶段 slowdown 强度之间的 bootstrap 对比。
- `local_slope_by_interval.csv` 则按相邻 `2 h` nominal 区间计算局部导数风格的斜率。
- 我们在回复信中主要使用 `ETF-full` 的分段斜率 + embryo-bootstrap CI 来回答 Comment 11，并用局部 interval slope 作为描述性一致性检查。
- ETF 的主叙事仍然是“全局锚定近线性”，阶段分析只是检验是否存在温和的 stage dependence。

## 可选：SmoothGrad 热图

SmoothGrad 属于**定性**分析，耗时较长；论文定量复现不需要。

### 在全流程中启用
```bash
RUN_SALIENCY=1 bash scripts/reproduce_all.sh
```

指定模型（默认 `full`）：
```bash
RUN_SALIENCY=1 SALIENCY_MODEL=full bash scripts/reproduce_all.sh
```

也支持：`nocons` / `meanpool` / `cnn_single`。

### 热图做了什么（实现细节）
启用后，`scripts/reproduce_all.sh` 会调用：
- `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>`

该脚本会：
- 在 `ID28C5_TEST/<model>/embryo.csv` 中按最小 `rmse_resid` 选择 "best" 胚胎（tie-breaker：`max_abs_resid`）
- 对**五段 clip**（starts：`0 / 42 / 84 / 126 / 168`）运行 SmoothGrad（`analysis/vis_clip_saliency.py`）
- 输出到：`runs/.../vis_best_<EID>_<MODEL>_smoothgrad_five/`
- 关键输出文件：`saliency_time_overlay.png`

### 可选可视化参数（环境变量）
均为可选；括号内为默认值：
- `SAL_AMP=0` — saliency 使用 AMP（默认关闭）
- `SAL_SG_N=20` — SmoothGrad 采样数
- `SAL_SG_SIGMA=0.01` — 噪声 sigma
- `SAL_HM_LO=90` — 热图低分位数
- `SAL_HM_HI=99.5` — 热图高分位数
- `SAL_HM_GAMMA=0.55` — 热图 gamma
- `SAL_BLUR_K=9` — 模糊核大小
- `SAL_ALPHA_THR=0.25` — 叠加透明度阈值
- `SAL_ALPHA_MAX=0.98` — 叠加透明度最大值

---

## 指标说明（外域 25C）

### ID（28.5C）
滑动窗口点级 MAE/RMSE/R² 可作为描述性准确度指标。

### 外域（25C）
温度变化会改变发育 tempo，此时名义映射：
- `t(s) = T0 + DT*s`

（即预测与名义时间对比时的 "y=x" 轴）**不再是 25C 的真实发育时钟**。

因此：
- `MAE_vs_nominal` / `RMSE_vs_nominal` / `R2_vs_nominal` 衡量的是**相对名义轴的偏离**，仅作描述性比较（不是外域 accuracy）。

**外域建议优先报告（胚胎级）：**
- `m_anchor` — anchored tempo 斜率（`m<1` 表示变慢）
- `rmse_resid` — anchored 拟合残差散布（越小越稳定）
- `max_abs_resid` — 最坏离群/长尾

### 可选：起始时间偏置诊断（`t0_final`）
每胚胎推理 JSON 还包含一个截距型诊断：
- 对每个 start `s`：`t0_hat(s) = t_hat(s) - DT*s`
- 对其做 trimmed mean（`trim=0.2`）得到 `t0_final`

该量为**描述性 QC 诊断**（如有效 time-zero 不确定性），不用于推断比较。

---

## 可选：训练规格（EXP4；以 checkpoint cfg 为准）

论文复现**不需要重新训练**（Option B 直接使用发布的 checkpoints 推理）。

每个发布 checkpoint（`*_best.pt`）都在 `ckpt["cfg"]` 中保存完整训练配置。论文数值以发布 checkpoint 的 `cfg` 为准（可能与 CLI 默认值不同）。

### EXP4 共享超参（来自 `cfg`）
下列参数与发布的 `EXP4_full` checkpoint cfg 一致：

**数据/采样**
- `clip_len=24`
- `img_size=384`
- `expect_t=192`
- `samples_per_embryo=32`
- `jitter=2`
- `cache_items=16`

**优化/调度**
- `epochs=300`
- `batch_size=32`
- `val_batch_size=64`
- `num_workers=8`
- `lr=6e-4`
- `weight_decay=0.01`
- `warmup_ratio=0.01`
- `lr_min_ratio=0.05`
- `max_grad_norm=1.0`
- `grad_accum=1`
- `amp=true`

**模型（Transformer 变体）**
- `model_dim=128`
- `model_depth=4`
- `model_heads=4`
- `model_mlp_ratio=2.0`
- `temporal_mode=transformer`
- `temporal_drop_p=0.05`
- `drop=0.1`
- `attn_drop=0.0`

**CNN 帧编码器**
- `cnn_base=32`
- `cnn_expand=2`
- `cnn_se_reduction=4`

**损失**
- `abs_loss_type=l1`
- `lambda_abs=1.0`
- `cons_ramp_ratio=0.2`
- `lambda_diff` — 随消融而变化（见下）

**EMA**
- `ema_decay=0.99`
- `ema_eval=true`
- `ema_start_ratio=0.0`

**复现/工程**
- `seed=42`
- `mem_profile=lowmem`

机器相关字段（示例）：`out_dir`, `proc_dir`, `split_json`。

### 消融差异（建议分别以各自 checkpoint cfg 核对）
- `cnn_single`：`temporal_mode=identity`, `model_depth=0`, `temporal_drop_p=0.0`, `lambda_diff=0.0`
- `meanpool`：`temporal_mode=meanpool`, `model_depth=0`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `nocons`：`temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `full`：`temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=1.0`

### 打印 checkpoint 内保存的 cfg
```bash
python3 -c "import torch,json; print(json.dumps(torch.load('path/to/best.pt',map_location='cpu')['cfg'],indent=2,sort_keys=True))"
```

---

## 可选：Option A（从原始 OME-TIFF 预处理）

```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir /ABS/PATH/raw_ome_tiffs \
  --proc_dir /ABS/PATH/processed \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 \
  --p_hi 99 \
  --max_pages 0
```

**预处理概要：**
- 分位数裁剪 + 归一化（默认 `p_lo=1`, `p_hi=99`）
- resize 到 `384x384`（PIL 双线性）
- 时间维 pad/trim 到 `192` 帧
- 每胚胎保存一个 `.npy`

---

## 可选：导入 S-BIAD840 Princeton PNG 导出

`S-BIAD840` 不是“一胚胎一个堆栈文件”的结构，而是每个时间点一个目录
（`Dataset_C/<time_hpf>/`、`Dataset_D/<time_hpf>/`），每个目录下有 96 张
PNG，各自对应一个胚胎。为了让这批外部数据可直接接入 ETF 流程，我们先按
胚胎重组时间序列，再应用与发布版一致的预处理参数：`p_lo=1`、`p_hi=99`、
resize 到 `384x384`，并可选地再做 release 风格的固定长度时间轴处理。

为了与发布 checkpoint 的时间语义对齐，辅助脚本会先把两种条件都对齐到
`4.5 hpf`：

- `Dataset_C`（28.5C）丢弃最前 4 帧（`3.5 -> 4.25 hpf`）
- `Dataset_D`（25C）丢弃最前 8 帧（`2.5 -> 4.25 hpf`）
- 两者随后都保留 `168` 个真实帧（`4.5 -> 46.25 hpf`）

默认 **不会** 补到 `192` 帧；这是刻意的，因为 ETF 推理只要求 `T >= clip_len`，
保留原生 `168` 帧可以避免在外部域测试里注入尾部重复帧。如果确实需要和发布
版完全一致的固定长度数组，再显式设置 `PAD_TO_EXPECT=1`。

如果你已经拿到打包好的 Princeton 处理后数据（例如
`sbiad840_aligned_4p5.tar.gz`），则**不需要**再运行
`scripts/34_preprocess_sbiad840.sh`；只需把它解压到：

```text
./data/sbiad840_aligned_4p5
```

然后直接进入 inference / aggregation / summarization 步骤。

运行：

```bash
bash scripts/34_preprocess_sbiad840.sh
bash scripts/34_preprocess_sbiad840.sh ./data/sbiad840_aligned_4p5
```

常用环境变量：

```bash
SBIAD840_SRC_ROOT=/ABS/PATH/TO/s-biad840/Files/Princeton_Data
SBIAD840_OUT_ROOT=./data/sbiad840_aligned_4p5
ALIGN_START_HPF=4.5
PAD_TO_EXPECT=0
LIMIT=0
```

输出：

- `processed_28C5_sbiad840/*.npy`
- `processed_25C_sbiad840/*.npy`
- `splits/28C5_sbiad840_test.json`
- `splits/25C_sbiad840_test.json`

处理完成后，可直接做外部域评估：

```bash
bash scripts/10_infer_all.sh runs/sbiad840_eval_20260311_4models
bash scripts/35_aggregate_sbiad840.sh runs/sbiad840_eval_20260311_4models
bash scripts/36_summarize_sbiad840.sh runs/sbiad840_eval_20260311_4models
```

汇总输出：

- `runs/.../sbiad840_external_summary.csv`
- `runs/.../sbiad840_external_summary.md`

如果要补一个更接近 KimmelNet 论文口径的 `cnn_single` 密集单帧对照：

```bash
bash scripts/37_infer_sbiad840_cnn_dense.sh runs/sbiad840_eval_dense_cnn_single
bash scripts/35_aggregate_sbiad840.sh runs/sbiad840_eval_dense_cnn_single
bash scripts/36_summarize_sbiad840.sh runs/sbiad840_eval_dense_cnn_single
bash scripts/38_compare_sbiad840_kimmelnet.sh \
  runs/sbiad840_eval_zero_shot \
  runs/sbiad840_eval_dense_cnn_single
```

对照输出：

- `runs/.../sbiad840_vs_kimmelnet.csv`
- `runs/.../sbiad840_vs_kimmelnet.md`

---

## 可选：S-BIAD840 低样本微调

如果 Princeton 的 zero-shot 校准仍然不够，可以直接从发布 checkpoint 做**重新
开始的低样本微调**。这里用的是 `init_ckpt` 模式：只加载模型权重，不继承原训练
的 optimizer / scheduler 状态，因此更适合新站点适配，而不是简单续训。

1. 先从 `SBIAD840_28C5_TEST` 生成低样本微调 split：

```bash
bash scripts/39_make_sbiad840_finetune_splits.sh
```

默认会生成：

- `data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft12_v12_seed42.json`
- `data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft24_v12_seed42.json`
- `data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_manifest_seed42.json`

对应两档：

- `12 train / 12 val / 72 test`
- `24 train / 12 val / 60 test`

2. 再用 stage-specific freeze policy 做微调：

```bash
bash scripts/41_finetune_sbiad840.sh
```

这个辅助脚本会自动从所选 checkpoint 的 cfg 里恢复模型架构和主要训练默认值
（例如 `cnn_base`、`model_dim`、`mem_profile`），因此低样本微调默认会与原始
权重保持结构兼容，而不是悄悄退回到通用 `train` CLI 的默认参数。

常用环境变量：

```bash
MODEL=cnn_single
STAGE=head_only
SPLIT_JSON=./data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft12_v12_seed42.json
PROC_DIR=./data/sbiad840_aligned_4p5/processed_28C5_sbiad840
OUT_DIR=./runs/finetune_cnn_single_head_only
EPOCHS=30
LR=3e-4
```

支持的 `STAGE`：

- `head_only`：冻结整个 frame encoder 和 temporal 模块，只训练最终回归头
- `proj_head`：在 `head_only` 基础上，额外解冻 frame 投影层（`frame_enc.proj`）
- `frame_tail1`：在 `head_only` 基础上，额外解冻 frame 投影层和最后一个 CNN block
- `frame_tail2`：在 `head_only` 基础上，额外解冻 frame 投影层和最后两个 CNN block
- `temporal_last1`：先冻结 frame encoder 与 temporal 模块，再重新放开最后一个 temporal block，以及 transformer readout 路径里的 `cls_token` 和 `norm`
- `temporal_last2`：在 `temporal_last1` 基础上，放开最后两个 temporal block，以及 `cls_token` 和 `norm`
- `temporal_head`：只冻结 frame encoder，让整个 temporal stack 和最终回归头一起适配
- `full_trainable`：不冻结，做完整低样本微调

说明：

- `frame_tail*` 主要用于测试“只适配高层视觉语义”是否已经足够。
- `temporal_last*` / `temporal_head` 主要用于真正带 temporal stack 的模型（例如 `full`、`nocons`）。
- `analysis/run_sbiad840_finetune.py` 现在会直接拒绝把 `temporal_last*` / `temporal_head` 用在 `cnn_single`、`meanpool` 这类非 transformer checkpoint 上，而不是静默保留一个名义上“temporal”但实际上不起作用的 stage。

3. 微调完成后，可把多个 Princeton adaptation 结果汇总成统一对照表：

```bash
bash scripts/42_summarize_sbiad840_finetune.sh
```

需要显式提供实验目录，例如：

```bash
CNN_RUN_DIR=./runs/finetune_cnn_single_ft12_frame_tail1_20260311_211714 \
CNN_EVAL28_OUTROOT=./runs/sbiad840_ft12_frame_tail1_eval \
CNN_EVAL25_OUTROOT=./runs/sbiad840_ft12_25c_eval \
FULL_RUN_DIR=./runs/finetune_full_ft12_temporal_last1_20260311_224924 \
FULL_EVAL28_OUTROOT=./runs/sbiad840_ft12_full_temporal_last1_eval \
FULL_EVAL25_OUTROOT=./runs/sbiad840_ft12_25c_eval \
bash scripts/42_summarize_sbiad840_finetune.sh
```

说明：

- 上面的 dated run 目录只是示例，不是脚本写死的默认值。
- `42` 现在只是 `analysis/run_sbiad840_finetune_summary.py` 的薄包装；实验元组全部通过环境变量显式传入。
- rebuttal 里的 held-out `28.5C` 微调对照表使用的是 fine-tune split 的 test 子集（`28C5_sbiad840_ft12_v12_seed42.json`），而 `25C` 仍使用完整外部测试集。
- 结果路径可用 `OUT_DIR`、`OUT_CSV`、`OUT_MD` 覆盖。

默认输出：

- `runs/sbiad840_finetune_compare/sbiad840_finetune_compare.csv`
- `runs/sbiad840_finetune_compare/sbiad840_finetune_compare.md`

4. 若要对某个微调 checkpoint 做 Princeton held-out 外部评估，可直接运行：

```bash
bash scripts/43_eval_sbiad840_finetuned.sh
```

常用环境变量：

```bash
FT_CKPT=./runs/finetune_full_ft12_temporal_last1_20260311_224924/best.pt
MODEL=full
OUTROOT=./runs/sbiad840_ft_eval_full_temporal_last1
DATASETS=SBIAD840_28C5_TEST,SBIAD840_25C_TEST
PROC_28C5_SBIAD840=./data/sbiad840_aligned_4p5/processed_28C5_sbiad840
PROC_25C_SBIAD840=./data/sbiad840_aligned_4p5/processed_25C_sbiad840
SPLIT_28C5_SBIAD840=./data/sbiad840_aligned_4p5/splits/finetune/28C5_sbiad840_ft12_v12_seed42.json
SPLIT_25C_SBIAD840=./data/sbiad840_aligned_4p5/splits/25C_sbiad840_test.json
bash scripts/43_eval_sbiad840_finetuned.sh
```

说明：

- `43` 现在只是 `analysis/eval_sbiad840_finetuned.py` 的薄包装，shell 不再自己串联 inference / aggregation / summarize。
- 这个流程必须显式提供 `FT_CKPT`；它不再回退到发布版 `CKPT_*` 的 zero-shot checkpoint。
- Princeton 数据路径既可以像上面这样显式给出，也可以由 Python 端从 `.env` 读取。
- `FORCE_INFER=1` 是默认值，也是在复用同一个 `OUTROOT` 时的推荐值，因为它能避免把旧 checkpoint 或旧推理参数留下来的 JSON 误当成新结果重新汇总。只有当你明确想复用现有 JSON 缓存时，才设置 `FORCE_INFER=0`。
- 如果你要复现 rebuttal 里 held-out `28.5C` 的微调结果，`SPLIT_28C5_SBIAD840` 应指向 fine-tune split JSON；若改回 `28C5_sbiad840_test.json`，则是在完整 Princeton `28.5C` 外部池上评估。
- 默认输出：
  - `<OUTROOT>/SBIAD840_*/<MODEL>/{json,points.csv,embryo.csv,summary.json}`
  - `<OUTROOT>/sbiad840_external_summary.csv`
  - `<OUTROOT>/sbiad840_external_summary.md`
- 这些输出里，ETF 的原生指标是 `m_anchor`、`rmse_resid`、`max_abs_resid`；用于和 KimmelNet 对齐的辅助指标是 `m_origin`、过原点残差和 through-origin line-fit `R2`。

Princeton 脚本真值表：

| 脚本 | 作用 | 必需输入 | 默认输出 |
|---|---|---|---|
| `38_compare_sbiad840_kimmelnet.sh <BASE_OUTROOT> <DENSE_OUTROOT>` | 用过原点 `y = mx` 口径把 ETF Princeton 结果和 KimmelNet Table 1/2 对齐比较 | 已汇总的 zero-shot outroot；已汇总的 dense `cnn_single` outroot | `<BASE_OUTROOT>/sbiad840_vs_kimmelnet.{csv,md}` |
| `42_summarize_sbiad840_finetune.sh [OUT_DIR]` | 把多个 Princeton 微调实验汇总成一张对照表 | `CNN_RUN_DIR`、`CNN_EVAL28_OUTROOT`、`CNN_EVAL25_OUTROOT`、`FULL_RUN_DIR`、`FULL_EVAL28_OUTROOT`、`FULL_EVAL25_OUTROOT` | `<OUT_DIR>/sbiad840_finetune_compare.{csv,md}` |
| `43_eval_sbiad840_finetuned.sh [OUTROOT]` | 对单个微调 checkpoint 做 Princeton held-out 外部评估 | `FT_CKPT`、`MODEL`；Princeton proc/split 路径可显式给出，也可从 `.env` 解析；`FORCE_INFER={0,1}` 可选 | `<OUTROOT>/SBIAD840_*/<MODEL>/{json,points.csv,embryo.csv,summary.json}`，以及 `<OUTROOT>/sbiad840_external_summary.{csv,md}` |
| `44_stage_tempo_dependence.sh [OUTROOT] [OUT_DIR]` | 做阶段依赖 tempo 分析，并输出 embryo-bootstrap 分段斜率 | 已聚合的 ETF outroot；可选 dataset/model/bootstrap 覆盖 | `<OUT_DIR>/piecewise_stage_slopes.csv`、`local_slope_by_interval.csv`、`stage_delta_contrasts.csv`；只有在 `models` 包含 `full` 且 `datasets` 同时包含 `ID28C5_TEST` 与 `EXT25C_TEST` 时，才额外生成 ETF-full 的 markdown/SVG 摘要 |

建议顺序：

1. 先做 `MODEL=cnn_single STAGE=head_only`
2. 如果校准仍明显偏移，再试 `MODEL=cnn_single STAGE=frame_tail1`
3. 对 clip-based 主方法，再做 `MODEL=full STAGE=head_only`
4. 然后测试局部 temporal 适配，例如 `MODEL=full STAGE=temporal_last1`
5. 只有轻量阶段不够时，再继续尝试更大范围解冻（`frame_tail2`、`temporal_last2`、`temporal_head` 或 `full_trainable`）

第一轮通常建议**只用 `SBIAD840_28C5_TEST` 做微调**，把 `SBIAD840_25C_TEST`
保留为外部验证集，用来检查 site-specific 适配后温度减速结论是否仍成立。

---

## ETF CLI 速查

```bash
python3 src/EmbryoTempoFormer.py -h
python3 src/EmbryoTempoFormer.py preprocess -h
python3 src/EmbryoTempoFormer.py make_split -h
python3 src/EmbryoTempoFormer.py train -h
python3 src/EmbryoTempoFormer.py eval -h
python3 src/EmbryoTempoFormer.py infer -h
```

---

## 代表性硬件 / 耗时

论文主结果复现**不需要重新训练**，直接使用发布的 checkpoint 即可。为了提高可访问性，这里给出本次修回中实际使用的代表性单机资源与耗时。

原始 released checkpoint 的训练环境明显比下面这些单卡示例更重：

| 场景 | 硬件 / 显存情况 |
|---|---|
| 原始 released checkpoint 训练 | `4 × RTX 3090`，DDP；发布 checkpoint 本身使用 `mem_profile=lowmem` 训练，原始训练中每卡显存通常约 `13-15 GB`；更高显存档位在原始 batch / clip 设置下并不现实 |
| 本次修回 Princeton 推理 / low-shot adaptation | 单卡 `RTX 4060 Laptop GPU (8188 MiB)`，开启 `AMP=1` 与 `mem_profile=lowmem` |

| 任务 | 代表性配置 | 耗时 | 峰值显存 |
|---|---|---:|---:|
| Princeton 外部零样本推理 | `2` 个数据集 × `4` 个模型 × `96` 个胚胎，共 `768` 个 embryo-model job | 总计 `50.5 min`（平均 `3.95 s/job`） | 单卡 `RTX 4060 Laptop (8188 MiB)` 推理 |
| 低样本微调：`cnn_single + ft12 + frame_tail1` | `batch_size=32`，`val_batch_size=64`，`clip_len=24`，`AMP=1`，`mem_profile=lowmem` | `73.7 s/epoch` | `3.66 GB` |
| 低样本微调：`full + ft12 + temporal_last1` | `batch_size=16`，`val_batch_size=32`，`clip_len=24`，`AMP=1`，`mem_profile=lowmem` | `135.7 s/epoch` | `5.15 GB` |

上述数字对应的代表性硬件为：

- GPU：`NVIDIA GeForce RTX 4060 Laptop GPU`（`8188 MiB`）
- CPU：`13th Gen Intel Core i7-13650HX`（`20` 逻辑线程；`10` 核 / `20` 线程）
- 内存：`15 GiB`

`lowmem` 不是一个模糊标签；代码里它具体把内存配置从默认 balanced 改成如下形式：

| 设置 | `balanced` | `lowmem` | 作用 |
|---|---:|---:|---|
| `frame_chunk` | `8` | `4` | 每次 CNN 编码更少帧 |
| `ckpt_frame` | `False` | `True` | 对**整个 frame encoder**按 chunk 做 checkpoint |
| `ckpt_cnn` | `True` | `False` | 不再额外做 CNN 内部分段 checkpoint，因为整段 frame checkpoint 已经是主节省项 |
| `ckpt_segments` | `2` | `1` | 低内存路径下简化 checkpoint 分段 |

在同一套 `full + temporal_last1` 的低样本微调配置下，这几档显存策略在 `RTX 4060 Laptop GPU` 上的表现如下：

| 显存档位 | 单个代表性 epoch 耗时 | 峰值显存 | 说明 |
|---|---:|---:|---|
| `ultra` | `142.9 s` | `2.31 GB` | 最省显存，但计算换显存最激进 |
| `lowmem` | `145.5 s` | `5.12 GB` | 发布 checkpoint 使用的档位；在 `8 GB` 级 GPU 上仍可实际运行 |
| `balanced` | `251.7 s` | `8.80 GB` | 在 `8 GB` 级笔记本 GPU 上已经接近/超过可用上限 |
| `fast` | 在这台 `8 GB` 级 GPU 上没有稳定完成代表性 epoch | 接近显存上限 | 对该类硬件并不现实 |

这些数字是**实际参考值**，不是严格下限；具体 wall-clock 会随硬件、存储和软件环境而变化。

---

## 常见问题

- **Windows：**工作流脚本为 `bash`；建议使用 WSL 或 Linux/macOS 环境。
- **提示 `bash: command not found`：**请在 bash shell 中运行。
- **macOS 没有 `sha256sum`：**可安装 coreutils（`brew install coreutils`）或跳过校验。
- **依赖缺失/ImportError：**确认在当前环境执行过 `pip install -r requirements.txt`。
- **PyTorch GPU/CUDA 安装：**`pip install -r requirements.txt` 通常安装 CPU 版本；如需 GPU，请按 PyTorch 官方指南安装匹配版本。
- **GPU/CUDA 数值非确定性：**不同硬件/驱动/库组合下可能出现轻微数值差异。
- **`RUNS_DIR` 说明：**通常保持 `RUNS_DIR=./runs`；`scripts/reproduce_all.sh` 现在通过 Python 编排显式传递 `OUTROOT`，不再依赖扫描 `./runs/paper_eval_*`。
- **训练 OOM：**论文复现不需要训练；如需训练，请参考发布 checkpoint 的 cfg（例如 `mem_profile=lowmem`）。

---

## 许可证

MIT（见 LICENSE）。

</details>
