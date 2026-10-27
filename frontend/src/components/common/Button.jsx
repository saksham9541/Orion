const variants = {
  primary:
    'bg-merge text-deep hover:bg-merge/90 active:translate-y-px border border-transparent font-semibold shadow-sm hover:shadow-md transition-all duration-200',
  ghost: 'bg-transparent text-ink border border-line hover:border-merge/50 hover:bg-raised/60 hover:shadow-sm transition-all duration-200',
  quiet: 'bg-raised text-ink border border-line hover:bg-line/70 transition-all duration-200',
  danger: 'bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25 transition-all duration-200',
}

const sizes = {
  sm: 'text-[13px] px-3.5 py-1.5 gap-1.5',
  md: 'text-sm px-4 py-2.5 gap-2',
  lg: 'text-[15px] px-7 py-3.5 gap-2.5',
  // Landing-page calls to action: prominent, but not oversized.
  cta: 'text-[14px] px-6 py-3 gap-2.5',
}

export default function Button({
  as: Tag = 'button',
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...rest
}) {
  return (
    <Tag
      className={`inline-flex items-center justify-center rounded-panel font-medium disabled:opacity-40 disabled:pointer-events-none ${variants[variant]} ${sizes[size]} ${className}`}
      {...rest}
    >
      {children}
    </Tag>
  )
}
