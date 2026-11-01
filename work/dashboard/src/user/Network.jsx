import { useState } from 'react'
import Events from './Events.jsx'
import People from './People.jsx'
import SubTabs from './SubTabs.jsx'
import { newsletterNetworkPart } from './newsletterNavigation.js'

// Network: alumni in your field near you, and meetups and events in your area.
export default function Network() {
  const [part, setPart] = useState(() => newsletterNetworkPart(window.location.search))
  return <section className="area">
    <SubTabs label="Network" active={part} onChange={setPart} tabs={[['people', 'People near you'], ['events', 'Meetups & events']]} />
    {part === 'people' ? <People /> : <Events />}
  </section>
}
