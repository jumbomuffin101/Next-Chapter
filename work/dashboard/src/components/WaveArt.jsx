// Flowing line-art in the style of tkh.org's backgrounds, drawn as SVG (no images copied).
const fan = (count, step) => Array.from({ length: count }, (_, i) => {
  const o = i * step
  return `M ${o} 0 C ${140 + o * 1.3} 90, ${-60 + o * 1.8} 210, ${170 + o * 1.5} 400`
})

export default function WaveArt() {
  return <div className="wave-art" aria-hidden="true">
    <svg className="wave wave-top" viewBox="0 0 460 400" fill="none">{fan(34, 9).map(d => <path key={d} d={d} />)}</svg>
    <svg className="wave wave-bottom" viewBox="0 0 460 400" fill="none">{fan(30, 10).map(d => <path key={d} d={d} />)}</svg>
  </div>
}
