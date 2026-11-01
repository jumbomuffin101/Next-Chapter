import test from 'node:test'
import assert from 'node:assert/strict'
import { monthLabel, safeOpportunityUrl } from './monthlyNewsletter.js'

test('newsletter month is displayed without local timezone drift', () => {
  assert.equal(monthLabel('2026-10'), 'October 2026')
  assert.equal(monthLabel('invalid'), 'This month')
})

test('job links accept only absolute web destinations without credentials', () => {
  assert.equal(safeOpportunityUrl('https://boards.greenhouse.io/example/jobs/123'),
    'https://boards.greenhouse.io/example/jobs/123')
  for (const url of ['javascript:alert(1)', 'file:///tmp/job.html', '//example.org/job',
    'https://user:password@example.org/job', '']) assert.equal(safeOpportunityUrl(url), null)
})
