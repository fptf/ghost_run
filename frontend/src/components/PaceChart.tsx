import { useTranslation } from "react-i18next";

import { formatPace } from "../lib/format";

interface Split {
  idx: number;
  distance_m: number;
  time_s: number;
}

/** Темп по километрам: столбик на каждый км, чем быстрее — тем выше. */
export function PaceChart({ splits }: { splits: Split[] }) {
  const { t } = useTranslation();
  const paces = splits
    .filter((s) => s.distance_m >= 50)
    .map((s) => ({ idx: s.idx, pace: s.time_s / (s.distance_m / 1000) }));
  if (paces.length === 0) return null;

  const slowest = Math.max(...paces.map((p) => p.pace));
  const fastest = Math.min(...paces.map((p) => p.pace));
  const span = slowest - fastest || 30;
  // Самый медленный км — 20% высоты, самый быстрый — 100%.
  const height = (pace: number) => 20 + ((slowest - pace) / span) * 80;
  // При большом числе км подписываем только лучший и худший, остальные — в подсказке.
  const labelAll = paces.length <= 14;

  return (
    <figure className="pace-chart">
      <figcaption className="field__hint">{t("track.paceByKm")}</figcaption>
      <ol className="pace-chart__bars" aria-label={t("track.paceByKm")}>
        {paces.map((p) => (
          <li key={p.idx} className="pace-chart__col" title={`${p.idx} км — ${formatPace(p.pace)}`}>
            <span
              className={`pace-chart__value${labelAll || p.pace === fastest || p.pace === slowest ? "" : " pace-chart__value--hidden"}`}
              aria-hidden="true"
            >
              {formatPace(p.pace)}
            </span>
            <span
              className={`pace-chart__bar${p.pace === fastest ? " pace-chart__bar--best" : ""}`}
              style={{ height: `${height(p.pace)}%` }}
            />
            <span className="pace-chart__label">{p.idx}</span>
            <span className="visually-hidden">{`${p.idx} км — ${formatPace(p.pace)}`}</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}
