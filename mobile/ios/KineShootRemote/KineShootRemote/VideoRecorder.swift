import AVFoundation
import Foundation
import Photos
import UIKit

final class VideoRecorder: NSObject, ObservableObject {
    @Published private(set) var isRecording = false
    @Published private(set) var statusText = "相机待机"
    @Published private(set) var cameraPosition: AVCaptureDevice.Position = .back
    @Published private(set) var zoomFactor: CGFloat = 1
    @Published private(set) var maxZoomFactor: CGFloat = 1
    @Published var errorMessage: String?

    let session = AVCaptureSession()
    private let movieOutput = AVCaptureMovieFileOutput()
    private var sessionConfigured = false
    private var activeURL: URL?
    private var videoInput: AVCaptureDeviceInput?
    private var currentCamera: AVCaptureDevice?

    func prepare() async throws {
        try await ensureCameraPermission()

        if !sessionConfigured {
            try configureSession()
        }

        if !session.isRunning {
            session.startRunning()
        }
    }

    func startRecording() async throws {
        try await prepare()

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

    func switchCamera(to position: AVCaptureDevice.Position) async throws {
        guard !isRecording else {
            throw RecorderError.cannotSwitchWhileRecording
        }
        guard position != cameraPosition || videoInput == nil else {
            return
        }

        let camera = try cameraDevice(for: position)
        let newInput = try AVCaptureDeviceInput(device: camera)
        let previousInput = videoInput

        session.beginConfiguration()
        if let previousInput {
            session.removeInput(previousInput)
        }

        guard session.canAddInput(newInput) else {
            if let previousInput, session.canAddInput(previousInput) {
                session.addInput(previousInput)
            }
            session.commitConfiguration()
            throw RecorderError.cameraInputUnavailable
        }

        session.addInput(newInput)
        videoInput = newInput
        currentCamera = camera
        cameraPosition = position
        zoomFactor = 1
        updateVideoConnection()
        session.commitConfiguration()
        updateZoomRange(for: camera)
        applyZoom(1, to: camera)
    }

    func setZoom(_ requestedZoom: CGFloat) {
        guard let currentCamera else {
            return
        }
        let clampedZoom = min(max(requestedZoom, 1), maxZoomFactor)
        applyZoom(clampedZoom, to: currentCamera)
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
        let camera = try cameraDevice(for: cameraPosition)

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
        videoInput = input
        currentCamera = camera
        updateVideoConnection()
        session.commitConfiguration()
        sessionConfigured = true
        updateZoomRange(for: camera)
        applyZoom(1, to: camera)
    }

    private func cameraDevice(for position: AVCaptureDevice.Position) throws -> AVCaptureDevice {
        let deviceTypes: [AVCaptureDevice.DeviceType]
        if position == .front {
            deviceTypes = [.builtInTrueDepthCamera, .builtInWideAngleCamera]
        } else {
            deviceTypes = [.builtInTripleCamera, .builtInDualWideCamera, .builtInWideAngleCamera]
        }

        for deviceType in deviceTypes {
            if let camera = AVCaptureDevice.default(deviceType, for: .video, position: position) {
                return camera
            }
        }

        throw RecorderError.cameraUnavailable
    }

    private func updateZoomRange(for camera: AVCaptureDevice) {
        let practicalMaximum = cameraPosition == .front ? 4.0 : 10.0
        maxZoomFactor = max(1, min(CGFloat(camera.maxAvailableVideoZoomFactor), practicalMaximum))
        zoomFactor = min(max(zoomFactor, 1), maxZoomFactor)
    }

    private func applyZoom(_ zoom: CGFloat, to camera: AVCaptureDevice) {
        do {
            try camera.lockForConfiguration()
            camera.videoZoomFactor = min(max(zoom, 1), maxZoomFactor)
            camera.unlockForConfiguration()
            zoomFactor = camera.videoZoomFactor
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func updateVideoConnection() {
        guard let connection = movieOutput.connection(with: .video) else {
            return
        }
        if connection.isVideoOrientationSupported {
            connection.videoOrientation = .portrait
        }
        if connection.isVideoMirroringSupported {
            connection.isVideoMirrored = cameraPosition == .front
        }
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
    case cannotSwitchWhileRecording

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
        case .cannotSwitchWhileRecording:
            return "录像过程中不能切换前后摄像头。"
        }
    }
}
