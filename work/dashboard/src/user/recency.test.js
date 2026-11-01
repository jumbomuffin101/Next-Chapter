import assert from 'node:assert/strict'
import test from 'node:test'
import { ago, daysSince, isNew } from './recency.js'

const NOW = Date.parse('2026-10-17T12:00:00Z')
const daysBefore = n => new Date(NOW - n * 86_400_000).toISOString()

test('ago says today, yesterday, then days, weeks, months and years', () => {
  assert.equal(ago(daysBefore(0), NOW), 'today')
  assert.equal(ago(daysBefore(1), NOW), 'yesterday')
  assert.equal(ago(daysBefore(3), NOW), '3 days ago')
  assert.equal(ago(daysBefore(13), NOW), '13 days ago')
  assert.equal(ago(daysBefore(14), NOW), '2 weeks ago')
  assert.equal(ago(daysBefore(59), NOW), '8 weeks ago')
  assert.equal(ago(daysBefore(60), NOW), '2 months ago')
  assert.equal(ago(daysBefore(400), NOW), '13 months ago')
  assert.equal(ago(daysBefore(800), NOW), '2 years ago')
})

test('missing or invalid dates are reported honestly, never invented', () => {
  for (const bad of [null, undefined, '', 'not a date']) assert.equal(ago(bad, NOW), 'date unknown')
  assert.equal(daysSince(null, NOW), null)
  assert.equal(isNew(null, NOW), false)
})

test('a timestamp slightly in the future counts as today (clock skew), not a negative age', () => {
  assert.equal(ago(new Date(NOW + 3_600_000).toISOString(), NOW), 'today')
  assert.equal(daysSince(new Date(NOW + 3_600_000).toISOString(), NOW), 0)
})

test('isNew is true up to 7 days old and false after', () => {
  assert.equal(isNew(daysBefore(7), NOW), true)
  assert.equal(isNew(daysBefore(8), NOW), false)
  assert.equal(isNew(daysBefore(30), NOW, 30), true)
})
