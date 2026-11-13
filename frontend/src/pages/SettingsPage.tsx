import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api } from "../api/client";
import type { Schemas } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { useMe } from "../auth/useMe";

const RADIUS_MIN = 200;
const RADIUS_MAX = 500;

function errorText(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function SettingsForm({ me }: { me: Schemas["OwnProfile"] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { forget } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState(me.name);
  const [city, setCity] = useState(me.city ?? "");
  const [about, setAbout] = useState(me.about ?? "");
  const [lat, setLat] = useState(me.home ? String(me.home.lat) : "");
  const [lon, setLon] = useState(me.home ? String(me.home.lon) : "");
  const [radius, setRadius] = useState(String(me.hide_radius_m ?? 300));
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    const hasHome = lat.trim() !== "" && lon.trim() !== "";
    const { data, error } = await api.PATCH("/me", {
      body: {
        name,
        city,
        about,
        home: hasHome ? { lat: Number(lat), lon: Number(lon) } : null,
        ...(hasHome ? { hide_radius_m: Number(radius) } : {}),
      },
    });
    if (data) {
      queryClient.setQueryData(["me"], data);
      setMessage({ ok: true, text: t("settings.saved") });
    } else {
      setMessage({ ok: false, text: errorText(error, t("settings.saveFailed")) });
    }
  }

  function useMyLocation() {
    navigator.geolocation?.getCurrentPosition((pos) => {
      setLat(pos.coords.latitude.toFixed(6));
      setLon(pos.coords.longitude.toFixed(6));
    });
  }

  async function onDelete() {
    const { response } = await api.DELETE("/me");
    if (response.ok) {
      forget();
      navigate("/", { replace: true });
    }
  }

  return (
    <main className="page">
      <h1>{t("settings.title")}</h1>
      <form className="stack" onSubmit={onSave}>
        <section className="card">
          <h2 className="card__title">{t("settings.profileSection")}</h2>
          <label className="field">
            {t("settings.name")}
            <input
              className="input"
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="field">
            {t("settings.city")}
            <input
              className="input"
              maxLength={100}
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
          </label>
          <label className="field">
            {t("settings.about")}
            <textarea
              className="input"
              maxLength={1000}
              value={about}
              onChange={(e) => setAbout(e.target.value)}
            />
          </label>
        </section>

        <section className="card">
          <h2 className="card__title">{t("settings.privacy")}</h2>
          <p className="muted">{t("settings.privacyHint")}</p>
          <div className="grid-2">
            <label className="field">
              {t("settings.lat")}
              <input
                className="input"
                inputMode="decimal"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
              />
            </label>
            <label className="field">
              {t("settings.lon")}
              <input
                className="input"
                inputMode="decimal"
                value={lon}
                onChange={(e) => setLon(e.target.value)}
              />
            </label>
          </div>
          <div className="row">
            <button type="button" className="btn btn--secondary btn--sm" onClick={useMyLocation}>
              {t("settings.myLocation")}
            </button>
          </div>
          <label className="field">
            {t("settings.radius", { min: RADIUS_MIN, max: RADIUS_MAX })}
            <input
              className="input"
              type="number"
              step={10}
              value={radius}
              onChange={(e) => setRadius(e.target.value)}
            />
            <span className="field__hint">{t("settings.radiusHint")}</span>
          </label>
        </section>

        <button type="submit" className="btn btn--primary btn--block">
          {t("settings.save")}
        </button>
        {message && (
          <p role="status" className={`notice notice--${message.ok ? "ok" : "error"}`}>
            {message.text}
          </p>
        )}
      </form>

      <section className="card card--danger">
        <h2 className="card__title">{t("settings.deleteTitle")}</h2>
        {!confirmDelete ? (
          <div className="row">
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={() => setConfirmDelete(true)}
            >
              {t("settings.delete")}
            </button>
          </div>
        ) : (
          <>
            <p className="notice notice--error">{t("settings.deleteWarning")}</p>
            <div className="row">
              <button type="button" className="btn btn--danger btn--sm" onClick={onDelete}>
                {t("settings.deleteConfirm")}
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
    </main>
  );
}

export function SettingsPage() {
  const { t } = useTranslation();
  const me = useMe();
  if (!me.data) {
    return (
      <main className="page">
        <p className="muted">{t("common.loading")}</p>
      </main>
    );
  }
  return <SettingsForm me={me.data} />;
}
