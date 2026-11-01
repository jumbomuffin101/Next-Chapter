import Panel from './Panel.jsx'

// ONE illustrative career path, clearly labeled as a sample (not a real alumnus).
const STEPS = [
  { title: 'Help Desk Technician', org: 'Demo Health', when: '2021 – 2022', pay: '$42k' },
  { title: 'IT Support Specialist', org: 'Demo Health', when: '2022 – 2023', pay: '$58k' },
  { title: 'Systems Administrator', org: 'Demo Cloud', when: '2023 – 2025', pay: '$76k' },
  { title: 'Cloud Engineer', org: 'Demo Cloud', when: '2025 – now', pay: '$98k' },
]

export default function CareerSample() {
  return <Panel title="Sample career progression" caption="SAMPLE · illustrative, not a real alumnus" className="span-5">
    <ol className="path">{STEPS.map((step, i) => <li key={step.title}>
      <span className="step-no">{i + 1}</span>
      <div><strong>{step.title}</strong><small>{step.org} · {step.when}</small></div>
      <b>{step.pay}</b>
    </li>)}</ol>
    <p className="map-note">Four roles in four years, pay up 133%. Real paths appear here as alumni add their history.</p>
  </Panel>
}
