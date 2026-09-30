import CoreBluetooth
import Foundation

final class BluetoothController: NSObject, ObservableObject {
    static let serviceUUID = CBUUID(string: "6b1d0001-9a3f-4d2a-8f6f-6b1d00000001")
    static let commandUUID = CBUUID(string: "6b1d0002-9a3f-4d2a-8f6f-6b1d00000002")

    @Published private(set) var isReady = false
    @Published private(set) var statusText = "正在检查蓝牙"
    @Published private(set) var deviceName: String?
    @Published var errorMessage: String?

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var commandCharacteristic: CBCharacteristic?
    private var reconnectWorkItem: DispatchWorkItem?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    func startScanning() {
        errorMessage = nil
        guard central.state == .poweredOn else {
            statusText = "等待蓝牙可用"
            return
        }

        reconnectWorkItem?.cancel()
        if let peripheral, peripheral.state == .connected {
            return
        }

        isReady = false
        statusText = "正在查找 KineShoot-Cam"
        central.scanForPeripherals(
            withServices: [Self.serviceUUID],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: false]
        )
    }

    @discardableResult
    func sendStartCapture() -> Bool {
        guard let peripheral, let commandCharacteristic else {
            errorMessage = "设备尚未连接，无法开始 IMU 采集。"
            return false
        }

        peripheral.writeValue(Data([0x01]), for: commandCharacteristic, type: .withResponse)
        return true
    }

    private func connect(_ peripheral: CBPeripheral) {
        self.peripheral = peripheral
        peripheral.delegate = self
        central.stopScan()
        isReady = false
        statusText = "正在连接 \(peripheral.name ?? "KineShoot")"
        central.connect(peripheral, options: nil)
    }

    private func scheduleReconnect() {
        reconnectWorkItem?.cancel()
        let item = DispatchWorkItem { [weak self] in
            self?.startScanning()
        }
        reconnectWorkItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0, execute: item)
    }
}

extension BluetoothController: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            startScanning()
        case .poweredOff:
            isReady = false
            statusText = "蓝牙已关闭"
        case .unauthorized:
            isReady = false
            statusText = "没有蓝牙权限"
            errorMessage = "请在系统设置中允许 KineShoot 使用蓝牙。"
        default:
            isReady = false
            statusText = "蓝牙暂不可用"
        }
    }

    func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any],
        rssi RSSI: NSNumber
    ) {
        let advertisedName = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        let name = advertisedName ?? peripheral.name ?? ""
        guard name.hasPrefix("KineShoot") else {
            return
        }
        connect(peripheral)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        statusText = "正在配置 KineShoot"
        peripheral.discoverServices([Self.serviceUUID])
    }

    func centralManager(
        _ central: CBCentralManager,
        didFailToConnect peripheral: CBPeripheral,
        error: Error?
    ) {
        isReady = false
        statusText = "连接失败"
        errorMessage = error?.localizedDescription
        scheduleReconnect()
    }

    func centralManager(
        _ central: CBCentralManager,
        didDisconnectPeripheral peripheral: CBPeripheral,
        error: Error?
    ) {
        self.peripheral = peripheral
        commandCharacteristic = nil
        isReady = false
        statusText = "设备已断开"
        scheduleReconnect()
    }
}

extension BluetoothController: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error {
            errorMessage = error.localizedDescription
            return
        }

        guard let service = peripheral.services?.first(where: { $0.uuid == Self.serviceUUID }) else {
            statusText = "没有找到 KineShoot 服务"
            return
        }

        peripheral.discoverCharacteristics([Self.commandUUID], for: service)
    }

    func peripheral(
        _ peripheral: CBPeripheral,
        didDiscoverCharacteristicsFor service: CBService,
        error: Error?
    ) {
        if let error {
            errorMessage = error.localizedDescription
            return
        }

        commandCharacteristic = service.characteristics?.first(where: {
            $0.uuid == Self.commandUUID && ($0.properties.contains(.write) || $0.properties.contains(.writeWithoutResponse))
        })

        isReady = commandCharacteristic != nil
        deviceName = peripheral.name
        statusText = isReady ? "已连接，可以开始采集" : "命令通道不可用"
    }
}
