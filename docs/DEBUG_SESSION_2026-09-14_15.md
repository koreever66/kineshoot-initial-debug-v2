# Kin Shoot IMU 调试报告

日期：2026-09-14 至 2026-09-15

## 一、本次目标

从最初的 ESP32-S3 与 ICM-20948 硬件摸底版本出发，完成以下工作：

1. 解决 I2C 地址和通信不稳定问题。
2. 建立可重复的高速采样固件。
3. 扩大加速度和角速度量程，避免动作削顶。
4. 解决采集过程中 Flash 写入造成的采样停顿。
5. 实现充电宝供电、按键触发、本地 Flash 记录和 USB 导出。
6. 完成静止、动态和模拟投篮测试。
7. 记录数据、错误、原因、修复过程和剩余风险。

## 二、最终工作配置

### 硬件

```text
ESP32-S3-DevKitC-1，N16R8
ICM-20948
充电宝 5V USB 供电
USB-C 数据线用于烧录和导出
```

### I2C 接线

```text
ICM VCC  -> ESP32 3V3
ICM GND  -> ESP32 GND
ICM SCLK -> ESP32 GPIO9
ICM SDI  -> ESP32 GPIO8
ICM NCS  -> ESP32 3V3
ICM AD0  -> ESP32 GND
```

说明：

- ICM 模块上的 `SCLK` 在 I2C 模式下等价于 `SCL`。
- `SDI` 在 I2C 模式下等价于 `SDA`。
- `NCS` 接高电平用于确定 I2C 模式。
- `AD0` 接低电平用于固定地址 `0x68`。

### Arduino IDE

```text
Board: ESP32S3 Dev Module
Port: COM5
Upload Speed: 921600
Flash Size: 4MB
Partition Scheme: Default 4MB with spiffs
USB CDC On Boot: Enabled
USB Mode: Hardware CDC and JTAG
```

## 三、调试过程

### 1. 初始数据复查

对原始三组数据进行了统计分析：

```text
imu_20260913_192923.csv
rows=36
duration=3.640 s
状态：后续出现极端值和错误温度，数据不可用

imu_20260913_193817.csv
rows=201
duration=4.401 s
状态：有效动作，但在 -2000 mg 和 -250.14 dps 附近削顶

imu_20260913_194905.csv
rows=842
duration=30.005 s
状态：发生 10.993 s 数据中断，随后出现固定异常值和传感器复位特征
```

关键分析：

- 初始固件使用 SparkFun 默认 `+/-2g` 和 `+/-250dps`。
- 动作峰值已经触及默认量程。
- `delay(20)` 将采样率限制在约 50 Hz。
- 绘图脚本直接连接长时间缺口，造成视觉上的线性漂移假象。

### 2. I2C 扫描与地址问题

现象：

```text
0x68、0x69、0x0C 交替出现
Trying AD0_VAL=0 status=Data Underflow
Trying AD0_VAL=1 status=Data Underflow
```

原因分析：

- `Data Underflow` 在库中对应 `NoData`，本质是读取没有获得完整字节。
- AD0 未明确固定，地址会漂移。
- 杜邦线、面包板和连接器在移动中会产生间歇性接触。
- NCS 悬空会让接口模式不够确定。

修复：

- SCLK/SDI 改接到 GPIO9/GPIO8。
- NCS 固定接 3V3。
- AD0 固定接 GND。
- I2C 先使用 50 kHz 验证稳定性。
- 重新执行扫描，最终稳定为 `0x68`。
- WHO_AM_I 连续读取结果为 `0xEA`。

### 3. 串口无输出问题

现象：

```text
串口监视器完全空白
```

原因：

- `USB CDC On Boot` 被设置为 `Disabled`。

修复：

- 将其改为 `Enabled`。
- 上传 `serial_probe.ino` 后稳定输出：

```text
SERIAL_PROBE_READY
SERIAL_PROBE_ALIVE,ms=1000
SERIAL_PROBE_ALIVE,ms=2000
```

### 4. v2 高速串口采集

主要改动：

