import Foundation

public struct ActivitySnapshot: Equatable {
    public var slotIndex: Int
    public var activityId: String
    /// active|stale|pending|ended|dismissed
    public var state: String

    public init(slotIndex: Int, activityId: String, state: String) {
        self.slotIndex = slotIndex
        self.activityId = activityId
        self.state = state
    }
}

public struct ActivitySnapshotDTO: Encodable, Equatable {
    public var slot_index: Int
    public var activity_id: String?
    public var state: String

    public init(slot_index: Int, activity_id: String?, state: String) {
        self.slot_index = slot_index
        self.activity_id = activity_id
        self.state = state
    }

    enum CodingKeys: String, CodingKey { case slot_index, activity_id, state }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(slot_index, forKey: .slot_index)
        try c.encode(activity_id, forKey: .activity_id) // explicit null when nil
        try c.encode(state, forKey: .state)
    }
}

public struct ReconcileReport: Encodable {
    public var device_id: String
    public var activities_enabled: Bool
    public var complete: Bool
    public var push_to_start_token: String?
    public var slots: [ActivitySnapshotDTO]

    public init(device_id: String, activities_enabled: Bool, complete: Bool,
                push_to_start_token: String?, slots: [ActivitySnapshotDTO]) {
        self.device_id = device_id
        self.activities_enabled = activities_enabled
        self.complete = complete
        self.push_to_start_token = push_to_start_token
        self.slots = slots
    }

    enum CodingKeys: String, CodingKey {
        case device_id, activities_enabled, complete, push_to_start_token, slots
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(device_id, forKey: .device_id)
        try c.encode(activities_enabled, forKey: .activities_enabled)
        try c.encode(complete, forKey: .complete)
        try c.encode(push_to_start_token, forKey: .push_to_start_token) // explicit null when nil
        try c.encode(slots, forKey: .slots)
    }
}

public struct LocalStart: Decodable {
    public var slot_index: Int
    public var content: PlannContentState
    public var stale_epoch: Double?
    public var relevance: Double
    public var attributes: [String: String]?
}

public struct ReconcileResponse: Decodable {
    public var end: [Int]
    public var end_activities: [String]
    public var start_locally: [LocalStart]

    enum CodingKeys: String, CodingKey { case end, end_activities, start_locally }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        end = try c.decodeIfPresent([Int].self, forKey: .end) ?? []
        end_activities = try c.decodeIfPresent([String].self, forKey: .end_activities) ?? []
        start_locally = try c.decodeIfPresent([LocalStart].self, forKey: .start_locally) ?? []
    }
}

/// Activity ids to end: those whose slot index is in `end`, plus the explicit `end_activities`.
public func endInstructions(response: ReconcileResponse, current: [ActivitySnapshot]) -> Set<String> {
    let slots = Set(response.end)
    var ids = Set(response.end_activities)
    for a in current where slots.contains(a.slotIndex) { ids.insert(a.activityId) }
    return ids
}
