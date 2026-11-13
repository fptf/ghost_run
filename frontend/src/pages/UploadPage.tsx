import { useTranslation } from "react-i18next";

/** Заглушка: экран загрузки появится в add-track-upload. */
export function UploadPage() {
  const { t } = useTranslation();
  return (
    <main>
      <h1>{t("upload.title")}</h1>
      <p>{t("upload.soon")}</p>
    </main>
  );
}
