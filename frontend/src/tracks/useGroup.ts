import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export function useGroup(trackId: string, enabled = true) {
  return useQuery({
    queryKey: ["group", trackId],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET("/tracks/{track_id}/group", {
        params: { path: { track_id: trackId } },
      });
      if (error || !data) throw new Error("group failed");
      return data;
    },
  });
}
