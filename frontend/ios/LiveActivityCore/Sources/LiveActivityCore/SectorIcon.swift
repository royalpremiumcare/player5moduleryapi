// Maps the server's sector icon token (ContentState.icon) to an SF Symbol name.
// All symbols exist on iOS 16. Missing or unknown tokens fall back to "hourglass".

public func symbolForIcon(_ icon: String?) -> String {
    switch icon {
    case "hair": return "scissors"
    case "beauty": return "paintbrush.pointed"
    case "spa": return "leaf"
    case "diet": return "fork.knife"
    case "therapy": return "bubble.left.and.bubble.right"
    case "dental": return "stethoscope"
    default: return "hourglass"
    }
}
