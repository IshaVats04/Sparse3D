import { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

const VARIANTS = {
  primary: 'grad-btn border border-transparent',
  secondary: 'border border-line bg-ink-700 text-slate-100 hover:border-line-strong hover:bg-ink-600',
  ghost: 'border border-transparent text-slate-300 hover:bg-ink-700 hover:text-white',
  danger: 'border border-red-500/40 bg-red-500/10 text-red-300 hover:bg-red-500/20',
  success: 'border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20',
};
const SIZES = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

/**
 * Button. Pass `to` to render a router Link, `href` for an anchor.
 * `loading` disables the button and shows a spinner.
 */
const Button = forwardRef(function Button(
  { variant = 'secondary', size = 'md', loading = false, disabled = false, icon: Icon, iconRight: IconRight,
    to, href, className = '', children, type = 'button', ...rest },
  ref,
) {
  const cls = `inline-flex items-center justify-center gap-2 rounded-lg font-medium transition
    disabled:cursor-not-allowed disabled:opacity-45 aria-disabled:cursor-not-allowed aria-disabled:opacity-45
    ${VARIANTS[variant]} ${SIZES[size]} ${className}`;
  const content = (
    <>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : Icon ? <Icon className="h-4 w-4" aria-hidden /> : null}
      {children}
      {IconRight && !loading ? <IconRight className="h-4 w-4" aria-hidden /> : null}
    </>
  );
  if (to && !disabled) {
    return <Link ref={ref} to={to} className={cls} {...rest}>{content}</Link>;
  }
  if (href && !disabled) {
    return <a ref={ref} href={href} className={cls} {...rest}>{content}</a>;
  }
  return (
    <button ref={ref} type={type} disabled={disabled || loading} className={cls} {...rest}>
      {content}
    </button>
  );
});

export default Button;
