# 数据索引

本文件记录仓库内实机数据的用途和关键指标。原始文件位于 `data/`。

## 初始硬件摸底

| 文件 | 行数 | 时长 | 状态 |
|---|---:|---:|---|
| `imu_20260913_192923.csv` | 36 | 3.640 s | 无效，极端值和错误温度 |
| `imu_20260913_193817.csv` | 201 | 4.401 s | 有效动作，但发生默认量程削顶 |
| `imu_20260913_194905.csv` | 842 | 30.005 s | 包含 10.993 s 中断和固定异常值 |

## v2 串口稳定采集

| 文件 | 行数 | 时长 | 采样率 | 最大间隔 | 结果 |
|---|---:|---:|---:|---:|---|
| `imu_v2_20260914_232426.csv` | 6645 | 30.001 s | 221.46 Hz | 4.603 ms | 静止通过 |
| `imu_v2_20260914_233222.csv` | 1124 | 4.999 s | 224.62 Hz | 6.542 ms | 小幅动态通过 |
| `imu_v2_20260914_233240.csv` | 1119 | 4.988 s | 224.12 Hz | 6.707 ms | 小幅动态通过 |

## v3 本地 Flash 对照

| 文件 | 行数 | 时长 | 采样率 | 最大间隔 | 结果 |
|---|---:|---:|---:|---:|---|
| `flash_v3_test_001.csv` | 2094 | 9.999 s | 209.32 Hz | 52.659 ms | 有 31 个超过 20 ms 的写入缺口 |

## v4 RAM 缓冲与无绳记录

| 文件 | 行数 | 时长 | 采样率 | 最大间隔 | 结果 |
|---|---:|---:|---:|---:|---|
| `flash_v4_test_002.csv` | 2269 | 9.996 s | 226.89 Hz | 5.844 ms | 静止通过 |
| `flash_v4_untethered_003.csv` | 2270 | 9.998 s | 226.93 Hz | 5.874 ms | 充电宝和按键通过 |
| `flash_v4_button_004.csv` | 2269 | 9.997 s | 226.88 Hz | 6.396 ms | USB 按键复测通过 |
| `flash_v4_handheld_005.csv` | 2270 | 9.999 s | 226.93 Hz | 6.286 ms | 链路通过，动作主要落在前 1.2 s |
| `flash_v4_sim_shot_006.csv` | 2270 | 9.999 s | 226.93 Hz | 5.932 ms | 首组有效模拟投篮 |
| `flash_v4_shot_trial_007.csv` | 2269 | 9.997 s | 226.88 Hz | 6.335 ms | 强动作，角速度峰值 1033.02 dps |
| `flash_v4_shot_trial_008.csv` | 2269 | 9.994 s | 226.93 Hz | 5.844 ms | 中等动作，角速度峰值 235.13 dps |
| `flash_v4_shot_trial_009.csv` | 2269 | 9.998 s | 226.84 Hz | 6.322 ms | 有效，动作后发生电源线脱落 |
| `flash_v4_static_retest_001.csv` | 2269 | 9.997 s | 226.88 Hz | 6.244 ms | 清盘后的静止复测 |
| `flash_v4_strength_retest_002.csv` | 2269 | 9.997 s | 226.88 Hz | 6.357 ms | 加强动作复测 |

## 无效或截断数据

| 文件/记录 | 问题 | 处理 |
|---|---|---|
| 早期 `capture_010.csv`，0 行 | 电源线脱落后初始化失败 | 已从设备删除 |
| 早期 `capture_011.csv`，822 行 | 文件系统满，写盘失败 | 已导出分析并从设备删除 |

## 2026-09-16 六轮稳定性复测

目录：

```text
data/raw/20260916/
```

六轮均使用 H1 六线直连、5V 充电宝和 F4 固件。

| 文件 | 行数 | 采样率 | 最大间隔 | 结果 |
|---|---:|---:|---:|---|
| `stability_run01_round01.csv` | 2269 | 226.846 Hz | 5.908 ms | 通过 |
| `stability_run01_round02.csv` | 2269 | 226.854 Hz | 5.844 ms | 通过 |
| `stability_run01_round03.csv` | 2269 | 226.882 Hz | 6.110 ms | 通过 |
| `stability_run01_round04.csv` | 2269 | 226.877 Hz | 6.350 ms | 通过 |
| `stability_run01_round05.csv` | 2269 | 226.893 Hz | 5.844 ms | 通过 |
| `stability_run01_round06.csv` | 2270 | 226.931 Hz | 5.992 ms | 通过 |

