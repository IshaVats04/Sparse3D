import { Link } from 'react-router-dom';

export function CubeLogo({ className = 'h-7 w-7' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden fill="none" stroke="url(#recon-logo-g)" strokeWidth="2" strokeLinejoin="round">
      <defs>
        <linearGradient id="recon-logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3b82f6" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <path d="M16 3l11 6v14l-11 6-11-6V9z" />
      <path d="M5 9l11 6 11-6M16 15v14" />
    </svg>
  );
}

export default function Logo({ to = '/', className = '' }) {
  return (
    <Link to={to} className={`inline-flex items-center gap-2.5 ${className}`} aria-label="3D RECON LAB home">
      <CubeLogo />
      <span className="text-sm font-bold tracking-[0.18em] text-white">3D RECON LAB</span>
    </Link>
  );
}
