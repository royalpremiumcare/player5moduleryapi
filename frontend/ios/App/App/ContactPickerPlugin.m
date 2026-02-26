#import <Capacitor/Capacitor.h>

CAP_PLUGIN(ContactPickerPlugin, "ContactPickerPlugin",
    CAP_PLUGIN_METHOD(pickContacts, CAPPluginReturnPromise);
)
