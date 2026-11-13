export function Avatar({
  name,
  url,
  small = false,
}: {
  name: string;
  url: string | null | undefined;
  small?: boolean;
}) {
  const className = small ? "avatar avatar--sm" : "avatar";
  if (url) return <img className={className} src={url} alt="" referrerPolicy="no-referrer" />;
  return (
    <span className={className} aria-hidden="true">
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}
