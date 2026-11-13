import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { Avatar } from "../components/Avatar";
import { BackButton } from "../components/BackButton";
import { CATEGORY_LABELS } from "../lib/format";
import { useTrack } from "../tracks/api";
import { useAuth } from "../auth/useAuth";
import { GroupTable } from "../tracks/GroupTable";
import { Photos } from "../tracks/Photos";
import { TrackSummaryCard } from "../tracks/TrackSummaryCard";
import { useGpxDownload } from "../tracks/useGpxDownload";

export function TrackNotFound() {
  const { t } = useTranslation();
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

/** Просмотр трека — для всех; автору доступны «Редактировать» и публикация черновика. */
export function TrackPage() {
  const { trackId = "" } = useParams();
  const { t } = useTranslation();
  const track = useTrack(trackId, { poll: true });
  const navigate = useNavigate();
  const download = useGpxDownload();
  const { status } = useAuth();
  const flash = (useLocation().state as { flash?: "published" | "saved" } | null)?.flash;

  if (track.isPending) {
    return (
      <main className="page">
        <p className="muted">{t("common.loading")}</p>
      </main>
    );
  }
  if (track.isError || !track.data) return <TrackNotFound />;

  const tr = track.data;
  const ready = tr.status === "draft" || tr.status === "published";

  return (
    <main className="page">
      <div className="page-head">
        <BackButton fallback={tr.is_owner ? "/me" : "/"} />
        <div className="page-head__title">
          <h1>{tr.title ?? t("track.untitled")}</h1>
          <p className="muted">
            {tr.category && `${CATEGORY_LABELS[tr.category] ?? tr.category} · `}
            {tr.is_owner ? (
              tr.status === "published" ? (
                t(`track.visibility.${tr.visibility}`)
              ) : (
                t(`track.status.${tr.status}`)
              )
            ) : (
              <Link to={`/users/${tr.author.id}`} className="author-link">
                <Avatar name={tr.author.name} url={tr.author.avatar_url} small />
                {tr.author.name}
              </Link>
            )}
          </p>
        </div>
        {tr.is_owner && ready && (
          <Link to={`/tracks/${tr.id}/edit`} className="btn btn--secondary btn--sm">
            {t("track.edit")}
          </Link>
        )}
      </div>

      {flash && (
        <p role="status" className="notice notice--ok">
          {flash === "published" ? t("track.published") : t("track.saved")}
        </p>
      )}
      {tr.is_owner && tr.status === "draft" && (
        <div className="notice notice--info row-between">
          <span>{t("track.draftNote")}</span>
          <Link to={`/tracks/${tr.id}/edit`} className="btn btn--primary btn--sm">
            {t("track.publish")}
          </Link>
        </div>
      )}
      {tr.achievements.length > 0 && (
        <div className="row">
          {tr.achievements.map((a) => (
            <span key={a.code} className="achievement-pill">
              <span aria-hidden>⚡</span> {t("result.achievement", { title: a.title })}
            </span>
          ))}
        </div>
      )}
      {tr.attempt_of && (
        <p className="notice notice--info">
          {t("match.attemptOf")}{" "}
          <Link to={`/tracks/${tr.attempt_of.id}`}>
            «{tr.attempt_of.title ?? t("track.untitled")}»
          </Link>{" "}
          · {tr.attempt_of.author.name}
          {tr.is_owner && (
            <>
              {" · "}
              <Link to={`/tracks/${tr.id}/result`}>{t("result.title")}</Link>
            </>
          )}
        </p>
      )}
      {tr.status === "processing" && <p className="notice notice--info">{t("track.processing")}</p>}
      {tr.status === "rejected" && (
        <p className="notice notice--error">{tr.reject_message ?? t("upload.failed")}</p>
      )}

      {ready && (
        <>
          <TrackSummaryCard track={tr} />
          {tr.geometry && (
            <section className="card">
              {!tr.is_owner && <p className="notice notice--info">{t("track.runItHint")}</p>}
              <div className="row">
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  onClick={() => void download(tr.id, tr.title)}
                >
                  {t("track.downloadGpx")}
                </button>
                {tr.status === "published" && tr.visibility === "public" && !tr.attempt_of && (
                  <button
                    type="button"
                    className="btn btn--secondary btn--sm"
                    onClick={() => navigate(`/?track=${tr.id}&fit=1`)}
                  >
                    {t("track.showOnMap")}
                  </button>
                )}
                {tr.status === "published" && !tr.attempt_of && (
                  <Link
                    to={
                      status === "authenticated"
                        ? `/tracks/${tr.id}/check`
                        : `/login?next=${encodeURIComponent(`/tracks/${tr.id}/check`)}`
                    }
                    className="btn btn--secondary btn--sm"
                  >
                    {t("check.button")}
                  </Link>
                )}
              </div>
              {tr.status === "published" && <GroupTable trackId={tr.id} />}
            </section>
          )}
          {(tr.description || tr.photos.length > 0) && (
            <section className="card">
              {tr.description && <p>{tr.description}</p>}
              <Photos trackId={tr.id} photos={tr.photos} />
            </section>
          )}
        </>
      )}
    </main>
  );
}
