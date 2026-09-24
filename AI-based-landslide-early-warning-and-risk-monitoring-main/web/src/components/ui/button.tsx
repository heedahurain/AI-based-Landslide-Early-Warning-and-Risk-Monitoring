"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Focus rings are visible by default. Motion is transform and opacity only.
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-md)] " +
    "font-medium transition-[transform,opacity,background-color,border-color] " +
    "duration-[var(--duration-fast)] ease-[var(--ease-out)] " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--border-focus)] " +
    "disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] " +
    "[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-[var(--accent)] text-[var(--accent-fg)] hover:bg-[var(--accent-hover)]",
        secondary:
          "border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--fg-primary)] hover:border-[var(--border-strong)]",
        ghost:
          "text-[var(--fg-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--fg-primary)]",
        // Reserved for irreversible operator actions, such as issuing an
        // evacuation alert. Never use it for ordinary navigation.
        critical: "bg-[var(--sev-red)] text-white hover:opacity-90",
      },
      size: {
        sm: "h-8 px-3 text-[length:var(--text-xs)]",
        md: "h-9 px-4 text-[length:var(--text-base)]",
        lg: "h-11 px-6 text-[length:var(--text-md)]",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
