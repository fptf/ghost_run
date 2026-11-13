import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { formatBytes } from "../lib/format";
import { uploadTrack, useTrack } from "../tracks/api";
import type { UploadError } from "../tracks/api";

type State =
  | { kind: "idle" }
  | { kind: "uploading"; file: File }
  | { kind: "processing"; file: File; trackId: string }
  | { kind: "failed"; file: File | null; message: string; duplicateId?: string | null };

const ACCEPT = ".gpx,.tcx,.fit";

function Processing({
  file,
  trackId,
  onRejected,
}: {
  file: File;
  trackId: string;
  onRejected: (message: string) => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const track = useTrack(trackId, { poll: true });
  const status = track.data?.status ?? "processing";

  useEffect(() => {
    if (status === "draft" || status === "published") {
      void queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate(`/tracks/${trackId}/edit`, { replace: true });
    }
    if (status === "rejected") onRejected(track.data?.reject_message ?? t("upload.failed"));
  }, [status, trackId, navigate, onRejected, track.data, t, queryClient]);

  const steps = [
    { label: t("upload.stepRead"), state: "done" },
    { label: t("upload.stepMetrics"), state: status === "processing" ? "active" : "done" },
    { label: t("upload.stepMatch"), state: status === "processing" ? "pending" : "done" },
  ];

  return (
    <section className="card" aria-live="polite">
      <FileChip file={file} />
      <ol className="steps">
        {steps.map((s) => (
          <li key={s.label} className={`step step--${s.state}`}>
            <span className="step__dot" aria-hidden />
            {s.label}
          </li>
        ))}
      </ol>
      <p className="muted">{t("upload.canLeave")}</p>
      <div className="row">
        <Link to="/" className="btn btn--secondary">
          {t("upload.backToMap")}
        </Link>
      </div>
    </section>
  );
}

function FileChip({ file }: { file: File }) {
  const ext = file.name.split(".").pop()?.toUpperCase() ?? "";
  return (
    <div className="file-chip">
      <span className="badge">{ext}</span>
      <span className="file-chip__name">{file.name}</span>
      <span className="muted">{formatBytes(file.size)}</span>
    </div>
  );
}

export function UploadPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<State>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function start(file: File) {
    setState({ kind: "uploading", file });
    const { data, error, response } = await uploadTrack(file);
    if (data) {
      setState({ kind: "processing", file, trackId: data.id });
      return;
    }
    const err = error as UploadError | { detail?: unknown } | undefined;
    const detail = typeof err?.detail === "string" ? err.detail : t("upload.failed");
    setState({
      kind: "failed",
      file,
      message: response.status === 409 ? t("upload.duplicate") : detail,
      duplicateId: response.status === 409 ? (err as UploadError).track_id : null,
    });
  }

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void start(file);
    e.target.value = "";
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) void start(file);
  }

  return (
    <main className="page">
      <h1>{t("upload.title")}</h1>

      {state.kind === "idle" && (
        <label
          className={`dropzone${dragging ? " dropzone--active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            className="visually-hidden"
            onChange={onPick}
            aria-label={t("upload.pick")}
          />
          <strong>{t("upload.drop")}</strong>
          <span className="muted">{t("upload.formats")}</span>
          <span className="btn btn--primary">{t("upload.pick")}</span>
        </label>
      )}

      {state.kind === "uploading" && (
        <section className="card" aria-live="polite">
          <FileChip file={state.file} />
          <p className="muted">{t("upload.sending")}</p>
        </section>
      )}

      {state.kind === "processing" && (
        <Processing
          file={state.file}
          trackId={state.trackId}
          onRejected={(message) => setState({ kind: "failed", file: state.file, message })}
        />
      )}

      {state.kind === "failed" && (
        <section className="card">
          {state.file && <FileChip file={state.file} />}
          <h2 className="card__title">
            {state.duplicateId ? t("upload.duplicateTitle") : t("upload.rejectedTitle")}
          </h2>
          <p role="alert" className="notice notice--error">
            {state.message}
          </p>
          <div className="row">
            {state.duplicateId && (
              <Link to={`/tracks/${state.duplicateId}`} className="btn btn--primary">
                {t("upload.openExisting")}
              </Link>
            )}
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => setState({ kind: "idle" })}
            >
              {t("upload.another")}
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
