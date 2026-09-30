import { computeFreeSlots, minutesToTime } from "./freeSlots";

const asTimes = (gaps) => gaps.map((g) => `${minutesToTime(g.start)}-${minutesToTime(g.end)}@${minutesToTime(g.bookAt)}`);

describe("computeFreeSlots", () => {
  it("randevu öncesi, arası ve sonrasındaki boşlukları verir", () => {
    const gaps = computeFreeSlots({
      openTime: "09:00",
      closeTime: "18:00",
      busy: [["10:00", 60], ["13:00", 60], ["15:30", 90]],
      nowTime: "08:00",
    });
    expect(asTimes(gaps)).toEqual([
      "09:00-10:00@09:00",
      "11:00-13:00@11:00",
      "14:00-15:30@14:00",
      "17:00-18:00@17:00",
    ]);
  });

  it("geçmiş kısmı gösterilmez, devam eden boşluk sonraki slottan başlar", () => {
    const gaps = computeFreeSlots({
      openTime: "09:00",
      closeTime: "18:00",
      busy: [["10:00", 60], ["15:30", 60]],
      nowTime: "13:42",
    });
    expect(asTimes(gaps)).toEqual(["13:45-15:30@13:45", "16:30-18:00@16:30"]);
  });

  it("molayı dolu sayar, 30 dk'dan kısa boşluğu atlar", () => {
    const gaps = computeFreeSlots({
      openTime: "09:00",
      closeTime: "13:00",
      busy: [["09:00", 60], { start: "10:20", end: "11:00" }, ["11:00", 90]],
      nowTime: "08:00",
    });
    // 10:00-10:20 (20 dk) atlanır, 12:30-13:00 kalır
    expect(asTimes(gaps)).toEqual(["12:30-13:00@12:30"]);
  });

  it("çakışan randevuları birleştirir, randevu bitişi slota hizalanır", () => {
    const gaps = computeFreeSlots({
      openTime: "08:30",
      closeTime: "12:00",
      busy: [["08:30", 50], ["08:45", 30]],
      nowTime: "07:00",
    });
    // İçteki randevu 09:15'te biter, blok 09:20'de; rezervasyon slotu 08:30'dan 15 dk adımla → 09:30
    expect(asTimes(gaps)).toEqual(["09:20-12:00@09:30"]);
  });

  it("kapanış 00:00 gece yarısı demek; süresi olmayan randevu 30 dk sayılır", () => {
    const gaps = computeFreeSlots({
      openTime: "20:00",
      closeTime: "00:00",
      busy: [["20:00", null]],
      nowTime: "19:00",
    });
    expect(asTimes(gaps)).toEqual(["20:30-00:00@20:30"]);
  });

  it("kapanıştan sonra ya da gün doluyken boş liste", () => {
    expect(computeFreeSlots({ openTime: "09:00", closeTime: "18:00", busy: [], nowTime: "18:30" })).toEqual([]);
    expect(computeFreeSlots({ openTime: "09:00", closeTime: "10:00", busy: [["09:00", 60]], nowTime: "08:00" })).toEqual([]);
  });
});
