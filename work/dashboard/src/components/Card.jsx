// Shared wrapper so every dashboard section looks the same
function Card({ title, className = '', children }) {
  return (
    <section className={`card ${className}`}>
      <h2 className="card-title">{title}</h2>
      {children}
    </section>
  )
}

export default Card
