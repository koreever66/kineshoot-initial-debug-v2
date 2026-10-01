import Combine
import Foundation

@MainActor
final class PlayerSessionStore: ObservableObject {
    @Published private(set) var registry: PlayerRegistry
    @Published private(set) var activeSession: PlayerSession?
    @Published private(set) var lastExportURLs: [URL] = []
    @Published var isSharePresented = false
    @Published var errorMessage: String?

    private let fileManager = FileManager.default
    private let rootURL: URL
    private let registryURL: URL

    private var encoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }

    private var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    init() {
        let documents = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
        rootURL = documents.appendingPathComponent("KineShootData", isDirectory: true)
        registryURL = rootURL.appendingPathComponent("PlayerRegistry.json")
        let initialDecoder = JSONDecoder()
        initialDecoder.dateDecodingStrategy = .iso8601

        do {
            try fileManager.createDirectory(at: rootURL, withIntermediateDirectories: true)
            let loadedRegistry: PlayerRegistry
            if fileManager.fileExists(atPath: registryURL.path) {
                let data = try Data(contentsOf: registryURL)
                loadedRegistry = try initialDecoder.decode(PlayerRegistry.self, from: data)
            } else {
                loadedRegistry = Self.makeSeedRegistry()
            }
            registry = loadedRegistry
            if let playerId = loadedRegistry.activePlayerId,
               let sessionId = loadedRegistry.activeSessionId {
                activeSession = try loadSession(playerId: playerId, sessionId: sessionId)
            } else {
                activeSession = nil
            }
            try saveRegistry()
        } catch {
            registry = Self.makeSeedRegistry()
            activeSession = nil
            errorMessage = error.localizedDescription
            try? saveRegistry()
        }
    }

    var nextNewPlayerId: String {
        registry.nextNewPlayerId
    }

    func startSession(
        playerId: String?,
        type: PlayerSessionType,
        fixedAction: ShotAction? = nil,
        fixedDistance: ShotDistance? = nil,
        targetValidCount: Int? = nil
    ) throws {
        guard activeSession == nil else {
            throw StoreError.activeSessionExists
        }

        let resolvedPlayerId: String
        if let playerId {
            resolvedPlayerId = playerId
        } else {
            resolvedPlayerId = try allocateNewFormalPlayer()
        }

        guard var profile = registry.players[resolvedPlayerId] else {
            throw StoreError.playerNotFound
        }

        if type == .test && !profile.isTest {
            throw StoreError.invalidTestPlayer
        }
        if type == .fatigue && (fixedAction == nil || fixedDistance == nil || (targetValidCount ?? 0) < 1) {
            throw StoreError.invalidFatigueConfiguration
        }

        if type == .repeat20 {
            try abolishPreviousFormalSessions(for: resolvedPlayerId)
            profile = registry.players[resolvedPlayerId] ?? profile
        }

        let revision = profile.sessionIds.count + 1
        let sessionId = makeSessionId(playerId: resolvedPlayerId, type: type, revision: revision)
        let session = PlayerSession(
            id: sessionId,
            playerId: resolvedPlayerId,
            sessionType: type,
            revision: revision,
            isTest: profile.isTest,
            startedAt: Date(),
            endedAt: nil,
            status: .active,
            targetValidCount: targetValidCount ?? type.defaultTarget,
            fixedAction: fixedAction,
            fixedDistance: fixedDistance,
            records: []
        )

        profile.sessionIds.append(sessionId)
        registry.players[resolvedPlayerId] = profile
        registry.activePlayerId = resolvedPlayerId
        registry.activeSessionId = sessionId
        activeSession = session
        try saveSession(session)
        try saveRegistry()
    }

    func addRecord(_ record: ShotRecord) throws {
        guard var session = activeSession else {
            throw StoreError.noActiveSession
        }
        session.records.append(record)
        activeSession = session
        try saveSession(session)
    }

    func updateRecord(_ record: ShotRecord) throws {
        guard var session = activeSession,
              let index = session.records.firstIndex(where: { $0.id == record.id }) else {
            throw StoreError.recordNotFound
        }
        session.records[index] = record
        activeSession = session
        try saveSession(session)
    }

    func updateLastRecordPhotoIdentifier(_ identifier: String) throws {
        guard var session = activeSession,
              var last = session.records.last,
              last.photoLocalIdentifier == nil else {
            return
        }
        last.photoLocalIdentifier = identifier
        session.records[session.records.count - 1] = last
        activeSession = session
        try saveSession(session)
    }

    @discardableResult
    func endActiveSession() throws -> [URL] {
        guard var session = activeSession else {
            throw StoreError.noActiveSession
        }
        session.status = session.validCount >= session.targetValidCount ? .ended : .endedEarly
        session.endedAt = Date()
        activeSession = session
        try saveSession(session)
        registry.activePlayerId = nil
        registry.activeSessionId = nil
        activeSession = nil
        try saveRegistry()

        let urls = try export(session: session)
        lastExportURLs = urls
        isSharePresented = true
        return urls
    }

    func sessions(for playerId: String) -> [PlayerSession] {
        guard let profile = registry.players[playerId] else {
            return []
        }
        return profile.sessionIds.compactMap { try? loadSession(playerId: playerId, sessionId: $0) }
            .sorted { $0.startedAt > $1.startedAt }
    }

    func exportSession(_ session: PlayerSession) throws -> [URL] {
        try export(session: session)
    }

    @discardableResult
    func exportRegistryArchive() throws -> [URL] {
        var sessions: [PlayerSession] = []
        for profile in registry.sortedPlayers {
            for sessionId in profile.sessionIds {
                if let session = try? loadSession(playerId: profile.id, sessionId: sessionId) {
                    sessions.append(session)
                }
            }
        }

        let exportsDirectory = rootURL.appendingPathComponent("exports", isDirectory: true)
        try fileManager.createDirectory(at: exportsDirectory, withIntermediateDirectories: true)
        let timestamp = Self.fileTimestamp.string(from: Date())
        let url = exportsDirectory.appendingPathComponent("PlayerRegistry_\(timestamp).json")
        let archive = PlayerRegistryArchive(exportedAt: Date(), registry: registry, sessions: sessions)
        try encoder.encode(archive).write(to: url, options: .atomic)
        lastExportURLs = [url]
        isSharePresented = true
        return [url]
    }

    func importRegistry(from url: URL) throws {
        let canAccessSecurityScope = url.startAccessingSecurityScopedResource()
        defer {
            if canAccessSecurityScope {
                url.stopAccessingSecurityScopedResource()
            }
        }

        let data = try Data(contentsOf: url)
        if let archive = try? decoder.decode(PlayerRegistryArchive.self, from: data) {
            let imported = Self.normalized(archive.registry)
            registry = imported
            try saveRegistry()
            for session in archive.sessions {
                try saveSession(session)
            }
            activeSession = try activeSession(from: imported)
            return
        }

        let imported = Self.normalized(try decoder.decode(PlayerRegistry.self, from: data))
        registry = imported
        try saveRegistry()
        activeSession = try activeSession(from: imported)
    }

    func makeReviewDraft(for video: RecordedVideo) -> ShotReviewDraft {
        guard let session = activeSession else {
            return ShotReviewDraft(
                shotNo: 1,
                plannedAction: nil,
                plannedDistance: nil,
                action: .shot,
                distance: .free,
                orientation: .facingBasket,
                shotResult: .undecided,
                dataValidity: .valid,
                invalidReasons: [],
                notes: "",
                capturedAt: video.startedAt,
                videoFileName: video.fileURL.lastPathComponent,
                photoLocalIdentifier: nil
            )
        }
        let slot = session.nextPlannedSlot
        return ShotReviewDraft(
            shotNo: session.nextShotNo,
            plannedAction: slot?.action,
            plannedDistance: slot?.distance,
            action: slot?.action ?? .shot,
            distance: slot?.distance ?? .free,
            orientation: .facingBasket,
            shotResult: .undecided,
            dataValidity: .valid,
            invalidReasons: [],
            notes: "",
            capturedAt: video.startedAt,
            videoFileName: video.fileURL.lastPathComponent,
            photoLocalIdentifier: nil
        )
    }

    func makeEditDraft(for record: ShotRecord) -> ShotReviewDraft {
        ShotReviewDraft(
            recordId: record.id,
            shotNo: record.shotNo,
            plannedAction: record.plannedAction,
            plannedDistance: record.plannedDistance,
            action: record.action,
            distance: record.distance,
            orientation: record.orientation,
            shotResult: record.shotResult,
            dataValidity: record.dataValidity,
            invalidReasons: record.invalidReasons,
            notes: record.notes,
            capturedAt: record.capturedAt,
            videoFileName: record.videoFileName,
            photoLocalIdentifier: record.photoLocalIdentifier
        )
    }

    private func allocateNewFormalPlayer() throws -> String {
        let playerId = registry.nextNewPlayerId
        guard registry.players[playerId] == nil else {
            throw StoreError.playerAlreadyExists
        }
        let profile = PlayerProfile(id: playerId, isTest: false, createdAt: Date(), sessionIds: [])
        registry.players[playerId] = profile
        if let numeric = Int(playerId) {
            registry.maxFormalPlayerId = max(registry.maxFormalPlayerId, numeric)
        }
        try saveRegistry()
        return playerId
    }

    private func activeSession(from registry: PlayerRegistry) throws -> PlayerSession? {
        guard let playerId = registry.activePlayerId,
              let sessionId = registry.activeSessionId else {
            return nil
        }
        return try loadSession(playerId: playerId, sessionId: sessionId)
    }

    private func abolishPreviousFormalSessions(for playerId: String) throws {
        guard var profile = registry.players[playerId] else {
            return
        }
        for sessionId in profile.sessionIds {
            guard var session = try? loadSession(playerId: playerId, sessionId: sessionId) else {
                continue
            }
            if session.sessionType == .fatigue || session.sessionType == .test {
                continue
            }
            session.status = .abolished
            if session.endedAt == nil {
                session.endedAt = Date()
            }
            try saveSession(session)
        }
        registry.players[playerId] = profile
    }

    private func export(session: PlayerSession) throws -> [URL] {
        let exportsDirectory = rootURL
            .appendingPathComponent("players", isDirectory: true)
            .appendingPathComponent(session.playerId, isDirectory: true)
            .appendingPathComponent("exports", isDirectory: true)
        try fileManager.createDirectory(at: exportsDirectory, withIntermediateDirectories: true)

        let timestamp = Self.fileTimestamp.string(from: Date())
        let baseName = "\(session.playerId)_\(session.sessionType.rawValue)_\(session.revision)_\(timestamp)"
        let csvURL = exportsDirectory.appendingPathComponent("\(baseName).csv")
        let sessionURL = exportsDirectory.appendingPathComponent("\(baseName)_session.json")
        let registryCopyURL = exportsDirectory.appendingPathComponent("\(baseName)_PlayerRegistry.json")

        try csv(session: session).write(to: csvURL, atomically: true, encoding: .utf8)
        try encoder.encode(session).write(to: sessionURL, options: .atomic)
        try encoder.encode(registry).write(to: registryCopyURL, options: .atomic)
        return [csvURL, sessionURL, registryCopyURL]
    }

    private func csv(session: PlayerSession) -> String {
        let header = [
            "player_id", "session_id", "session_type", "target_valid_count",
            "is_test", "session_status", "shot_no", "planned_action",
            "planned_distance", "action", "distance", "orientation",
            "shot_result", "data_valid", "invalid_reasons", "notes",
            "captured_at", "video_file_name", "video_photo_local_identifier"
        ].joined(separator: ",")

        let rows = session.records.map { record -> String in
            [
                session.playerId,
                session.id,
                session.sessionType.rawValue,
                String(session.targetValidCount),
                session.isTest ? "true" : "false",
                session.status.rawValue,
                String(record.shotNo),
                record.plannedAction?.title ?? "",
                record.plannedDistance?.title ?? "",
                record.action.title,
                record.distance.title,
                record.orientation.title,
                record.shotResult.title,
                record.dataValidity.title,
                record.invalidReasons.map(\.title).joined(separator: ";"),
                record.notes,
                Self.iso8601.string(from: record.capturedAt),
                record.videoFileName ?? "",
                record.photoLocalIdentifier ?? ""
            ].map(Self.csvEscape).joined(separator: ",")
        }
        return ([header] + rows).joined(separator: "\n") + "\n"
    }

    private func saveRegistry() throws {
        try encoder.encode(registry).write(to: registryURL, options: .atomic)
    }

    private func saveSession(_ session: PlayerSession) throws {
        let url = sessionURL(playerId: session.playerId, sessionId: session.id)
        try fileManager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try encoder.encode(session).write(to: url, options: .atomic)
    }

    private func loadSession(playerId: String, sessionId: String) throws -> PlayerSession {
        let url = sessionURL(playerId: playerId, sessionId: sessionId)
        let data = try Data(contentsOf: url)
        return try decoder.decode(PlayerSession.self, from: data)
    }

    private func sessionURL(playerId: String, sessionId: String) -> URL {
        rootURL
            .appendingPathComponent("players", isDirectory: true)
            .appendingPathComponent(playerId, isDirectory: true)
            .appendingPathComponent("sessions", isDirectory: true)
            .appendingPathComponent("\(sessionId).json")
    }

    private func makeSessionId(playerId: String, type: PlayerSessionType, revision: Int) -> String {
        "\(playerId)-\(Self.fileTimestamp.string(from: Date()))-\(type.rawValue)-r\(revision)"
    }

    private static func makeSeedRegistry() -> PlayerRegistry {
        var registry = PlayerRegistry()
        let now = Date()
        registry.players["000"] = PlayerProfile(id: "000", isTest: true, createdAt: now, sessionIds: [])
        for value in 1...6 {
            let id = String(format: "%03d", value)
            registry.players[id] = PlayerProfile(id: id, isTest: false, createdAt: now, sessionIds: [])
        }
        registry.maxFormalPlayerId = 6
        return registry
    }

    private static func normalized(_ registry: PlayerRegistry) -> PlayerRegistry {
        var result = registry
        let formalIds = result.players.values
            .filter { !$0.isTest }
            .compactMap { Int($0.id) }
        result.maxFormalPlayerId = max(result.maxFormalPlayerId, formalIds.max() ?? 6)
        return result
    }

    private static let csvEscape: (String) -> String = { value in
        if value.contains(",") || value.contains("\"") || value.contains("\n") {
            return "\"\(value.replacingOccurrences(of: "\"", with: "\"\""))\""
        }
        return value
    }

    private static let fileTimestamp: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return formatter
    }()

    private static let iso8601: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
}

enum StoreError: LocalizedError {
    case activeSessionExists
    case noActiveSession
    case playerNotFound
    case playerAlreadyExists
    case recordNotFound
    case invalidTestPlayer
    case invalidFatigueConfiguration

    var errorDescription: String? {
        switch self {
        case .invalidTestPlayer: return "只有 000 测试球员可以创建测试会话。"
        case .invalidFatigueConfiguration: return "疲劳测试需要固定动作、固定距离和至少 1 次目标。"
        case .activeSessionExists: return "已有正在进行的球员采集，请先结束当前会话。"
        case .noActiveSession: return "当前没有正在进行的采集会话。"
        case .playerNotFound: return "没有找到该球员编号。"
        case .playerAlreadyExists: return "该球员编号已经存在。"
        case .recordNotFound: return "没有找到要编辑的记录。"
        }
    }
}
