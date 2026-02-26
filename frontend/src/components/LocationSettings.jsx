import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GoogleMap, Marker, useLoadScript } from "@react-google-maps/api";
import usePlacesAutocomplete, { getDetails } from "use-places-autocomplete";
import { ArrowLeft, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import api from "../api/api";

const MAP_LIBRARIES = ["places"];
const DEFAULT_CENTER = { lat: 41.0082, lng: 28.9784 }; // Istanbul default
const DEFAULT_CENTER_LONDON = { lat: 51.5074, lng: -0.1278 };
const PREDICTIONS_DEBOUNCE_MS = 500;

const MAP_OPTIONS = {
  streetViewControl: false,
  mapTypeControl: false,
  fullscreenControl: false,
};

const mapContainerStyle = {
  width: "100%",
  height: "320px",
  borderRadius: "12px",
};

const LocationMap = memo(function LocationMap({ isLoaded, center, markerPos, zoom, onMarkerDragEnd }) {
  if (!isLoaded) {
    return <div className="w-full h-[320px] rounded-xl bg-gray-100 border border-gray-200" />;
  }

  return (
    <GoogleMap
      mapContainerStyle={mapContainerStyle}
      zoom={zoom}
      center={center}
      options={MAP_OPTIONS}
    >
      {markerPos && (
        <Marker
          position={markerPos}
          draggable
          onDragEnd={onMarkerDragEnd}
        />
      )}
    </GoogleMap>
  );
});

const LocationSettings = ({ onNavigate }) => {
  const { t, i18n } = useTranslation();
  const apiKey = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

  const loadScriptOptions = useMemo(() => ({
    googleMapsApiKey: apiKey || "",
    libraries: MAP_LIBRARIES,
  }), [apiKey]);

  const { isLoaded, loadError } = useLoadScript(loadScriptOptions);

  const sessionTokenRef = useRef(null);
  const [sessionToken, setSessionToken] = useState(null);

  const [settings, setSettings] = useState(null);
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);

  const [activePredictionIndex, setActivePredictionIndex] = useState(-1);

  const [address, setAddress] = useState("");
  const [markerPos, setMarkerPos] = useState(null);

  const isEnglish = (i18n.language || "").toLowerCase().startsWith("en");
  const countryCode = isEnglish ? "gb" : "tr";
  const fallbackCenter = isEnglish ? DEFAULT_CENTER_LONDON : DEFAULT_CENTER;

  const canUseMaps = Boolean(apiKey) && isLoaded && !loadError;

  const placesRequestOptions = useMemo(() => (
    sessionToken
      ? { sessionToken, componentRestrictions: { country: countryCode } }
      : undefined
  ), [sessionToken, countryCode]);

  const {
    ready,
    value,
    suggestions,
    setValue,
    clearSuggestions,
    init,
  } = usePlacesAutocomplete({
    initOnMount: false,
    debounce: PREDICTIONS_DEBOUNCE_MS,
    requestOptions: placesRequestOptions,
  });

  const center = useMemo(() => markerPos || fallbackCenter, [markerPos, fallbackCenter]);

  const refreshSessionToken = useCallback(() => {
    if (!window.google?.maps?.places) return;
    const nextToken = new window.google.maps.places.AutocompleteSessionToken();
    sessionTokenRef.current = nextToken;
    setSessionToken(nextToken);
  }, []);

  const loadSettings = useCallback(async () => {
    setLoadingSettings(true);
    try {
      const response = await api.get("/settings");
      const data = response.data;
      setSettings(data);

      const existingLocation = data?.location;
      if (existingLocation?.address) {
        setAddress(existingLocation.address);
        setValue(existingLocation.address, false);
      }
      if (existingLocation?.coordinates?.lat != null && existingLocation?.coordinates?.lng != null) {
        setMarkerPos({
          lat: Number(existingLocation.coordinates.lat),
          lng: Number(existingLocation.coordinates.lng),
        });
      }
    } catch (err) {
      toast.error(t('settings.locationPage.loadError'));
    } finally {
      setLoadingSettings(false);
    }
  }, [setValue, t]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (!canUseMaps) return;

    if (!sessionTokenRef.current) {
      const nextToken = new window.google.maps.places.AutocompleteSessionToken();
      sessionTokenRef.current = nextToken;
      setSessionToken(nextToken);
    }

    init();
  }, [canUseMaps, init]);

  const selectPlaceById = useCallback(async (placeId) => {
    if (!placeId) return;
    if (!canUseMaps) return;
    if (!sessionTokenRef.current) return;

    try {
      const place = await getDetails({
        placeId,
        sessionToken: sessionTokenRef.current,
        fields: ["geometry", "name", "formatted_address"],
      });

      if (!place) {
        toast.error(t('settings.locationPage.placeDetailsError'));
        return;
      }

      const lat = place.geometry?.location?.lat?.();
      const lng = place.geometry?.location?.lng?.();
      if (lat == null || lng == null) {
        toast.error(t('settings.locationPage.coordinateError'));
        return;
      }

      const formattedAddress = place.formatted_address || place.name || "";

      setAddress(formattedAddress);
      setValue(formattedAddress, false);
      setMarkerPos({ lat, lng });
      clearSuggestions();
      setActivePredictionIndex(-1);

      // IMPORTANT: Refresh token after a selection to start a new billing session next time
      refreshSessionToken();
    } catch (err) {
      toast.error(t('settings.locationPage.placeDetailsError'));
    }
  }, [canUseMaps, clearSuggestions, refreshSessionToken, setValue, t]);

  const handleInputChange = (e) => {
    const value = e.target.value;
    const shouldFetch = Boolean(value && value.trim().length >= 3);
    setValue(value, shouldFetch);
    if (!shouldFetch) {
      clearSuggestions();
      setActivePredictionIndex(-1);
    }
  };

  const predictions = suggestions?.data || [];
  const showPredictions = suggestions?.status === "OK" && predictions.length > 0;

  const handlePredictionClick = (prediction) => {
    selectPlaceById(prediction.place_id);
  };

  const handleKeyDown = (e) => {
    const predictions = suggestions?.data || [];
    if (!predictions.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActivePredictionIndex((idx) => Math.min(idx + 1, predictions.length - 1));
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActivePredictionIndex((idx) => Math.max(idx - 1, 0));
    }

    if (e.key === "Enter") {
      if (activePredictionIndex >= 0 && predictions[activePredictionIndex]) {
        e.preventDefault();
        selectPlaceById(predictions[activePredictionIndex].place_id);
      }
    }

    if (e.key === "Escape") {
      clearSuggestions();
      setActivePredictionIndex(-1);
    }
  };

  const handleMarkerDragEnd = useCallback((e) => {
    const lat = e.latLng?.lat?.();
    const lng = e.latLng?.lng?.();
    if (lat == null || lng == null) return;
    setMarkerPos({ lat, lng });
  }, []);

  const handleRemoveLocation = async () => {
    setRemoving(true);
    try {
      await api.delete("/settings/location");
      setAddress("");
      setValue("", false);
      setMarkerPos(null);
      clearSuggestions();
      toast.success(t('settings.locationPage.removed'));
      await loadSettings();
    } catch (err) {
      const msg = err?.response?.data?.detail || t('settings.locationPage.removeError');
      toast.error(msg);
    } finally {
      setRemoving(false);
    }
  };

  const handleSave = async () => {
    if (!address || !markerPos) {
      toast.error(t('settings.locationPage.selectAddressError'));
      return;
    }

    setSaving(true);
    try {
      await api.put("/settings/location", {
        address,
        coordinates: {
          lat: markerPos.lat,
          lng: markerPos.lng,
        },
      });
      toast.success(t('settings.locationPage.saved'));
      await loadSettings();
    } catch (err) {
      const msg = err?.response?.data?.detail || t('settings.locationPage.saveError');
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  if (!apiKey) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: "Inter, sans-serif" }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <h2 className="text-lg font-bold text-gray-900">{t('settings.locationPage.title')}</h2>
            <p className="text-sm text-gray-600 mt-2">
              {t('settings.locationPage.apiKeyMissing')}
            </p>
            <div className="mt-6">
              <Button onClick={() => onNavigate && onNavigate("settings")} variant="ghost">
                {t('settings.backToSettings')}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: "Inter, sans-serif" }}>
        <div className="px-4 pt-6 pb-4">
          <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
            <h2 className="text-lg font-bold text-gray-900">{t('settings.locationPage.title')}</h2>
            <p className="text-sm text-gray-600 mt-2">{t('settings.locationPage.mapLoadError')}</p>
            <div className="mt-6">
              <Button onClick={() => onNavigate && onNavigate("settings")} variant="ghost">
                {t('settings.backToSettings')}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20" style={{ fontFamily: "Inter, sans-serif" }}>
      <div className="px-4 pt-6 pb-4">
        <Card className="bg-white shadow-md border border-gray-200 rounded-xl p-6">
          <div className="mb-4">
            <button
              onClick={() => onNavigate && onNavigate("settings")}
              className="flex items-center gap-2 text-gray-700 hover:text-gray-900 mb-4 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm font-medium">{t('settings.backToSettings')}</span>
            </button>
            <div>
              <h2 className="text-lg font-bold text-gray-900">{t('settings.locationPage.title')}</h2>
              <p className="text-sm text-gray-600 mt-1">{t('settings.locationPage.subtitle')}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="location-search" className="text-sm font-semibold text-gray-900">
                {t('settings.locationPage.addressLabel')}
              </Label>
              <div className="relative">
                <Input
                  id="location-search"
                  type="text"
                  value={value}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={t('settings.locationPage.addressPlaceholder')}
                  className="text-base"
                  disabled={!isLoaded || !ready}
                />

                {showPredictions && (
                  <div className="absolute z-50 mt-2 w-full bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
                    {predictions.map((p, idx) => (
                      <button
                        key={p.place_id}
                        type="button"
                        onClick={() => handlePredictionClick(p)}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${
                          idx === activePredictionIndex ? "bg-gray-50" : "bg-white"
                        }`}
                      >
                        <div className="font-medium text-gray-900">{p.structured_formatting?.main_text || p.description}</div>
                        {p.structured_formatting?.secondary_text && (
                          <div className="text-xs text-gray-500">{p.structured_formatting.secondary_text}</div>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {address && (
                <p className="text-xs text-gray-600">{t('settings.locationPage.selected')}: {address}</p>
              )}
            </div>

            <div>
              <LocationMap
                isLoaded={isLoaded}
                zoom={markerPos ? 16 : 12}
                center={center}
                markerPos={markerPos}
                onMarkerDragEnd={handleMarkerDragEnd}
              />
            </div>

            <div className="flex items-center justify-end gap-2">
              {settings?.location?.address && (
                <Button
                  onClick={handleRemoveLocation}
                  disabled={removing || saving || loadingSettings}
                  variant="outline"
                  className="border-red-300 text-red-600 hover:bg-red-50 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4 mr-1" />
                  {removing ? t('settings.locationPage.removing') : t('settings.locationPage.remove')}
                </Button>
              )}
              <Button onClick={handleSave} disabled={saving || loadingSettings} className="bg-blue-600 hover:bg-blue-700">
                {saving ? t('settings.locationPage.saving') : t('settings.locationPage.save')}
              </Button>
            </div>

            {settings?.location?.coordinates && (
              <div className="text-xs text-gray-500">
                {t('settings.locationPage.current')}: {Number(settings.location.coordinates.lat).toFixed(6)}, {Number(settings.location.coordinates.lng).toFixed(6)}
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default LocationSettings;
