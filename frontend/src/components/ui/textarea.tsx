import * as React from "react"

import { cn } from "@/lib/utils"

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        // zinc (not slate) for the text colour on purpose: index.css remaps the
        // slate text utilities under .dark with !important, which would beat a
        // dark: variant here. Without an explicit colour the textarea inherited
        // near-black and was invisible on the dark panels.
        "flex min-h-[60px] w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 text-base text-zinc-900 caret-zinc-900 shadow-sm placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm dark:border-zinc-800 dark:text-white dark:caret-white dark:placeholder:text-zinc-400 dark:focus-visible:ring-zinc-300",
        className
      )}
      ref={ref}
      {...props}
    />
  )
})
Textarea.displayName = "Textarea"

export { Textarea }
