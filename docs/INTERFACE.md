# 硬件与软件接口

接口版本：I1

## 电气连接

```text
ESP32-S3 GPIO8  <-> ICM-20948 SDI / SDA
ESP32-S3 GPIO9  <-> ICM-20948 SCLK / SCL
ESP32-S3 3V3    <-> ICM-20948 VCC
ESP32-S3 GND    <-> ICM-20948 GND
ESP32-S3 3V3    <-> ICM-20948 NCS
ESP32-S3 GND    <-> ICM-20948 AD0
```

固定参数：

```text
I2C address: 0x68
I2C clock:   50 kHz
WHO_AM_I:    0xEA
```

## 电源

```text
充电宝 5V -> 电源开关 -> ESP32 5V
充电宝 GND -> ESP32 GND
```

规则：

- 开关放在 5V 电源路径，不切换 3.3V。
- 连接电脑进行烧录或导出时，断开充电宝。
- ESP32 与 ICM 的相对位置和线束必须有应力释放。
- 正式动作测试时，连接器不能承受传感器惯性拉力。

## 记录触发

```text
BOOT / GPIO0: 运行状态下短按，开始 10 秒本地记录
RST / EN:     上电或复位前必须松开 BOOT
```

## 板载指示

```text
红色电源灯: 不可控，仅表示供电
RGB LED:    WS2812B，GPIO48
```

无绳测试建议：

```text
蓝色: 固件运行，等待记录
红色: 正在记录
绿色: 写盘成功
```

## 软件契约

硬件版本变化时需要同步提供：

```text
hardware_revision
wiring diagram
mount_position
connector type
power path
strain relief method
assembly photo
known risks
```

软件侧承诺：

```text
固定地址 0x68
固定量程 +/-16g 和 +/-2000dps
约 220-225 Hz 采样
10 秒本地记录
CSV + meta + event 文件
```

## 修改规则

- 修改引脚、地址、电压或接口器件时，接口版本必须递增。
- 禁止在 `main` 上直接修改接口文件。
- 硬件对话只修改 `hardware/` 和 `docs/hardware/`。
- 软件对话只修改 `firmware/`、`tools/`、`data/` 和 `docs/software/`。
- 共同修改 `docs/INTERFACE.md` 时，必须说明原因并同步更新版本号。
