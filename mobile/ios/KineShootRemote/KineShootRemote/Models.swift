import Foundation

enum PlayerSessionType: String, Codable, CaseIterable, Identifiable, Hashable {
    case standard20
    case repeat20
    case supplementary20
    case fatigue
    case test

    var id: String { rawValue }

    var title: String {
        switch self {
        case .standard20: return "正常采集"
        case .repeat20: return "重采"
        case .supplementary20: return "补采"
        case .fatigue: return "疲劳测试"
        case .test: return "测试采集"
        }
    }

    var defaultTarget: Int {
        switch self {
        case .standard20, .repeat20, .supplementary20, .test: return 20
        case .fatigue: return 50
        }
    }
}

enum PlayerSessionStatus: String, Codable, Hashable {
    case active
    case ended
    case endedEarly = "ended_early"
    case abolished

    var title: String {
        switch self {
        case .active: return "进行中"
        case .ended: return "已结束"
        case .endedEarly: return "提前结束"
        case .abolished: return "已废除"
        }
    }
}

enum ShotAction: String, Codable, CaseIterable, Identifiable, Hashable {
    case staticSimulation
    case shot
    case rhythmVariation
    case stanceVariation
    case freeVariation
    case freeTest

    var id: String { rawValue }

    var title: String {
        switch self {
        case .staticSimulation: return "静止模拟投篮"
        case .shot: return "投篮"
        case .rhythmVariation: return "变化节奏"
        case .stanceVariation: return "变化站姿"
        case .freeVariation: return "自由变化组投篮"
        case .freeTest: return "自由测试"
        }
    }
}

enum ShotDistance: String, Codable, CaseIterable, Identifiable, Hashable {
    case noBall
    case close
    case mid
    case three
    case free

    var id: String { rawValue }

    var title: String {
        switch self {
        case .noBall: return "无球"
        case .close: return "近距离"
        case .mid: return "中距离"
        case .three: return "三分"
        case .free: return "自由"
        }
    }
}

enum ShotOrientation: String, Codable, CaseIterable, Identifiable, Hashable {
    case facingBasket
    case side
    case free

    var id: String { rawValue }

    var title: String {
        switch self {
        case .facingBasket: return "正对篮筐"
        case .side: return "侧身"
        case .free: return "自由朝向"
        }
    }
}

enum ShotResult: String, Codable, CaseIterable, Identifiable, Hashable {
    case made
    case missed
    case undecided

    var id: String { rawValue }

    var title: String {
        switch self {
        case .made: return "进"
        case .missed: return "不进"
        case .undecided: return "未判定"
        }
    }
}

enum DataValidity: String, Codable, CaseIterable, Identifiable, Hashable {
    case pending
    case valid
    case invalid

    var id: String { rawValue }

    var title: String {
        switch self {
        case .pending: return "待检"
        case .valid: return "有效"
        case .invalid: return "无效"
        }
    }
}

enum InvalidReason: String, Codable, CaseIterable, Identifiable, Hashable {
    case handNotStable
    case startedWithBallRaised
    case processError
    case outOfFrame
    case deviceIssue
    case other

    var id: String { rawValue }

    var title: String {
        switch self {
        case .handNotStable: return "手未放稳"
        case .startedWithBallRaised: return "开始举球"
        case .processError: return "流程错误"
        case .outOfFrame: return "出画/遮挡"
        case .deviceIssue: return "设备异常"
        case .other: return "其他"
        }
    }
}

struct CapturePlanSlot: Codable, Equatable {
    let action: ShotAction
    let distance: ShotDistance
}

struct ShotRecord: Codable, Identifiable, Equatable {
    var id: UUID = UUID()
    var shotNo: Int
    var plannedAction: ShotAction?
    var plannedDistance: ShotDistance?
    var action: ShotAction
    var distance: ShotDistance
    var orientation: ShotOrientation
    var shotResult: ShotResult
    var dataValidity: DataValidity
    var invalidReasons: [InvalidReason]
    var notes: String
    var capturedAt: Date
    var videoFileName: String?
    var photoLocalIdentifier: String?
}

