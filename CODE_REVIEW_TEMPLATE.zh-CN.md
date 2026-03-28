# EmbryoTempoFormer 代码审查模板

适用于本仓库的 PR、分支审查和合并前检查。
审查时优先关注正确性、可复现性、数据切分卫生和统计有效性，而不是只提风格问题。

## 审查元信息

| 字段 | 内容 |
| --- | --- |
| 审查对象 | |
| 分支 / PR | |
| Commit / tag | |
| 审查人 | |
| 日期 | |
| 审查类型 | PR / 本地分支 / release / hotfix |

## 变更摘要

- 改了什么？
- 为什么改？
- 影响的是哪个流水线阶段？
  `src/` 模型代码 / `analysis/` Python 流水线 / `scripts/` shell 入口 / split 或数据工具 / 图表或 summary

## 问题列表

按严重程度排序列出问题。给出文件引用，并明确说明具体风险。

| 严重级别 | 文件 / 模块 | 问题 | 影响 | 建议修改 |
| --- | --- | --- | --- | --- |
| P0 | | | 阻断正确性或可复现性 | |
| P1 | | | 高概率 bug / 结论无效 / 数据泄漏风险 | |
| P2 | | | 可维护性 / 健壮性 / 可移植性风险 | |
| P3 | | | 次要问题或后续优化 | |

严重级别建议：
- `P0`：结果无效、流水线跑不通、train/test 泄漏、破坏性输出变更
- `P1`：较可能的科学或工程 bug、错误指标、错误聚合、隐性回归
- `P2`：健壮性、清晰度、可移植性或性能风险
- `P3`：可选清理项或后续跟进项

## 项目专用检查清单

每项填写 `Yes`、`No` 或 `N/A`。

### 1. 可复现性与环境

- [ ] 没有在本地 `.env` 之外引入新的机器相关绝对路径
- [ ] 新增环境变量已同步到 `.env.example`，必要时有文档说明
- [ ] 输出仍然落在 `runs/` 下，而不是写死到外部目录
- [ ] 命令仍能从 repo root 相对路径正常运行
- [ ] 依赖变更已同步到 `requirements.txt`、`environment.yml` 或两者

### 2. 数据完整性与切分卫生

- [ ] train / val / test 边界没有被破坏
- [ ] embryo ID 在预处理、切分、推理和聚合过程中保持一致
- [ ] split JSON 的假设仍与 `split/README.md` 一致
- [ ] 可选外部域 `S-BIAD840` 逻辑仍与主论文复现流程隔离，除非这是明确目标
- [ ] 没有误提交 processed data、checkpoints 或 `runs/` 产物

### 3. 时间轴与生物学假设

- [ ] `DT_H`、`T0_HPF`、`CLIP_LEN`、`IMG_SIZE`、`EXPECT_T`、`STRIDE` 仍然相互一致
- [ ] 任何时间轴假设变更都已传播到下游分析和文档
- [ ] checkpoint 假设仍与 processed array 形状和 inference 设置匹配
- [ ] anchor 或分期逻辑变更有充分理由，并已反映到 summary / figures

### 4. 统计有效性

- [ ] 推断结论仍然是 embryo-level，而不是 point-level 伪重复
- [ ] 聚合仍正确区分 `points.csv`、`embryo.csv` 和 `summary.json`
- [ ] bootstrap / CI / power 计算仍作用于正确的统计单元
- [ ] 指标修改在科学上可解释，没有悄悄改变论文结论

### 5. 模型与推理正确性

- [ ] `preprocess`、`make_split`、`train`、`eval`、`infer` 的 CLI 行为保持一致
- [ ] EMA / AMP / device / batch-size 逻辑仍有合理默认值
- [ ] memory profile 的变更没有悄悄改变语义
- [ ] JSON 输出 schema 向后兼容；若破坏兼容性，已明确记录

### 6. 流水线编排

- [ ] `scripts/` 包装层与 `analysis/run_reproduction_pipeline.py` 保持同步
- [ ] `RUN_CONTINUOUS_POWER`、`RUN_CLIPLEN_SENSITIVITY`、`RUN_SALIENCY` 等可选开关行为仍与文档一致
- [ ] 步骤顺序仍符合预期复现流程
- [ ] 对缺失 env、缺失文件或 subprocess 失败仍然保持 fail-fast

### 7. 图表、表格与输出契约

- [ ] 输出文件名和目录结构保持稳定，除非是明确版本化调整
- [ ] 下游 figure 或 summary 脚本仍能找到预期输入文件
- [ ] 任何重命名输出都已同步到 README 或 release 说明
- [ ] 仅用于本地检查的生成产物没有被提交

## 已执行验证

只记录实际跑过的检查，不写“理论上应该跑什么”。

| 检查项 | 命令 / 方法 | 结果 |
| --- | --- | --- |
| 环境检查 | `bash scripts/00_check_env.sh` | |
| 目标脚本 | | |
| 目标 Python 模块 | | |
| 变更路径 smoke test | | |
| 全流程复现 | | |

## 审查备注

### 未决问题

- 

### 风险总结

- 科学风险：
- 可复现性风险：
- 工程风险：

## 审查结论

- [ ] Approve
- [ ] Request changes
- [ ] Comment only

## 简短总结

用 3 到 6 行总结：
- 这次修改是否适合合并
- 最高优先级问题是什么
- 你实际验证了什么
- 还剩下哪些不确定性
