import { cn } from "@/lib/utils"

type PoweredByPolymarketProps = {
  className?: string
  /** Visual size — `xs` used inline, `sm` standard in forms, `md` stands alone. */
  size?: "xs" | "sm" | "md"
  /** Optional href — defaults to polymarket.com. */
  href?: string
}

export function PoweredByPolymarket({
  className,
  size = "sm",
  href = "https://polymarket.com",
}: PoweredByPolymarketProps) {
  const sizeCls = {
    xs: "px-2 py-1 text-[0.6875rem] gap-1.5",
    sm: "px-3 py-1.5 text-[0.8125rem] gap-2",
    md: "px-3.5 py-2 text-sm gap-2",
  }[size]

  const logoSize = {
    xs: "h-4 w-4",
    sm: "h-5 w-5",
    md: "h-6 w-6",
  }[size]

  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cn(
        "inline-flex w-fit items-center rounded-full border border-line/70 bg-obsidian-800/40",
        "font-medium text-ink-dim hover:text-ink hover:border-line-strong",
        "transition-premium",
        sizeCls,
        className,
      )}
      aria-label="Partenaire Polymarket"
    >
      {/* Official Polymarket app icon — blue rounded square + white geometric mark */}
      <svg
        viewBox="0 0 2184 2184"
        aria-hidden
        className={cn("shrink-0", logoSize)}
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="2184" height="2184" rx="420" fill="#1652F0" />
        <g transform="translate(0,2184) scale(0.1,-0.1)" fill="white">
          <path d="M10445 15709 c-2667 -764 -4860 -1391 -4872 -1394 l-23 -5 0 -3345 0
-3344 23 -7 c79 -25 9722 -2782 9724 -2780 2 1 2 2761 1 6133 l-3 6129 -4850
-1387z m3915 -1910 c0 -1939 -1 -2041 -17 -2037 -160 43 -7100 2032 -7105
2037 -7 6 7068 2037 7105 2040 16 1 17 -102 17 -2040z m-4263 -1806 c1976
-565 3591 -1028 3590 -1029 -4 -4 -7141 -2045 -7169 -2051 l-28 -5 0 2056 c0
1131 3 2056 8 2056 4 0 1623 -462 3599 -1027z m4263 -3864 l0 -2041 -27 5
c-16 3 -1617 460 -3560 1016 -1942 556 -3535 1011 -3539 1011 -4 0 -4 3 0 7 5
6 7095 2040 7119 2042 4 1 7 -918 7 -2040z" />
        </g>
      </svg>
      <span className="leading-none">Partenaire Polymarket</span>
    </a>
  )
}
