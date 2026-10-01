import AVFoundation
import SwiftUI
import UniformTypeIdentifiers
import UIKit

struct HomeView: View {
    @ObservedObject var store: PlayerSessionStore
    @ObservedObject var bluetooth: BluetoothController

    let onContinue: () -> Void
    let onOpenExistingPlayers: () -> Void
    let onOpenFatigue: () -> Void
    let onOpenNewPlayer: () -> Void
    let onOpenTestPlayer: () -> Void

    @State private var isImportingRegistry = false

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                bluetoothCard

                if store.activeSession != nil {
                    activeSessionCard
                }

                VStack(spacing: 10) {
                    homeButton(
                        title: "已有球员：重采、补采、查看历史",
                        subtitle: "001 起的正式球员",
                        systemImage: "person.2.fill",
                        action: onOpenExistingPlayers
                    )
                    homeButton(
                        title: "疲劳测试",
                        subtitle: "已有球员或新球员均可进入",
                        systemImage: "figure.run",
                        action: onOpenFatigue
                    )
                    homeButton(
                        title: "新建球员 \(store.nextNewPlayerId)",
                        subtitle: "编号自动分配，不能手填",
                        systemImage: "person.badge.plus",
                        action: onOpenNewPlayer
                    )
                    homeButton(
                        title: "000 测试球员",
                        subtitle: "只用于测试，不进入正式统计",
                        systemImage: "testtube.2",
                        action: onOpenTestPlayer
                    )
                }

