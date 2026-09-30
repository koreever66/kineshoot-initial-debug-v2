import SwiftUI

struct ContentView: View {
    @StateObject private var bluetooth = BluetoothController()
    @StateObject private var recorder = VideoRecorder()
    @State private var isStarting = false
    @State private var autoStopTask: Task<Void, Never>?

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                statusCard
                captureButton
                Text("点击开始后，App 会同时启动录像和 IMU 采集；约 12 秒后自动停止录像。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(24)
            .navigationTitle("KineShoot 采集")
            .onAppear {
                bluetooth.startScanning()
            }
        }
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Circle()
                    .fill(bluetooth.isReady ? Color.green : Color.orange)
                    .frame(width: 10, height: 10)
                Text(bluetooth.statusText)
                    .font(.headline)
                Spacer()
            }

            Label(bluetooth.deviceName ?? "KineShoot-Cam", systemImage: "dot.radiowaves.left.and.right")
                .foregroundStyle(.secondary)

            Label(recorder.statusText, systemImage: recorder.isRecording ? "record.circle" : "camera")
                .foregroundStyle(.secondary)

            if let message = bluetooth.errorMessage ?? recorder.errorMessage {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var captureButton: some View {
        Button {
            if recorder.isRecording {
                stopShot()
            } else {
                startShot()
            }
        } label: {
            HStack(spacing: 12) {
                Image(systemName: recorder.isRecording ? "stop.fill" : "video.fill")
                Text(recorder.isRecording ? "停止并保存" : "开始投篮")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 18)
        }
        .buttonStyle(.borderedProminent)
        .tint(recorder.isRecording ? .red : .blue)
        .disabled(!bluetooth.isReady || isStarting)
    }

    private func startShot() {
        guard bluetooth.isReady else {
            bluetooth.errorMessage = "请先等待 KineShoot-Cam 连接完成。"
            return
        }

        isStarting = true
        Task { @MainActor in
            do {
                try await recorder.startRecording()
                guard bluetooth.sendStartCapture() else {
                    recorder.stopRecording()
                    throw RecorderError.cameraUnavailable
                }

                autoStopTask?.cancel()
                autoStopTask = Task { @MainActor in
                    try? await Task.sleep(nanoseconds: 12_000_000_000)
                    guard !Task.isCancelled else {
                        return
                    }
                    stopShot()
                }
            } catch {
                recorder.errorMessage = error.localizedDescription
            }
            isStarting = false
        }
    }

    private func stopShot() {
        autoStopTask?.cancel()
        autoStopTask = nil
        recorder.stopRecording()
    }
}
