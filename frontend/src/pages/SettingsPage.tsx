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
  const [message, setMessage] = useState<string | null>(null);
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
      setMessage(t("settings.saved"));
    } else {
      setMessage(errorText(error, t("settings.saveFailed")));
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
    <main>
      <h1>{t("settings.title")}</h1>
      <form onSubmit={onSave}>
        <label>
          {t("settings.name")}
          <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          {t("settings.city")}
          <input maxLength={100} value={city} onChange={(e) => setCity(e.target.value)} />
        </label>
        <label>
          {t("settings.about")}
          <textarea maxLength={1000} value={about} onChange={(e) => setAbout(e.target.value)} />
        </label>

        <fieldset>
          <legend>{t("settings.privacy")}</legend>
          <p>{t("settings.privacyHint")}</p>
          <label>
            {t("settings.lat")}
            <input inputMode="decimal" value={lat} onChange={(e) => setLat(e.target.value)} />
          </label>
          <label>
            {t("settings.lon")}
            <input inputMode="decimal" value={lon} onChange={(e) => setLon(e.target.value)} />
          </label>
          <button type="button" onClick={useMyLocation}>
            {t("settings.myLocation")}
          </button>
          <label>
            {t("settings.radius", { min: RADIUS_MIN, max: RADIUS_MAX })}
            <input
              type="number"
              step={10}
              value={radius}
              onChange={(e) => setRadius(e.target.value)}
            />
          </label>
        </fieldset>

        <button type="submit">{t("settings.save")}</button>
        {message && <p role="status">{message}</p>}
      </form>

      <section>
        <h2>{t("settings.deleteTitle")}</h2>
        {!confirmDelete ? (
          <button type="button" onClick={() => setConfirmDelete(true)}>
            {t("settings.delete")}
          </button>
        ) : (
          <>
            <p>{t("settings.deleteWarning")}</p>
            <button type="button" onClick={onDelete}>
              {t("settings.deleteConfirm")}
            </button>
            <button type="button" onClick={() => setConfirmDelete(false)}>
              {t("common.cancel")}
            </button>
          </>
        )}
      </section>
    </main>
  );
}

export function SettingsPage() {
  const { t } = useTranslation();
  const me = useMe();
  if (!me.data) return <p>{t("common.loading")}</p>;
  return <SettingsForm me={me.data} />;
}
