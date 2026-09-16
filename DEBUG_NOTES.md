# 初版调试记录

日期：2026-09-13

## 一、目标

先完成单节点硬件验证：

```text
ESP32-S3 + ICM-20948 + USB 供电
```

验证内容包括：

- ESP32-S3 能被电脑识别和烧录
- ICM-20948 能通过 I2C 扫描到
- 能读取加速度、角速度、磁力计和温度
- 能连续保存 CSV
- 能生成第一版运动曲线

## 二、硬件连接

### 直接接线

最初验证的接法：

```text
ESP32-S3 3V3   -> ICM-20948 VCC
ESP32-S3 GND   -> ICM-20948 GND
ESP32-S3 GPIO8 -> ICM-20948 SDA
ESP32-S3 GPIO9 -> ICM-20948 SCL
```

### 面包板接线排号

调试过程中记录的排号：

```text
ESP32 3V3   = 第 42 排
ESP32 GND   = 第 64 排
ESP32 GPIO8 = 第 53 排
ESP32 GPIO9 = 第 56 排
```

```text
ICM VCC = 第 28 排
ICM GND = 第 29 排
ICM SCL = 第 30 排
ICM SDA = 第 31 排
```

注意：面包板中间断槽两边的孔不连通，插线必须和端口所在半边一致。

## 三、遇到的问题

### 问题 1：ESP32 开发板包下载失败

现象：

```text
Failed to install platform esp32:3.3.11
Connection failed
```

原因：

- Arduino IDE 从 GitHub 下载 ESP32 工具链时网络连接失败。

解决思路：

- 获取 Espressif Arduino 包索引。
- 将 GitHub 下载地址改写为乐鑫中国镜像。
- 启动本机索引服务，供 Arduino IDE 使用。
- 使用 Arduino IDE 内置的 arduino-cli 安装 ESP32 核心。

结果：

```text
esp32:esp32 3.3.11 installed
```

### 问题 2：ICM-20948 没有预焊排针

现象：

- 购买的 ICM-20948 模块排针未焊。

处理：

- 焊接 2.54mm 单排针。
- 排针保持垂直，不能倾斜。
- 使用面包板固定排针后再焊接。

结果：

- 排针焊好后模块可以插入面包板并使用杜邦线连接。

### 问题 3：I2C 扫描不到设备

现象：

```text
I2C scanner started
```

没有稳定的 `0x68` 或 `0x69`。

可能原因：

- SDA/SCL 接反。
- 排线插错面包板半边。
- VCC 或 GND 没有真正连通。
- 杜邦线或排针接触不良。
- AD0 引脚状态不稳定。

处理过程：

- 检查 `SDA`、`SCL`、`VCC`、`GND`。
- 对调 SDA/SCL 做软件和接线测试。
- 发现 `0x0C`、`0x68`、`0x69` 交替出现。
- 最终稳定使用地址 `0x69`。

结果：

```text
Found device at 0x69
```

### 问题 4：出现 Data Underflow

现象：

```text
Trying AD0_VAL=0 status=Data Underflow
Trying AD0_VAL=1 status=Data Underflow
```

分析：

- I2C 地址有响应，但寄存器读取数据不完整。
- 采集程序设置了 `Wire.setClock(400000)`，而扫描程序使用默认的约 `100kHz`。
- 面包板和杜邦线在 400kHz 下容易出现时序和接触问题。

处理：

- 将 I2C 时钟改为 `100000`。

结果：

- 采集固件已更新为 100kHz，待明天继续验证。

### 问题 5：采集过程中数据停止或饱和

现象：

- 第一次采集保存 36 行。
- 第二次采集保存 201 行，采样率约 45Hz。
- 第三次采集保存 842 行，持续 30 秒，采样率约 28Hz。
- 第三次数据最后约 5.5 秒出现固定饱和值：

```text
GX = -500.27 dps
GY = 500.26 dps
AZ = 3999.88 mg
```

分析：

- 饱和值不是正常动作数据，可能是接线松动或 I2C 通信异常。
- 杜邦线、面包板接触和 USB 线拉扯会影响数据连续性。

