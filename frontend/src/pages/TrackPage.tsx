import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { api } from "../api/client";
import { Avatar } from "../components/Avatar";
import { PaceChart } from "../components/PaceChart";
import { TrackMap } from "../components/TrackMap";
import { CATEGORY_LABELS, formatDuration, formatKm, formatPace } from "../lib/format";
import { uploadPhoto, useTrack } from "../tracks/api";
import type { TrackDetail } from "../tracks/api";
import { Photos } from "../tracks/Photos";

const VISIBILITIES = ["public", "link", "private"] as const;
type VisibilityValue = (typeof VISIBILITIES)[number];
const MAX_PHOTOS = 5;

function Metrics({ track }: { track: TrackDetail }) {
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

function OwnerForm({ track }: { track: TrackDetail }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [title, setTitle] = useState(track.title ?? "");
  const [description, setDescription] = useState(track.description ?? "");
  const [visibility, setVisibility] = useState<VisibilityValue>(
    track.owner?.fully_hidden ? "private" : track.status === "draft" ? "public" : track.visibility,
  );
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const fullyHidden = track.owner?.fully_hidden ?? false;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["track", track.id] });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const { data, error } = await api.PATCH("/tracks/{track_id}", {
      params: { path: { track_id: track.id } },
      body: { title, description, visibility, publish: true },
    });
    if (data) {
      queryClient.setQueryData(["track", track.id], data);
      void queryClient.invalidateQueries({ queryKey: ["my-tracks"] });
      void queryClient.invalidateQueries({ queryKey: ["me"] });
      setMessage({
        ok: true,
        text: track.status === "draft" ? t("track.published") : t("track.saved"),
      });
    } else {
      const detail = (error as { detail?: unknown } | undefined)?.detail;
      setMessage({ ok: false, text: typeof detail === "string" ? detail : t("track.saveFailed") });
    }
  }

  async function onPhoto(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const { error } = await uploadPhoto(track.id, file);
    if (error) {
      const detail = (error as { detail?: unknown }).detail;
      setMessage({ ok: false, text: typeof detail === "string" ? detail : t("track.photoFailed") });
    }
    void refresh();
  }

  async function onDeletePhoto(photoId: string) {
    await api.DELETE("/tracks/{track_id}/photos/{photo_id}", {
      params: { path: { track_id: track.id, photo_id: photoId } },
    });
    void refresh();
  }

  async function onDeleteTrack() {
    await api.DELETE("/tracks/{track_id}", { params: { path: { track_id: track.id } } });
    void queryClient.invalidateQueries({ queryKey: ["my-tracks"] });
    void queryClient.invalidateQueries({ queryKey: ["me"] });
    navigate("/me", { replace: true });
  }

  return (
    <>
      <form className="card" onSubmit={onSubmit}>
        <label className="field">
          {t("track.title")}
          <input
            className="input"
            required
            maxLength={120}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="field">
          {t("track.description")}
          <textarea
            className="input"
            maxLength={2000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>

        <Photos trackId={track.id} photos={track.photos} onDelete={onDeletePhoto} />
        {track.photos.length < MAX_PHOTOS && (
          <label className="btn btn--dashed">
            {t("track.addPhoto")}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="visually-hidden"
              onChange={onPhoto}
            />
          </label>
        )}

        <fieldset className="field">
          <legend>{t("track.visibilityLabel")}</legend>
          <div className="segmented" role="radiogroup">
            {VISIBILITIES.map((v) => (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={visibility === v}
                aria-selected={visibility === v}
                className="segmented__item"
                disabled={fullyHidden && v !== "private"}
                onClick={() => setVisibility(v)}
              >
                {t(`track.visibility.${v}`)}
              </button>
            ))}
          </div>
          <span className="field__hint">
            {fullyHidden ? t("track.fullyHidden") : t("track.visibilityHint")}
          </span>
        </fieldset>

        <button type="submit" className="btn btn--primary btn--block">
          {track.status === "draft" ? t("track.publish") : t("track.save")}
        </button>
        {message && (
          <p role="status" className={`notice notice--${message.ok ? "ok" : "error"}`}>
            {message.text}
          </p>
        )}
      </form>

      <section className="card card--danger">
        {!confirmDelete ? (
          <div className="row">
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={() => setConfirmDelete(true)}
            >
              {t("track.delete")}
            </button>
          </div>
        ) : (
          <>
            <p className="notice notice--error">{t("track.deleteWarning")}</p>
            <div className="row">
              <button type="button" className="btn btn--danger btn--sm" onClick={onDeleteTrack}>
                {t("track.deleteConfirm")}
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setConfirmDelete(false)}
              >
                {t("common.cancel")}
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}

export function TrackPage() {
  const { trackId = "" } = useParams();
  const { t } = useTranslation();
  const track = useTrack(trackId, { poll: true });

  if (track.isPending) {
    return (
      <main className="page">
        <p className="muted">{t("common.loading")}</p>
      </main>
    );
  }
  if (track.isError || !track.data) {
    return (
      <main className="page page--narrow">
        <div className="card">
          <h1>{t("track.notFound")}</h1>
          <Link to="/" className="btn btn--secondary">
            {t("notFound.home")}
          </Link>
        </div>
      </main>
    );
  }

  const tr = track.data;
  const owner = tr.owner;
  const ready = tr.status === "draft" || tr.status === "published";

  return (
    <main className="page">
      <div className="stack">
        <h1>{tr.status === "draft" ? t("track.newTrack") : (tr.title ?? t("track.untitled"))}</h1>
        <p className="muted">
          {tr.category && `${CATEGORY_LABELS[tr.category] ?? tr.category} · `}
          {tr.is_owner ? (
            t(`track.status.${tr.status}`)
          ) : (
            <Link to={`/users/${tr.author.id}`} className="author-link">
              <Avatar name={tr.author.name} url={tr.author.avatar_url} small />
              {tr.author.name}
            </Link>
          )}
        </p>
      </div>

      {tr.status === "processing" && <p className="notice notice--info">{t("track.processing")}</p>}
      {tr.status === "rejected" && (
        <p className="notice notice--error">{tr.reject_message ?? t("upload.failed")}</p>
      )}

      {ready && (
        <>
          <section className="card card--flush">
            <TrackMap
              line={tr.geometry?.coordinates}
              fullLine={owner?.full_geometry?.coordinates}
              zone={owner?.hidden_zone}
              label={t("track.mapLabel")}
            />
            {owner?.hidden_zone && (
              <p className="map-note">
                {t("track.zoneNote", { radius: owner.hidden_zone.radius_m })}
              </p>
            )}
            {/* Место под плашку совпадения с маршрутом — add-route-matching */}
          </section>
          <section className="card">
            <Metrics track={tr} />
            <PaceChart splits={tr.splits} />
            {!tr.is_owner && tr.description && <p>{tr.description}</p>}
            {!tr.is_owner && <Photos trackId={tr.id} photos={tr.photos} />}
          </section>
          {tr.is_owner && <OwnerForm track={tr} />}
        </>
      )}
    </main>
  );
}
