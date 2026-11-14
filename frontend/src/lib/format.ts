/** Форматирование только на фронте: в API — метры и секунды. */
import { isCategory } from "../search/params";
import type { Category } from "../search/params";

export function formatDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null) return "—";
  const s = Math.round(totalSeconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(sec).padStart(2, "0")}`;
}

export function formatPace(secondsPerKm: number | null | undefined): string {
  if (secondsPerKm == null || !Number.isFinite(secondsPerKm) || secondsPerKm <= 0) return "—";
  const s = Math.round(secondsPerKm);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function formatKm(meters: number | null | undefined, digits = 1): string {
  if (meters == null) return "—";
  return (meters / 1000).toLocaleString("ru-RU", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  return `${(bytes / 1024 / 1024).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} МБ`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export const CATEGORY_LABELS: Record<Category, string> = {
  "1": "1 км",
  "5": "5 км",
  "10": "10 км",
  "21": "21 км",
  "21+": "Более 21 км",
};

/** Подпись категории из ответа API (там она строка); неизвестная показывается как есть. */
export function categoryLabel(category: string): string {
  return isCategory(category) ? CATEGORY_LABELS[category] : category;
}

/** Разница во времени без знака: «18 с», «1:05». */
export function formatDiff(seconds: number): string {
  const s = Math.round(Math.abs(seconds));
  return s < 60 ? `${s} с` : formatDuration(s);
}

/** «12 ноября» — без года, как в макетах. */
export function formatDayMonth(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}
