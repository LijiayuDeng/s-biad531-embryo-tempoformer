# EmbryoTempoFormer (ETF, S-BIAD531)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18318139.svg)](https://doi.org/10.5281/zenodo.18318139)

EmbryoTempoFormer (ETF) is a **paper-grade reproducible pipeline** for:
- **clip-based developmental time prediction** from zebrafish brightfield time-lapse microscopy, and
- **embryo-level developmental tempo estimation** (anchored slope `m_anchor` + stability diagnostics) for cross-condition comparison (e.g., temperature shift).

**Links**
- **Code repo:** https://github.com/LijiayuDeng/s-biad531-embryo-tempoformer
- **Zenodo reproducibility bundle (FULL processed + checkpoints + splits):** https://doi.org/10.5281/zenodo.18318139
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
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Quickstart (Option B, recommended)

**Goal:** reproduce paper quantitative results and figures using the Zenodo bundle (**no re-training required**).

### Requirements
- A **bash** environment (Linux / macOS / WSL).
- Python 3.9+ recommended.
- `pip` (or conda).

### Step 1 — Download and extract the Zenodo bundle
From the Zenodo record:
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

(Optional) checksum verification:
```bash
cd embryo-tempoformer_release_v1
sha256sum -c SHA256SUMS.txt
cd ..
```

### Step 2 — Clone the repo and install dependencies
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
# External-domain processed npy dirs / splits (after running scripts/34_preprocess_sbiad840.sh)
PROC_28C5_SBIAD840=./data/sbiad840_aligned_4p5/processed_28C5_sbiad840
PROC_25C_SBIAD840=./data/sbiad840_aligned_4p5/processed_25C_sbiad840
SPLIT_28C5_SBIAD840=./data/sbiad840_aligned_4p5/splits/28C5_sbiad840_test.json
SPLIT_25C_SBIAD840=./data/sbiad840_aligned_4p5/splits/25C_sbiad840_test.json

# Output root directory
# IMPORTANT: keep RUNS_DIR=./runs because scripts/reproduce_all.sh assumes ./runs
RUNS_DIR=./runs

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
10. `scripts/40_make_figures.sh <OUTROOT>` — generates publication figures (PNG + PDF)
11. (optional) `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>` if `RUN_SALIENCY=1`

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

**Figures**
- `figures_jobs/` — publication figures (PNG + PDF)

**Meta**
- `OUTROOT.txt` — records OUTROOT path (written by `scripts/10_infer_all.sh`)

Models (`<model>`): `cnn_single`, `meanpool`, `nocons`, `full`.

Thin-shell note:
- shell entrypoints under `scripts/` are orchestration wrappers only
- dataset/model enumeration, per-embryo scheduling, env checking, aggregation, CI/power matrix traversal, and top-level pipeline branching now live in Python (`analysis/check_env.py`, `analysis/run_infer_matrix.py`, `analysis/aggregate_matrix.py`, `analysis/run_ci_power_matrix.py`, `analysis/run_cliplen_sensitivity.py`, `analysis/select_best_embryo.py`, `analysis/run_reproduction_pipeline.py`)

Common overrides for `scripts/10_infer_all.sh`:
```bash
OUTROOT=./runs/paper_eval_manual \
DATASETS=ID28C5_TEST \
MODELS=full \
bash scripts/10_infer_all.sh
```

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
bash scripts/11_cliplen_sensitivity.sh
```

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
  runs/sbiad840_eval_20260311_4models \
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

- `head_only`: freeze frame encoder and temporal module; adapt only the final regression head
- `temporal_head`: freeze frame encoder; allow temporal stack + head to adapt
- `frame_tail1`: keep head-only behavior but unfreeze the last CNN stage
- `frame_tail2`: unfreeze the last two CNN stages in addition to the head
- `full_trainable`: no freezing; full low-shot fine-tuning

Recommended order:

1. Start with `MODEL=cnn_single STAGE=head_only`
2. If calibration remains poor, try `MODEL=cnn_single STAGE=frame_tail1`
3. Then move to `MODEL=full STAGE=head_only`
4. Only unfreeze more of the temporal/CNN stack if the lighter stages are insufficient

The Princeton `25C` subset is typically best kept as **external validation** in
the first round, so the initial fine-tune splits are generated only from
`SBIAD840_28C5_TEST`.

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
- 常见问题
- 许可证

---

## 快速开始（Option B，推荐）

**目标：**使用 Zenodo 发布包复现论文定量结果与图表（**无需重新训练**）。

### 环境要求
- **bash** 环境（Linux / macOS / WSL）
- Python 3.9+
- `pip`（或 conda）

### Step 1 — 下载并解压 Zenodo 发布包
从 Zenodo 下载：
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

（可选）校验：
```bash
cd embryo-tempoformer_release_v1
sha256sum -c SHA256SUMS.txt
cd ..
```

### Step 2 — 克隆仓库并安装依赖
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
# 输出根目录
# 重要：保持 RUNS_DIR=./runs，因为 scripts/reproduce_all.sh 假定使用 ./runs
RUNS_DIR=./runs

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
10. `scripts/40_make_figures.sh <OUTROOT>` — 生成论文图（PNG + PDF）
11. （可选）若 `RUN_SALIENCY=1`，运行 `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>`

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

**论文图**
- `figures_jobs/` — 论文图（PNG + PDF）

**元信息**
- `OUTROOT.txt` — 记录 OUTROOT 路径（由 `scripts/10_infer_all.sh` 写入）

模型（`<model>`）：`cnn_single`, `meanpool`, `nocons`, `full`。

Thin-shell 说明：
- `scripts/` 下的 shell 入口只负责环境加载、默认参数和一键编排
- dataset/model 矩阵遍历、胚胎级调度、环境检查、aggregation、CI/power 批处理、以及顶层 pipeline 分支控制已经收敛到 Python：
  - `analysis/check_env.py`
  - `analysis/run_infer_matrix.py`
  - `analysis/aggregate_matrix.py`
  - `analysis/run_ci_power_matrix.py`
  - `analysis/run_cliplen_sensitivity.py`
  - `analysis/select_best_embryo.py`
  - `analysis/run_reproduction_pipeline.py`

---

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
  runs/sbiad840_eval_20260311_4models \
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

- `head_only`：冻结 frame encoder 和 temporal 模块，只训练最终回归头
- `temporal_head`：冻结 frame encoder，只让 temporal stack + head 适配
- `frame_tail1`：在 head-only 基础上额外解冻最后一个 CNN stage
- `frame_tail2`：额外解冻最后两个 CNN stage
- `full_trainable`：不冻结，做完整低样本微调

建议顺序：

1. 先做 `MODEL=cnn_single STAGE=head_only`
2. 如果校准仍明显偏移，再试 `MODEL=cnn_single STAGE=frame_tail1`
3. 然后做 `MODEL=full STAGE=head_only`
4. 只有轻量阶段不够时，再继续解冻 temporal / CNN 更多层

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