处理：

- 固定主板、传感器、USB 线和四根信号线。
- 移动时移动整块底板，不单独拉扯传感器。
- 固件增加错误判断，通信异常时不再写入无效数据。

结果：

- 短时间数据有效。
- 长时连续采集仍需要继续验证接线稳定性。

## 四、当前结果

已完成：

- ESP32-S3 正常烧录和串口输出
- ICM-20948 排针焊接
- I2C 地址扫描
- 获得 `0x69` 地址
- 真实加速度、角速度、磁力计和温度数据读取
- 201 行和 842 行两段采样数据
- 生成运动曲线图

尚未完成：

- 长时稳定采集
- 面包板接线完全稳定
- 正式投篮动作数据采集

## 五、下一步

1. 上传最新的 100kHz 自动地址检测固件。
2. 串口确认出现：

```text
IMU_READY
```

3. 固定传感器和线束后重新采集 30 秒。
4. 确认保存行数大于 800。
5. 确认温度正常，没有长时间固定饱和值。
6. 稳定后再进行第一次实际投篮动作采集。

## 六、2026-09-14 稳定链路复测

硬件处理：

- 改为六线直连，减少面包板和松动线材的影响。
- `NCS` 接 `3V3`，固定 I2C 模式。
- `AD0` 接 `GND`，固定地址为 `0x68`。
- SDA 接 `GPIO8`，SCL 接 `GPIO9`。
- I2C 时钟保持 `50kHz`。

通信验证：

```text
Found device at 0x68
tx=0 rx=1 who=0xEA
```

30 秒静止采集结果：

```text
rows                    6645
firmware duration       30.001 s
sample rate             221.46 Hz
median interval         4.515 ms
p95 interval            4.528 ms
maximum interval        4.603 ms
timestamp gaps >= 20ms  0
sequence discontinuities 0
errors                  0
resets                  0
clipped samples         0
gravity magnitude       1012.46 mg
gravity stdev           5.45 mg
gyro mean               below 1 dps per axis
temperature             33.06-34.21 C
```

验收结论：

- 长时读数连续性通过。
- 无固定饱和值和通信复位。
- 静止重力模长接近 `1000 mg`。
- 当前六线直连方案可作为后续动作采集基线。

原始文件：

```text
data/imu_v2_20260914_232426.csv
data/imu_v2_20260914_232426.events.log
data/imu_v2_20260914_232426.meta.json
```

两次 5 秒小幅动态测试：

```text
第一次
rows                    1124
sample rate             224.62 Hz
maximum interval        6.542 ms
timestamp gaps >= 20ms  0
errors                  0
resets                  0
clipped samples         0
gyro magnitude max      16.91 dps

第二次
rows                    1119
sample rate             224.12 Hz
maximum interval        6.707 ms
timestamp gaps >= 20ms  0
errors                  0
resets                  0
clipped samples         0
gyro magnitude max      41.11 dps
```

动作测试结论：

- 小幅运动时采样链路保持连续。
- 没有出现 v1 数据中的全零、固定饱和或传感器重启。
- 当前数据线长度只能完成桌面小幅动作测试。
- 正式投篮动作需要无绳供电和本地记录，或更长的 USB 数据线。

原始文件：

```text
data/imu_v2_20260914_233222.csv
data/imu_v2_20260914_233240.csv
```

## 七、2026-09-15 无绳 Flash 记录

v3 本地记录测试结果：

```text
rows                    2094
sampling duration       10.004 s
average sample rate     209.3 Hz
errors                  0
resets                  0
write failures          0
file size               129440 bytes
```

问题是 v3 每采样一次就写入 LittleFS，Flash 写入会周期性阻塞：

```text
gaps >= 20 ms           31
largest gap             52.659 ms
median interval         4.368 ms
p95 interval            4.443 ms
```

该方案可以保存桌面数据，但投篮峰值可能落入写入停顿。v4 改为：

- 10 秒采样期间只写入 RAM 缓冲。
- 采样结束后一次性生成 CSV 并写入 LittleFS。
- 文件导出协议保持与 v3 相同。

