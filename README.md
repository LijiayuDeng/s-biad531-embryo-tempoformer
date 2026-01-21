```markdown
# EmbryoTempoFormer (S‑BIAD531)

EmbryoTempoFormer (ETF) is a reproducible pipeline for **clip-based developmental time prediction** and **embryo-level developmental tempo estimation** from zebrafish brightfield time‑lapse microscopy.

- **Data source:** BioImage Archive (EMBL‑EBI), accession **S‑BIAD531**  
  https://www.ebi.ac.uk/bioimage-archive/galleries/S-BIAD531.html

This repository is designed for **paper-grade reproducibility**:
- machine-specific absolute paths live in a local `.env` (**never commit**),
- scripts run end-to-end and produce **JSON/CSV summaries + publication figures** under `runs/`.

---

# 中文说明（面向科研人员与审稿人）

## 1) 复现路径概览（两种路径）
本仓库提供两种复现路径：

- **Option B（推荐、最快、审稿人友好）**：下载 Zenodo 发布包（FULL processed + checkpoints + splits + 校验文件）→ 一键复现论文定量结果与图表  
- **Option A（可选、更严格）**：从原始 OME‑TIFF 运行 `preprocess` 生成 processed →（可选训练）→ 推理 → 复现

本 README 以 **Option B** 为主，同时提供 preprocess/训练/推理命令，以便从原始数据开始复现。

---

## 2) 项目亮点（Highlights）
- clip-based 多帧建模优于单帧基线，可稳定预测发育时间并进行消融对比  
- temporal-difference consistency（同胚胎内差分一致性）提升轨迹自洽性（full vs nocons 因果对照）  
- 外域 25°C 测试下 tempo 斜率 m 明显小于 1，可量化温度导致的发育变慢  
- 胚胎级 bootstrap（embryo-level）用于 Δm 置信区间，避免 time‑lapse 窗口伪重复

---

## 3) 目录结构（你需要知道的）
- `src/EmbryoTempoFormer.py`：主 CLI（preprocess / make_split / train / eval / infer）
- `analysis/aggregate_kimmel.py`：聚合 per‑embryo infer JSON → `points.csv / embryo.csv / summary.json`
- `analysis/ci_delta_m.py`：Δm embryo‑bootstrap 95% CI
- `analysis/power_curve.py`：样本效率 power(E)（可选）
- `analysis/make_figures_jobs.py`：顶刊风格 4 张图（PNG+PDF）
- `analysis/vis_clip_saliency.py`：SmoothGrad 可解释性（可选，用于 Supplement）
- `scripts/`：傻瓜式全链路脚本（infer → aggregate → CI/power → figures；可选热图）

---

## 4) 安装（最小依赖）
```bash
pip install -r requirements.txt
```

可选：使用 conda
```bash
conda env create -f environment.yml
conda activate embryo-tempoformer
```

---

## 5) Option B：Zenodo FULL processed（从下载到开始使用，一条链路打通）
我们推荐通过 Zenodo 提供的 **FULL processed + checkpoints + splits + 校验文件** 快速复现论文图表（无需从原始 TIFF 重新预处理）。

- Zenodo DOI：**https://doi.org/10.5281/zenodo.18318139**
- 建议下载的发布包文件名：`embryo-tempoformer_release_v1_full.tar.gz`

### 5.1 下载（Download）
由于不同网络环境可能对 Zenodo 直链有差异，推荐从 DOI 页面进入 record 再下载文件：
- https://doi.org/10.5281/zenodo.18318139

下载完成后，你应得到：
- `embryo-tempoformer_release_v1_full.tar.gz`

### 5.2 校验（Verify，推荐）
```bash
ls -lh embryo-tempoformer_release_v1_full.tar.gz
tar -tzf embryo-tempoformer_release_v1_full.tar.gz | head -n 20
```

### 5.3 解压（Extract）
```bash
tar -xzf embryo-tempoformer_release_v1_full.tar.gz
```

解压后会得到目录（包内真实顶层目录名）：
- `embryo-tempoformer_release_v1/`

该目录结构应包含：
```text
embryo-tempoformer_release_v1/
├─ processed_28C5/
├─ processed_25C/
├─ splits/
├─ checkpoints/
├─ MANIFEST.json
└─ SHA256SUMS.txt
```

（可选）完整校验：
```bash
cd embryo-tempoformer_release_v1
sha256sum -c SHA256SUMS.txt
cd ..
```

### 5.4 配置仓库并运行（复现论文定量结果）
1) 克隆本仓库并安装依赖：
```bash
git clone <GITHUB_REPO_URL>
cd s-biad531-embryo-tempoformer
pip install -r requirements.txt
```

2) 配置 `.env` 指向解压目录（推荐用 REL 一次性定义方式）

> 注意：Linux 的 `sed -i` 可直接用；macOS 请改为 `sed -i ''` 或手动编辑 `.env`。

```bash
cp .env.example .env

REL=/ABS/PATH/TO/embryo-tempoformer_release_v1

