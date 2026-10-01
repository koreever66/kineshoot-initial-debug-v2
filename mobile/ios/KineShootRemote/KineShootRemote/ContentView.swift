import SwiftUI

enum AppRoute: Hashable {
    case newPlayer
    case existingPlayers
    case player(String)
    case fatigue
    case testPlayer
    case capture
}

private struct PendingSessionStart {
    let playerId: String?
    let type: PlayerSessionType
    let fixedAction: ShotAction?
    let fixedDistance: ShotDistance?
    let targetValidCount: Int?
}

struct ContentView: View {
    @StateObject private var bluetooth = BluetoothController()
    @StateObject private var recorder = VideoRecorder()
    @StateObject private var store = PlayerSessionStore()

    @State private var path: [AppRoute] = []
    @State private var pendingStart: PendingSessionStart?
    @State private var isSwitchPromptPresented = false

    var body: some View {
        NavigationStack(path: $path) {
            HomeView(
                store: store,
                bluetooth: bluetooth,
                onContinue: { path.append(.capture) },
                onOpenExistingPlayers: { path.append(.existingPlayers) },
                onOpenFatigue: { path.append(.fatigue) },
                onOpenNewPlayer: { path.append(.newPlayer) },
                onOpenTestPlayer: { path.append(.testPlayer) }
            )
            .navigationDestination(for: AppRoute.self) { route in
                destination(for: route)
            }
        }
        .sheet(isPresented: $store.isSharePresented) {
            ActivityView(activityItems: store.lastExportURLs)
        }
        .confirmationDialog(
            "当前已有采集会话",
            isPresented: $isSwitchPromptPresented,
            titleVisibility: .visible
        ) {
            Button("结束当前并继续", role: .destructive) {
                endCurrentAndStartPending()
            }
            Button("取消", role: .cancel) {
                pendingStart = nil
            }
        } message: {
            Text("为避免数据串组，必须先结束并保存当前会话。")
        }
        .alert("操作失败", isPresented: errorBinding) {
            Button("好", role: .cancel) {}
        } message: {
            Text(store.errorMessage ?? "")
        }
    }

    @ViewBuilder
    private func destination(for route: AppRoute) -> some View {
        switch route {
        case .newPlayer:
            NewPlayerView(expectedPlayerId: store.nextNewPlayerId) {
                requestStart(PendingSessionStart(
                    playerId: nil,
                    type: .standard20,
                    fixedAction: nil,
                    fixedDistance: nil,
                    targetValidCount: 20
                ))
            }
        case .existingPlayers:
            ExistingPlayersView(store: store) { playerId in
                path.append(.player(playerId))
            }
        case .player(let playerId):
            PlayerDetailView(store: store, playerId: playerId) { type in
                requestStart(PendingSessionStart(
                    playerId: playerId,
                    type: type,
                    fixedAction: nil,
                    fixedDistance: nil,
                    targetValidCount: type.defaultTarget
                ))
            }
        case .fatigue:
            FatigueSetupView(store: store) { playerId, action, distance, target in
                requestStart(PendingSessionStart(
                    playerId: playerId,
                    type: .fatigue,
                    fixedAction: action,
                    fixedDistance: distance,
                    targetValidCount: target
                ))
            }
        case .testPlayer:
            TestPlayerView {
                requestStart(PendingSessionStart(
                    playerId: "000",
                    type: .test,
                    fixedAction: nil,
                    fixedDistance: nil,
                    targetValidCount: 20
                ))
            }
        case .capture:
            if store.activeSession != nil {
                SessionCaptureView(
                    bluetooth: bluetooth,
                    recorder: recorder,
                    store: store
                ) {
                    path.removeAll()
                }
            } else {
                VStack(spacing: 12) {
                    Text("当前没有进行中的采集")
                        .font(.headline)
                    Button("返回首页") {
                        path.removeAll()
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding()
                .navigationTitle("KineShoot")
            }
        }
    }

    private var errorBinding: Binding<Bool> {
        Binding(
            get: { store.errorMessage != nil },
            set: { isPresented in
                if !isPresented {
                    store.errorMessage = nil
                }
            }
        )
    }

    private func requestStart(_ start: PendingSessionStart) {
        if store.activeSession != nil {
            pendingStart = start
            isSwitchPromptPresented = true
        } else {
            performStart(start)
        }
    }

    private func performStart(_ start: PendingSessionStart) {
        pendingStart = nil
        do {
            try store.startSession(
                playerId: start.playerId,
                type: start.type,
                fixedAction: start.fixedAction,
                fixedDistance: start.fixedDistance,
                targetValidCount: start.targetValidCount
            )
            path.append(.capture)
        } catch {
            store.errorMessage = error.localizedDescription
        }
    }

    private func endCurrentAndStartPending() {
        guard let pendingStart else {
            return
        }
        do {
            try store.endActiveSession()
            performStart(pendingStart)
        } catch {
            store.errorMessage = error.localizedDescription
        }
    }
}