当前状态：

- USB CDC 串口、LittleFS、自动格式化和文件导出流程已打通。
- v4 本地记录测试通过。

v4 对照结果：

```text
rows                    2269
sampling duration       9.9959 s
average sample rate     226.89 Hz
median interval         4.049 ms
p95 interval            5.795 ms
maximum interval        5.844 ms
gaps >= 10 ms           0
gaps >= 20 ms           0
sequence discontinuities 0
errors                  0
resets                  0
write failures          0
```

v4 数据文件：

```text
data/flash_v4_test_002.csv
```

无绳与按键验证：

```text
充电宝 + BOOT 键触发
file                    capture_003.csv
rows                    2270
duration                9.9985 s
sample rate             226.93 Hz
maximum interval        5.874 ms
gaps >= 10 ms           0
gaps >= 20 ms           0
sequence discontinuities 0
errors                  0
resets                  0
clipped samples         0
```

USB 连接状态下的按键复测：

```text
file                    capture_004.csv
rows                    2269
duration                9.9967 s
sample rate             226.88 Hz
maximum interval        6.396 ms
gaps >= 20 ms           0
errors                  0
resets                  0
```

归档文件：

```text
data/flash_v4_untethered_003.csv
data/flash_v4_button_004.csv
```

当前结论：

- 充电宝供电、`BOOT` 键触发、Flash 本地记录、USB 导出已全部打通。
- v4 采样间隔不再受 Flash 写入影响。
- 可以进行传感器与 ESP32 的一体化腕部固定和首次真实投篮动作采集。

手持动态测试：

```text
file                    capture_005.csv
rows                    2270
duration                9.9988 s
sample rate             226.93 Hz
maximum interval        6.286 ms
gaps >= 10 ms           0
sequence discontinuities 0
errors                  0
resets                  0
clipped samples         0
```

动作峰值出现在：

```text
0.205 s                 gyro magnitude 16.43 dps
1.175 s                 gyro magnitude 15.33 dps
1.171 s                 gyro magnitude 15.24 dps
```

`3-10 s` 几乎没有明显动作，因此该数据用于验证无绳链路有效，但不作为模拟投篮样本。

归档文件：

```text
data/flash_v4_handheld_005.csv
```

第一组有效模拟投篮动作：

```text
file                    capture_006.csv
rows                    2270
duration                9.9986 s
sample rate             226.93 Hz
maximum interval        5.932 ms
gaps >= 10 ms           0
sequence discontinuities 0
errors                  0
resets                  0
clipped samples         0
```

动作统计：

```text
lead-in 0-1.5 s          gyro mean 3.42 dps
action 2-5 s             gyro mean 47.57 dps
action 2-5 s             gyro maximum 196.22 dps
action 2-5 s             acceleration magnitude 280.19-1665.17 mg
overall acceleration max 2378.96 mg
overall gyro max         196.22 dps
```

结论：

- 模拟投篮动作已经被清晰记录，主要峰值约为 `3.77 s`。
- 采样间隔稳定，没有 Flash 写入造成的缺口。
- 当前量程 `+/-16g` 和 `+/-2000dps` 尚有充足余量。
- 该组可作为第一份可用的模拟投篮基线数据。

归档文件：

```text
data/flash_v4_sim_shot_006.csv
```

三组连续模拟投篮：

```text
file                    capture_007.csv
rows                    2269
sample rate             226.88 Hz
maximum interval        6.335 ms
gyro magnitude max      1033.02 dps
acceleration magnitude max 6715.93 mg
clipped samples         0

file                    capture_008.csv
rows                    2269
sample rate             226.93 Hz
maximum interval        5.844 ms
gyro magnitude max      235.13 dps
acceleration magnitude max 2074.91 mg
clipped samples         0

file                    capture_009.csv
rows                    2269
sample rate             226.84 Hz
maximum interval        6.322 ms
gyro magnitude max      311.07 dps
acceleration magnitude max 1988.86 mg
clipped samples         0
```

三组均无采样缺口、序号跳变、传感器复位或削顶，已作为有效模拟投篮数据保存。

