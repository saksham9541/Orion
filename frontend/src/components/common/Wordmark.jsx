import Logo from './Logo'

export default function Wordmark({ size = 'md', animated = false }) {
  const s = size === 'lg' ? 'text-2xl' : size === 'sm' ? 'text-base' : 'text-xl'
  const icon = size === 'lg' ? 34 : size === 'sm' ? 22 : 28
  return (
    <span className="inline-flex items-center gap-2.5">
      <Logo size={icon} animated={animated} />
      <span className={`${s} font-semibold tracking-tight`}>
        Rail<span className="text-muted font-normal">Opt</span>
      </span>
    </span>
  )
}
