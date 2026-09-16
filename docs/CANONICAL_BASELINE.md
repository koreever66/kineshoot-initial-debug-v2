# Kineshoot 统一基线

基线编号：KB-2026-09-15-H1-F4-I1

状态：冻结

本文件是两个对话共同使用的唯一基准。若硬件设计、引脚、I2C 地址或软件协议与本文冲突，以本文为准，除非双方明确批准新的版本号。

## 一、基线原则

```text
软件定义接口和数据格式
硬件负责实现、固定和验证
硬件不能静默修改软件依赖的地址、引脚、电压或协议
```

任何接口变化必须：

1. 提交变更原因。
2. 更新 `docs/INTERFACE.md`。
3. 更新 `project.json`。
4. 增加接口或软件版本号。
5. 重新完成静止和动态验收。

## 二、硬件基线 H1

```text
ESP32-S3-DevKitC-1，N16R8
ICM-20948
六线直连
充电宝 5V 供电
USB-C 数据口用于烧录和导出
```

板载接口补充：

```text
BOOT       = GPIO0
RST        = 硬件复位
RGB LED    = WS2812B，GPIO48
电源红灯   = 不可控，仅表示供电
USB-C 接口 = CH340 串口口 + 原生 USB-OTG 口
```

测试规则：

- 始终使用电脑识别为 `COM5` 的那个 USB-C 口进行烧录和串口调试。
- 充电宝测试优先使用同一个 USB-C 口，只改变供电源，不改变端口。
- 电源红灯亮只能说明板子有电，不能说明固件已经运行或正在记录。
- 无绳状态使用 GPIO48 的 WS2812B 提供反馈。

固定接线：

```text
ESP32 GPIO8  -> ICM SDI / SDA
ESP32 GPIO9  -> ICM SCLK / SCL
ESP32 3V3    -> ICM VCC
ESP32 GND    -> ICM GND
ESP32 3V3    -> ICM NCS
ESP32 GND    -> ICM AD0
```

固定通信参数：

```text
I2C address: 0x68
I2C clock:   50 kHz
WHO_AM_I:    0xEA
```

明确禁止：

```text
0x69 作为长期主地址
0x0C 作为 ICM 主地址
AD0 悬空
NCS 悬空
3.3V 电源路径串入拨动开关
```

H1 是功能基线，不是最终机械版本。H1 仍依赖人工防止线缆受力。

## 三、软件基线 F4

固件目录：

```text
firmware/imu_flash_logger_v4/
```

配置：

```text
加速度              +/-16g
陀螺仪              +/-2000dps
加速度 DLPF         111.4Hz
陀螺仪 DLPF         119.5Hz
加速度 ODR          约 225Hz
陀螺仪 ODR          约 220Hz
记录时长             10 秒
采样期间             RAM 缓冲
记录结束             批量写入 LittleFS
运行状态触发          短按 BOOT
串口状态             USB CDC On Boot = Enabled
```

F4 不读取磁力计，只保存：

```text
timestamp_us
ax_mg
ay_mg
az_mg
gx_dps
gy_dps
gz_dps
temp_c
```

## 四、标准操作流程

### 无绳记录

```text
1. 连接充电宝
2. 不碰 BOOT，等待约 5 秒
3. 短按 BOOT 并立即松开
4. 前 1-2 秒保持静止
5. 执行测试动作
6. 等待 10 秒记录结束
7. 再等待约 2 秒完成 Flash 写入
8. 断开充电宝
```

### 导出

```text
1. 连接电脑 USB
2. 如果进入下载模式，松开 BOOT 后按一次 RST
3. 确认 IMU_FLASH_V4_READY
4. 关闭串口监视器
5. 运行 export_capture.bat
```

导出后必须得到：

```text
capture_XXX.csv
capture_XXX.meta.json
```

元数据必须包含：

```text
hardware_revision
software_revision
interface_revision
firmware_protocol
mount_position
test_type
operator
git_sha
```

## 五、数据基准

### 静止基准

```text
data/flash_v4_static_retest_001.csv
rows                    2269
sample rate             226.88 Hz
maximum interval        6.244 ms
gaps >= 10 ms           0
errors                  0
resets                  0
```

### 加强动作基准

```text
data/flash_v4_strength_retest_002.csv
rows                    2269
sample rate             226.88 Hz
maximum interval        6.357 ms
gaps >= 10 ms           0
errors                  0
resets                  0
```

### 六轮连续性基准

```text
directory               data/raw/20260916/
rounds                  6
rows per round          2269-2270
sample rate             226.846-226.931 Hz
maximum interval        5.844-6.350 ms
gaps >= 10 ms           0
sequence discontinuities 0
errors                  0
resets                  0
```

### 三组小幅动态基准

```text
directory               data/raw/20260916/
rounds                  3
rows per round          2269-2270
sample rate             226.854-226.940 Hz
maximum interval        5.843-6.360 ms
gyro magnitude max      263.49-388.66 dps
gaps >= 10 ms           0
errors                  0
resets                  0
clipped samples         0
```

### 充电宝与 BOOT 供电验证

```text
directory               data/raw/20260916/
files                   powerbank_boot_run01_round01-03.csv
power_source            power_bank
trigger_source          boot_button
status                  power and write pass
motion status           no motion in the intended 2-5 second window
```

### 模拟投篮基准

```text
data/flash_v4_sim_shot_006.csv
data/flash_v4_shot_trial_007.csv
data/flash_v4_shot_trial_008.csv
data/flash_v4_shot_trial_009.csv
```

历史无效数据：

```text
早期 v1 数据         保留用于问题分析，不作为当前基准
v3 数据              保留用于 Flash 停顿对照
空 capture_010       已删除
截断 capture_011     保留分析副本，不作为有效数据
```

## 六、验收门槛

静止和动作测试必须全部满足：

```text
采样率 >= 200 Hz
最大采样间隔 <= 10 ms
超过 20 ms 缺口 = 0
序号跳变 = 0
错误 = 0
复位 = 0
全零段 = 0
固定饱和段 = 0
削顶样本 = 0
```

真实投篮前还要满足：

```text
ESP32 和 ICM 位于同一硬质底板
四根信号线有应力释放
USB 线不拉主板接口
电源开关不经过 3.3V
静止测试通过
动态测试通过
```

## 七、给硬件对话的固定约束

硬件代码和记录放在独立仓库：

```text
https://github.com/koreever66/kineshoot-initial-debug-v1
```

软件、接口和数据基线以本仓库为准：

```text
https://github.com/koreever66/kineshoot-initial-debug-v2
```

硬件型号、连接器和机械结构可以变化，但 H2 必须继续满足：

```text
GPIO8 = SDA
GPIO9 = SCL
NCS = 3V3
AD0 = GND
ICM VCC = 3V3
GND 共地
地址 = 0x68
```

硬件对话完成 H2 后，必须提交：

```text
硬件版本
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

## 八、版本升级规则

以下变化必须升级版本：

```text
引脚变化
I2C 地址变化
电压变化
量程变化
采样率变化
数据格式变化
文件命名变化
触发方式变化
```

机械结构调整可以不改变 I1 和 F4，但必须记录新的硬件版本，例如 H2。