`capture_010.csv` 只有表头、0 行数据。原因是第三次动作导致传感器 VCC 连接脱落，重新接好后 ICM 没有成功恢复通信，按键再次触发时只创建了空文件。

硬件结论：

- 当前手持结构在剧烈动作下不可靠，VCC 电源线会脱落。
- 在完成机械固定和线束应力释放前，停止继续做大幅动作。

归档文件：

```text
data/flash_v4_shot_trial_007.csv
data/flash_v4_shot_trial_008.csv
data/flash_v4_shot_trial_009.csv
```

文件系统满盘测试：

```text
capture_010.csv
rows                    2269
duration                9.9945 s
sample rate             226.92 Hz
maximum interval        6.029 ms
gyro magnitude max      2.08 dps
status                  valid static capture

capture_011.csv
rows in file            822
duration                3.6185 s
gyro magnitude max      13.50 dps
status                  invalid/truncated
reason                  filesystem full during write
```

处理：

- 从 ESP32 下载并删除了 `capture_001` 到 `capture_011`，释放 `1433600` bytes。
- 导出工具改为下载成功后在 ESP32 上删除对应文件。
- v4 增加最低剩余空间检查。
- v4 写盘失败时删除半成品文件，并分别报告采样行数和实际写入行数。

清理后静止与加强测试：

```text
file                    capture_001.csv
test                    static
rows                    2269
duration                9.9965 s
sample rate             226.88 Hz
maximum interval        6.244 ms
gaps >= 10 ms           0
gyro magnitude max      1.94 dps
acceleration magnitude  974.34-1006.55 mg
errors                  0
resets                  0

file                    capture_002.csv
test                    2 s still, 2-6 s motion, 6-10 s still
rows                    2269
duration                9.9966 s
sample rate             226.88 Hz
maximum interval        6.357 ms
gaps >= 10 ms           0
gyro magnitude mean     28.81 dps during 2-6 s
gyro magnitude max      187.33 dps
acceleration magnitude max 1465.84 mg
errors                  0
resets                  0
clipped samples         0
```

结论：

- 清理文件系统后记录和导出恢复正常。
- 加强动作没有造成连接脱落、采样缺口或传感器复位。
- 仍需更可靠的机械固定后才能进行接近真实投篮强度的测试。

归档文件：

```text
data/flash_v4_static_retest_001.csv
data/flash_v4_strength_retest_002.csv
```

## 八、2026-09-16 六轮连续性复测

测试条件：

```text
H1 六线直连
5V 充电宝
F4 固件
6 轮连续无绳记录
```

结果：

| 轮次 | 行数 | 采样率 | 最大间隔 |
|---:|---:|---:|---:|
| 1 | 2269 | 226.846 Hz | 5.908 ms |
| 2 | 2269 | 226.854 Hz | 5.844 ms |
| 3 | 2269 | 226.882 Hz | 6.110 ms |
| 4 | 2269 | 226.877 Hz | 6.350 ms |
| 5 | 2269 | 226.893 Hz | 5.844 ms |
| 6 | 2270 | 226.931 Hz | 5.992 ms |

全部通过：

```text
gaps >= 10 ms           0
gaps >= 20 ms           0
sequence discontinuities 0
all-zero samples        0
clipped samples         0
resets                  0
```

前 0.5 秒的角速度峰值来自按 BOOT 时的手部扰动，第 1 秒以后六轮均恢复到约 1.1 dps 的静止水平。

数据目录：

```text
data/raw/20260916/
```

### 三组小幅动态复测

测试动作：

```text
0-2 秒：静止
2-5 秒：缓慢屈腕、旋前臂
5-10 秒：静止
```

结果：

| 轮次 | 行数 | 采样率 | 最大间隔 | 角速度峰值 | 加速度模长峰值 |
|---:|---:|---:|---:|---:|---:|
| 1 | 2269 | 226.877 Hz | 6.360 ms | 263.49 dps | 1460.23 mg |
| 2 | 2269 | 226.854 Hz | 5.902 ms | 356.54 dps | 1534.83 mg |
| 3 | 2270 | 226.940 Hz | 5.843 ms | 388.66 dps | 1286.24 mg |

