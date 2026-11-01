import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeResumeDraft, validateProfile } from './profile.js'

test('resume import preserves known fields and career history for review', () => {
  const existing = {
    full_name: 'Alex Rivera', email: 'account@example.org', phone: '555-123-4567', location: 'Boston, MA',
    work_experience: [{ employer: 'Atlas Labs', title: 'Engineer', start_date: '2022', is_current: true, description: 'Existing details' }],
    education: [{ school: 'City College', degree: 'BS', end_date: '2021' }],
    skills: ['Python'], certifications: ['AWS Cloud Practitioner'],
  }
  const parsed = {
    full_name: '', email: 'different@example.org', phone: '', location: '',
    work_experience: [{ employer: 'Atlas Labs', title: 'Engineer', start_date: '2022', description: '' },
      { employer: 'New Company', title: 'Analyst', start_date: '2024' }],
    skills: ['python', 'Data Analysis'], certifications: [], warnings: ['Review dates'],
  }
  const draft = mergeResumeDraft(existing, parsed)
  assert.equal(draft.email, existing.email)
  assert.equal(draft.full_name, existing.full_name)
  assert.equal(draft.phone, existing.phone)
  assert.equal(draft.location, existing.location)
  assert.equal(draft.work_experience.length, 2)
  assert.equal(draft.work_experience[0].description, 'Existing details')
  assert.equal(draft.work_experience[0].is_current, true)
  assert.equal(draft.education.length, 1)
  assert.deepEqual(draft.skills, ['python', 'Data Analysis'])
  assert.deepEqual(draft.certifications, ['AWS Cloud Practitioner'])
  assert.deepEqual(draft.warnings, ['Review dates'])
  assert.equal(validateProfile(draft, draft.skills.join(', '), draft.certifications.join('\n')).work_experience.length, 2)
})
