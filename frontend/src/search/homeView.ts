/** Исходная область карты и ответ на «Показать треки рядом?» — в localStorage браузера. */
import { VLADIVOSTOK } from "./params";
import type { View } from "./params";

const HOME_KEY = "runners.homeView";
const NEARBY_KEY = "runners.nearbyAnswer";

export type NearbyAnswer = "accepted" | "declined";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // хранилище недоступно (приватный режим) — вопрос просто зададим снова
  }
}

export function getHomeView(): View {
  const raw = read(HOME_KEY);
  if (!raw) return VLADIVOSTOK;
  try {
    const v = JSON.parse(raw) as View;
    return Number.isFinite(v.lat) && Number.isFinite(v.lon) && Number.isFinite(v.z)
      ? v
      : VLADIVOSTOK;
  } catch {
    return VLADIVOSTOK;
  }
}

export function setHomeView(v: View): void {
  write(HOME_KEY, JSON.stringify(v));
}

export function getNearbyAnswer(): NearbyAnswer | null {
  const v = read(NEARBY_KEY);
  return v === "accepted" || v === "declined" ? v : null;
}

export function setNearbyAnswer(a: NearbyAnswer): void {
  write(NEARBY_KEY, a);
}

export function locate(): Promise<{ lat: number; lon: number }> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("no geolocation"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      reject,
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    );
  });
}
