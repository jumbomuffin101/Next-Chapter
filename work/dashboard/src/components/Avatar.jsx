// Generic person icon until profile photos exist
function Avatar({ size = 32 }) {
  return (
    <svg className="avatar" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="12" cy="9" r="3.5" />
      <path d="M5.5 19c.8-3 3.4-5 6.5-5s5.7 2 6.5 5" />
    </svg>
  )
}

export default Avatar
