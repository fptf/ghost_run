import { useEffect, useRef } from "react";

interface GoogleId {
  accounts: {
    id: {
      initialize(options: {
        client_id: string;
        callback: (response: { credential: string }) => void;
      }): void;
      renderButton(element: HTMLElement, options: Record<string, string>): void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleId;
  }
}

const GIS_SRC = "https://accounts.google.com/gsi/client";

function loadGis(): Promise<GoogleId> {
  return new Promise((resolve, reject) => {
    if (window.google) return resolve(window.google);
    const script = document.createElement("script");
    script.src = GIS_SRC;
    script.async = true;
    script.onload = () => (window.google ? resolve(window.google) : reject(new Error("no gis")));
    script.onerror = () => reject(new Error("gis load failed"));
    document.head.appendChild(script);
  });
}

export function GoogleButton({
  clientId,
  onCredential,
}: {
  clientId: string;
  onCredential: (idToken: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    loadGis()
      .then((google) => {
        if (cancelled || !ref.current) return;
        google.accounts.id.initialize({
          client_id: clientId,
          callback: (r) => onCredential(r.credential),
        });
        google.accounts.id.renderButton(ref.current, { theme: "outline", size: "large" });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [clientId, onCredential]);

  return <div ref={ref} data-testid="google-button" />;
}
