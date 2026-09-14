# 对话与操作摘要

日期：2026-09-14 至 2026-09-15

本文件按时间顺序总结本次对话中的目标、操作、问题和决定。串口原始输出、CSV 数据和错误细节仍以仓库内数据文件和调试报告为准。

## 2026-09-14

### 1. 读取初始仓库

用户提供 GitHub 仓库，要求先阅读昨天的项目内容。

完成：

- 克隆 `kineshoot-initial-debug-v1`。
- 阅读 README、调试记录、固件、Python 工具和三组 CSV。
- 发现初始项目只有 ESP32-S3、ICM-20948、串口记录和第一轮数据，没有游戏主工程。

初始分析结论：

- 默认量程只有 `+/-2g` 和 `+/-250dps`。
- 采样循环被 `delay(20)` 限制在约 50 Hz。
- 长时数据中存在中断、传感器复位特征和固定异常值。
- 绘图脚本会跨越长缺口直接连线。

### 2. 制定 v2 方案

用户要求给出详细步骤。

确定方向：

- 固定 AD0。
- 固定 NCS。
- I2C 使用稳定速率。
- 量程改为 `+/-16g` 和 `+/-2000dps`。
- 启用 DLPF。
- 采样率提高到约 220-225 Hz。
- 增加状态检查、错误恢复和微秒时间戳。
- 改进采集脚本和绘图脚本。

### 3. 连通性调试

现象：

- `Data Underflow`。
- 0x68、0x69、0x0C 间歇出现。
- 串口有时完全空白。

处理：

- 检查传感器 `SCLK=SCL`、`SDI=SDA`。
- 检查 GPIO8 和 GPIO9。
- 使用 50 kHz I2C 扫描。
- 明确固定 `NCS -> 3V3`、`AD0 -> GND`。
- 将 `USB CDC On Boot` 改为 Enabled。
- 使用 WHO_AM_I 测试确认 `0xEA`。

最终链路：

```text
Address: 0x68
WHO_AM_I: 0xEA
I2C: 50kHz
```

### 4. v2 高速串口采集

完成：

- 新增 `firmware/imu_csv_logger_v2/`。
- 使用固定 `0x68`。
- 配置 `+/-16g`、`+/-2000dps`、DLPF 和约 225 Hz ODR。
- 只读取加速度、角速度和温度。
- 新增 `DATA`、`STAT`、`ERR`、`RESET` 协议。

30 秒静止结果：

```text
6645 rows, 221.46 Hz, maximum interval 4.603 ms
0 gaps, 0 errors, 0 resets, 0 clipping
gravity mean 1012.46 mg
```

### 5. 动态测试

完成两组约 5 秒小幅动作：

```text
1124 rows, 224.62 Hz
1119 rows, 224.12 Hz
```

结果：

- 无缺口、错误和复位。
- 数据能够反映小幅动作。
- 数据线长度限制正式投篮动作。

## 2026-09-15

### 6. 无绳供电方案

用户提出使用手机 USB-C 充电线连接充电宝。

结论：

- 可以无绳供电。
- 当前串口版 v2 不会在无绳状态保存数据。
- 需要实现 ESP32 本地 Flash 记录。

### 7. v3 本地 Flash 记录

完成：

- 使用 LittleFS。
- 短按 BOOT 触发 10 秒记录。
- 支持 LIST、INFO、START、DUMP、DELETE。
- 新增 `tools/flash_export.py`。

遇到的问题：

```text
Corrupted dir pair
LittleFS mount failed
```

修复：

- 挂载失败后自动格式化。
- 格式化后重新挂载。

v3 结果：

```text
2094 rows, 209.3 Hz
31 gaps over 20 ms
maximum gap 52.659 ms
```

原因：

- 每采样一次写一次 Flash，写入阻塞采样。

### 8. v4 RAM 缓冲

完成：

- 采样期间只写入 RAM。
- 10 秒结束后批量写入 CSV。
- 导出协议保持兼容。

v4 静态结果：

```text
2269 rows, 226.89 Hz
maximum interval 5.844 ms
0 gaps, 0 errors, 0 resets
```

### 9. 导出问题

现象：

```text
Timed out with 92530 bytes remaining
```

原因：

- 无绳模式串口发送超时为 0。
- 导出大文件时 USB 缓冲溢出并丢字节。

修复：

- 正常运行使用非阻塞发送。
- DUMP 文件时切换为阻塞发送。
- 每 256 字节增加短暂延时。

### 10. 下载模式和 BOOT 键

多次出现：

```text
boot:0x0 (DOWNLOAD(USB/UART0))
waiting for download
```

原因：

- 连接电脑或复位时仍按住 BOOT。

结论：

- 运行中短按 BOOT 可以安全触发记录。
- 上电和连接电脑时必须松开 BOOT。
- 已进入下载模式时，松开 BOOT 后按 RST 恢复。

### 11. 模拟投篮

完成：

- 手持动作测试。
- 第一次有效模拟投篮。
- 三组连续模拟投篮。
- 清理文件系统后的静止和加强动作复测。

有效模拟投篮峰值：

```text
capture_007: 1033.02 dps, 6715.93 mg
capture_008: 235.13 dps, 2074.91 mg
capture_009: 311.07 dps, 1988.86 mg
```

全部无削顶。

### 12. VCC 线脱落

现象：

- 第三次剧烈动作后 ICM VCC 连接脱落。
- 重新连接后产生空文件 `capture_010.csv`。

处理：

- 判断为空文件并从设备删除。
- 后续确认有效数据仍完整保存在 Flash。
- 明确指出机械固定和应力释放是下一阶段前置条件。

### 13. 文件系统满盘

现象：

```text
No more free space
write_failed=1
```

原因：

- 1.44 MB 分区被多份 10 秒数据占满。

修复：

- 导出到电脑成功后自动删除 ESP32 远程文件。
- v4 增加最低 220 KB 空间检查。
- 写盘失败时删除半成品。
- 分别报告采样行数和实际写入行数。

### 14. 清理后的复测

静止测试：

```text
2269 rows, 226.88 Hz
gyro max 1.94 dps
no gaps, no errors, no resets
```

加强动作：

```text
2269 rows, 226.88 Hz
2-6 s gyro mean 28.81 dps
gyro max 187.33 dps
acceleration max 1465.84 mg
no gaps, no errors, no resets, no clipping
```

## 当前状态

- v4 是无绳和高速记录的主版本。
- 数据文件已经导出并归档。
- 导出工具会在下载成功后清理 ESP32。
- 当前软件链路可用。
- 机械固定和真实投篮是下一阶段任务。
