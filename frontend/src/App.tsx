import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router";

import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { BottomNav } from "./components/BottomNav";
import { Header } from "./components/Header";
import { LoginPage } from "./pages/LoginPage";
import { MyProfilePage } from "./pages/MyProfilePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PublicProfilePage } from "./pages/PublicProfilePage";
import { SettingsPage } from "./pages/SettingsPage";
import { UploadPage } from "./pages/UploadPage";

// Страницы с картой подгружаются отдельно: шапка и навигация не ждут MapLibre (~1 МБ).
const HomePage = lazy(() => import("./pages/HomePage").then((m) => ({ default: m.HomePage })));
const TrackPage = lazy(() => import("./pages/TrackPage").then((m) => ({ default: m.TrackPage })));
const TrackEditPage = lazy(() =>
  import("./pages/TrackEditPage").then((m) => ({ default: m.TrackEditPage })),
);

function Loading() {
  return <div className="page-loading" aria-busy="true" />;
}

function Shell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  return <div className={`app${pathname === "/" ? " app--map" : ""}`}>{children}</div>;
}

export function App({ queryClient = new QueryClient() }: { queryClient?: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Shell>
          <Header />
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/users/:userId" element={<PublicProfilePage />} />
              <Route path="/tracks/:trackId" element={<TrackPage />} />
              <Route
                path="/tracks/:trackId/edit"
                element={
                  <RequireAuth>
                    <TrackEditPage />
                  </RequireAuth>
                }
              />
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
          </Suspense>
          <BottomNav />
        </Shell>
      </AuthProvider>
    </QueryClientProvider>
  );
}
