# 投篮发力链项目：初版硬件调试

本仓库只保存 ESP32-S3 与 ICM-20948 的硬件到货、焊接、接线、固件和第一轮数据采集内容。

不包含此前的项目计划书、商业计划、比赛报名资料和商品采购截图。

本次 v1 到 v4 的完整调试报告见：

```text
docs/DEBUG_SESSION_2026-09-14_15.md
docs/CONVERSATION_SUMMARY.md
docs/DATA_INDEX.md
docs/INTERFACE.md
docs/SOFTWARE_PROTOCOL.md
CHANGELOG.md
```

## 当前硬件

- ESP32-S3-DevKitC-1，N16R8
- ICM-20948 九轴传感器模块
- 面包板和杜邦线
- USB 数据线
- 电脑：Windows，Arduino IDE 2.3.10

## 目录

```text
firmware/imu_plotter/       串口实时曲线固件
firmware/imu_csv_logger/    CSV 数据采集固件
firmware/imu_csv_logger_v2/ 稳定接线后的 220Hz 高速采集固件
firmware/imu_flash_logger_v3/ 无绳供电时写入 Flash 的本地采集固件
firmware/imu_flash_logger_v4/ RAM 缓冲后写入 Flash 的无绳采集固件
tools/                      串口采集和 CSV 绘图脚本
data/                       原始 CSV 数据
plots/                      CSV 生成的曲线图
photos/                     焊接和面包板接线照片
DEBUG_NOTES.md              问题、解决思路和结果记录
```

## 当前结论

- ESP32-S3 能正常烧录，电脑识别端口为 `COM5`。
- ICM-20948 的 I2C 地址扫描出现过 `0x68`、`0x69` 和 `0x0C`。
- 稳定有效的 ICM-20948 地址是 `0x69`。
- 采集固件已改为自动尝试 `0x68` 和 `0x69`。
- I2C 时钟已从 `400kHz` 降到 `100kHz`，以提高面包板接线稳定性。

## 明日继续

1. 重新上传最新的 `imu_csv_logger.ino`。
2. 查看串口是否出现 `IMU_READY`。
3. 固定传感器、线束和 USB 线，避免接线松动。
4. 重新采集 30 秒数据。
5. 检查温度、采样连续性和是否出现固定饱和值。

## v2 稳定采集

使用条件：

- ICM-20948 主地址固定为 `0x68`
- `NCS` 接 `3V3`
- `AD0` 接 `GND`
- SDA 接 `GPIO8`，SCL 接 `GPIO9`

v2 固件默认配置：

- I2C：`50kHz`
- 加速度：`+/-16g`
- 陀螺仪：`+/-2000dps`
- 加速度 DLPF：`111.4Hz`
- 陀螺仪 DLPF：`119.5Hz`
- ODR：约 `220-225Hz`
- 串口：`230400`

采集 30 秒：

```powershell
python -m pip install -r tools\requirements.txt
python tools\serial_logger.py --port COM5 --baud 230400 --seconds 30 --output data
```

采集 5 秒动作压力测试：

```powershell
python tools\serial_logger.py --port COM5 --baud 230400 --seconds 5 --output data
```

绘图与质量检查：

```powershell
python tools\plot_imu_csv.py data\imu_v2_YYYYMMDD_HHMMSS.csv
```

采集脚本会同时生成 `.events.log` 和 `.meta.json`；绘图脚本会在 `plots/` 下生成带缺口和削顶标记的 `_quality.png`。

## v3 无绳本地记录

v3 使用 LittleFS 将数据保存在 ESP32 Flash 中，不依赖电脑持续连接。

- 短按 `BOOT`：开始记录 10 秒
- 记录结束后关闭文件
- 通过 USB 连接电脑后，运行导出脚本取回 CSV

导出：

```powershell
python tools\flash_export.py --port COM5 --baud 230400 --output data
```

导出后可继续使用：

```powershell
python tools\plot_imu_csv.py data\capture_001.csv
```

v4 在 10 秒采样期间把原始数据保存在 RAM，结束后再一次性写入 LittleFS，避免 v3 在 Flash 写入时产生约 20-50 ms 的采样停顿。