                registryActions
            }
            .padding(16)
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("KineShoot 采集")
        .fileImporter(
            isPresented: $isImportingRegistry,
            allowedContentTypes: [.json],
            allowsMultipleSelection: false
        ) { result in
            do {
                guard let url = try result.get().first else {
                    return
                }
                try store.importRegistry(from: url)
            } catch {
                store.errorMessage = error.localizedDescription
            }
        }
    }

    private var bluetoothCard: some View {
        HStack(spacing: 12) {
            Image(systemName: bluetooth.isReady ? "dot.radiowaves.left.and.right" : "antenna.radiowaves.left.and.right.slash")
                .font(.title2)
                .foregroundStyle(bluetooth.isReady ? .green : .orange)
            VStack(alignment: .leading, spacing: 3) {
                Text(bluetooth.statusText)
                    .font(.headline)
                Text(bluetooth.deviceName ?? "KineShoot-Cam")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Circle()
                .fill(bluetooth.isReady ? Color.green : Color.orange)
                .frame(width: 10, height: 10)
        }
        .padding(14)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var activeSessionCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("正在进行的采集", systemImage: "record.circle")
                .foregroundStyle(.red)
                .font(.headline)
            if let session = store.activeSession {
                Text("继续 \(session.playerId)，第 \(session.nextShotNo) 条")
                    .font(.title3.bold())
                Text("有效 \(session.validCount)/\(session.targetValidCount) · 废掉 \(session.invalidCount)")
                    .foregroundStyle(.secondary)
            }
            Button(action: onContinue) {
                Label("继续当前采集", systemImage: "arrow.forward.circle.fill")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var registryActions: some View {
        HStack(spacing: 10) {
            Button {
                isImportingRegistry = true
            } label: {
                Label("导入登记表", systemImage: "square.and.arrow.down")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)

            Button {
                do {
                    try store.exportRegistryArchive()
                } catch {
                    store.errorMessage = error.localizedDescription
                }
            } label: {
                Label("导出登记表", systemImage: "square.and.arrow.up")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
    }

    private func homeButton(
        title: String,
        subtitle: String,
        systemImage: String,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: systemImage)
                    .font(.title2)
                    .frame(width: 34)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .foregroundStyle(.tertiary)
            }
            .padding(14)
            .background(Color(.secondarySystemGroupedBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

struct ExistingPlayersView: View {
    @ObservedObject var store: PlayerSessionStore
    let onSelect: (String) -> Void

    private var players: [PlayerProfile] {
        store.registry.sortedPlayers.filter { !$0.isTest }
    }

    var body: some View {
        List(players) { player in
            Button {
                onSelect(player.id)
            } label: {
                HStack(spacing: 14) {
                    Text(player.id)
                        .font(.title3.monospacedDigit().bold())
                        .frame(width: 58, alignment: .leading)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("正式球员")
                            .font(.headline)
                        Text("\(player.sessionIds.count) 个会话")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    if store.activeSession?.playerId == player.id {
                        Text("进行中")
                            .font(.caption.bold())
                            .foregroundStyle(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.red)
                            .clipShape(Capsule())
                    }
                    Image(systemName: "chevron.right")
                        .foregroundStyle(.tertiary)
                }
            }
            .buttonStyle(.plain)
        }
        .navigationTitle("已有球员")
    }
}

private enum PlayerDetailAction: String, Identifiable, Hashable {
    case repeat20
    case supplementary20

    var id: String { rawValue }

    var title: String {
        switch self {
        case .repeat20: return "重采"
        case .supplementary20: return "补采"
        }
    }

    var message: String {
        switch self {
        case .repeat20:
            return "重采会保留旧文件，但把该球员以前的正式会话标记为废除。新会话从第 1 条开始。"
        case .supplementary20:
            return "补采不会改变旧会话状态，新会话从第 1 条开始，之后可与旧会话一起比较或训练。"
        }
    }

    var sessionType: PlayerSessionType {
        switch self {
        case .repeat20: return .repeat20
        case .supplementary20: return .supplementary20
        }
    }
}

struct PlayerDetailView: View {
    @ObservedObject var store: PlayerSessionStore
    let playerId: String
    let onRequestStart: (PlayerSessionType) -> Void

    @State private var pendingAction: PlayerDetailAction?

    private var sessions: [PlayerSession] {
        store.sessions(for: playerId)
    }

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text("球员 \(playerId)")
                        .font(.title2.bold())
                    Text("每个会话独立从第 1 条开始，历史数据不会覆盖。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .padding(.vertical, 4)

                if sessions.isEmpty {
                    Button {
                        onRequestStart(.standard20)
                    } label: {
                        Label("开始首次标准 20 组采集", systemImage: "play.circle.fill")
                    }
                }

                Button {
                    pendingAction = .repeat20
                } label: {
                    Label("重采（废除以前的正式会话）", systemImage: "arrow.counterclockwise")
                }

                Button {
                    pendingAction = .supplementary20
                } label: {
                    Label("补采（保留并新增独立会话）", systemImage: "plus.circle")
                }
            }

            Section("历史会话") {
                if sessions.isEmpty {
                    Text("暂无会话记录")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(sessions) { session in
                        SessionHistoryRow(session: session) {
                            do {
                                try store.exportSession(session)
                            } catch {
                                store.errorMessage = error.localizedDescription
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("球员 \(playerId)")
        .confirmationDialog(
            pendingAction?.title ?? "",
            isPresented: Binding(
                get: { pendingAction != nil },
                set: { isPresented in
                    if !isPresented {
                        pendingAction = nil
                    }
                }
            ),
            titleVisibility: .visible
        ) {
            if let pendingAction {
                Button(pendingAction.title, role: pendingAction == .repeat20 ? .destructive : nil) {
                    let type = pendingAction.sessionType
                    self.pendingAction = nil
                    onRequestStart(type)
                }
            }
            Button("取消", role: .cancel) {
                pendingAction = nil
            }
        } message: {
            Text(pendingAction?.message ?? "")
        }
    }
}

private struct SessionHistoryRow: View {
    let session: PlayerSession
    let onExport: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(session.sessionType.title)
                        .font(.headline)
                    Text(session.status.title)
                        .font(.caption.bold())
                        .foregroundStyle(statusColor)
                }
                Text("有效 \(session.validCount)/\(session.targetValidCount) · 废掉 \(session.invalidCount) · 共 \(session.records.count) 条")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(AppFormatters.dateTime.string(from: session.startedAt))
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            Spacer()
            Button("导出", action: onExport)
                .buttonStyle(.borderless)
        }
    }

    private var statusColor: Color {
        switch session.status {
        case .active: return .red
        case .ended: return .green
        case .endedEarly: return .orange
        case .abolished: return .gray
        }
    }
}

private enum FatiguePlayerSource: String, CaseIterable, Identifiable, Hashable {
    case existing
    case newPlayer

    var id: String { rawValue }

    var title: String {
        switch self {
        case .existing: return "已有球员"
        case .newPlayer: return "新球员"
        }
    }
}

private enum FatigueTargetPreset: String, CaseIterable, Identifiable, Hashable {
    case fifty
    case hundred
    case custom

    var id: String { rawValue }

    var title: String {
        switch self {
        case .fifty: return "50"
        case .hundred: return "100"
        case .custom: return "自定义"
        }
    }
}

struct FatigueSetupView: View {
    @ObservedObject var store: PlayerSessionStore
    let onStart: (String?, ShotAction, ShotDistance, Int) -> Void

    @State private var playerSource: FatiguePlayerSource = .existing
    @State private var selectedPlayerId = ""
    @State private var fixedAction: ShotAction = .shot
    @State private var fixedDistance: ShotDistance = .three
    @State private var targetPreset: FatigueTargetPreset = .fifty
    @State private var customTarget = "50"

    private var formalPlayers: [PlayerProfile] {
        store.registry.sortedPlayers.filter { !$0.isTest }
    }

    private var resolvedTarget: Int? {
        switch targetPreset {
        case .fifty: return 50
        case .hundred: return 100
        case .custom:
            guard let value = Int(customTarget), value > 0 else {
                return nil
            }
            return value
        }
    }

    var body: some View {
        Form {
            Section("球员") {
                Picker("来源", selection: $playerSource) {
                    ForEach(FatiguePlayerSource.allCases) { source in
                        Text(source.title).tag(source)
                    }
                }
                .pickerStyle(.segmented)

                if playerSource == .existing {
                    Picker("球员编号", selection: $selectedPlayerId) {
                        ForEach(formalPlayers) { player in
                            Text(player.id).tag(player.id)
                        }
                    }
                } else {
                    LabeledContent("新球员编号", value: store.nextNewPlayerId)
                }
            }

            Section("固定动作与距离") {
                Picker("动作", selection: $fixedAction) {
                    ForEach(ShotAction.allCases) { action in
                        Text(action.title).tag(action)
                    }
                }
                Picker("距离", selection: $fixedDistance) {
                    ForEach(ShotDistance.allCases) { distance in
                        Text(distance.title).tag(distance)
                    }
                }
                Text("整轮默认套用，单条记录仍可在标记页覆盖。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section("目标有效次数") {
                Picker("目标", selection: $targetPreset) {
                    ForEach(FatigueTargetPreset.allCases) { target in
                        Text(target.title).tag(target)
                    }
                }
                .pickerStyle(.segmented)

                if targetPreset == .custom {
                    TextField("自定义目标", text: $customTarget)
                        .keyboardType(.numberPad)
                }
            }

            Section {
                Button {
                    guard let target = resolvedTarget else {
                        return
                    }
                    let playerId = playerSource == .existing ? selectedPlayerId : nil
                    onStart(playerId, fixedAction, fixedDistance, target)
                } label: {
                    Label("开始疲劳测试", systemImage: "figure.run.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .disabled(resolvedTarget == nil || (playerSource == .existing && selectedPlayerId.isEmpty))
            }
        }
        .navigationTitle("疲劳测试")
        .onAppear {
            if selectedPlayerId.isEmpty {
                selectedPlayerId = formalPlayers.first?.id ?? ""
            }
        }
    }
}

struct NewPlayerView: View {
    let expectedPlayerId: String
    let onStart: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "person.badge.plus")
                .font(.system(size: 52))
                .foregroundStyle(.blue)
            Text("新建正式球员")
                .font(.title.bold())
            Text("系统自动分配编号")
                .foregroundStyle(.secondary)
            Text(expectedPlayerId)
                .font(.system(size: 54, weight: .bold, design: .rounded))
                .monospacedDigit()
            Text("不能手动输入编号，也不会复用已有球员编号。")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button(action: onStart) {
                Label("开始标准 20 组采集", systemImage: "play.circle.fill")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(24)
        .navigationTitle("新建球员")
    }
}

struct TestPlayerView: View {
    let onStart: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "testtube.2")
                .font(.system(size: 52))
                .foregroundStyle(.orange)
            Text("000 测试球员")
                .font(.title.bold())
            Text("用于录制、蓝牙、灯光、废数据和流程测试。")
                .multilineTextAlignment(.center)
            Text("测试数据永久排除正式统计、模型训练和 WPS 正式合并。")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button(action: onStart) {
                Label("开始测试会话", systemImage: "play.circle.fill")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
            .tint(.orange)
        }
        .padding(24)
        .navigationTitle("测试球员")
    }
}

enum AppFormatters {
    static let dateTime: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_CN")
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        return formatter
    }()
}

struct SessionCaptureView: View {
    @ObservedObject var bluetooth: BluetoothController
    @ObservedObject var recorder: VideoRecorder
    @ObservedObject var store: PlayerSessionStore
    let onSessionEnded: () -> Void

    @State private var isStarting = false
    @State private var autoStopTask: Task<Void, Never>?
    @State private var reviewDraft: ShotReviewDraft?
    @State private var isEndConfirmationPresented = false

    private var session: PlayerSession? {
        store.activeSession
    }

    var body: some View {
        Group {
            if let session {
                ScrollView {
                    VStack(spacing: 16) {
                        CameraPreview(session: recorder.session)
                            .aspectRatio(3.0 / 4.0, contentMode: .fit)
                            .clipShape(RoundedRectangle(cornerRadius: 12))

                        cameraControls
                        recordingStatus
                        captureButton
                        if session.records.isEmpty == false {
                            editLastButton
                        }
                    }
                    .padding(16)
                }
                .background(Color(.systemGroupedBackground))
                .safeAreaInset(edge: .top) {
                    ShotStatusBar(session: session)
                }
                .safeAreaInset(edge: .bottom) {
                    endSessionButton(session: session)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(.regularMaterial)
                }
            } else {
                Text("当前会话已结束")
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("球员 \(session?.playerId ?? "") 采集")
        .sheet(item: $reviewDraft) { draft in
            ShotReviewSheet(initialDraft: draft, isEditing: draft.recordId != nil) { finalDraft in
                saveReview(finalDraft)
            } onCancel: {
                reviewDraft = nil
            }
        }
        .onAppear {
            bluetooth.startScanning()
            Task {
                try? await recorder.prepare()
            }
        }
        .onChange(of: recorder.finishedRecording) { video in
            guard let video else {
                return
            }
            var draft = store.makeReviewDraft(for: video)
            draft.photoLocalIdentifier = recorder.lastPhotoIdentifier
            reviewDraft = draft
        }
        .onChange(of: recorder.lastPhotoIdentifier) { identifier in
            guard let identifier else {
                return
            }
            if var draft = reviewDraft {
                draft.photoLocalIdentifier = identifier
                reviewDraft = draft
            }
            try? store.updateLastRecordPhotoIdentifier(identifier)
        }
        .confirmationDialog(
            "结束球员采集？",
            isPresented: $isEndConfirmationPresented,
            titleVisibility: .visible
        ) {
            Button("结束并保存", role: .destructive) {
                endSession()
            }
            Button("继续采集", role: .cancel) {}
        } message: {
            Text("不要求达到目标次数。已采数据会立即保存并生成 CSV/JSON。")
        }
    }

    private var cameraControls: some View {
        VStack(spacing: 10) {
            Picker("摄像头", selection: cameraPositionBinding) {
                Text("后置").tag(AVCaptureDevice.Position.back)
                Text("前置").tag(AVCaptureDevice.Position.front)
            }
            .pickerStyle(.segmented)
            .disabled(recorder.isRecording)

            HStack(spacing: 10) {
                Image(systemName: "minus.magnifyingglass")
                    .foregroundStyle(.secondary)
                Slider(value: zoomBinding, in: 1...Double(max(1, recorder.maxZoomFactor)))
                Image(systemName: "plus.magnifyingglass")
                    .foregroundStyle(.secondary)
                Text(String(format: "%.1fx", recorder.zoomFactor))
                    .monospacedDigit()
                    .frame(width: 46, alignment: .trailing)
                Text(recorder.captureFormatText)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var recordingStatus: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Circle()
                    .fill(bluetooth.isReady ? Color.green : Color.orange)
                    .frame(width: 10, height: 10)
                Text(bluetooth.statusText)
                    .font(.headline)
                Spacer()
            }
            Label(recorder.statusText, systemImage: recorder.isRecording ? "record.circle" : "camera")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            if let message = bluetooth.errorMessage ?? recorder.errorMessage {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
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
                Text(recorder.isRecording ? "停止并保存" : "开始本轮")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
        }
        .buttonStyle(.borderedProminent)
        .tint(recorder.isRecording ? .red : .blue)
        .disabled(!bluetooth.isReady || isStarting)
    }

    private var editLastButton: some View {
        Button {
            guard let last = session?.records.last else {
                return
            }
            reviewDraft = store.makeEditDraft(for: last)
        } label: {
            Label("编辑上一组", systemImage: "pencil.circle")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)
        .disabled(recorder.isRecording)
    }

    private func endSessionButton(session: PlayerSession) -> some View {
        Button(role: .destructive) {
            isEndConfirmationPresented = true
        } label: {
            Label("结束 \(session.playerId) 球员采集", systemImage: "stop.circle.fill")
                .fontWeight(.semibold)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
        }
        .buttonStyle(.bordered)
    }

    private var cameraPositionBinding: Binding<AVCaptureDevice.Position> {
        Binding(
            get: { recorder.cameraPosition },
            set: { position in
                Task { @MainActor in
                    do {
                        try await recorder.switchCamera(to: position)
                    } catch {
                        recorder.errorMessage = error.localizedDescription
                    }
                }
            }
        )
    }

    private var zoomBinding: Binding<Double> {
        Binding(
            get: { Double(recorder.zoomFactor) },
            set: { recorder.setZoom(CGFloat($0)) }
        )
    }

    private func startShot() {
        guard bluetooth.isReady else {
            bluetooth.errorMessage = "请先等待 KineShoot-Cam 连接完成。"
            return
        }
        guard session != nil else {
            return
        }

        isStarting = true
        Task { @MainActor in
            do {
                try await recorder.startRecording()
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard bluetooth.sendStartCapture() else {
                    recorder.stopRecording()
                    throw RecorderError.cameraUnavailable
                }

                autoStopTask?.cancel()
                autoStopTask = Task { @MainActor in
                    try? await Task.sleep(nanoseconds: 14_000_000_000)
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

    private func saveReview(_ draft: ShotReviewDraft) {
        var record = draft.makeRecord()
        if record.photoLocalIdentifier == nil {
            record.photoLocalIdentifier = recorder.lastPhotoIdentifier
        }
        do {
            if draft.recordId == nil {
                try store.addRecord(record)
            } else {
                try store.updateRecord(record)
            }
            reviewDraft = nil
            recorder.clearFinishedRecording()
        } catch {
            store.errorMessage = error.localizedDescription
        }
    }

    private func endSession() {
        autoStopTask?.cancel()
        autoStopTask = nil
        if recorder.isRecording {
            recorder.stopRecording()
        }
        do {
            try store.endActiveSession()
            onSessionEnded()
        } catch {
            store.errorMessage = error.localizedDescription
        }
    }
}

private struct ShotStatusBar: View {
    let session: PlayerSession

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("当前第 \(session.nextShotNo) 条")
                        .font(.title2.bold())
                    Text(session.sessionType.title)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text("有效 \(session.validCount)/\(session.targetValidCount)")
                        .font(.headline)
                    Text("废掉 \(session.invalidCount)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            ProgressView(value: Double(session.validCount), total: Double(max(1, session.targetValidCount)))
            Text(planText)
                .font(.subheadline.bold())
                .foregroundStyle(session.hasReachedTarget ? Color.green : Color.primary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(.regularMaterial)
    }

    private var planText: String {
        if session.hasReachedTarget {
            return "预设已完成，追加采集需手动分类"
        }
        if let slot = session.nextPlannedSlot {
            if session.sessionType == .fatigue {
                return "固定：\(slot.action.title) · \(slot.distance.title) · 目标 \(session.targetValidCount)"
            }
            return "当前预设：\(slot.action.title) · \(slot.distance.title) · 计划 \(session.validCount + 1)/\(session.targetValidCount)"
        }
        return "测试或追加采集：录像后手动选择动作和距离"
    }
}

private struct ShotReviewSheet: View {
    @State private var draft: ShotReviewDraft
    let isEditing: Bool
    let onSave: (ShotReviewDraft) -> Void
    let onCancel: () -> Void

    init(
        initialDraft: ShotReviewDraft,
        isEditing: Bool,
        onSave: @escaping (ShotReviewDraft) -> Void,
        onCancel: @escaping () -> Void
    ) {
        _draft = State(initialValue: initialDraft)
        self.isEditing = isEditing
        self.onSave = onSave
        self.onCancel = onCancel
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("第 \(draft.shotNo) 条")
                        .font(.title2.bold())
                    Picker("数据状态", selection: $draft.dataValidity) {
                        Text("有效").tag(DataValidity.valid)
                        Text("废掉").tag(DataValidity.invalid)
                    }
                    .pickerStyle(.segmented)
                }

                if draft.dataValidity == .valid {
                    Section("结果与分类") {
                        Picker("结果", selection: $draft.shotResult) {
                            Text("请选择").tag(ShotResult.undecided)
                            Text("进").tag(ShotResult.made)
                            Text("不进").tag(ShotResult.missed)
                        }
                        .pickerStyle(.segmented)

                        Picker("动作", selection: $draft.action) {
                            ForEach(ShotAction.allCases) { action in
                                Text(action.title).tag(action)
                            }
                        }

                        Picker("距离", selection: $draft.distance) {
                            ForEach(ShotDistance.allCases) { distance in
                                Text(distance.title).tag(distance)
                            }
                        }

                        Picker("朝向", selection: $draft.orientation) {
                            ForEach(ShotOrientation.allCases) { orientation in
                                Text(orientation.title).tag(orientation)
                            }
                        }
                    }
                } else {
                    Section("废掉原因") {
                        ForEach(InvalidReason.allCases) { reason in
                            Toggle(reason.title, isOn: reasonBinding(reason))
                        }
                        Text("废掉仍占当前序号，但不会推进有效目标和预设进度。下一条会继续当前预设分类。")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("备注") {
                    TextField("自由备注", text: $draft.notes, axis: .vertical)
                        .lineLimit(2...5)
                }

                if let plannedAction = draft.plannedAction,
                   let plannedDistance = draft.plannedDistance {
                    Section("本组预设") {
                        LabeledContent("动作", value: plannedAction.title)
                        LabeledContent("距离", value: plannedDistance.title)
                    }
                }
            }
            .navigationTitle(isEditing ? "编辑上一组" : "标记本组")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if isEditing {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("取消", action: onCancel)
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        onSave(draft)
                    }
                    .disabled(!canSave)
                }
            }
        }
        .interactiveDismissDisabled(!isEditing)
    }

    private var canSave: Bool {
        switch draft.dataValidity {
        case .invalid:
            return !draft.invalidReasons.isEmpty
        case .valid:
            return draft.shotResult != .undecided
        case .pending:
            return false
        }
    }

    private func reasonBinding(_ reason: InvalidReason) -> Binding<Bool> {
        Binding(
            get: { draft.invalidReasons.contains(reason) },
            set: { isSelected in
                if isSelected {
                    if !draft.invalidReasons.contains(reason) {
                        draft.invalidReasons.append(reason)
                    }
                } else {
                    draft.invalidReasons.removeAll { $0 == reason }
                }
            }
        )
    }
}

struct ActivityView: UIViewControllerRepresentable {
    let activityItems: [URL]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: activityItems, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
