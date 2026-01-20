```markdown
# EmbryoTempoFormer (S‑BIAD531)

EmbryoTempoFormer (ETF) is a reproducible pipeline for **clip-based developmental time prediction** and **embryo-level developmental tempo estimation** from zebrafish brightfield time‑lapse microscopy.

- **Data source:** BioImage Archive (EMBL‑EBI), accession **S‑BIAD531**  
  https://www.ebi.ac.uk/bioimage-archive/galleries/S-BIAD531.html

This repository is designed for **paper-grade reproducibility**:
- machine-specific absolute paths live in a local `.env` (**never commit**),
- scripts run end-to-end and produce **JSON/CSV summaries + publication figures** under `runs/`.

---

# 中文说明（Chinese）

## 1) 项目亮点（Highlights）
- clip-based 多帧建模优于单帧基线，可稳定预测发育时间并进行消融对比  
- temporal-difference consistency（同胚胎内差分一致性）提升轨迹自洽性（full vs nocons 因果对照）  
- 外域 25°C 测试下 tempo 斜率 m 明显小于 1，可量化温度导致的发育变慢  
- 胚胎级 bootstrap（embryo-level）用于 Δm 置信区间，避免 time‑lapse 窗口伪重复

---

## 2) 目录结构
- `src/EmbryoTempoFormer.py`：主 CLI（preprocess / make_split / train / eval / infer）
- `analysis/aggregate_kimmel.py`：聚合 per‑embryo infer JSON → `points.csv / embryo.csv / summary.json`
- `analysis/ci_delta_m.py`：Δm embryo‑bootstrap 95% CI
- `analysis/power_curve.py`：样本效率 power(E)（可选）
- `analysis/make_figures_jobs.py`：顶刊风格 4 张图（PNG+PDF）
- `analysis/vis_clip_saliency.py`：SmoothGrad 可解释性（可选，用于 Supplement）
- `scripts/`：傻瓜式全链路脚本（从 infer 到出图）

---

## 3) 安装（最小依赖）
推荐在你自己的 conda 环境中安装：

```bash
pip install -r requirements.txt
```

可选：使用 conda
```bash
conda env create -f environment.yml
conda activate embryo-tempoformer
```

---

## 4) 复现（审稿人推荐：方案 B / Zenodo FULL processed）
我们推荐通过 Zenodo 提供的 **FULL processed + checkpoints + splits** 快速复现论文图表（无需从原始 TIFF 重新预处理）。

- Zenodo bundle（FULL processed + checkpoints + splits + MANIFEST）：**DOI: <填你的 DOI>**
- Raw data source：BioImage Archive S‑BIAD531

### 4.1 下载并解压 Zenodo 包
将 Zenodo 包解压到任意目录，例如：
- `./data_release/`

解压后建议目录形态如下：
```text
data_release/
├─ processed_28C5/
├─ processed_25C/
├─ splits/
│  ├─ 28C5.json
│  └─ 25C.json
└─ checkpoints/
   ├─ cnn_single_best.pt
   ├─ meanpool_best.pt
   ├─ nocons_best.pt
   └─ full_best.pt
```

### 4.2 配置 `.env`
```bash
cp .env.example .env
# 编辑 .env：将 PROC_28C5/PROC_25C/SPLIT_*/CKPT_* 指向 data_release 下对应路径
bash scripts/00_check_env.sh
```

### 4.3 一键复现（infer → aggregate → CI/power → figures）
```bash
bash scripts/reproduce_all.sh
```

输出会生成在：
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

最终 4 张图在：
- `runs/paper_eval_YYYYMMDD_HHMMSS/figures_jobs/`（PNG + PDF）

---

## 5)（可选）从原始 OME‑TIFF 生成 processed `.npy`
如果需要从原始数据开始复现 processed，可使用 ETF 的 `preprocess` 子命令：

```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir   /ABS/PATH/raw_ome_tiffs \
  --proc_dir /ABS/PATH/processed_efl384_p1p99 \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 --p_hi 99 \
  --max_pages 0
