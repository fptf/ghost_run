import type { TFunction } from "i18next";

import { formatDiff } from "../lib/format";

/** Порог равенства с автором, как на сервере: разница меньше секунды — «вровень». */
export const TIE_S = 1;

/**
 * «на 18 с быстрее автора» / «медленнее» / «вровень».
 * `equal` — готовый признак от сервера; без него равенство считается по порогу.
 */
export function verdictText(
  t: TFunction,
  diffS: number | null | undefined,
  equal?: boolean,
): string {
  const isEqual = equal ?? (diffS == null || Math.abs(diffS) < TIE_S);
  if (isEqual || diffS == null) return t("match.equal");
  return diffS < 0
    ? t("match.faster", { diff: formatDiff(diffS) })
    : t("match.slower", { diff: formatDiff(diffS) });
}
