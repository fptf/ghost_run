import { useTranslation } from "react-i18next";

import { PaceChart } from "../components/PaceChart";
import { TrackMap } from "../components/TrackMap";
import { formatDuration, formatKm, formatPace } from "../lib/format";
import type { TrackDetail } from "./api";

export function TrackMetrics({ track }: { track: TrackDetail }) {
  const { t } = useTranslation();
  const items = [
    { label: t("track.distance"), value: `${formatKm(track.distance_m)} км` },
    { label: t("track.time"), value: formatDuration(track.total_time_s) },
    { label: t("track.pace"), value: formatPace(track.avg_pace_s_per_km) },
    {
      label: t("track.climb"),
      value: track.has_elevation ? `${Math.round(track.elevation_gain_m ?? 0)} м` : "—",
    },
  ];
  return (
    <dl className="metrics">
      {items.map((m) => (
        <div key={m.label} className="metric">
          <dt>{m.label}</dt>
          <dd>{m.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Карта и показатели трека — общие для просмотра и формы. */
export function TrackSummaryCard({ track }: { track: TrackDetail }) {
  const { t } = useTranslation();
  const owner = track.owner;
  return (
    <>
      <section className="card card--flush">
        <TrackMap
          line={track.geometry?.coordinates}
          fullLine={owner?.full_geometry?.coordinates}
          zone={owner?.hidden_zone}
          label={t("track.mapLabel")}
        />
        {owner?.hidden_zone && (
          <p className="map-note">{t("track.zoneNote", { radius: owner.hidden_zone.radius_m })}</p>
        )}
        {/* Место под плашку совпадения с маршрутом — add-route-matching */}
      </section>
      <section className="card">
        <TrackMetrics track={track} />
        <PaceChart splits={track.splits} />
      </section>
    </>
  );
}
