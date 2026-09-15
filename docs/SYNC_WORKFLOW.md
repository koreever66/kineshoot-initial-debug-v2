# 两个对话的 GitHub 同步流程

仓库：

```text
https://github.com/koreever66/kineshoot-initial-debug-v2
```

## 分支

```text
main                        稳定集成版本
codex/software-data         软件、固件、采集和分析
codex/hardware-bringup      硬件、采购、接线、结构和装配
```

## 所有权

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

硬件对话只修改：

```text
hardware/
docs/hardware/
project.json 中的 hardware_revision、mount_position
```

共同文件：

```text
docs/INTERFACE.md
docs/CANONICAL_BASELINE.md
README.md
CHANGELOG.md
```

共同文件修改后必须说明原因，并检查是否要升级接口版本。

## 同步顺序

每次开始工作前：

```powershell
git fetch --all
git rebase origin/main
```

每次完成工作后：

```powershell
git add .
git commit -m "描述本次改动"
git push
```

不要在两个对话中同时编辑同一个文件。出现冲突时，不强制推送，先保留双方版本并人工合并。

## 集成为 main

硬件或软件分支完成后：

1. 确认自己的分支只修改了职责范围内文件。
2. 确认 `docs/INTERFACE.md` 没有冲突。
3. 更新 `CHANGELOG.md`。
4. 合并到 `main`。
5. 使用基线数据重新进行静止和动态验收。

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

## 硬件交接

硬件对话完成一个版本后，必须提供：

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

软件对话完成一个版本后，必须提供：

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

## 数据同步

- `data/raw/` 中的原始数据只增加，不覆盖。
- 每个 CSV 必须配合同名 `.meta.json`。
- 数据元数据必须包含硬件版本、软件版本、接口版本和 Git SHA。
- 无效数据可以保留，但必须在 `docs/DATA_INDEX.md` 中标记。
