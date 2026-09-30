import AVFoundation
import Foundation
import Photos
import UIKit

final class VideoRecorder: NSObject, ObservableObject {
    @Published private(set) var isRecording = false
    @Published private(set) var statusText = "相机待机"
    @Published var errorMessage: String?

    private let session = AVCaptureSession()
    private let movieOutput = AVCaptureMovieFileOutput()
    private var sessionConfigured = false
    private var activeURL: URL?

    func startRecording() async throws {
        try await ensureCameraPermission()

        if !sessionConfigured {
            try configureSession()
        }

        if !session.isRunning {
            session.startRunning()
        }

        let outputURL = try makeOutputURL()
        activeURL = outputURL
        isRecording = true
        statusText = "录像中"
        UIApplication.shared.isIdleTimerDisabled = true
        movieOutput.startRecording(to: outputURL, recordingDelegate: self)
    }

    func stopRecording() {
        guard movieOutput.isRecording else {
            return
        }
        movieOutput.stopRecording()
    }

    private func ensureCameraPermission() async throws {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            return
        case .notDetermined:
            let granted = await AVCaptureDevice.requestAccess(for: .video)
            if !granted {
                throw RecorderError.cameraPermissionDenied
            }
        default:
            throw RecorderError.cameraPermissionDenied
        }
    }

    private func configureSession() throws {
        guard let camera = AVCaptureDevice.default(
            .builtInWideAngleCamera,
            for: .video,
            position: .back
        ) else {
            throw RecorderError.cameraUnavailable
        }

        let input = try AVCaptureDeviceInput(device: camera)

        session.beginConfiguration()
        session.sessionPreset = .high

        guard session.canAddInput(input) else {
            session.commitConfiguration()
            throw RecorderError.cameraInputUnavailable
        }
        session.addInput(input)

        guard session.canAddOutput(movieOutput) else {
            session.commitConfiguration()
            throw RecorderError.movieOutputUnavailable
        }
        session.addOutput(movieOutput)
        session.commitConfiguration()
        sessionConfigured = true
    }

    private func makeOutputURL() throws -> URL {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("KineShootVideos", isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyyMMdd-HHmmss-SSS"
        return directory.appendingPathComponent("shot-\(formatter.string(from: Date())).mov")
    }

    private func saveToPhotos(_ url: URL) {
        PHPhotoLibrary.requestAuthorization(for: .addOnly) { [weak self] status in
            guard status == .authorized || status == .limited else {
                DispatchQueue.main.async {
                    self?.statusText = "视频已保留在临时目录"
                    self?.errorMessage = "没有照片写入权限，视频未保存到照片。"
                }
                return
            }

            PHPhotoLibrary.shared().performChanges {
                PHAssetChangeRequest.creationRequestForAssetFromVideo(atFileURL: url)
            } completionHandler: { success, error in
                DispatchQueue.main.async {
                    if success {
                        self?.statusText = "视频已保存到照片"
                    } else {
                        self?.statusText = "视频已保留在临时目录"
                        self?.errorMessage = error?.localizedDescription ?? "保存视频失败。"
                    }
                }
            }
        }
    }
}

extension VideoRecorder: AVCaptureFileOutputRecordingDelegate {
    func fileOutput(
        _ output: AVCaptureFileOutput,
        didFinishRecordingTo outputFileURL: URL,
        from connections: [AVCaptureConnection],
        error: Error?
    ) {
        DispatchQueue.main.async {
            if self.session.isRunning {
                self.session.stopRunning()
            }
            self.isRecording = false
            UIApplication.shared.isIdleTimerDisabled = false

            if let error {
                self.statusText = "录像失败"
                self.errorMessage = error.localizedDescription
                return
            }

            self.saveToPhotos(outputFileURL)
        }
    }
}

enum RecorderError: LocalizedError {
    case cameraPermissionDenied
    case cameraUnavailable
    case cameraInputUnavailable
    case movieOutputUnavailable

    var errorDescription: String? {
        switch self {
        case .cameraPermissionDenied:
            return "没有相机权限。"
        case .cameraUnavailable:
            return "没有找到后置相机。"
        case .cameraInputUnavailable:
            return "无法配置后置相机输入。"
        case .movieOutputUnavailable:
            return "无法配置视频输出。"
        }
    }
}
