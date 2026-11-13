import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { useAuth } from "./useAuth";

export function useMe() {
  const { status } = useAuth();
  return useQuery({
    queryKey: ["me"],
    enabled: status === "authenticated",
    queryFn: async () => {
      const { data, error } = await api.GET("/me");
      if (error || !data) throw new Error("me failed");
      return data;
    },
  });
}
