# F4 软件与数据协议

软件版本：F4

## 固件职责

- ESP32-S3 初始化 ICM-20948。
- I2C 固定地址 `0x68`。
- 加速度量程 `+/-16g`。
- 陀螺仪量程 `+/-2000dps`。
- ODR 约 `220-225Hz`。
- 采样期间仅写 RAM。
- 10 秒结束后批量写入 LittleFS。
- 支持 BOOT 键或串口 `START` 触发。

## 串口命令

```text
LIST
INFO
START
DUMP /capture_001.csv
DELETE /capture_001.csv
```

## 设备文件格式

```text
seq,timestamp_us,ax_mg,ay_mg,az_mg,gx_dps,gy_dps,gz_dps,temp_c
```

注意事项：

- `timestamp_us` 来自 ESP32 `esp_timer_get_time()`。
- `seq` 从 0 递增。
- 默认不保存磁力计数据。
- 参数变化时必须更新 `project.json` 中的 `software_revision`。

## 主机导出格式

`flash_export.py` 下载 CSV 后生成同名 `.meta.json`：

```json
{
  "project": "kineshoot",
  "hardware_revision": "H2",
  "software_revision": "F4",
  "interface_revision": "I1",
  "firmware_protocol": "imu-v4-csv",
  "mount_position": "wrist_dorsal",
  "test_type": "real_shot",
  "operator": "kore",
  "git_sha": "...",
  "remote_path": "/capture_001.csv",
  "remote_size": 137000,
  "downloaded_at": "..."
}
```

命令行可覆盖项目状态：

```powershell
python tools\flash_export.py `
  --port COM5 `
  --output data\raw `
  --hardware-revision H2 `
  --mount-position wrist_dorsal `
  --test-type real_shot `
  --operator kore
```

## 数据目录约定

```text
data/raw/         原始 CSV 和同源元数据
data/processed/   后处理数据
data/archive/     历史测试数据
plots/            图片
reports/          分析报告
```

## 测试类型

```text
static
small_motion
strength_test
simulated_shot
real_shot
calibration
```

## 验收要求

静止和加强测试继续使用：

```text
采样率 >= 200 Hz
最大间隔 <= 10 ms
无复位
无全零段
无固定饱和
无削顶
```