六轮均无超过 10ms 的缺口、无序号跳变、无全零、无固定饱和、无削顶、无复位。

### 三组小幅动态复测

数据来源：

```text
power_source = computer_usb
trigger_source = serial_start
```

| 文件 | 行数 | 采样率 | 最大间隔 | 角速度峰值 | 结果 |
|---|---:|---:|---:|---:|---|
| `dynamic_run01_round01.csv` | 2269 | 226.877 Hz | 6.360 ms | 263.49 dps | 通过 |
| `dynamic_run01_round02.csv` | 2269 | 226.854 Hz | 5.902 ms | 356.54 dps | 通过 |
| `dynamic_run01_round03.csv` | 2270 | 226.940 Hz | 5.843 ms | 388.66 dps | 通过 |

三组均无缺口、序号跳变、复位、全零、固定饱和和削顶。

### 充电宝与 BOOT 验证

```text
power_source = power_bank
trigger_source = boot_button
```

文件：

```text
powerbank_boot_run01_round01.csv
powerbank_boot_run01_round02.csv
powerbank_boot_run01_round03.csv
```

三份文件均成功写入，无采样缺口、复位或通信错误。但 2-5 秒动作窗口内没有明显运动，因此这组数据只用于验证充电宝供电和 BOOT 触发，不用于动态分析。

### 充电宝 BOOT 动作第二轮

| 文件 | 行数 | 采样率 | 最大间隔 | 角速度峰值 | 加速度模长峰值 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| `powerbank_boot_motion_run02_round01.csv` | 2269 | 226.886 Hz | 5.844 ms | 175.98 dps | 1315.89 mg | 通过 |
| `powerbank_boot_motion_run02_round02.csv` | 2270 | 226.924 Hz | 6.335 ms | 271.98 dps | 1530.47 mg | 通过 |
| `powerbank_boot_motion_run02_round03.csv` | 2269 | 226.888 Hz | 5.844 ms | 466.36 dps | 3270.16 mg | 通过 |

第二组为上肢完整投篮动作，第三组为站立起跳投篮。两组均回到起始姿势，所有记录无缺口、复位、全零、固定饱和或削顶。

### 五组静止对照 Run 02

| 文件 | 行数 | 采样率 | 最大间隔 | 1 秒后角速度均值 | 结果 |
|---|---:|---:|---:|---:|---|
| `static_control_run02_round01.csv` | 2269 | 226.845 Hz | 5.982 ms | 1.543 dps | 通过 |
| `static_control_run02_round02.csv` | 2270 | 226.924 Hz | 6.331 ms | 1.422 dps | 通过 |
| `static_control_run02_round03.csv` | 2270 | 226.934 Hz | 5.844 ms | 1.483 dps | 通过 |
| `static_control_run02_round04.csv` | 2270 | 226.939 Hz | 5.844 ms | 1.347 dps | 通过 |
| `static_control_run02_round05.csv` | 2270 | 226.927 Hz | 6.228 ms | 1.227 dps | 通过 |

五组均无缺口、序号跳变、复位、全零、固定饱和和削顶。

### 动作速度对照 Run 03

| 文件 | 动作 | 采样率 | 最大间隔 | 角速度峰值 | 加速度模长峰值 | 结果 |
|---|---|---:|---:|---:|---:|---|
| `comparison_run03_static.csv` | 静止 | 226.890 Hz | 5.844 ms | 90.82 dps | 1058.76 mg | 通过 |
| `comparison_run03_slow.csv` | 偏慢 | 226.878 Hz | 6.166 ms | 198.50 dps | 1353.99 mg | 通过 |
| `comparison_run03_medium.csv` | 适中 | 226.877 Hz | 6.251 ms | 425.75 dps | 2045.14 mg | 通过 |
| `comparison_run03_fast.csv` | 偏快 | 226.916 Hz | 6.266 ms | 433.32 dps | 2308.26 mg | 通过 |

四份记录均无缺口、复位、全零、固定饱和和削顶。

## 主要动作峰值

| 数据 | 角速度模长峰值 | 加速度模长峰值 | 削顶 |
|---|---:|---:|---|
| `flash_v4_sim_shot_006.csv` | 196.22 dps | 2378.96 mg | 否 |
| `flash_v4_shot_trial_007.csv` | 1033.02 dps | 6715.93 mg | 否 |
| `flash_v4_shot_trial_008.csv` | 235.13 dps | 2074.91 mg | 否 |
| `flash_v4_shot_trial_009.csv` | 311.07 dps | 1988.86 mg | 否 |
| `flash_v4_strength_retest_002.csv` | 187.33 dps | 1465.84 mg | 否 |
