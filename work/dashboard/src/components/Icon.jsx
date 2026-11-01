const paths = {
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  upload: <path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5" />,
  briefcase: <><rect x="3" y="7" width="18" height="14" rx="3" /><path d="M8 7V4h8v3M3 12a22 22 0 0 0 18 0M12 12v4" /></>,
  person: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 11h18m-12 4h6" /></>,
  spark: <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" />,
  pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  file: <path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8m-8 4h6" />,
  chart: <path d="M4 20V4m0 16h16M8 16v-4m4 4V8m4 8v-6" />,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6.5 6.5 0 0 1 3.5 6" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" /><path d="m3 7 9 6.5L21 7" /></>,
  linkedin: <><rect x="3" y="3" width="18" height="18" /><path d="M8 10.5V17M8 7.5v.01M12 17v-6.5m0 2a2.5 2.5 0 0 1 5 0V17" /></>,
  alert: <><path d="M12 3 2 20h20Z" /><path d="M12 10v4m0 3v.01" /></>,
}
export default function Icon({ name, size = 20 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.spark}</svg>
}
