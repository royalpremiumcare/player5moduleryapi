import { computeHasActiveSessions } from "./sessionPackageNav";

describe("computeHasActiveSessions", () => {
  it("boş veya tek seanslı gruplarda false", () => {
    expect(computeHasActiveSessions([])).toBe(false);
    expect(computeHasActiveSessions([{ session_group_id: "g1", session_total: 1, status: "Bekliyor" }])).toBe(
      false
    );
  });

  it("çok seanslı pakette açık randevu varken true", () => {
    const appointments = [
      { session_group_id: "g1", session_total: 3, session_number: 1, status: "Tamamlandı" },
      { session_group_id: "g1", session_total: 3, session_number: 2, status: "Bekliyor" },
    ];
    expect(computeHasActiveSessions(appointments)).toBe(true);
  });

  it("tüm seanslar terminal ise false", () => {
    const appointments = [
      { session_group_id: "g1", session_total: 2, status: "Tamamlandı" },
      { session_group_id: "g1", session_total: 2, status: "İptal Edildi" },
    ];
    expect(computeHasActiveSessions(appointments)).toBe(false);
  });

  it("session_group_id yoksa yoksay", () => {
    expect(computeHasActiveSessions([{ session_total: 3, status: "Bekliyor" }])).toBe(false);
  });

  it("paket tamamlanınca (hepsi terminal) Seanslar kapansın — false", () => {
    expect(
      computeHasActiveSessions([
        { session_group_id: "g1", session_total: 2, status: "Tamamlandı" },
        { session_group_id: "g1", session_total: 2, status: "Tamamlandı" },
      ])
    ).toBe(false);
  });
});
