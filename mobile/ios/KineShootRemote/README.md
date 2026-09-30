# KineShoot iPhone Remote

这个 App 用一个按钮同时完成两件事：

1. 启动 iPhone 后置相机录像。
2. 通过 BLE 向 ESP32 写入开始采集命令。

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
3. 点击“开始投篮”。
4. App 启动录像并向 ESP32 写入 `0x01`。
5. 约 12 秒后 App 自动停止录像并保存到照片。

视频和 IMU 仍通过 ESP32 的 RGB 灯变化进行对齐。