```

输出目录会包含：
- 每个样本一个 `.npy`（uint8，shape=[T,H,W]，T=192，H=W=384）
- `preprocess_meta.json`

---

## 6) ETF CLI 子命令总结（预处理 / 训练 / 推理）
本节汇总 `src/EmbryoTempoFormer.py` 的全部子命令。任何参数都可通过 `-h` 查看：

```bash
python3 src/EmbryoTempoFormer.py -h
python3 src/EmbryoTempoFormer.py preprocess -h
python3 src/EmbryoTempoFormer.py make_split -h
python3 src/EmbryoTempoFormer.py train -h
python3 src/EmbryoTempoFormer.py eval -h
python3 src/EmbryoTempoFormer.py infer -h
```

### 6.1 preprocess：原始 TIFF/OME‑TIFF → processed `.npy`
**用途**：将原始 time‑lapse stack 预处理为固定形状 uint8 `.npy`。  
处理包括：percentile clipping → 双线性 resize 到正方形 → pad/trim 到 `expect_t` 帧。

**命令模板：**
```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir   /ABS/PATH/raw_tiffs \
  --proc_dir /ABS/PATH/processed_dir \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 --p_hi 99 \
  --max_pages 0 \
  --limit 0
```

### 6.2 make_split：生成 train/val/test split
**用途**：扫描 `proc_dir/*.npy` 并写出 split JSON：
```json
{"train":[...], "val":[...], "test":[...]}
```

**命令模板：**
```bash
python3 src/EmbryoTempoFormer.py make_split \
  --proc_dir /ABS/PATH/processed_dir \
  --out_json /ABS/PATH/split.json \
  --val_ratio 0.15 \
  --test_ratio 0.15 \
  --seed 42
```

### 6.3 train：训练（pair sampling + temporal-difference consistency）
**用途**：训练 clip‑based 模型预测发育时间（hpf）。训练以同一胚胎内成对窗口为单位：
- `lambda_abs`：绝对回归项  
- `lambda_diff`：时间差一致性项（SmoothL1），并通过 `cons_ramp_ratio` 线性 warm‑up

**full 模型示例命令：**
```bash
python3 src/EmbryoTempoFormer.py train \
  --proc_dir   /ABS/PATH/processed_28C5 \
  --split_json /ABS/PATH/split/28C5.json \
  --out_dir    runs/EXP_full \
  --epochs 300 \
  --batch_size 64 --val_batch_size 64 \
  --num_workers 8 \
  --samples_per_embryo 32 \
  --jitter 2 \
  --clip_len 24 --img_size 384 --expect_t 192 \
  --temporal_mode transformer \
  --model_dim 128 --model_depth 4 --model_heads 4 --model_mlp_ratio 2.0 \
  --drop 0.1 --attn_drop 0.0 --temporal_drop_p 0.0 \
  --cnn_base 24 --cnn_expand 2 --cnn_se_reduction 4 \
  --lambda_abs 1.0 --lambda_diff 1.0 --cons_ramp_ratio 0.2 \
  --abs_loss_type l1 \
  --lr 6e-4 --weight_decay 0.01 --warmup_ratio 0.01 --lr_min_ratio 0.05 \
  --max_grad_norm 1.0 --grad_accum 1 \
  --mem_profile lowmem \
  --amp \
  --ema_decay 0.99 --ema_eval \
  --seed 42 --device auto
```

**四模型消融（论文一致）：**
- **cnn_single**：`--temporal_mode identity --model_depth 0`
- **meanpool**：`--temporal_mode meanpool --model_depth 0`
- **nocons**：`--temporal_mode transformer --model_depth 4 --lambda_diff 0`
- **full**：`--temporal_mode transformer --model_depth 4 --lambda_diff 1`

### 6.4 eval：验证集 clip-level 指标（训练监控用）
**用途**：在 val split 上做 clip‑level 评估（用于训练监控/保存 best）。  
注意：clip-level 窗口在同一胚胎内高度相关，不应用作论文推断结论的统计单位。

**命令模板：**
```bash
python3 src/EmbryoTempoFormer.py eval \
  --proc_dir   /ABS/PATH/processed_28C5 \
  --split_json /ABS/PATH/split/28C5.json \
  --ckpt       /ABS/PATH/best.pt \
  --clip_len 24 --img_size 384 --expect_t 192 \
  --batch_size 64 --num_workers 4 \
  --mem_profile balanced \
  --amp --device auto \
  --use_ema
```

### 6.5 infer：单胚胎滑窗推理（输出 per-embryo JSON）
**用途**：对单个 `.npy`（或 `.tif/.tiff`）做滑窗推理，输出 JSON（包含 `starts` 与 `t0_hats`）。  
论文后续 tempo 拟合与统计分析主要使用 `starts + t0_hats`。

**命令模板：**
```bash
python3 src/EmbryoTempoFormer.py infer \
  --ckpt /ABS/PATH/best.pt \
  --input_path /ABS/PATH/processed_dir/<eid>.npy \
  --out_json runs/infer_json/<eid>.json \
  --clip_len 24 --img_size 384 --expect_t 192 \
  --stride 8 \
  --trim 0.2 \
  --batch_size 64 --num_workers 0 \
  --mem_profile lowmem \
  --amp --device auto \
  --use_ema
```

---

## 7) scripts 一键工作流（推荐）
我们提供一键脚本串联：
- infer → aggregate → CI/power → figures

```bash
bash scripts/reproduce_all.sh
```

### 输出说明（runs/paper_eval_*/）
`runs/paper_eval_YYYYMMDD_HHMMSS/` 下的关键文件：
- `ID28C5_TEST/<model>/json/*.json`：per-embryo infer 输出（每胚胎一个）
- `ID28C5_TEST/<model>/{points.csv,embryo.csv,summary.json}`：聚合后的表与指标
- `EXT25C_TEST/<model>/{points.csv,embryo.csv,summary.json}`：外域聚合
- `CI_<model>_m_anchor.json`：Δm 的 95% CI（embryo-bootstrap）
- `power_<model>_m_anchor.csv/png`：power(E)（可选）
- `figures_jobs/`：顶刊风格 4 张图（PNG+PDF）