- 固定地址 `0x68`。
- I2C `50kHz`。
- 加速度 `+/-16g`。
- 陀螺仪 `+/-2000dps`。
- 加速度 DLPF `111.4Hz`。
- 陀螺仪 DLPF `119.5Hz`。
- ODR 约 `220-225Hz`。
- 串口 `230400`。
- 仅读取加速度、角速度和温度，不再读取磁力计。
- 使用微秒时间戳和采样序号。

30 秒静止结果：

```text
rows                    6645
duration                30.001 s
sample rate             221.46 Hz
median interval         4.515 ms
p95 interval            4.528 ms
maximum interval        4.603 ms
gaps >= 20ms            0
sequence discontinuities 0
errors                  0
resets                  0
clipped samples         0
gravity mean            1012.46 mg
temperature             33.06-34.21 C
```

### 5. v3 本地 Flash 记录

目标：

- 使用充电宝供电。
- 短按 BOOT 开始记录。
- 10 秒数据写入 LittleFS。
- 重新连接 USB 后导出。

遇到问题：

```text
Corrupted dir pair at {0x0, 0x1}
LittleFS mount failed
```

修复：

- 先尝试正常挂载。
- 挂载失败时执行 `LittleFS.format()`。
- 格式化后重新挂载。

v3 记录结果：

```text
rows                    2094
duration                10.004 s
sample rate             209.3 Hz
errors                  0
resets                  0
write failures          0
```

v3 问题：

```text
gaps >= 20ms            31
largest gap             52.659 ms
```

原因：

- v3 每采一个点就写入 Flash。
- LittleFS 周期性写入阻塞了采样循环。

### 6. v4 RAM 缓冲记录

主要改动：

- 10 秒采样期间只保存到 RAM。
- 采样结束后一次性写出 CSV。
- 静态 RAM 缓冲大小约为 2700 个原始样本。
- 文件导出协议与 v3 保持一致。

v4 静止结果：

```text
rows                    2269
duration                9.9959 s
sample rate             226.89 Hz
median interval         4.049 ms
p95 interval            5.795 ms
maximum interval        5.844 ms
gaps >= 10ms            0
gaps >= 20ms            0
sequence discontinuities 0
errors                  0
resets                  0
write failures          0
```

结论：

- RAM 缓冲消除了记录期间的 Flash 写入停顿。

### 7. 导出失败问题

现象：

```text
TimeoutError: Timed out with 92530 bytes remaining in the download.
```

原因：

- 无绳运行时为了避免串口阻塞，发送超时被设置为 0。
- 导出大文件时 USB 缓冲溢出，部分字节被丢弃。

修复：

- 正常运行保持非阻塞。
- 执行 `DUMP` 时临时设置为阻塞发送。
- 每发送 256 字节增加 1 ms 间隔。
- 下载结束后恢复非阻塞。
- 主机端下载超时提高到 30 秒。

### 8. 下载模式问题

现象：

```text
boot:0x0 (DOWNLOAD(USB/UART0))
waiting for download
```

原因：

- 在复位或上电时 BOOT/GPIO0 为低电平。
- 常见于用户按住 BOOT 时连接电脑或复位。

处理：

- 运行状态下短按 BOOT 不会进入下载模式。
- 连接电脑和复位之前必须松开 BOOT。
- 如果已经进入下载模式，松开 BOOT 后按一次 RST。

### 9. 文件系统满盘

现象：

```text
No more free space
write_failed=1
```

原因：

- LittleFS 总空间约 1.44 MB。
- 单份 10 秒记录约 130-140 KB。
- 多份记录累积后耗尽空间。

修复：

- 导出工具改为下载到电脑成功后删除 ESP32 远程文件。
- v4 开始记录前检查最低 220 KB 剩余空间。
- 写盘失败时删除半成品文件。
- 分别报告采样行数和实际写入行数。

### 10. 线缆脱落

现象：

- 第三次剧烈模拟动作后，ICM VCC 连接脱落。
- 重新连接后再次触发记录，生成了只有表头、0 行数据的 `capture_010.csv`。

原因：

