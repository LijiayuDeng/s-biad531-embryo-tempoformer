# README (English) — EmbryoTempoFormer (ETF, S‑BIAD531)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18318139.svg)](https://doi.org/10.5281/zenodo.18318139)

EmbryoTempoFormer (ETF) is a **paper-grade reproducible pipeline** for:

- **clip-based developmental time prediction** from zebrafish brightfield time‑lapse microscopy, and  
- **embryo-level developmental tempo estimation** (anchored slope `m_anchor` + stability diagnostics) for cross-condition comparison (e.g., temperature shift).

**Links**
- **Code repo:** https://github.com/LijiayuDeng/s-biad531-embryo-tempoformer  
- **Zenodo reproducibility bundle (FULL processed + checkpoints + splits):** https://doi.org/10.5281/zenodo.18318139  
- **Raw data source:** BioImage Archive accession **S‑BIAD531**  
  https://www.ebi.ac.uk/bioimage-archive/galleries/S-BIAD531.html

**Design principles**
- machine-specific absolute paths live in a local `.env` (**never commit**),
- scripts run end-to-end and produce **JSON/CSV summaries + publication figures** under `runs/`,
- time-lapse sliding-window predictions are correlated within embryo; inferential comparisons are performed at the **embryo level** (avoid pseudo-replication).

---

