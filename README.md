下面给你一份**可直接替换**的 `README.md`（中英双份、偏 Patterns/顶刊风格、傻瓜式步骤、把你的 pipeline/输出/指标含义/外域注意事项都写清楚）。你可以原样粘贴覆盖。

---

```markdown
# EmbryoTempoFormer (S‑BIAD531)

**EmbryoTempoFormer** is a reproducible code + analysis pipeline for **clip-based developmental time prediction** and **embryo-level developmental tempo (slope) estimation** from zebrafish brightfield time‑lapse microscopy.

- **Data source:** BioImage Archive (EMBL‑EBI), accession **S‑BIAD531**  
  https://www.ebi.ac.uk/bioimage-archive/galleries/S-BIAD531.html

This repository is designed for **paper-grade reproducibility**:
- all machine-specific absolute paths are stored in a local `.env` (not committed),
- scripts run end-to-end and produce **JSON/CSV summaries + publication figures** under `runs/`.

---

# 中文说明（Chinese)

## 1. 项目做什么？
本项目用于斑马鱼亮场 time‑lapse 数据的发育时间与发育速率（tempo）量化，核心输出包括：
- **每个 clip 的发育时间预测** \(\hat{t}\)（单位 hpf）
- **胚胎级 tempo 斜率** `m_anchor`：通过对窗口点拟合关系 `y − 4.5 = m · (x − 4.5)` 得到
- **外域温度（25°C）** 下的 tempo 变化与稳定性对比
- **胚胎级 bootstrap 置信区间**（Δm 的 95% CI）
- **顶刊风格 PNG+PDF 图**（可直接插 Word）

### 为什么要强调“胚胎级”？
time‑lapse 滑窗点在同一胚胎内高度相关。我们以 **胚胎为统计独立单位**（per‑embryo 的 m），避免把窗口点当独立样本导致伪重复。

---

## 2. 目录结构（你应该关心的部分）
- `src/EmbryoTempoFormer.py`：主 CLI（preprocess / make_split / train / eval / infer）
- `analysis/aggregate_kimmel.py`：汇总 per‑embryo infer JSON → `points.csv / embryo.csv / summary.json`
- `analysis/ci_delta_m.py`：Δm embryo‑bootstrap 95% CI
- `analysis/power_curve.py`：样本效率（power）曲线（可选）
- `analysis/make_figures_jobs.py`：顶刊风格 4 张图（PNG+PDF）
- `analysis/vis_clip_saliency.py`：SmoothGrad 可解释性（可选，用于 Supplement）
- `scripts/`：傻瓜式一键脚本（从 infer 到出图）

---

## 3. 安装（最小依赖）
推荐用你自己的 conda 环境，然后安装依赖：

```bash
pip install -r requirements.txt
```

如果缺 CUDA/torch，请按你的服务器环境安装对应版本的 PyTorch。

---

## 4. 傻瓜式运行（一条命令跑完全流程）
### 4.1 配置 `.env`
把模板复制成本地配置（**不提交 git**）：

```bash
cp .env.example .env
```

编辑 `.env`，把下面这些变量改成你机器上的真实路径：
- `PROC_28C5` / `PROC_25C`：processed `.npy` 目录
- `SPLIT_28C5` / `SPLIT_25C`：split json（格式见下）
- `CKPT_*`：四个模型的 best checkpoint
- 其它参数可先保持默认

检查是否配置正确：

```bash
bash scripts/00_check_env.sh
```

### 4.2 一键复现（infer → aggregate → CI/power → figures）
```bash
bash scripts/reproduce_all.sh
```

运行完成后会生成一个时间戳目录：
- `runs/paper_eval_YYYYMMDD_HHMMSS/`

里面包含：
- 每模型/每数据集的 `json/`、`points.csv`、`embryo.csv`、`summary.json`
- `CI_*.json`、`power_*.csv/png`
- `figures_jobs/` 下的 4 张最终图（PNG+PDF）

---

## 5. Split 文件格式
`split.json` 采用：

```json
{
  "train": ["<eid1>", "<eid2>", ...],
  "val":   ["<eid...>", ...],
  "test":  ["<eid...>", ...]
}
```

其中 `eid` 是 processed 文件名去掉 `.npy` 后的 stem，例如：
`FishDev_WT_01_1_MMStack_A1-Site_0.ome`

---

## 6. 指标解释（很重要，避免误读）
### 6.1 ID 28.5°C（内测）
`summary.json` 中 `global_metrics_points.mae/rmse/r2` 可以作为点级准确度参考。

### 6.2 External 25°C（外域）
在 25°C 下，`MAE/RMSE vs y=x` 主要反映**温度导致的系统性延缓累积**，不应作为“accuracy”主结论。外域对比建议报告：
- `m_anchor`（tempo 斜率，<1 表示变慢）
- `rmse_resid`（拟合残差散布，越小越稳定）
- `max_abs_resid`（最坏离群，长尾/坏孔敏感）

---

## 7. 预处理说明（发布口径）
预处理对每帧执行 percentile 强度裁剪并将图像通过双线性插值缩放至 384×384 以统一输入尺寸。对部分贴近视野边界、存在裁切的样本，缩放插值在边界处可能强化边缘效应并引入几何形变；这类影响主要表现为残差长尾，本文以胚胎为统计单位并报告残差与置信区间以减轻其对总体结论的影响。

---

# English README

## 1. What is this repository?
This repository provides a reproducible pipeline for zebrafish brightfield time‑lapse analysis:
- **clip-level developmental time prediction** \(\hat{t}\) (hpf)
- **embryo-level tempo estimation** via an anchored fit `y − 4.5 = m · (x − 4.5)`
- external **25°C** testing vs **28.5°C** (ID)
- embryo-bootstrap uncertainty (95% CI for Δm)
- publication-ready figures (PNG + PDF)

## 2. Layout
- `src/EmbryoTempoFormer.py`: main CLI (preprocess / make_split / train / eval / infer)
- `analysis/aggregate_kimmel.py`: infer JSON → points/embryo/summary
- `analysis/ci_delta_m.py`: embryo-bootstrap CI for Δm
- `analysis/power_curve.py`: sample efficiency (optional)
- `analysis/make_figures_jobs.py`: publication figures (4 panels, PNG+PDF)
- `analysis/vis_clip_saliency.py`: SmoothGrad interpretability (optional)
- `scripts/`: one-command reproducible workflow

## 3. Install
```bash
pip install -r requirements.txt
```

## 4. One-command reproduction
### 4.1 Configure `.env`
```bash
cp .env.example .env
# edit paths in .env
bash scripts/00_check_env.sh
```

### 4.2 Run full pipeline
```bash
bash scripts/reproduce_all.sh
```

Outputs are saved under:
- `runs/paper_eval_YYYYMMDD_HHMMSS/`
including per-embryo JSONs, aggregated CSV/JSON summaries, bootstrap CI, and figures.

## 5. Split JSON format
```json
{"train":[...], "val":[...], "test":[...]}
```
IDs are file stems of processed `.npy`.

## 6. Metric notes
- **ID (28.5°C):** pointwise MAE/RMSE/R² can be interpreted as accuracy.
- **External (25°C):** MAE/RMSE vs nominal clock `y=x` primarily reflects true temperature-induced delay; the main external readouts are `m_anchor`, `rmse_resid`, and `max_abs_resid`.

## 7. Preprocessing note
Frames are percentile-clipped and resized to 384×384 via bilinear interpolation. For embryos near the field-of-view boundary, interpolation may accentuate boundary artifacts and geometric distortion; we report embryo-level summaries and residual diagnostics to mitigate the influence of rare outlier windows.
```

---

## 你接下来要做的两件“小修补”（我建议）
1) 你的 `requirements.txt` 里如果还没写：至少要有 `matplotlib`（你画图要用）  
2) README 最后建议加 “Citation / Contact / License”（你要投 Patterns，最好加一句引用方式）

如果你把你现在的 `requirements.txt` 和 `scripts/reproduce_all.sh` 内容贴我一下，我可以帮你检查“别人 clone 下来是否真的一键跑通”，以及 README 是否还缺一个关键解释（比如输出目录结构）。