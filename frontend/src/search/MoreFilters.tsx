import { useTranslation } from "react-i18next";

import { formatPace } from "../lib/format";
import type { Filters } from "./params";

function parsePace(text: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(text.trim());
  if (!m) return null;
  return Number(m[1]) * 60 + Number(m[2]);
}

function PaceInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <label className="field field--compact">
      {label}
      <input
        className="input input--sm"
        placeholder="4:30"
        inputMode="numeric"
        defaultValue={value !== null ? formatPace(value) : ""}
        onBlur={(e) => onChange(e.target.value.trim() === "" ? null : parsePace(e.target.value))}
      />
    </label>
  );
}

export function MoreFilters({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
}) {
  const { t } = useTranslation();
  const numeric = (v: string) => (v === "" ? null : Number(v));
  return (
    <div className="more-filters">
      <div className="grid-2">
        <label className="field field--compact">
          {t("search.timeFrom")}
          <input
            className="input input--sm"
            type="number"
            min={0}
            value={filters.tmin ?? ""}
            onChange={(e) => onChange({ tmin: numeric(e.target.value) })}
          />
        </label>
        <label className="field field--compact">
          {t("search.timeTo")}
          <input
            className="input input--sm"
            type="number"
            min={0}
            value={filters.tmax ?? ""}
            onChange={(e) => onChange({ tmax: numeric(e.target.value) })}
          />
        </label>
        <PaceInput
          label={t("search.paceFrom")}
          value={filters.pmin}
          onChange={(v) => onChange({ pmin: v })}
        />
        <PaceInput
          label={t("search.paceTo")}
          value={filters.pmax}
          onChange={(v) => onChange({ pmax: v })}
        />
        <label className="field field--compact">
          {t("search.dateFrom")}
          <input
            className="input input--sm"
            type="date"
            value={filters.from ?? ""}
            onChange={(e) => onChange({ from: e.target.value || null })}
          />
        </label>
        <label className="field field--compact">
          {t("search.dateTo")}
          <input
            className="input input--sm"
            type="date"
            value={filters.to ?? ""}
            onChange={(e) => onChange({ to: e.target.value || null })}
          />
        </label>
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={filters.att === true}
          onChange={(e) => onChange({ att: e.target.checked ? true : null })}
        />
        {t("search.hasAttempts")}
      </label>
    </div>
  );
}
