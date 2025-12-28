import { GoogleMap, Marker, useLoadScript } from "@react-google-maps/api";
import { Button } from "@/components/ui/button";
import { useMemo, memo } from "react";
import { useTranslation } from "react-i18next";

const mapContainerStyle = {
  width: "100%",
  height: "260px",
  borderRadius: "12px",
};

const BusinessMap = ({ location }) => {
  const { t } = useTranslation();
  const apiKey = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

  const loadScriptOptions = useMemo(() => ({
    googleMapsApiKey: apiKey || "",
  }), [apiKey]);

  const { isLoaded, loadError } = useLoadScript(loadScriptOptions);

  if (!location?.coordinates?.lat || !location?.coordinates?.lng) return null;

  const lat = Number(location.coordinates.lat);
  const lng = Number(location.coordinates.lng);

  const destination = `${lat},${lng}`;
  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;

  if (!apiKey) {
    return (
      <div className="w-full">
        <div className="w-full h-[260px] rounded-xl bg-zinc-100 border border-zinc-200 flex items-center justify-center">
          <div className="text-sm text-zinc-600">{t('publicBooking.map.apiKeyRequired')}</div>
        </div>
        <div className="mt-3 flex justify-end">
          <Button asChild className="bg-zinc-900 hover:bg-black text-white">
            <a href={directionsUrl} target="_blank" rel="noreferrer">
              {t('publicBooking.map.getDirections')}
            </a>
          </Button>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="w-full">
        <div className="w-full h-[260px] rounded-xl bg-zinc-100 border border-zinc-200 flex items-center justify-center">
          <div className="text-sm text-zinc-600">{t('publicBooking.map.loadError')}</div>
        </div>
        <div className="mt-3 flex justify-end">
          <Button asChild className="bg-zinc-900 hover:bg-black text-white">
            <a href={directionsUrl} target="_blank" rel="noreferrer">
              {t('publicBooking.map.getDirections')}
            </a>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="w-full">
        {isLoaded ? (
          <GoogleMap
            mapContainerStyle={mapContainerStyle}
            zoom={16}
            center={{ lat, lng }}
            options={{
              streetViewControl: false,
              mapTypeControl: false,
              fullscreenControl: false,
              gestureHandling: "greedy",
            }}
          >
            <Marker position={{ lat, lng }} />
          </GoogleMap>
        ) : (
          <div className="w-full h-[260px] rounded-xl bg-zinc-100 border border-zinc-200" />
        )}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs text-zinc-500 truncate pr-3">{location?.address || ""}</div>
        <Button asChild className="bg-zinc-900 hover:bg-black text-white">
          <a href={directionsUrl} target="_blank" rel="noreferrer">
            {t('publicBooking.map.getDirections')}
          </a>
        </Button>
      </div>
    </div>
  );
};

export default memo(BusinessMap);
