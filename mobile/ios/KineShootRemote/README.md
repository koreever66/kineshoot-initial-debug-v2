# KineShoot iPhone Remote

当前版本用一个按钮同时完成两件事：

1. 启动 iPhone 后置相机录像。
2. 通过 BLE 向 ESP32 写入开始采集命令。

录像结束后 App 会立即打开标记页，可以记录有效/废掉、进/不进、动作、距离、朝向、废掉原因和备注。所有标记实时保存到 App 文档目录，强制关闭后重新打开会继续当前 active 会话。

## 球员会话

- `000`：固定测试球员，永久排除正式统计和 WPS 正式合并。
- `001-006`：初始正式球员。
- 新球员只能使用 `max(正式编号) + 1`，不能手填旧编号。
- 正常采集、重采、补采、疲劳测试、测试采集分别保存。
- 每个会话都从第 1 条重新开始；废掉记录占序号，但不推进有效目标。
- 重采会把该球员以前的正式会话标记为废除，但不会删除文件。
- 补采保留旧会话有效性，并创建新的独立会话。
- 同一时间只允许一个 active 会话；切换任务前必须先结束当前会话。

## 云端生成 IPA

仓库已经包含 GitHub Actions 工作流：

```text
.github/workflows/ios-unsigned.yml
```

推送代码后，在 GitHub 仓库的 `Actions` 页面打开：

```text
Build unsigned iOS IPA
```

点击 `Run workflow`，等待构建完成，然后下载：

```text
KineShootRemote-unsigned-ipa
```

压缩包内包含 `KineShootRemote-unsigned.ipa`。

## Windows 安装

1. 在 Windows 安装 iTunes 和 Sideloadly。
2. 用数据线连接 iPhone，并信任这台电脑。
3. 把 `KineShootRemote-unsigned.ipa` 拖入 Sideloadly。
4. 输入自己的 Apple ID，等待签名和安装完成。
5. 在 iPhone 的 `设置 -> 通用 -> VPN 与设备管理` 中信任开发者证书。

免费 Apple ID 签名的 App 有效期为 7 天，到期后需要重新用 Sideloadly 安装。付费 Apple Developer 账号可以延长签名并支持 TestFlight。

## 使用

1. ESP32 上电并进入 `BLE_CONTROL_READY`。
2. 打开 App，等待状态显示“已连接，可以开始采集”。
3. 选择新球员、已有球员、疲劳测试或 000 测试。
4. 点击“开始本轮”。
5. App 启动录像并向 ESP32 写入 `0x01`。
6. 约 14 秒后 App 自动停止，也可以手动停止。
7. 在标记页选择数据状态和结果，然后继续下一轮。
8. 随时点击“结束 xxx 球员采集”；未达到目标也可以结束并导出。

视频和 IMU 仍通过 ESP32 的 RGB 灯变化进行对齐。

## 导出与 WPS 合并

结束会话后会生成 CSV、会话 JSON 和 PlayerRegistry 快照。首页还可以单独导出完整登记表归档，用于换机和重装恢复。

把 App CSV 合并到 WPS 模板：

```powershell
python tools/merge_shot_marks.py `
  --template "C:\Users\kore\Desktop\KineShoot_投篮采集表_每人20条模板_WPS版.xlsx" `
  --csv "005_standard20.csv" "005_supplementary20.csv"
```

脚本只写入动作、距离、朝向、结果、有效性和备注列，默认输出带时间戳的新 XLSX，不覆盖模板。`000` 和已废除会话默认跳过；需要检查废除历史时可加 `--include-abolished`。
