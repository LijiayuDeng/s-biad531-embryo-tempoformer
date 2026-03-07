# EmbryoTempoFormer (ETF, S-BIAD531)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18318139.svg)](https://doi.org/10.5281/zenodo.18318139)

EmbryoTempoFormer (ETF) is a **paper-grade reproducible pipeline** for:
- **clip-based developmental time prediction** from zebrafish brightfield time-lapse microscopy, and
- **embryo-level developmental tempo estimation** (anchored slope `m_anchor` + stability diagnostics) for cross-condition comparison (e.g., temperature shift).

**Links**
- **Code repo:** https://github.com/LijiayuDeng/s-biad531-embryo-tempoformer
- **Zenodo reproducibility bundle (FULL processed + checkpoints + splits):** https://doi.org/10.5281/zenodo.18318139
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

**Option 2A: Docker (Easiest)**
Skip Python installation entirely! Just pull the pre-built Docker image:
```bash
docker pull lijiayudeng/embryo-tempoformer:latest
```
To run the pipeline inside the container, map your data directory to `/app/data` (or similar) when running `docker run`.

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

### Step 5 — One-command reproduction (infer → aggregate → CI/power → figures)
```bash
bash scripts/reproduce_all.sh
```

**What this script does (in order):**
1. `scripts/00_check_env.sh` — sanity-check required `.env` variables and paths
2. `scripts/10_infer_all.sh` — runs inference for 4 models (`cnn_single`, `meanpool`, `nocons`, `full`) on 2 test sets (`ID28C5_TEST`, `EXT25C_TEST`); produces per-embryo JSON under `.../<TAG>/<model>/json/*.json`; writes `OUTROOT/OUTROOT.txt`
3. `scripts/20_aggregate_all.sh <OUTROOT>` — aggregates JSON into `points.csv`, `embryo.csv`, `summary.json`
4. `scripts/30_ci_power_all.sh <OUTROOT>` — computes embryo-bootstrap CI and power curves
5. `scripts/40_make_figures.sh <OUTROOT>` — generates publication figures (PNG + PDF)
6. (optional) `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>` if `RUN_SALIENCY=1`

Output root directory (OUTROOT):
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

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

**Figures**
- `figures_jobs/` — publication figures (PNG + PDF)

**Meta**
- `OUTROOT.txt` — records OUTROOT path (written by `scripts/10_infer_all.sh`)

Models (`<model>`): `cnn_single`, `meanpool`, `nocons`, `full`.

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
- **`RUNS_DIR` confusion:** keep `RUNS_DIR=./runs` when using `scripts/reproduce_all.sh` (it scans `./runs/paper_eval_*` to find OUTROOT).
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

**选项 2A: 使用 Docker (最省心)**
你可以完全跳过 Python 和 CUDA 的安装，直接拉取我打包好的 Docker 镜像即可：
```bash
docker pull lijiayudeng/embryo-tempoformer:latest
```
运行容器时，请使用 `-v` 参数将你的数据目录挂载到容器内。

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
5. `scripts/40_make_figures.sh <OUTROOT>` — 生成论文图（PNG + PDF）
6. （可选）若 `RUN_SALIENCY=1`，运行 `scripts/50_saliency_best_id28c5.sh <OUTROOT> <model>`

输出根目录（OUTROOT）：
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

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

**论文图**
- `figures_jobs/` — 论文图（PNG + PDF）

**元信息**
- `OUTROOT.txt` — 记录 OUTROOT 路径（由 `scripts/10_infer_all.sh` 写入）

模型（`<model>`）：`cnn_single`, `meanpool`, `nocons`, `full`。

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
- **`RUNS_DIR` 说明：**使用 `scripts/reproduce_all.sh` 时保持 `RUNS_DIR=./runs`（脚本通过扫描 `./runs/paper_eval_*` 来确定 OUTROOT）。
- **训练 OOM：**论文复现不需要训练；如需训练，请参考发布 checkpoint 的 cfg（例如 `mem_profile=lowmem`）。

---

## 许可证

MIT（见 LICENSE）。

</details>
