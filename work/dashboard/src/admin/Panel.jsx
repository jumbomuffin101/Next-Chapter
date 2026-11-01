import { useEffect, useRef, useState } from 'react'
import { scrollBehavior } from '../comfort.js'

// A boxed section of the admin dashboard.
// collapsible: on narrow screens (900px and below, where CSS caps the content height) a card taller than the cap
// shows a preview and an Expand button in its header instead of scrolling inside itself. Wider, no button appears.
// A card that already has a sideways-scrolling row is compact enough: it shows in full, with no button and no fade.
export default function Panel({ title, caption, className = '', id, collapsible = false, children }) {
  const content = useRef(null)
  const [open, setOpen] = useState(false)
  const [overflows, setOverflows] = useState(false)
  const [hasRow, setHasRow] = useState(false)

  useEffect(() => {
    if (!collapsible || open) return // measured while collapsed; an open card keeps its button
    const el = content.current
    // fires once on observe and again whenever the content's size changes (e.g. when data loads)
    const observer = new ResizeObserver(() => {
      const row = [...el.querySelectorAll('*')].some(child => child.scrollWidth > child.clientWidth + 4 && /(auto|scroll)/.test(getComputedStyle(child).overflowX))
      setHasRow(row)
      setOverflows(!row && el.scrollHeight > el.clientHeight + 4)
    })
    observer.observe(el)
    if (el.firstElementChild) observer.observe(el.firstElementChild)
    return () => observer.disconnect()
  }, [collapsible, open])

  function toggle() {
    setOpen(value => !value)
    if (open) content.current.closest('.panel')?.scrollIntoView({ block: 'start', behavior: scrollBehavior() }) // back to the card's top
  }

  return <section id={id} className={`panel ${className} ${collapsible ? 'collapsible' : ''} ${overflows ? 'overflows' : ''} ${hasRow ? 'has-row' : ''} ${open ? 'open' : ''}`}>
    <header className="panel-head"><h2>{title}</h2>
      {collapsible && overflows && <button type="button" className="panel-toggle" aria-expanded={open} aria-label={`${open ? 'Collapse' : 'Expand'} ${title}`} title={open ? 'Collapse' : 'Expand'} onClick={toggle}><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg></button>}
      {caption && <span>{caption}</span>}
    </header>
    <div className="panel-body">
      {collapsible ? <div className="panel-content" ref={content}>{children}</div> : children}
    </div>
  </section>
}
