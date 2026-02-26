#import <Capacitor/Capacitor.h>

CAP_PLUGIN(FCMTokenPlugin, "FCMTokenPlugin",
    CAP_PLUGIN_METHOD(getToken, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(registerAndGetToken, CAPPluginReturnPromise);
)