struct PlayerSession: Codable, Identifiable, Equatable {
    let id: String
    let playerId: String
    let sessionType: PlayerSessionType
    let revision: Int
    let isTest: Bool
    let startedAt: Date
    var endedAt: Date?
    var status: PlayerSessionStatus
    var targetValidCount: Int
    var fixedAction: ShotAction?
    var fixedDistance: ShotDistance?
    var records: [ShotRecord]

    static let standardPlan: [CapturePlanSlot] = {
        var slots: [CapturePlanSlot] = []
        slots.append(contentsOf: Array(repeating: CapturePlanSlot(action: .staticSimulation, distance: .noBall), count: 2))
        slots.append(contentsOf: Array(repeating: CapturePlanSlot(action: .shot, distance: .close), count: 6))
        slots.append(contentsOf: Array(repeating: CapturePlanSlot(action: .shot, distance: .mid), count: 6))
        slots.append(contentsOf: Array(repeating: CapturePlanSlot(action: .shot, distance: .three), count: 6))
        return slots
    }()

    var validCount: Int {
        records.filter { $0.dataValidity == .valid }.count
    }

    var invalidCount: Int {
        records.filter { $0.dataValidity == .invalid }.count
    }

    var nextShotNo: Int {
        records.count + 1
    }

    var hasReachedTarget: Bool {
        validCount >= targetValidCount
    }

    var planRemaining: Int {
        max(0, targetValidCount - validCount)
    }

    var nextPlannedSlot: CapturePlanSlot? {
        switch sessionType {
        case .standard20, .repeat20, .supplementary20:
            guard validCount < Self.standardPlan.count else {
                return nil
            }
            return Self.standardPlan[validCount]
        case .fatigue:
            guard let fixedAction, let fixedDistance else {
                return nil
            }
            return CapturePlanSlot(action: fixedAction, distance: fixedDistance)
        case .test:
            return nil
        }
    }
}

struct PlayerProfile: Codable, Identifiable, Equatable {
    let id: String
    var isTest: Bool
    var createdAt: Date
    var sessionIds: [String]
}

struct PlayerRegistry: Codable {
    var version: Int = 1
    var players: [String: PlayerProfile] = [:]
    var maxFormalPlayerId: Int = 6
    var activePlayerId: String?
    var activeSessionId: String?

    var sortedPlayers: [PlayerProfile] {
        players.values.sorted { $0.id < $1.id }
    }

    var nextNewPlayerId: String {
        String(format: "%03d", maxFormalPlayerId + 1)
    }
}

struct PlayerRegistryArchive: Codable {
    let exportedAt: Date
    let registry: PlayerRegistry
    let sessions: [PlayerSession]
}

struct ShotReviewDraft: Identifiable, Equatable {
    var id: UUID = UUID()
    var recordId: UUID?
    var shotNo: Int
    var plannedAction: ShotAction?
    var plannedDistance: ShotDistance?
    var action: ShotAction
    var distance: ShotDistance
    var orientation: ShotOrientation
    var shotResult: ShotResult
    var dataValidity: DataValidity
    var invalidReasons: [InvalidReason]
    var notes: String
    var capturedAt: Date
    var videoFileName: String?
    var photoLocalIdentifier: String?

    func makeRecord() -> ShotRecord {
        ShotRecord(
            id: recordId ?? UUID(),
            shotNo: shotNo,
            plannedAction: plannedAction,
            plannedDistance: plannedDistance,
            action: action,
            distance: distance,
            orientation: orientation,
            shotResult: shotResult,
            dataValidity: dataValidity,
            invalidReasons: invalidReasons,
            notes: notes,
            capturedAt: capturedAt,
            videoFileName: videoFileName,
            photoLocalIdentifier: photoLocalIdentifier
        )
    }
}
