const money = (value, compact) => (value == null ? '—' : compact ? `$${Math.round(value / 1000)}k` : `$${Math.round(value).toLocaleString('en-US')}`)

// The three headline values: employment 3–5 years out (or at the latest year reached), median pay from year 1 to then,
// and the growth between them. Shared by this tab and the Past cohorts card. null when no one has reached year 1.
function outcomeHeadline(rows, compact) {
  const reached = rows.filter(r => r.years_out > 0 && r.alumni > 0)
  if (!reached.length) return null
  const band = reached.filter(r => r.years_out >= 3 && r.years_out <= 5)
  const scope = band.length ? band : [reached.at(-1)]
  const employed = scope.map(r => r.employed_pct).filter(v => v != null)
  const low = Math.min(...employed), high = Math.max(...employed)
  const first = reached.find(r => r.years_out === 1)?.median_salary
  const lastRow = [...scope].reverse().find(r => r.median_salary != null)
  const latest = lastRow?.median_salary
  return {
    employedLabel: band.length ? 'Employed 3–5 years out' : `Employed ${scope[0].years_out} year${scope[0].years_out === 1 ? '' : 's'} out`,
    employed: employed.length ? (low === high ? `${low}%` : `${low}–${high}%`) : '—',
    payLabel: `Median pay, year 1 → year ${lastRow?.years_out ?? scope.at(-1).years_out}`,
    pay: `${money(first, compact)} → ${money(latest, compact)}`,
    growth: first && latest ? `${latest >= first ? '+' : ''}${Math.round(((latest - first) / first) * 100)}%` : '—',
  }
}

// compact: $61k instead of $60,750, for narrow cards
export default function OutcomeHeadline({ rows, compact = false }) {
  const h = outcomeHeadline(rows, compact)
  if (!h) return <p className="panel-empty">No one in this selection has reached a year after graduation yet.</p>
  return <div className="outcome-headline">
    <div><span className="kpi-label">{h.employedLabel}</span><strong>{h.employed}</strong></div>
    <div><span className="kpi-label">{h.payLabel}</span><strong>{h.pay}</strong></div>
    <div><span className="kpi-label">Pay growth</span><strong>{h.growth}</strong></div>
  </div>
}