sed -i "s|^PROC_28C5=.*|PROC_28C5=$REL/processed_28C5|" .env
sed -i "s|^PROC_25C=.*|PROC_25C=$REL/processed_25C|" .env
sed -i "s|^SPLIT_28C5=.*|SPLIT_28C5=$REL/splits/28C5.json|" .env
sed -i "s|^SPLIT_25C=.*|SPLIT_25C=$REL/splits/25C.json|" .env

sed -i "s|^CKPT_CNN_SINGLE=.*|CKPT_CNN_SINGLE=$REL/checkpoints/cnn_single_best.pt|" .env
sed -i "s|^CKPT_MEANPOOL=.*|CKPT_MEANPOOL=$REL/checkpoints/meanpool_best.pt|" .env
sed -i "s|^CKPT_NOCONS=.*|CKPT_NOCONS=$REL/checkpoints/nocons_best.pt|" .env
sed -i "s|^CKPT_FULL=.*|CKPT_FULL=$REL/checkpoints/full_best.pt|" .env
```

3) 检查路径：
```bash
bash scripts/00_check_env.sh
```

4) 一键复现论文定量结果（infer → aggregate → CI/power → figures）：
```bash
bash scripts/reproduce_all.sh
```

脚本会打印本次输出目录（OUTROOT），例如：
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

最终 4 张图在：
- `runs/paper_eval_YYYYMMDD_HHMMSS/figures_jobs/`（PNG + PDF）

### 5.5（可选）在同一次全流程中自动生成热图（SmoothGrad）
默认情况下，`scripts/reproduce_all.sh` 只复现论文定量结果，**不会**自动跑热图（热图较慢，属于 Supplement 的定性解释）。

如需在同一次全流程中同时生成 SmoothGrad 热图：
```bash
RUN_SALIENCY=1 bash scripts/reproduce_all.sh
```

可选：指定用于热图的模型（默认 full）：
```bash
RUN_SALIENCY=1 SALIENCY_MODEL=full bash scripts/reproduce_all.sh
# 也可用：nocons / meanpool / cnn_single
```

热图输出会写入本次 OUTROOT 目录下，例如：
- `runs/paper_eval_YYYYMMDD_HHMMSS/vis_best_<EID>_<MODEL>_smoothgrad_five/`

---

## 6)（可选）单独生成可解释性热图（SmoothGrad）
如果不想在全流程中跑，也可以在完成 `reproduce_all.sh` 后单独运行：

```bash
bash scripts/50_saliency_best_id28c5.sh
```

或指定 OUTROOT + 模型：
```bash
bash scripts/50_saliency_best_id28c5.sh ./runs/paper_eval_YYYYMMDD_HHMMSS full
bash scripts/50_saliency_best_id28c5.sh ./runs/paper_eval_YYYYMMDD_HHMMSS nocons
```

---

## 7)（可选）Option A：从原始 OME‑TIFF 生成 processed `.npy`
```bash
python3 src/EmbryoTempoFormer.py preprocess \
  --in_dir   /ABS/PATH/raw_ome_tiffs \
  --proc_dir /ABS/PATH/processed_efl384_p1p99 \
  --expect_t 192 \
  --img_size 384 \
  --p_lo 1 --p_hi 99 \
  --max_pages 0
