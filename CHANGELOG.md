# Changelog

## 2026-09-15

### Added

- `firmware/imu_csv_logger_v2/`
- `firmware/imu_flash_logger_v3/`
- `firmware/imu_flash_logger_v4/`
- `tools/flash_export.py`
- `tools/project_metadata.py`
- `tools/requirements.txt`
- `project.json`
- `docs/CANONICAL_BASELINE.md`
- `docs/INTERFACE.md`
- `docs/SOFTWARE_PROTOCOL.md`
- `docs/SYNC_WORKFLOW.md`
- v2 串口采集数据、v4 Flash 采集数据和调试报告

### Changed

- `tools/serial_logger.py` 支持 `DATA` 协议、事件日志、元数据和质量统计。
- `tools/plot_imu_csv.py` 支持长缺口断线、削顶标记、温度和采样间隔图。
- `tools/start_logging.bat` 改为相对路径并默认使用 `230400`。
- `README.md` 增加 v2、v3、v4 使用说明。
- `DEBUG_NOTES.md` 增加稳定链路、无绳记录和动作测试记录。
- 串口记录和 Flash 导出自动附带硬件版本、软件版本、接口版本和 Git 提交。
- 冻结基线 `KB-2026-09-15-H1-F4-I1`，供软件和硬件对话共同引用。
- 定义软件、硬件分支职责和 GitHub 同步流程。
- 明确软件仓库、硬件仓库和项目介绍仓库三者的职责边界。

### Fixed

- I2C 地址不稳定。
- `Data Underflow`。
- Arduino 串口空白。
- LittleFS 损坏后无法挂载。
- 每样本写 Flash 造成的采样停顿。
- 导出时 USB CDC 丢字节。
- 文件系统满盘后生成半文件。
- 下载模式误入和空文件问题。

## v4

- 10 秒采样期间使用 RAM 缓冲。
- 采样结束后批量写入 LittleFS。
- 支持 `START`、`LIST`、`INFO`、`DUMP`、`DELETE`。
- 支持 BOOT 键触发。
- 低空间保护。
- 写盘失败自动删除半成品。
- 无绳运行时串口非阻塞，下载时串口阻塞发送。

## v3

- 增加 LittleFS 本地记录。
- 支持 BOOT 键触发 10 秒采集。
- 支持串口命令和文件导出。

## v2

- 固定 `0x68` 和 `50kHz`。
- 量程改为 `+/-16g` 和 `+/-2000dps`。
- 启用 DLPF。
- ODR 约 `220-225Hz`。
- 只读取加速度、角速度和温度。
