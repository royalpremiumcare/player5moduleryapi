#import <Capacitor/Capacitor.h>

CAP_PLUGIN(PlannLiveActivityPlugin, "PlannLiveActivity",
    CAP_PLUGIN_METHOD(register, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(reconcile, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(unregister, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(getStatus, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(openSettings, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(setWidgetCredential, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(clearWidgetCredential, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(reloadWidgets, CAPPluginReturnPromise);
    CAP_PLUGIN_METHOD(widgetCredentialPresent, CAPPluginReturnPromise);
)
