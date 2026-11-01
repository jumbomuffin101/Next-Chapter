import Panel from './Panel.jsx'

// Who to watch: career gaps, help requests, missing info. The full list lives on the Needs action page.
export default function ActionsPreview({ items, total, onOpen }) {
  return <Panel collapsible title="Watch list" caption={total ? `${total} may need help` : 'Nothing open'} className="square">
    {items.length === 0 ? <p className="panel-empty">No one needs attention in this cohort right now.</p> : <ul className="preview-list">
      {items.map(item => <li key={item.id}>
        <span className={`prio ${item.priority}`}>{item.priority}</span>
        <div><strong>{item.name}</strong><small>{item.flags.map(flag => flag.detail).join(' · ')}</small></div>
      </li>)}
    </ul>}
    <button className="text-button" onClick={onOpen}>{total > items.length ? `View all ${total}` : 'Open the Needs action page'} →</button>
  </Panel>
}
