import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Schemas } from "../api/client";

export type TrackDetail = Schemas["TrackDetail"];
export type TrackSummary = Schemas["TrackSummary"];

export function useTrack(trackId: string, opts: { poll?: boolean; enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["track", trackId],
    enabled: opts.enabled ?? true,
    queryFn: async () => {
      const { data, error } = await api.GET("/tracks/{track_id}", {
        params: { path: { track_id: trackId } },
      });
      if (error || !data) throw new Error("not found");
      return data;
    },
    retry: false,
    refetchInterval: (query) =>
      opts.poll && query.state.data?.status === "processing" ? 1000 : false,
  });
}

/** Ключ кэша «мои треки»: его сбрасывают все мутации, меняющие список. */
export const MY_TRACKS_KEY = ["my-tracks"] as const;

export function useMyTracks() {
  return useQuery({
    queryKey: MY_TRACKS_KEY,
    queryFn: async () => (await api.GET("/me/tracks")).data ?? [],
  });
}

export async function uploadTrack(file: File) {
  const form = new FormData();
  form.append("file", file);
  return api.POST("/tracks", {
    body: { file: "" },
    bodySerializer: () => form,
  });
}

export async function uploadPhoto(trackId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return api.POST("/tracks/{track_id}/photos", {
    params: { path: { track_id: trackId } },
    body: { file: "" },
    bodySerializer: () => form,
  });
}