---

## 8) 指标解释（避免外域误读）
- **ID（28.5°C）**：`summary.json` 的 `global_metrics_points.mae/rmse/r2` 可作为点级准确度参考。
- **External（25°C）**：相对名义时钟 `y=x` 的 MAE/RMSE 主要反映温度导致的系统性延缓累积，不应作为外域 accuracy 主结论；外域对比建议报告：
  - `m_anchor`（tempo 斜率，<1 表示变慢）
  - `rmse_resid`（拟合残差散布，越小越稳定）
  - `max_abs_resid`（最坏离群，长尾/坏孔敏感）

---

## 9) 预处理说明（发布口径）
预处理将每帧图像通过双线性插值缩放至 384×384 以统一输入尺寸（PIL resize, bilinear）。在靠近视野边界且存在裁切的样本中，缩放插值在边界处可能强化边缘效应并引入几何形变；这类影响主要表现为残差长尾，因此本文报告胚胎级汇总与残差诊断以减轻少量异常窗口对总体结论的影响。

---

## 10) License
MIT（见 LICENSE）。

---

# English README

## 1) Highlights
- Clip-based time-lapse modeling improves performance over single-frame baselines  
- Temporal-difference consistency reduces trajectory scatter (causal ablation: full vs nocons)  
- External 25°C testing yields tempo slopes m < 1, quantifying temperature-induced slowdown  
- Embryo-level bootstrap confidence intervals provide rigorous uncertainty for Δm

## 2) Repository layout
- `src/EmbryoTempoFormer.py`: main CLI (preprocess / make_split / train / eval / infer)
- `analysis/aggregate_kimmel.py`: infer JSON → points/embryo/summary
- `analysis/ci_delta_m.py`: embryo-bootstrap CI for Δm
- `analysis/power_curve.py`: sample efficiency (optional)
- `analysis/make_figures_jobs.py`: publication figures (PNG+PDF)
- `analysis/vis_clip_saliency.py`: SmoothGrad interpretability (optional)
- `scripts/`: one-command end-to-end workflow

## 3) Install
```bash
pip install -r requirements.txt
```

(Optional) conda:
```bash
conda env create -f environment.yml
conda activate embryo-tempoformer
```

