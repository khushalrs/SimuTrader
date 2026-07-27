import * as React from "react"
import { cn } from "@/lib/utils"

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  value?: string
  onValueChange?: (value: string) => void
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, value, onValueChange, onChange, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        value={value}
        onChange={(e) => {
          onChange?.(e)
          onValueChange?.(e.target.value)
        }}
        className={cn(
          "flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        {...props}
      >
        {children}
      </select>
    )
  }
)
Select.displayName = "Select"

export const SelectTrigger = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("w-full", className)} {...props}>{children}</div>
)

export const SelectValue = ({ placeholder }: { placeholder?: string }) => null

export const SelectContent = ({ children }: { children: React.ReactNode }) => <>{children}</>

export const SelectItem = React.forwardRef<
  HTMLOptionElement,
  React.OptionHTMLAttributes<HTMLOptionElement>
>(({ className, children, ...props }, ref) => (
  <option ref={ref} className={cn("py-1", className)} {...props}>
    {children}
  </option>
))
SelectItem.displayName = "SelectItem"
