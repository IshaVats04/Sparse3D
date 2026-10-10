export default function Card({ title, subtitle, actions, children, className = '', bodyClassName = 'p-5', id, ...rest }) {
  return (
    <section id={id} className={`card ${className}`} {...rest}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line-soft px-5 py-4">
          <div className="min-w-0">
            {title && <h2 className="text-base font-semibold text-white">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