- 手持设备和线束没有机械固定。
- 连接头直接承受动作惯性。

处理：

- 删除空文件。
- 后续加强测试降低到可控动作范围。
- 明确要求先完成硬质底板、扎带和应力释放。

## 四、关键错误与修复汇总

| 问题 | 原因 | 修复 |
|---|---|---|
| Data Underflow | 地址漂移、接触不良、NCS/AD0 不确定 | 固定 NCS/AD0，降低 I2C 时钟，重新验证 WHO_AM_I |
| 地址 0x68/0x69/0x0C 交替 | AD0 悬空、线材接触 | AD0 接 GND，稳定为 0x68 |
| v1 动作削顶 | 默认 +/-2g 和 +/-250dps | v2 改为 +/-16g 和 +/-2000dps |
| v1 采样率低 | delay(20) | v2 使用 dataReady，目标约 225Hz |
| 串口空白 | USB CDC On Boot Disabled | 改为 Enabled |
| LittleFS mount failed | 目录损坏 | 自动格式化并重新挂载 |
| 长时采样停顿 | 每样本写 Flash | v4 改为 RAM 缓冲后批量写入 |
| 导出超时 | 非阻塞串口丢字节 | DUMP 期间切换阻塞发送并限速 |
| 进入下载模式 | 复位时 BOOT 为低 | 松开 BOOT 后按 RST |
| 空文件/半文件 | 文件系统满 | 下载后清理，记录前检查空间，失败删除半成品 |
| VCC 脱落 | 缺少机械固定 | 必须使用硬质底板和应力释放 |

## 五、有效数据索引

### v2 串口采集

```text
imu_v2_20260914_232426.csv
imu_v2_20260914_233222.csv
imu_v2_20260914_233240.csv
```

### v4 Flash 数据

```text
flash_v4_test_002.csv
flash_v4_untethered_003.csv
flash_v4_button_004.csv
flash_v4_handheld_005.csv
flash_v4_sim_shot_006.csv
flash_v4_shot_trial_007.csv
flash_v4_shot_trial_008.csv
flash_v4_shot_trial_009.csv
flash_v4_static_retest_001.csv
flash_v4_strength_retest_002.csv
```

对应的详细指标见 `docs/DATA_INDEX.md`。

## 六、难点与经验

### 难点 1：地址扫描通过但初始化失败

地址应答只证明设备 ACK，不证明寄存器读取稳定。最终通过 WHO_AM_I 和长时间采样确认链路。

### 难点 2：通信故障与机械故障混在一起

总线错误、供电瞬断、连接器松动和数据越界会产生相似现象。处理顺序必须是：

```text
机械连接
-> 供电
-> 地址
-> WHO_AM_I
-> 长时间静止采样
-> 动作测试
```

### 难点 3：Flash 写入与高采样率冲突

文件系统写操作会周期性阻塞。高采样率数据必须先进入 RAM，记录结束后再批量写入。

### 难点 4：无绳运行与 USB 导出需求冲突

无绳运行要求串口发送不能阻塞；导出又要求不能丢字节。最终按模式切换串口发送策略。

### 难点 5：缺少机械固定

软件已经能够稳定运行，但手持结构无法承受真实投篮惯性。机械固定已经成为下一阶段的首要问题。

## 七、当前结论

- I2C 地址、WHO_AM_I、高速采样、Flash 记录和 USB 导出均已打通。
- v4 在静态和中等强度动作下没有采样缺口、复位或削顶。
- 当前量程在上次最大模拟动作中仍有约一半余量。
- 真实投篮前必须完成硬质底板固定和线束应力释放。
- 导出工具现在会在下载成功后自动清理 ESP32 文件，避免再次满盘。

## 八、下一步

1. 将 ESP32 和 ICM 固定在同一块硬质底板上。
2. 对 VCC、GND、SDA、SCL 和 USB 线分别做应力释放。
3. 完成一次 10 秒静止验证。
4. 完成一次中等强度模拟投篮。
5. 确认没有缺口、复位和削顶后，再进行真实投篮。
6. 对齐视频或外部动作标记，进行后续发力链分析。
