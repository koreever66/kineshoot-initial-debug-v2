# 两个对话与三个仓库的同步流程

## 仓库职责

软件、数据和接口基线：

```text
https://github.com/koreever66/kineshoot-initial-debug-v2
```

硬件、采购、接线、结构和装配：

```text
https://github.com/koreever66/kineshoot-initial-debug-v1
```

项目介绍、PPT 和商业材料：

```text
https://github.com/koreever66/shooting-motion-chain-app
```

## 分支

软件仓库：

```text
main                 软件稳定集成版本
codex/software-data  软件、固件、采集和分析
```

硬件仓库：

```text
main                   硬件稳定版本
codex/hardware-bringup 硬件、采购、接线、结构和装配
```

## 软件仓库内容

软件对话只修改：

```text
firmware/
tools/
data/
plots/
reports/
docs/software/
docs/experiments/
project.json 中的 software_revision
```

接口基准：

```text
docs/INTERFACE.md
docs/CANONICAL_BASELINE.md
docs/SOFTWARE_PROTOCOL.md
```

## 硬件仓库内容

硬件对话只修改：

```text
hardware/
docs/hardware/
README.md
hardware revisions
采购记录
装配照片
接线和机械文件
```

硬件仓库不得复制或修改软件源码。需要引用软件基线时，记录：

```text
software_baseline_id
software_repository
software_commit
interface_revision
```

## 项目介绍仓库

`shooting-motion-chain-app` 只保存：

```text
项目介绍
商业计划
比赛材料
PPT
演示图片
```

不放入固件、原始 CSV、硬件采购明细或调试日志。

## 共同接口文件

以下文件以软件仓库为唯一版本：

```text
docs/INTERFACE.md
docs/CANONICAL_BASELINE.md
```

硬件仓库可以保存一份带提交哈希的只读快照，但不能自行修改接口定义。

## 同步顺序

软件对话开始前：

```powershell
cd kineshoot-initial-debug-v2
git fetch --all
git switch codex/software-data
git rebase origin/main
```

硬件对话开始前：

```powershell
cd kineshoot-initial-debug-v1
git fetch --all
git switch codex/hardware-bringup
git rebase origin/main
```

两个对话不要同时编辑同一个仓库中的同一个文件。出现冲突时，不强制推送，先保留双方版本并人工合并。

## 接口变更

硬件对话不能直接修改接口。确需修改时：

1. 在软件仓库创建 Issue 或提交变更说明。
2. 软件对话更新 `docs/INTERFACE.md` 和 `project.json`。
3. 软件版本或接口版本递增。
4. 软件对话推送新的基线提交。
5. 硬件仓库记录新的软件提交哈希。

## 基线标识

当前冻结基线：

```text
KB-2026-09-15-H1-F4-I1
```

版本含义：

```text
H1  六线直连硬件基线
F4  v4 RAM 缓冲本地记录固件
I1  当前引脚、地址和协议
```

基线定义位于软件仓库：

```text
docs/CANONICAL_BASELINE.md
```

## 硬件交接

硬件对话在 `kineshoot-initial-debug-v1` 完成一个版本后，必须提供：

```text
hardware_revision
接线图
连接器型号
固定方式
电源路径
开关位置
应力释放方式
实物照片
测试结果
已知风险
```

## 软件交接

软件对话在 `kineshoot-initial-debug-v2` 完成一个版本后，必须提供：

```text
software_revision
Git commit
固件目录
协议版本
采样率
量程
测试数据
数据质量结果
对硬件的约束
```

## 跨仓库引用

硬件仓库中的 `SOFTWARE_BASELINE.md` 建议记录：

```text
Baseline: KB-2026-09-15-H1-F4-I1
Software repository: koreever66/kineshoot-initial-debug-v2
Software commit: <commit sha>
Interface revision: I1
Hardware revision: H2
```

只有软件对话可以更新基线定义。硬件仓库只引用该提交，不复制源码。

## 数据同步

- `data/raw/` 中的原始数据只增加，不覆盖。
- 每个 CSV 必须配合同名 `.meta.json`。
- 数据元数据必须包含硬件版本、软件版本、接口版本和 Git SHA。
- 无效数据可以保留，但必须在 `docs/DATA_INDEX.md` 中标记。