```

---

## 8) ETF CLI 子命令（速查）
查看帮助：
```bash
python3 src/EmbryoTempoFormer.py -h
python3 src/EmbryoTempoFormer.py preprocess -h
python3 src/EmbryoTempoFormer.py make_split -h
python3 src/EmbryoTempoFormer.py train -h
python3 src/EmbryoTempoFormer.py eval -h
python3 src/EmbryoTempoFormer.py infer -h
```

---

## 9) 关键输出说明（runs/paper_eval_*/）
`runs/paper_eval_YYYYMMDD_HHMMSS/` 下关键文件：
- `ID28C5_TEST/<model>/json/*.json`：per‑embryo infer 输出（每胚胎一个）
- `ID28C5_TEST/<model>/{points.csv,embryo.csv,summary.json}`：聚合后的表与指标
- `EXT25C_TEST/<model>/{points.csv,embryo.csv,summary.json}`：外域聚合
- `CI_<model>_m_anchor.json`：Δm 的 95% CI（embryo-bootstrap）
- `power_<model>_m_anchor.csv/png`：power(E)（可选）
- `figures_jobs/`：顶刊风格 4 张图（PNG+PDF）

---

## 10) 指标解释（避免外域误读）
- **ID（28.5°C）**：`summary.json` 的 `global_metrics_points.mae/rmse/r2` 可作为点级准确度参考。
- **External（25°C）**：相对名义时钟 `y=x` 的 MAE/RMSE 主要反映温度导致的系统性延缓累积，不应作为外域 accuracy 主结论；外域对比建议报告：
  - `m_anchor`（tempo 斜率，<1 表示变慢）
  - `rmse_resid`（拟合残差散布，越小越稳定）
  - `max_abs_resid`（最坏离群，长尾/坏孔敏感）

---

## 11) 预处理说明（发布口径）
预处理将每帧图像通过双线性插值缩放至 384×384 以统一输入尺寸（PIL resize, bilinear）。在靠近视野边界且存在裁切的样本中，缩放插值在边界处可能强化边缘效应并引入几何形变；这类影响主要表现为残差长尾，因此本文报告胚胎级汇总与残差诊断以减轻少量异常窗口对总体结论的影响。

---

## 12) License
MIT（见 LICENSE）。

---

# English README (for researchers and reviewers)

## 1) Reproducibility paths (two options)
We provide two reproduction paths:

- **Option B (recommended, fastest, reviewer-friendly):** Zenodo bundle with **FULL processed arrays + checkpoints + splits + integrity checks** → one-command reproduction  
- **Option A (optional, stricter):** preprocess from raw OME‑TIFF → (optional training) → inference → reproduction

This README prioritizes Option B while still providing preprocessing/training/inference commands.

## 2) Highlights
- Clip-based time-lapse modeling improves performance over single-frame baselines  
- Temporal-difference consistency reduces trajectory scatter (causal ablation: full vs nocons)  
- External 25°C testing yields tempo slopes m < 1, quantifying temperature-induced slowdown  
- Embryo-level bootstrap confidence intervals provide rigorous uncertainty for Δm

## 3) Install
```bash
pip install -r requirements.txt
```

(Optional) conda:
```bash
conda env create -f environment.yml
conda activate embryo-tempoformer
```

## 4) Option B: Zenodo FULL processed (download → verify → extract → run)
We recommend a Zenodo bundle containing **FULL processed arrays + checkpoints + splits + integrity checks**.

- Zenodo DOI: **https://doi.org/10.5281/zenodo.18318139**
- Recommended bundle filename: `embryo-tempoformer_release_v1_full.tar.gz`

### 4.1 Download
Download the archive from the Zenodo record page:
- https://doi.org/10.5281/zenodo.18318139

After download you should have:
- `embryo-tempoformer_release_v1_full.tar.gz`

### 4.2 Verify (recommended)
```bash
ls -lh embryo-tempoformer_release_v1_full.tar.gz
tar -tzf embryo-tempoformer_release_v1_full.tar.gz | head -n 20
```

### 4.3 Extract
```bash
tar -xzf embryo-tempoformer_release_v1_full.tar.gz
```

The archive extracts to:
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

(Optional) full checksum verification:
```bash
cd embryo-tempoformer_release_v1
sha256sum -c SHA256SUMS.txt
cd ..
```

### 4.4 Configure the repo and run (quantitative reproduction)
1) Clone and install:
```bash
git clone <GITHUB_REPO_URL>
cd s-biad531-embryo-tempoformer
pip install -r requirements.txt
```

2) Configure `.env` (Linux `sed -i`; on macOS use `sed -i ''` or edit manually):
```bash
cp .env.example .env

REL=/ABS/PATH/TO/embryo-tempoformer_release_v1

sed -i "s|^PROC_28C5=.*|PROC_28C5=$REL/processed_28C5|" .env
sed -i "s|^PROC_25C=.*|PROC_25C=$REL/processed_25C|" .env
sed -i "s|^SPLIT_28C5=.*|SPLIT_28C5=$REL/splits/28C5.json|" .env
sed -i "s|^SPLIT_25C=.*|SPLIT_25C=$REL/splits/25C.json|" .env

sed -i "s|^CKPT_CNN_SINGLE=.*|CKPT_CNN_SINGLE=$REL/checkpoints/cnn_single_best.pt|" .env
sed -i "s|^CKPT_MEANPOOL=.*|CKPT_MEANPOOL=$REL/checkpoints/meanpool_best.pt|" .env
sed -i "s|^CKPT_NOCONS=.*|CKPT_NOCONS=$REL/checkpoints/nocons_best.pt|" .env
sed -i "s|^CKPT_FULL=.*|CKPT_FULL=$REL/checkpoints/full_best.pt|" .env
```

3) Verify paths:
```bash
bash scripts/00_check_env.sh
```

4) One-command reproduction (infer → aggregate → CI/power → figures):
```bash
bash scripts/reproduce_all.sh
```

The script prints the output root directory (OUTROOT), e.g.:
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

Final figures:
- `runs/paper_eval_YYYYMMDD_HHMMSS/figures_jobs/` (PNG + PDF)

## 5) (Optional) Saliency (SmoothGrad)
Saliency is qualitative (supplement) and slow; it is not run by default.

### 5.1 Run saliency within the full pipeline
```bash
RUN_SALIENCY=1 bash scripts/reproduce_all.sh
```

Optionally choose the model for saliency (default: `full`):
```bash
RUN_SALIENCY=1 SALIENCY_MODEL=full bash scripts/reproduce_all.sh
# also supports: nocons / meanpool / cnn_single
```

### 5.2 Standalone saliency
```bash
bash scripts/50_saliency_best_id28c5.sh
```

## 6) Key outputs
Key outputs under `runs/paper_eval_*/`:
- per-embryo `json/*.json`
- aggregated `points.csv`, `embryo.csv`, `summary.json`
- bootstrap `CI_*.json`
- final figures in `figures_jobs/` (PNG+PDF)

## 7) License
MIT (see LICENSE).
```