/** Tailwind class strings shared across components. */

export const fieldLabel = 'text-[11.5px] font-semibold uppercase tracking-wide text-muted'

export const input =
  'h-9.5 w-full rounded-lg border border-line bg-panel-2 px-2.5 focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent-soft aria-invalid:border-danger'

/** A segmented-control option: a <label> wrapping a visually hidden radio. */
export const segment = (small = false) =>
  [
    'cursor-pointer select-none border border-line bg-panel-2 not-first-of-type:border-l-0',
    'first-of-type:rounded-l-lg last-of-type:rounded-r-lg',
    'has-checked:border-accent has-checked:bg-accent has-checked:text-accent-ink',
    'has-focus-visible:outline-2 has-focus-visible:outline-offset-1 has-focus-visible:outline-accent',
    small ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1.5 text-[13px]',
  ].join(' ')

export const hiddenRadio = 'pointer-events-none absolute opacity-0'

/** Pill coloured by the `--risk` custom property. */
export const riskBadge =
  'inline-block whitespace-nowrap rounded-full bg-(--risk) px-1.75 py-0.5 text-[11px] font-bold text-white'

export const spinner =
  'inline-block size-4.5 flex-none animate-spin rounded-full border-2 border-accent-soft border-t-accent'

export const toggle = 'inline-flex cursor-pointer select-none items-center gap-1.5 text-[13px]'
export const checkbox = 'size-4 accent-accent'
