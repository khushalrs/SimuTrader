import * as React from "react"
import { cn } from "@/lib/utils"

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  value?: string
  onValueChange?: (value: string) => void
}

// Marker components for the shadcn/Radix-style composition. They are never
// rendered to the DOM themselves — the parent <Select> introspects them to
// build a single valid native <select>. (Rendering a <div> inside <select>,
// as this shim previously did, is invalid HTML and triggers React hydration
// errors.)
export const SelectTrigger = ({ children }: React.HTMLAttributes<HTMLDivElement>) => <>{children}</>
SelectTrigger.displayName = "SelectTrigger"

export const SelectValue = (_props: { placeholder?: string }) => null
SelectValue.displayName = "SelectValue"

export const SelectContent = ({ children }: { children?: React.ReactNode }) => <>{children}</>
SelectContent.displayName = "SelectContent"

export const SelectItem = React.forwardRef<
  HTMLOptionElement,
  React.OptionHTMLAttributes<HTMLOptionElement>
>(({ className, children, ...props }, ref) => (
  <option ref={ref} className={cn("py-1", className)} {...props}>
    {children}
  </option>
))
SelectItem.displayName = "SelectItem"

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, value, onValueChange, onChange, children, ...props }, ref) => {
    // Introspect the composition so the resulting DOM is a valid native
    // <select> whose only children are <option> elements. We lift the
    // trigger's className (so per-usage styling is preserved) and the
    // SelectValue placeholder, and pull option items out of SelectContent.
    let triggerClassName: string | undefined
    let placeholder: string | undefined
    let contentChildren: React.ReactNode = null
    const looseChildren: React.ReactNode[] = []

    React.Children.forEach(children, (child) => {
      if (!React.isValidElement(child)) return
      if (child.type === SelectTrigger) {
        triggerClassName = (child.props as { className?: string }).className
        React.Children.forEach(
          (child.props as { children?: React.ReactNode }).children,
          (trigChild) => {
            if (React.isValidElement(trigChild) && trigChild.type === SelectValue) {
              placeholder = (trigChild.props as { placeholder?: string }).placeholder
            }
          }
        )
      } else if (child.type === SelectContent) {
        contentChildren = (child.props as { children?: React.ReactNode }).children
      } else {
        // Support bare <SelectItem>/<option> children too.
        looseChildren.push(child)
      }
    })

    const optionChildren = contentChildren != null ? contentChildren : looseChildren

    return (
      <select
        ref={ref}
        value={value ?? ""}
        onChange={(e) => {
          onChange?.(e)
          onValueChange?.(e.target.value)
        }}
        className={cn(
          "flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          triggerClassName,
          className
        )}
        {...props}
      >
        {placeholder != null && (
          <option value="" disabled hidden>
            {placeholder}
          </option>
        )}
        {React.Children.toArray(optionChildren)}
      </select>
    )
  }
)
Select.displayName = "Select"