三组全部通过：

```text
gaps >= 10 ms           0
sequence discontinuities 0
resets                  0
all-zero samples        0
fixed saturation        0
clipped samples         0
```

### 充电宝 + BOOT 写入验证

```text
power_source = power_bank
trigger_source = boot_button
```

结果：

- 三份文件均成功写入 LittleFS。
- 三份文件均无通信缺口、序号跳变、复位、全零、固定饱和和削顶。
- 第 2-5 秒没有明显动作，角速度约 1.1 dps。
- 角速度峰值出现在按 BOOT 后的前 0.6 秒，属于按键扰动。

结论：

```text
充电宝供电正常
BOOT 触发正常
本地写盘正常
本组不能作为动态动作数据
```

### 充电宝 BOOT 动作第二轮

结果：

| 轮次 | 动作 | 角速度峰值 | 加速度模长峰值 | 削顶 |
|---:|---|---:|---:|---|
| 1 | 辅助动作 | 175.98 dps | 1315.89 mg | 无 |
| 2 | 完整上肢投篮 | 271.98 dps | 1530.47 mg | 无 |
| 3 | 站立起跳投篮 | 466.36 dps | 3270.16 mg | 无 |

三轮均：

```text
rows                     2269-2270
sample rate              226.886-226.924 Hz
maximum interval         5.844-6.335 ms
gaps >= 10 ms            0
sequence discontinuities 0
resets                   0
all-zero samples         0
fixed saturation         0
clipped samples          0
```

该组数据可作为充电宝供电条件下的有效模拟投篮基线。

### 五组静止对照 Run 02

结果：

| 轮次 | 行数 | 采样率 | 最大间隔 | 1 秒后角速度均值 | 1 秒后角速度峰值 |
|---:|---:|---:|---:|---:|---:|
| 1 | 2269 | 226.845 Hz | 5.982 ms | 1.543 dps | 15.054 dps |
| 2 | 2270 | 226.924 Hz | 6.331 ms | 1.422 dps | 10.101 dps |
| 3 | 2270 | 226.934 Hz | 5.844 ms | 1.483 dps | 12.968 dps |
| 4 | 2270 | 226.939 Hz | 5.844 ms | 1.347 dps | 8.260 dps |
| 5 | 2270 | 226.927 Hz | 6.228 ms | 1.227 dps | 4.182 dps |

五组全部通过：

```text
gaps >= 10 ms           0
sequence discontinuities 0
resets                  0
all-zero samples        0
fixed saturation        0
clipped samples         0
```

### 动作速度对照 Run 03

```text
power_source = power_bank
trigger_source = boot_button
```

| 动作 | 行数 | 采样率 | 最大间隔 | 角速度峰值 | 加速度模长峰值 |
|---|---:|---:|---:|---:|---:|
| 静止 | 2269 | 226.890 Hz | 5.844 ms | 90.82 dps | 1058.76 mg |
| 偏慢投篮 | 2269 | 226.878 Hz | 6.166 ms | 198.50 dps | 1353.99 mg |
| 适中投篮 | 2269 | 226.877 Hz | 6.251 ms | 425.75 dps | 2045.14 mg |
| 偏快投篮 | 2269 | 226.916 Hz | 6.266 ms | 433.32 dps | 2308.26 mg |

四组均无采样缺口、复位、全零、固定饱和和削顶。速度档与峰值总体一致，偏快和适中动作的角速度峰值高于偏慢动作。

### 供电源切换后的复位规则

实测现象：

- 从电脑切换到充电宝后，红色电源灯亮，但 RGB 熄灭。
- 此时 BOOT 记录不会生效。
- 松开 BOOT 并按一次 RST 后，蓝灯恢复，记录流程正常。
- 三组动作均按蓝、红、绿、蓝状态完成。

结论：

```text
红色电源灯亮只代表有电
RGB 蓝色常亮才代表 F4 已运行
每次切换供电源后必须先按 RST
```

该规则已加入统一基线流程。
