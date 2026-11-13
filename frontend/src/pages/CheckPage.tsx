import { useMutation, useQuery } from "@tanstack/react-query";
import type { Polygon } from "geojson";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import { api } from "../api/client";
import type { Schemas } from "../api/client";
import { BackButton } from "../components/BackButton";
import { TrackMap } from "../components/TrackMap";
import { formatDate, formatDayMonth, formatDiff, formatDuration, formatKm } from "../lib/format";
import { useTrack } from "../tracks/api";
import { useGpxDownload } from "../tracks/useGpxDownload";
import { TrackNotFound } from "./TrackPage";

type Rule = Schemas["CheckRule"];

function ruleText(rule: Rule, t: ReturnType<typeof useTranslation>["t"]): string {
  switch (rule.code) {
    case "start":
    case "finish":
      return t(`check.rule.${rule.code}`, {
        required: Math.round(rule.required),
        value: Math.round(rule.value),
      });
    case "corridor":
      return t(rule.ok ? "check.rule.corridorOk" : "check.rule.corridorFail", {
        value: Math.round(rule.value * 100),
        required: Math.round(rule.required * 100),
      });
    case "direction":
      return t(rule.ok ? "check.rule.directionOk" : "check.rule.directionFail");
    case "length":
      return t(rule.ok ? "check.rule.lengthOk" : "check.rule.lengthFail", {
        value: Math.round(Math.abs(rule.value - 1) * 100),
        required: Math.round(rule.required * 100),
      });
  }
}

function explain(r: Schemas["CheckResponse"], t: ReturnType<typeof useTranslation>["t"]): string {
  const run = t("check.runLabel", {
    title: r.track_title ?? t("track.untitled"),
    date: formatDayMonth(r.track_started_at),
  });
  if (r.matched) {
    const verdict =
      r.diff_s === null || r.diff_s === undefined || Math.abs(r.diff_s) < 1
        ? t("match.equal")
        : r.diff_s < 0
          ? t("match.faster", { diff: formatDiff(r.diff_s) })
          : t("match.slower", { diff: formatDiff(r.diff_s) });
    return `${run}. ${formatDuration(r.result_time_s)} — ${verdict}.`;
  }
  // Главная причина: при обратном ходе проседает и покрытие, поэтому направление — первым.
  const failed = (code: Rule["code"]) => r.rules.some((x) => x.code === code && !x.ok);
  if (failed("direction")) return `${run}. ${t("check.reversed")}`;
  if (failed("corridor") && r.deviation) {
    return `${run}. ${t("check.leftAt", { km: Math.max(1, Math.ceil(r.deviation.km)) })}`;
  }
  if (failed("length")) return `${run}. ${t("check.otherLength")}`;
  return `${run}. ${t("check.notThere")}`;
}

function directionOk(r: Schemas["CheckResponse"]): boolean {
  return r.rules.every((x) => x.code !== "direction" || x.ok);
}

/** «Проверить мою пробежку» (ФТ-19, макет CheckFail). */
export function CheckPage() {
  const { trackId = "" } = useParams();
  const { t } = useTranslation();
  const route = useTrack(trackId);
  const download = useGpxDownload();
  const [chosen, setChosen] = useState<string | null>(null);

  const mine = useQuery({
    queryKey: ["my-tracks"],
    queryFn: async () => (await api.GET("/me/tracks")).data ?? [],
  });
  const check = useMutation({
    mutationFn: async (myTrackId: string) => {
      const { data, error } = await api.POST("/tracks/{track_id}/check", {
        params: { path: { track_id: trackId } },
        body: { track_id: myTrackId },
      });
      if (error || !data) throw new Error("check failed");
      return data;
    },
  });

  if (route.isPending) {
    return (
      <main className="page">
        <p className="muted">{t("common.loading")}</p>
      </main>
    );
  }
  if (route.isError || !route.data) return <TrackNotFound />;

  const runs = (mine.data ?? []).filter(
    (x) => (x.status === "draft" || x.status === "published") && x.id !== trackId,
  );
  const result = chosen ? check.data : undefined;

  return (
    <main className="page">
      <div className="page-head">
        <BackButton fallback={`/tracks/${trackId}`} />
        <div className="page-head__title">
          <h1>{t("check.title")}</h1>
          <p className="muted">{route.data.title ?? t("track.untitled")}</p>
        </div>
      </div>

      {!chosen && (
        <section className="card">
          <h2 className="card__title">{t("check.choose")}</h2>
          {runs.length === 0 ? (
            <div className="empty">{t("check.noRuns")}</div>
          ) : (
            <ul className="result-list">
              {runs.map((run) => (
                <li key={run.id}>
                  <button
                    type="button"
                    className="result"
                    onClick={() => {
                      setChosen(run.id);
                      check.mutate(run.id);
                    }}
                  >
                    <strong className="result__title">{run.title ?? t("track.untitled")}</strong>
                    <span className="result__meta">
                      {formatDate(run.started_at)} · {formatKm(run.distance_m)} км ·{" "}
                      {formatDuration(run.total_time_s)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {chosen && check.isPending && <p className="muted">{t("check.checking")}</p>}
      {chosen && check.isError && <p className="notice notice--error">{t("check.failed")}</p>}

      {result && (
        <>
          <section className="card card--flush">
            <TrackMap
              line={result.route_line?.coordinates}
              label={t("check.mapLabel")}
              check={{
                corridor: (result.corridor as unknown as Polygon | null) ?? null,
                mine: result.track_line?.coordinates ?? null,
                // место схода имеет смысл, только если направление совпадает
                deviation: directionOk(result) ? (result.deviation ?? null) : null,
              }}
            />
            <p className="map-note">{t("check.legend")}</p>
          </section>
          <section className="card">
            <h2 className={`check-verdict check-verdict--${result.matched ? "ok" : "fail"}`}>
              {result.matched ? t("check.matched") : t("check.notMatched")}
            </h2>
            <p>{explain(result, t)}</p>
            <ul className="rules">
              {result.rules.map((rule) => (
                <li key={rule.code} className={`rule rule--${rule.ok ? "ok" : "fail"}`}>
                  <span className="rule__icon" aria-hidden>
                    {rule.ok ? "✓" : "✕"}
                  </span>
                  {ruleText(rule, t)}
                </li>
              ))}
            </ul>
            <div className="row">
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={() => {
                  setChosen(null);
                  check.reset();
                }}
              >
                {t("check.another")}
              </button>
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={() => void download(trackId, route.data.title)}
              >
                {t("check.downloadRoute")}
              </button>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