## Contents
- [Quickstart (Option B, recommended)](#quickstart-option-b-recommended)
- [Expected outputs](#expected-outputs)
- [Optional: SmoothGrad saliency](#optional-smoothgrad-saliency)
- [Metrics notes (external 25°C)](#metrics-notes-external-25c)
- [Optional: Training specification (EXP4; from checkpoint cfg)](#optional-training-specification-exp4-from-checkpoint-cfg)
- [Optional: Option A (preprocess from raw OME‑TIFF)](#optional-option-a-preprocess-from-raw-ome-tiff)
- [ETF CLI quick reference](#etf-cli-quick-reference)
- [License](#license)

---

## Quickstart (Option B, recommended)

**Goal:** reproduce paper quantitative results and figures using the Zenodo bundle (no re-training required).

### Step 1 — Download and extract the Zenodo bundle
From the Zenodo record (recommended filename):
- `embryo-tempoformer_release_v1_full.tar.gz`  
  https://doi.org/10.5281/zenodo.18318139

Extract:
```bash
tar -xzf embryo-tempoformer_release_v1_full.tar.gz
```

Expected extracted folder:
- `embryo-tempoformer_release_v1/`

Expected layout:
```text
embryo-tempoformer_release_v1/
├─ processed_28C5/
├─ processed_25C/
├─ splits/
├─ checkpoints/
├─ MANIFEST.json
└─ SHA256SUMS.txt
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

### Step 3 — Configure `.env` (manual editing is simplest and cross-platform)
Create your local `.env`:
```bash
cp .env.example .env
```

Open `.env` and set these paths to your extracted Zenodo folder (absolute paths recommended):

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

### Step 4 — Validate environment paths
```bash
bash scripts/00_check_env.sh
```

### Step 5 — One-command reproduction (infer → aggregate → CI → figures)
```bash
bash scripts/reproduce_all.sh
```

The script prints an output root directory (OUTROOT), e.g.:
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

---

## Expected outputs

Under `runs/paper_eval_YYYYMMDD_HHMMSS/`:

- `ID28C5_TEST/<model>/json/*.json` — per‑embryo inference JSON (one file per embryo)
- `ID28C5_TEST/<model>/{points.csv, embryo.csv, summary.json}` — aggregated metrics (in‑distribution, 28.5°C)
- `EXT25C_TEST/<model>/{points.csv, embryo.csv, summary.json}` — aggregated metrics (external, 25°C)
- `CI_<model>_m_anchor.json` — embryo-bootstrap 95% CI for Δm
- `figures_jobs/` — publication figures (PNG + PDF)

Models (`<model>`): `cnn_single`, `meanpool`, `nocons`, `full`.

---

## Optional: SmoothGrad saliency

SmoothGrad is **qualitative** and slower; it is not required for paper quantitative reproduction.

Run within the full pipeline:
```bash
RUN_SALIENCY=1 bash scripts/reproduce_all.sh
```

Choose the model (default `full`):
```bash
RUN_SALIENCY=1 SALIENCY_MODEL=full bash scripts/reproduce_all.sh
# also supports: nocons / meanpool / cnn_single
```

Output example:
- `runs/paper_eval_YYYYMMDD_HHMMSS/vis_best_<EID>_<MODEL>_smoothgrad_five/`

---

## Metrics notes (external 25°C)

### In-distribution (28.5°C)
Pointwise MAE/RMSE/R² over sliding windows can be interpreted as descriptive accuracy metrics.

### External domain (25°C)
Under a temperature-induced tempo shift, the nominal mapping
- `t(s) = T0 + DT*s`
(i.e., the “y=x” axis when plotting predicted vs nominal time) is **not** a ground-truth developmental clock at 25°C.

Therefore:
- `MAE_vs_nominal / RMSE_vs_nominal / R2_vs_nominal` quantify **deviation from the nominal axis** and are reported for descriptive comparison only (not external-domain accuracy).

Recommended primary external readouts:
- `m_anchor` — embryo-level anchored tempo slope (`m<1` indicates slowdown)
- `rmse_resid` — anchored-fit residual scatter (lower is more stable)
- `max_abs_resid` — worst-case outliers / long tails

### Optional start-time offset diagnostic (`t0_final`)
Inference JSON also includes an intercept-like diagnostic:
- for each start `s`: `t0_hat(s) = t_hat(s) - DT*s`
- aggregated as a trimmed mean (`trim=0.2`) to obtain `t0_final`

This is a **descriptive QC diagnostic** (e.g., effective time-zero uncertainty) and is not used for inferential comparisons.

---

## Optional: Training specification (EXP4; from checkpoint cfg)

Reproducing paper results does **not** require re-training (Option B uses released checkpoints).

Each released checkpoint (`*_best.pt`) stores the full training configuration under `ckpt["cfg"]`. Paper numbers correspond to the released checkpoints and their stored `cfg` (which may differ from CLI defaults).

### Shared EXP4 hyperparameters (from `cfg`)
The list below matches the released `EXP4_full` checkpoint cfg:

**Data / sampling**
- `clip_len=24`, `img_size=384`, `expect_t=192`
- `samples_per_embryo=32`, `jitter=2`, `cache_items=16`

**Optimization / schedule**
- `epochs=300`
- `batch_size=32`, `val_batch_size=64`, `num_workers=8`
- `lr=6e-4`, `weight_decay=0.01`
- `warmup_ratio=0.01`, `lr_min_ratio=0.05`
- `max_grad_norm=1.0`, `grad_accum=1`
- `amp=true`

**Model (Transformer variants)**
- `model_dim=128`, `model_depth=4`, `model_heads=4`, `model_mlp_ratio=2.0`
- `temporal_mode=transformer`, `temporal_drop_p=0.05`
- `drop=0.1`, `attn_drop=0.0`

**CNN frame encoder**
- `cnn_base=32`, `cnn_expand=2`, `cnn_se_reduction=4`

**Loss**
- `abs_loss_type=l1`, `lambda_abs=1.0`
- `cons_ramp_ratio=0.2`
- `lambda_diff` depends on ablation (see below)

**EMA**
- `ema_decay=0.99`, `ema_eval=true`, `ema_start_ratio=0.0`

**Repro / engineering**
- `seed=42`, `mem_profile=lowmem`

Machine-specific fields (examples): `out_dir`, `proc_dir`, `split_json`.

### Ablation differences (verify per checkpoint cfg)
- `cnn_single`: `temporal_mode=identity`, `model_depth=0`, `temporal_drop_p=0.0`, `lambda_diff=0.0`
- `meanpool`: `temporal_mode=meanpool`, `model_depth=0`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `nocons`: `temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `full`: `temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=1.0`

### Print the exact cfg stored in a checkpoint
```bash
python3 - <<'PY'
import torch, json
ckpt=torch.load("path/to/best.pt", map_location="cpu")
print(json.dumps(ckpt["cfg"], indent=2, sort_keys=True))
PY
```

---

## Optional: Option A (preprocess from raw OME‑TIFF)

```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir   /ABS/PATH/raw_ome_tiffs \
  --proc_dir /ABS/PATH/processed_efl384_p1p99 \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 --p_hi 99 \
  --max_pages 0
```

Preprocessing summary:
- percentile clip + normalize (default `p_lo=1`, `p_hi=99`)
- resize to `384×384` (PIL bilinear)
- pad/trim time axis to `192` frames
- store one `.npy` per embryo

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

## License
MIT (see LICENSE).

---

---

# README（中文）— EmbryoTempoFormer（ETF，S‑BIAD531）

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18318139.svg)](https://doi.org/10.5281/zenodo.18318139)

EmbryoTempoFormer（ETF）提供一套**可复现（paper-grade）**的管线，用于：

- 斑马鱼明场 time‑lapse 显微图像的 **clip-based 发育时间预测**，以及  
- **胚胎级（embryo-level）发育 tempo 估计**（`m_anchor` 及稳定性诊断），支持跨条件比较（如温度变化）。

**链接**
- **代码仓库：** https://github.com/LijiayuDeng/s-biad531-embryo-tempoformer  
- **Zenodo 可复现发布包（FULL processed + checkpoints + splits）：** https://doi.org/10.5281/zenodo.18318139  
- **原始数据：** BioImage Archive（S‑BIAD531）  
  https://www.ebi.ac.uk/bioimage-archive/galleries/S-BIAD531.html

**设计原则**
- 机器相关的绝对路径写在本地 `.env`（**不要提交到仓库**）
- 脚本端到端运行，在 `runs/` 下输出 **JSON/CSV 汇总 + 论文图**
- 滑动窗口预测在同一胚胎内高度相关；推断（CI/效应量）以**胚胎**为统计单位，避免伪重复（pseudo-replication）

---

## 目录
- [快速开始（Option B，推荐）](#快速开始option-b推荐)
- [你应该看到哪些输出](#你应该看到哪些输出)
- [可选：SmoothGrad 热图](#可选smoothgrad-热图)
- [指标说明（外域 25°C 特别重要）](#指标说明外域-25c-特别重要)
- [可选：训练规格（EXP4；以 checkpoint cfg 为准）](#可选训练规格exp4以-checkpoint-cfg-为准)
- [可选：Option A（从原始 OME‑TIFF 重新预处理）](#可选option-a从原始-ome-tiff-重新预处理)
- [ETF CLI 速查](#etf-cli-速查)
- [许可证](#许可证)

---

## 快速开始（Option B，推荐）

**目标：**使用 Zenodo 发布包一键复现论文定量结果与图表（无需重新训练）。

### Step 1 — 下载并解压 Zenodo 发布包
从 Zenodo 下载（推荐文件名）：
- `embryo-tempoformer_release_v1_full.tar.gz`  
  https://doi.org/10.5281/zenodo.18318139

解压：
```bash
tar -xzf embryo-tempoformer_release_v1_full.tar.gz
```

解压后目录：
- `embryo-tempoformer_release_v1/`

目录结构应包含：
```text
embryo-tempoformer_release_v1/
├─ processed_28C5/
├─ processed_25C/
├─ splits/
├─ checkpoints/
├─ MANIFEST.json
└─ SHA256SUMS.txt
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

### Step 3 — 配置 `.env`（推荐手动编辑，跨平台最稳）
生成本地 `.env`：
```bash
cp .env.example .env
```

打开 `.env`，把以下路径改为你机器上的**绝对路径**（指向解压后的 Zenodo 目录）：

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

### Step 4 — 检查环境与路径
```bash
bash scripts/00_check_env.sh
```

### Step 5 — 一键复现（推理 → 汇总 → CI → 作图）
```bash
bash scripts/reproduce_all.sh
```

脚本会打印本次输出根目录（OUTROOT），例如：
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

---

## 你应该看到哪些输出

在 `runs/paper_eval_YYYYMMDD_HHMMSS/` 下：

- `ID28C5_TEST/<model>/json/*.json`：每胚胎一个推理 JSON（per‑embryo）
- `ID28C5_TEST/<model>/{points.csv, embryo.csv, summary.json}`：ID（28.5°C）汇总指标
- `EXT25C_TEST/<model>/{points.csv, embryo.csv, summary.json}`：外域（25°C）汇总指标
- `CI_<model>_m_anchor.json`：Δm 的 embryo-bootstrap 95% 置信区间
- `figures_jobs/`：论文图（PNG + PDF）

模型（`<model>`）：`cnn_single`, `meanpool`, `nocons`, `full`。

---

## 可选：SmoothGrad 热图

SmoothGrad 属于**定性**补充，耗时较长，默认不跑。

在全流程中启用：
```bash
RUN_SALIENCY=1 bash scripts/reproduce_all.sh
```

可指定模型（默认 `full`）：
```bash
RUN_SALIENCY=1 SALIENCY_MODEL=full bash scripts/reproduce_all.sh
# 也支持：nocons / meanpool / cnn_single
```

输出示例：
- `runs/paper_eval_YYYYMMDD_HHMMSS/vis_best_<EID>_<MODEL>_smoothgrad_five/`

---

## 指标说明（外域 25°C 特别重要）

### ID（28.5°C）
滑动窗口点级 MAE/RMSE/R² 可作为描述性准确度指标。

### External（25°C）
温度变化会改变发育 tempo，此时名义映射
- `t(s)=T0 + DT*s`
（即预测与名义时间对比时的 `y=x` 轴）**不再是 25°C 的真实发育时钟**。

因此：
- `MAE_vs_nominal / RMSE_vs_nominal / R2_vs_nominal` 主要量化的是**相对名义轴的偏离**，仅作描述性比较，不应解释为外域 accuracy。

外域建议优先报告：
- `m_anchor`：胚胎级 anchored tempo 斜率（`m<1` 表示变慢）
- `rmse_resid`：anchored 拟合残差散布（越小越稳定）
- `max_abs_resid`：最坏离群/长尾（对异常窗口敏感）

### 可选起始偏置诊断（`t0_final`）
推理 JSON 同时输出一个截距型诊断：
- 每个 start `s`：`t0_hat(s)=t_hat(s) - DT*s`
- 对 `{t0_hat(s)}` 做 trimmed mean（`trim=0.2`）得到 `t0_final`

该量仅用于**描述性 QC 诊断**（例如有效 time‑zero 不确定性），不用于跨条件推断。

---

## 可选：训练规格（EXP4；以 checkpoint cfg 为准）

复现论文结果不需要重新训练（Option B 直接使用发布的 checkpoints 推理）。

每个发布的 checkpoint（`*_best.pt`）都包含 `ckpt["cfg"]`，记录训练超参；论文数值以发布 checkpoint 的 `cfg` 为准（可能与 CLI 默认值不同）。

### EXP4 共同超参（来自 `cfg`）
下列参数与发布的 `EXP4_full` checkpoint cfg 一致：

**数据/采样**
- `clip_len=24`, `img_size=384`, `expect_t=192`
- `samples_per_embryo=32`, `jitter=2`, `cache_items=16`

**优化/调度**
- `epochs=300`
- `batch_size=32`, `val_batch_size=64`, `num_workers=8`
- `lr=6e-4`, `weight_decay=0.01`
- `warmup_ratio=0.01`, `lr_min_ratio=0.05`
- `max_grad_norm=1.0`, `grad_accum=1`
- `amp=true`

**模型（Transformer 变体）**
- `model_dim=128`, `model_depth=4`, `model_heads=4`, `model_mlp_ratio=2.0`
- `temporal_mode=transformer`, `temporal_drop_p=0.05`
- `drop=0.1`, `attn_drop=0.0`

**CNN 帧编码器**
- `cnn_base=32`, `cnn_expand=2`, `cnn_se_reduction=4`

**损失**
- `abs_loss_type=l1`, `lambda_abs=1.0`
- `cons_ramp_ratio=0.2`
- `lambda_diff` 随消融而变化（见下）

**EMA**
- `ema_decay=0.99`, `ema_eval=true`, `ema_start_ratio=0.0`

**复现/工程**
- `seed=42`, `mem_profile=lowmem`

机器相关字段示例：`out_dir`, `proc_dir`, `split_json`。

### 消融差异（建议分别以各自 checkpoint cfg 核对）
- `cnn_single`：`temporal_mode=identity`, `model_depth=0`, `temporal_drop_p=0.0`, `lambda_diff=0.0`
- `meanpool`：`temporal_mode=meanpool`, `model_depth=0`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `nocons`：`temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=0.0`
- `full`：`temporal_mode=transformer`, `model_depth=4`, `temporal_drop_p=0.05`, `lambda_diff=1.0`

### 打印 checkpoint 中保存的 cfg
```bash
python3 - <<'PY'
import torch, json
ckpt=torch.load("path/to/best.pt", map_location="cpu")
print(json.dumps(ckpt["cfg"], indent=2, sort_keys=True))
PY
```

---

## 可选：Option A（从原始 OME‑TIFF 重新预处理）

```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir   /ABS/PATH/raw_ome_tiffs \
  --proc_dir /ABS/PATH/processed_efl384_p1p99 \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 --p_hi 99 \
  --max_pages 0
```

预处理概要：
- 分位数裁剪 + 归一化（默认 `p_lo=1`, `p_hi=99`）
- resize 到 `384×384`（PIL bilinear）
- 时间维 pad/trim 到 `192` 帧
- 每胚胎输出一个 `.npy`

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

## 许可证
MIT（见 LICENSE）。
