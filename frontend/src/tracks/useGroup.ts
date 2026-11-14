import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "../api/client";

export function useGroup(trackId: string, enabled = true) {
  const queryClient = useQueryClient();
  const group = useQuery({
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

  // Автор открыл группу своего маршрута — новые попытки просмотрены, счётчик сбрасывается.
  const viewerIsAuthor = group.data?.viewer_is_author ?? false;
  useEffect(() => {
    if (!viewerIsAuthor) return;
    void api
      .POST("/tracks/{track_id}/group/seen", { params: { path: { track_id: trackId } } })
      .then(() => {
        void queryClient.invalidateQueries({ queryKey: ["me"] });
        void queryClient.invalidateQueries({ queryKey: ["my-tracks"] });
      });
  }, [viewerIsAuthor, trackId, queryClient]);

  return group;
}
