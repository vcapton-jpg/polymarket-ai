import { forwardRef, type ButtonHTMLAttributes } from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "@radix-ui/react-slot"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-premium cursor-pointer select-none whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed",
  {
    variants: {
      variant: {
        primary:
          "bg-brand-500 text-obsidian-900 hover:bg-brand-400 active:bg-brand-600 shadow-[0_0_0_1px_rgba(11,224,166,0.25),0_6px_24px_-8px_rgba(11,224,166,0.5)]",
        secondary:
          "bg-obsidian-750 text-ink border border-line-strong hover:bg-obsidian-700 hover:border-line-strong",
        ghost:
          "text-ink-muted hover:text-ink hover:bg-obsidian-800",
        outline:
          "border border-line-strong text-ink hover:bg-obsidian-800 hover:border-brand-500/40",
        danger:
          "bg-signal-no/90 text-white hover:bg-signal-no",
        link:
          "text-brand-400 hover:text-brand-300 underline-offset-4 hover:underline px-0",
      },
      size: {
        xs: "h-7 px-2.5 text-label-sm",
        sm: "h-8 px-3 text-body-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-11 px-5 text-sm",
        xl: "h-12 px-6 text-[0.9375rem]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  },
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      />
    )
  },
)
Button.displayName = "Button"

export { buttonVariants }
