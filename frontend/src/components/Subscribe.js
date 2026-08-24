import { useEffect, useState } from "react";
import { ArrowLeft, Globe, ExternalLink } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Capacitor } from "@capacitor/core";
import { buildWebsiteSubscribeUrl, openWebsiteSubscribe, prefetchWebsiteSubscribeUrl } from "../lib/openWebsiteSubscribe";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import useInAppSubscribeEnabled from "../hooks/useInAppSubscribeEnabled";
import PlanPicker from "./PlanPicker";

const WebsiteSubscribeFallback = ({ onNavigate, webUrl, appWebsiteUrl }) => {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-white pb-20 flex items-center justify-center" style={{ fontFamily: "Inter, sans-serif" }}>
      <div className="px-4 w-full max-w-md">
        <Card className="bg-white shadow-xl border border-gray-200 rounded-3xl p-8 mx-auto text-center">
          <div>
            <div className="mx-auto mb-6 w-16 h-16 rounded-2xl border border-gray-200 flex items-center justify-center bg-white">
              <Globe className="w-8 h-8 text-gray-900" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-3">
              {t("settings.subscribePage.subscriptionManagement")}
            </h2>
            <p className="text-gray-600 mb-8 leading-relaxed px-2">
              {t("appCompliance.subscriptionInfo")}
            </p>
            <Button
              type="button"
              onClick={() => {
                const ok = openWebsiteSubscribe(appWebsiteUrl);
                if (!ok) toast.error(t("appCompliance.openWebsiteFailed"));
              }}
              className="w-full bg-gray-900 hover:bg-gray-800 text-white font-semibold py-6 rounded-2xl shadow-md transition-colors flex items-center justify-center gap-2"
            >
              <ExternalLink className="w-5 h-5" />
              {t("appCompliance.goToWebsite")}
            </Button>
            <button
              onClick={() => onNavigate && onNavigate("settings")}
              className="mt-6 text-sm text-gray-500 hover:text-gray-700 font-medium transition-colors duration-200 flex items-center justify-center gap-1 mx-auto"
            >
              <ArrowLeft className="w-4 h-4" />
              {t("settings.subscribePage.backToSettings")}
            </button>
          </div>
        </Card>
        <div className="mt-4 text-center text-xs text-gray-500">{webUrl.replace("https://", "")}</div>
      </div>
    </div>
  );
};

const Subscribe = ({ onNavigate, currentUser, settings }) => {
  const { t, i18n } = useTranslation();
  const { enabled: inAppEnabled, ready } = useInAppSubscribeEnabled();
  const isNative = Capacitor.isNativePlatform();
  const webUrl = i18n.language && i18n.language.toLowerCase().startsWith("en")
    ? "https://plannapp.co.uk"
    : "https://plannapp.co";
  const websiteSubscribeUrl = buildWebsiteSubscribeUrl(webUrl, null);
  const [appWebsiteUrl, setAppWebsiteUrl] = useState(websiteSubscribeUrl);

  useEffect(() => {
    if (!isNative || inAppEnabled) return;
    prefetchWebsiteSubscribeUrl(webUrl).then(setAppWebsiteUrl);
  }, [isNative, inAppEnabled, webUrl]);

  if (isNative && !ready) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: "Inter, sans-serif" }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <p className="text-sm text-gray-600">{t("settings.subscribePage.loading")}</p>
          </Card>
        </div>
      </div>
    );
  }

  if (isNative && !inAppEnabled) {
    return (
      <WebsiteSubscribeFallback
        onNavigate={onNavigate}
        webUrl={webUrl}
        appWebsiteUrl={appWebsiteUrl}
      />
    );
  }

  return <PlanPicker onNavigate={onNavigate} currentUser={currentUser} settings={settings} />;
};

export default Subscribe;
