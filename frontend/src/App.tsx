import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Route, Routes } from "react-router";

import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { Header } from "./components/Header";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { MyProfilePage } from "./pages/MyProfilePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PublicProfilePage } from "./pages/PublicProfilePage";
import { SettingsPage } from "./pages/SettingsPage";
import { TrackPage } from "./pages/TrackPage";
import { UploadPage } from "./pages/UploadPage";

export function App({ queryClient = new QueryClient() }: { queryClient?: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Header />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/users/:userId" element={<PublicProfilePage />} />
          <Route path="/tracks/:trackId" element={<TrackPage />} />
          <Route
            path="/upload"
            element={
              <RequireAuth>
                <UploadPage />
              </RequireAuth>
            }
          />
          <Route
            path="/me"
            element={
              <RequireAuth>
                <MyProfilePage />
              </RequireAuth>
            }
          />
          <Route
            path="/settings"
            element={
              <RequireAuth>
                <SettingsPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </QueryClientProvider>
  );
}
