"use client"

import { Slider as SliderPrimitive } from "@base-ui/react/slider"

import { cn } from "@/lib/utils"

function RangeSlider({
  className,
  value,
  min,
  max,
  step = 1,
  disabled,
  minimumLabel,
  maximumLabel,
  onValueChange,
}: {
  className?: string
  value: readonly [number, number]
  min: number
  max: number
  step?: number
  disabled?: boolean
  minimumLabel: string
  maximumLabel: string
  onValueChange: (
    value: readonly [number, number],
    changedBound: "min" | "max",
  ) => void
}) {
  return (
    <SliderPrimitive.Root
      value={value}
      min={min}
      max={max}
      step={step}
      minStepsBetweenValues={0}
      thumbCollisionBehavior="none"
      disabled={disabled}
      onValueChange={(next) => {
        if (next.length === 2) {
          const minimumDelta = Math.abs(next[0] - value[0])
          const maximumDelta = Math.abs(next[1] - value[1])
          onValueChange(
            [next[0], next[1]],
            maximumDelta > minimumDelta ? "max" : "min",
          )
        }
      }}
      className={cn(
        "relative flex w-full touch-none select-none items-center py-2",
        "data-disabled:cursor-not-allowed data-disabled:opacity-50",
        className,
      )}
    >
      <SliderPrimitive.Control className="relative flex h-5 w-full items-center">
        <SliderPrimitive.Track className="h-1.5 w-full rounded-full bg-muted">
          <SliderPrimitive.Indicator className="rounded-full bg-primary" />
        </SliderPrimitive.Track>
        <SliderPrimitive.Thumb
          index={0}
          getAriaLabel={() => minimumLabel}
          className="size-5 rounded-full border-2 border-primary bg-card outline-none transition-colors focus-within:ring-3 focus-within:ring-ring/40"
        />
        <SliderPrimitive.Thumb
          index={1}
          getAriaLabel={() => maximumLabel}
          className="size-5 rounded-full border-2 border-primary bg-card outline-none transition-colors focus-within:ring-3 focus-within:ring-ring/40"
        />
      </SliderPrimitive.Control>
    </SliderPrimitive.Root>
  )
}

export { RangeSlider }