## 4) Reproducibility (recommended for reviewers: Option B / Zenodo FULL processed)
We recommend reproducing paper results using a Zenodo bundle containing **FULL processed arrays + checkpoints + splits**.

- Zenodo bundle (FULL processed + checkpoints + splits + MANIFEST): **DOI: <fill DOI>**
- Raw data source: BioImage Archive S‑BIAD531

### 4.1 Download and extract the Zenodo bundle
Extract the bundle into any directory, e.g. `./data_release/`.

Expected layout:
```text
data_release/
├─ processed_28C5/
├─ processed_25C/
├─ splits/
│  ├─ 28C5.json
│  └─ 25C.json
└─ checkpoints/
   ├─ cnn_single_best.pt
   ├─ meanpool_best.pt
   ├─ nocons_best.pt
   └─ full_best.pt
```

### 4.2 Configure `.env`
```bash
cp .env.example .env
# edit .env: PROC_*/SPLIT_*/CKPT_* to point into data_release/
bash scripts/00_check_env.sh
```

### 4.3 One-command reproduction
```bash
bash scripts/reproduce_all.sh
```

Outputs are written to `runs/paper_eval_YYYYMMDD_HHMMSS/` (final figures in `figures_jobs/`).

## 5) (Optional) Preprocess from raw OME‑TIFF to processed `.npy`
```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir   /ABS/PATH/raw_ome_tiffs \
  --proc_dir /ABS/PATH/processed_efl384_p1p99 \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 --p_hi 99 \
  --max_pages 0
```

## 6) ETF CLI subcommands (preprocess / train / infer)
List help:
```bash
python3 src/EmbryoTempoFormer.py -h
python3 src/EmbryoTempoFormer.py preprocess -h
python3 src/EmbryoTempoFormer.py make_split -h
python3 src/EmbryoTempoFormer.py train -h
python3 src/EmbryoTempoFormer.py eval -h
python3 src/EmbryoTempoFormer.py infer -h
```

### 6.1 preprocess
Converts raw TIFF/OME‑TIFF stacks into fixed-shape uint8 `.npy`:
- percentile clipping (`p_lo/p_hi`)
- bilinear resize to `img_size × img_size` (default 384×384)
- pad/trim along time to `expect_t` frames (default 192)

### 6.2 make_split
Scans `proc_dir/*.npy` and writes:
```json
{"train":[...], "val":[...], "test":[...]}
```

### 6.3 train
Trains a clip-based model using within-embryo pair sampling and an optional temporal-difference consistency loss.
Ablations (paper):
- cnn_single: `--temporal_mode identity --model_depth 0`
- meanpool:   `--temporal_mode meanpool --model_depth 0`
- nocons:     `--temporal_mode transformer --model_depth 4 --lambda_diff 0`
- full:       `--temporal_mode transformer --model_depth 4 --lambda_diff 1`

### 6.4 eval
Clip-level validation metrics for training monitoring (note: windows are correlated within embryo).

### 6.5 infer
Embryo-level inference using sliding windows, producing per-embryo JSON with `starts` and `t0_hats`.
Downstream tempo fitting and statistics use `starts + t0_hats`.

## 7) End-to-end scripts (recommended)
Run:
```bash
bash scripts/reproduce_all.sh
```

Key outputs under `runs/paper_eval_*/`:
- per-embryo `json/*.json`
- aggregated `points.csv`, `embryo.csv`, `summary.json`
- bootstrap `CI_*.json`
- final figures in `figures_jobs/` (PNG+PDF)

## 8) Metric notes
- ID (28.5°C): pointwise MAE/RMSE/R² can be interpreted as accuracy.
- External (25°C): pointwise MAE/RMSE vs nominal clock `y=x` mainly reflects true temperature-induced delay; primary external readouts are `m_anchor`, `rmse_resid`, and `max_abs_resid`.

## 9) Preprocessing note
Frames are resized to 384×384 via bilinear interpolation. For embryos near the field-of-view boundary, interpolation may accentuate boundary artifacts and geometric distortion; we report embryo-level summaries and residual diagnostics to mitigate the influence of rare outlier windows.

## 10) License
MIT (see LICENSE).
```