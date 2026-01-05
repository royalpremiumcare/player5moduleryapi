import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { seoData } from "@/data/seoData";

const resolveLocale = (lang) => {
  if (!lang) return "en-GB";
  const l = String(lang).toLowerCase();
  if (l.startsWith("tr")) return "tr";
  return "en-GB";
};

const labels = {
  tr: {
    sections: {
      vertical: "Sektörler",
      feature: "Özellikler",
    },
    items: {
      "berber-randevu-programi": "Berber Randevu Programı",
      "diyetisyen-randevu-programi": "Diyetisyen Randevu Programı",
      "dis-klinigi-randevu-programi": "Diş Kliniği Randevu Programı",
      "psikolog-randevu-programi": "Psikolog Randevu Programı",
      "fizyoterapi-randevu-programi": "Fizyoterapi Randevu Programı",
      "kuafor-randevu-programi": "Kuaför Randevu Programı",
      "guzellik-merkezi-randevu-programi": "Güzellik Merkezi Randevu Programı",
      "protez-tirnak-randevu-programi": "Protez Tırnak Randevu Programı",
      "spor-salonu-randevu-programi": "Spor Salonu Randevu Programı",
      "ozel-ders-randevu-programi": "Özel Ders Randevu Programı",
      "pilates-studyo-randevu-programi": "Pilates Stüdyosu Randevu Programı",
      "hali-yikama-randevu-programi": "Halı Yıkama Randevu/Servis Takip",
      "oto-kuafor-randevu-programi": "Oto Kuaför Randevu Programı",
      "oto-ekspertiz-randevu-programi": "Oto Ekspertiz Randevu Programı",
      "veteriner-randevu-programi": "Veteriner Randevu Programı",

      "yapay-zeka-randevu-asistani": "Yapay Zeka Randevu Asistanı",
      "whatsapp-randevu-hatirlatma": "WhatsApp Randevu Hatırlatma",
      "online-randevu-sayfasi": "Online Randevu Sayfası",
      "gelir-gider-personel-takibi": "Gelir-Gider & Personel Takibi",
      "mobil-randevu-uygulamasi": "Mobil Randevu Uygulaması (PWA)",
    },
  },
  "en-GB": {
    sections: {
      vertical: "Sectors",
      feature: "Features",
    },
    items: {
      "barber-appointment-software": "Barber Appointment Software",
      "dietitian-appointment-software": "Dietitian Appointment Software",
      "dental-clinic-appointment-software": "Dental Clinic Appointment Software",
      "psychologist-appointment-software": "Psychologist Appointment Software",
      "physiotherapy-appointment-software": "Physiotherapy Appointment Software",
      "hair-salon-appointment-software": "Hair Salon Appointment Software",
      "beauty-salon-appointment-software": "Beauty Salon Appointment Software",
      "nail-studio-appointment-software": "Nail Studio Appointment Software",
      "gym-booking-software": "Gym Booking Software",
      "private-tutor-booking-software": "Tutor & Coach Booking Software",
      "pilates-studio-booking-software": "Pilates Studio Booking Software",
      "carpet-cleaning-scheduling-software": "Carpet Cleaning Scheduling Software",
      "car-detailing-appointment-software": "Car Detailing Appointment Software",
      "vehicle-inspection-booking-software": "Vehicle Inspection Booking Software",
      "vet-appointment-software": "Vet Appointment Software",

      "ai-appointment-assistant": "AI Appointment Assistant",
      "whatsapp-appointment-reminders": "WhatsApp Appointment Reminders",
      "online-booking-page": "Online Booking Page",
      "revenue-expenses-staff-tracking": "Revenue, Expenses & Staff Tracking",
      "mobile-appointment-app-pwa": "Mobile App (PWA)",
    },
  },
};

const buildPath = (item, localeKey) => {
  const isEn = localeKey === "en-GB";
  if (item.category === "vertical") {
    return isEn ? `/solutions/${item.slug}` : `/cozumler/${item.slug}`;
  }
  return isEn ? `/features/${item.slug}` : `/ozellikler/${item.slug}`;
};

export default function SeoLinks() {
  const { i18n } = useTranslation();

  const locale = resolveLocale(i18n.language);
  const isTr = locale === "tr";

  const localeKey = isTr ? "tr" : "en-GB";
  const copy = labels[localeKey];

  const { sectors, features } = useMemo(() => {
    const items = seoData.filter((x) => x.locale === localeKey);

    const vertical = items
      .filter((x) => x.category === "vertical")
      .map((x) => ({
        ...x,
        linkLabel: copy.items[x.slug] || x.title,
      }))
      .sort((a, b) => a.linkLabel.localeCompare(b.linkLabel, localeKey));

    const feature = items
      .filter((x) => x.category === "feature")
      .map((x) => ({
        ...x,
        linkLabel: copy.items[x.slug] || x.title,
      }))
      .sort((a, b) => a.linkLabel.localeCompare(b.linkLabel, localeKey));

    return { sectors: vertical, features: feature };
  }, [localeKey, copy]);

  return (
    <section className="mt-10">
      <div className="border-t border-gray-200 pt-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div>
            <h4 className="font-bold text-gray-900 mb-4">{copy.sections.vertical}</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2">
              {sectors.map((item) => (
                <Link
                  key={`${item.locale}-${item.category}-${item.slug}`}
                  to={buildPath(item, localeKey)}
                  className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  {item.linkLabel}
                </Link>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-bold text-gray-900 mb-4">{copy.sections.feature}</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
              {features.map((item) => (
                <Link
                  key={`${item.locale}-${item.category}-${item.slug}`}
                  to={buildPath(item, localeKey)}
                  className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  {item.linkLabel}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
