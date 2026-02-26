import Foundation
import Capacitor
import ContactsUI

@objc(ContactPickerPlugin)
public class ContactPickerPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "ContactPickerPlugin"
    public let jsName = "ContactPickerPlugin"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "pickContacts", returnType: CAPPluginReturnPromise)
    ]

    private var pendingCall: CAPPluginCall?

    @objc func pickContacts(_ call: CAPPluginCall) {
        self.pendingCall = call

        DispatchQueue.main.async {
            let picker = CNContactPickerViewController()
            picker.delegate = self
            self.bridge?.viewController?.present(picker, animated: true)
        }
    }
}

extension ContactPickerPlugin: CNContactPickerDelegate {
    public func contactPickerDidCancel(_ picker: CNContactPickerViewController) {
        pendingCall?.resolve(["contacts": []])
        pendingCall = nil
    }

    public func contactPicker(_ picker: CNContactPickerViewController, didSelect contacts: [CNContact]) {
        var result: [[String: Any]] = []

        for contact in contacts {
            let name = "\(contact.givenName) \(contact.familyName)".trimmingCharacters(in: .whitespaces)
            let phones = contact.phoneNumbers.map { $0.value.stringValue }

            if !name.isEmpty && !phones.isEmpty {
                result.append([
                    "name": name,
                    "phone": phones[0]
                ])
            }
        }

        pendingCall?.resolve(["contacts": result])
        pendingCall = nil
    }
}
