import test from 'node:test'
import assert from 'node:assert/strict'
import { newsletterArea, newsletterNetworkPart } from './newsletterNavigation.js'

test('newsletter links select existing Job Monitor, profile and events controls', () => {
  assert.equal(newsletterArea('?section=jobs'), 'jobs')
  assert.equal(newsletterArea('?section=profile'), 'profile')
  assert.equal(newsletterArea('?section=newsletter'), 'newsletter')
  assert.equal(newsletterArea('?section=events'), 'network')
  assert.equal(newsletterNetworkPart('?section=events'), 'events')
})

test('absent and unsupported destinations keep My profile as the default tab', () => {
  for (const search of ['', '?section=unknown', '?section=javascript:alert(1)']) {
    assert.equal(newsletterArea(search), 'profile')
    assert.equal(newsletterNetworkPart(search), 'people')
  }
})
