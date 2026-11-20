import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  block?: boolean;
  loading?: boolean;
}

export function Button({ variant = "primary", block, loading, className, disabled, children, ...rest }: Props) {
  const classes = ["btn", variant === "primary" ? "" : variant, block ? "block" : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button type="button" className={classes} disabled={disabled || loading} {...rest}>
      {loading ? "…" : children}
    </button>
  );
}
