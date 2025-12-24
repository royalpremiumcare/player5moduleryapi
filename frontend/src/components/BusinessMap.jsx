import { GoogleMap, Marker, useLoadScript } from "@react-google-maps/api";
import { Button } from "@/components/ui/button";

const mapContainerStyle = {
  width: "100%",
  height: "260px",
  borderRadius: "12px",
};

const BusinessMap = ({ location }) => {
  const apiKey = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

  const { isLoaded, loadError } = useLoadScript({
    googleMapsApiKey: apiKey || "",
  });

  if (!location?.coordinates?.lat || !location?.coordinates?.lng) return null;

  const lat = Number(location.coordinates.lat);
  const lng = Number(location.coordinates.lng);

  const destination = `${lat},${lng}`;
  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;

  if (!apiKey) {
    return (
      <div className="w-full">
        <div className="w-full h-[260px] rounded-xl bg-zinc-100 border border-zinc-200 flex items-center justify-center">
          <div className="text-sm text-zinc-600">Harita için API anahtarı gerekli.</div>
        </div>
        <div className="mt-3 flex justify-end">
          <Button asChild className="bg-zinc-900 hover:bg-black text-white">
            <a href={directionsUrl} target="_blank" rel="noreferrer">
              Yol Tarifi Al
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
          <div className="text-sm text-zinc-600">Harita yüklenemedi.</div>
        </div>
        <div className="mt-3 flex justify-end">
          <Button asChild className="bg-zinc-900 hover:bg-black text-white">
            <a href={directionsUrl} target="_blank" rel="noreferrer">
              Yol Tarifi Al
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
            Yol Tarifi Al
          </a>
        </Button>
      </div>
    </div>
  );
};

export default BusinessMap;
