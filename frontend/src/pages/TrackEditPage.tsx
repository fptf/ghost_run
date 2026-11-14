import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router";

import { api } from "../api/client";
import { errorDetail } from "../api/errors";
import { BackButton } from "../components/BackButton";
import { MY_TRACKS_KEY, uploadPhoto, useTrack } from "../tracks/api";
import type { TrackDetail } from "../tracks/api";
import { MatchPlaque } from "../tracks/MatchPlaque";
import { Photos } from "../tracks/Photos";
import { TrackSummaryCard } from "../tracks/TrackSummaryCard";
import { TrackNotFound } from "./TrackPage";

const VISIBILITIES = ["public", "link", "private"] as const;
type VisibilityValue = (typeof VISIBILITIES)[number];
const MAX_PHOTOS = 5;

function EditForm({ track }: { track: TrackDetail }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isDraft = track.status === "draft";
  const fullyHidden = track.owner?.fully_hidden ?? false;
  const [title, setTitle] = useState(track.title ?? "");
  const [description, setDescription] = useState(track.description ?? "");
  const [visibility, setVisibility] = useState<VisibilityValue>(
    fullyHidden ? "private" : isDraft ? "public" : track.visibility,
  );
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [saving, setSaving] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["track", track.id] });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    const { data, error: err } = await api.PATCH("/tracks/{track_id}", {
      params: { path: { track_id: track.id } },
      body: { title, description, visibility, publish: true, detach: false },
    });
    setSaving(false);
    if (!data) {
      setError(errorDetail(err, t("track.saveFailed")));
      return;
    }
    queryClient.setQueryData(["track", track.id], data);
    void queryClient.invalidateQueries({ queryKey: MY_TRACKS_KEY });
    void queryClient.invalidateQueries({ queryKey: ["me"] });
    // Форма закрывается: новая попытка в группе — экран результата, иначе просмотр трека.
    if (isDraft && data.attempt_of) {
      void queryClient.invalidateQueries({ queryKey: ["group"] });
      navigate(`/tracks/${track.id}/result`, { replace: true });
    } else {
      navigate(`/tracks/${track.id}`, {
        replace: true,
        state: { flash: isDraft ? "published" : "saved" },
      });
    }
  }

  async function onPhoto(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const { error: err } = await uploadPhoto(track.id, file);
    if (err) setError(errorDetail(err, t("track.photoFailed")));
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
    void queryClient.invalidateQueries({ queryKey: MY_TRACKS_KEY });
    void queryClient.invalidateQueries({ queryKey: ["me"] });
    queryClient.removeQueries({ queryKey: ["track", track.id] });
    navigate("/me", { replace: true });
  }

  return (
    <>
      <MatchPlaque track={track} visibility={visibility} />
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

        {error && (
          <p role="alert" className="notice notice--error">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn--primary btn--block" disabled={saving}>
          {isDraft ? t("track.publish") : t("track.save")}
        </button>
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

/** Превью нового трека и редактирование — только автору. */
export function TrackEditPage() {
  const { trackId = "" } = useParams();
  const { t } = useTranslation();
  const track = useTrack(trackId);

  if (track.isPending) {
    return (
      <main className="page">
        <p className="muted">{t("common.loading")}</p>
      </main>
    );
  }
  if (track.isError || !track.data) return <TrackNotFound />;
  const tr = track.data;
  if (!tr.is_owner || (tr.status !== "draft" && tr.status !== "published")) {
    return <Navigate to={`/tracks/${tr.id}`} replace />;
  }

  return (
    <main className="page">
      <div className="page-head">
        <BackButton fallback={`/tracks/${tr.id}`} />
        <h1 className="page-head__title">
          {tr.status === "draft" ? t("track.newTrack") : t("track.editTitle")}
        </h1>
      </div>
      <TrackSummaryCard track={tr} />
      <EditForm track={tr} />
    </main>
  );
}
