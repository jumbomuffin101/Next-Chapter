"""Prompt 2: isolated consent/ledger database and mocked provider; never sends mail."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
import uuid

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, ProgrammingError

from backend.app.auth import router as auth
from backend.app.newsletter import delivery, preferences, security
from backend.app.newsletter import content as selection
from backend.app.newsletter.preview import demo_newsletter
from backend.app.newsletter.provider import Message, ProviderFailure, ResendAdapter, Settings
from backend.app.newsletter.router import router
from backend.app.newsletter.calendar import current_month
from work.database.models import Alumni, NewsletterDelivery, NewsletterSubscription


@pytest.fixture
def setup(isolated_db, monkeypatch):
    monkeypatch.setenv('NEWSLETTER_TOKEN_SECRET', 'test-only-signing-key-not-for-deployment-1234')
    monkeypatch.delenv('NEWSLETTER_DRY_RUN', raising=False)
    monkeypatch.setenv('NEWSLETTER_APP_URL', 'https://app.example.org')
    monkeypatch.setenv('NEWSLETTER_PUBLIC_API_URL', 'https://api.example.org')
    monkeypatch.setenv('NEWSLETTER_FROM_EMAIL', 'newsletter@example.org')
    monkeypatch.setenv('NEWSLETTER_POSTAL_ADDRESS', 'Example test address; not a real sender')
    monkeypatch.setenv('NEWSLETTER_DEMO_RECIPIENTS', 'demo@example.org')
    monkeypatch.setenv('RESEND_API_KEY', 'test-only-never-used-on-network')
    monkeypatch.setenv('ADMIN_TOKEN_SECRET', 'test-only-admin-signing-key-not-for-deployment')
    monkeypatch.setenv('ADMIN_PASSWORD', 'test-only-admin-password')
    monkeypatch.setattr(preferences, 'SessionLocal', isolated_db.Session)
    monkeypatch.setattr(delivery, 'generate_newsletter', Mock(return_value=demo_newsletter()))
    identifiers = [uuid.UUID(int=i) for i in (8101, 8102, 8103)]
    with isolated_db.Session.begin() as s:
        for identifier, email, demo in zip(identifiers, ['demo@example.org', 'other@example.org', 'real@example.org'], [True, True, False]):
            s.add(Alumni(id=identifier, first_name='Example', last_name='Person', email=email, is_demo=demo))
    app = FastAPI(); app.include_router(router)
    return SimpleNamespace(db=isolated_db, monkeypatch=monkeypatch, ids=identifiers, client=TestClient(app),
                           month=current_month())


def headers(identifier):
    return {'Authorization': 'Bearer ' + security.demo_session(identifier)}


def test_preference_defaults_opt_in_out_and_identity_binding(setup):
    c, identifier = setup.client, setup.ids[0]
    assert c.get('/newsletter/preferences', headers=headers(identifier)).json()['subscribed'] is False
    r = c.put('/newsletter/preferences', headers=headers(identifier), json={'subscribed': True})
    assert r.status_code == 200 and r.json()['subscribed_at'] and r.json()['message']
    first_time = r.json()['subscribed_at']
    assert c.put('/newsletter/preferences', headers=headers(identifier), json={'subscribed': True}).json()['subscribed_at'] == first_time
    assert c.get('/newsletter/preferences', headers=headers(setup.ids[1])).json()['subscribed'] is False
    r = c.put('/newsletter/preferences', headers=headers(identifier), json={'subscribed': False})
    assert not r.json()['subscribed'] and r.json()['unsubscribed_at']


def test_no_unauthenticated_cross_user_or_real_account_updates(setup):
    for h in [{}, {'Authorization': 'Bearer arbitrary-id'}, {'Authorization': 'Bearer ' + auth.make_admin_token()}]:
        assert setup.client.put('/newsletter/preferences', headers=h, json={'subscribed': True}).status_code == 401
    h = headers(setup.ids[0])
    assert setup.client.put('/newsletter/preferences', headers=h, json={'subscribed': True, 'alumni_id': str(setup.ids[1])}).status_code == 422
    assert setup.client.put('/newsletter/preferences', headers=h, json={'subscribed': 'true'}).status_code == 422
    assert setup.client.put('/newsletter/preferences', headers=headers(setup.ids[2]), json={'subscribed': True}).status_code == 403
    assert setup.client.get(f'/newsletter/preferences/{setup.ids[1]}', headers=h).status_code == 404
    assert setup.client.post(f'/newsletter/deliveries/{setup.ids[0]}', json={'month': setup.month}).status_code == 401


def test_signed_sessions_expiry_tampering_purpose_and_missing_key(setup):
    token = security.sign('demo', setup.ids[0].hex, lifetime=10, now=100)
    assert security.verify(token, 'demo', now=109) == setup.ids[0].hex
    for value, kind in [(token, 'unsubscribe'), (token + 'x', 'demo')]:
        with pytest.raises(ValueError): security.verify(value, kind, now=105)
    with pytest.raises(ValueError): security.verify(token, 'demo', now=110)
    setup.monkeypatch.delenv('NEWSLETTER_TOKEN_SECRET')
    assert security.demo_session(setup.ids[0]) is None
    assert setup.client.get('/newsletter/preferences', headers={'Authorization': 'Bearer '+token}).status_code == 401


def unsubscribe_link(setup):
    preferences.update_preference(setup.ids[0], True)
    with setup.db.Session() as s:
        return security.unsubscribe_token(s.get(NewsletterSubscription, setup.ids[0]).token_nonce)


def test_unsubscribe_get_is_safe_post_needs_no_login_and_is_idempotent(setup):
    token = unsubscribe_link(setup)
    assert str(setup.ids[0]) not in token and 'demo@example.org' not in token
    r = setup.client.get('/newsletter/unsubscribe', params={'token': token})
    assert r.status_code == 200 and r.headers['cache-control'] == 'no-store'
    assert preferences.read_preference(setup.ids[0])['subscribed']
    for _ in range(2):
        assert setup.client.post('/newsletter/unsubscribe', params={'token': token}, data={'List-Unsubscribe': 'One-Click'}).status_code == 200
    assert not preferences.read_preference(setup.ids[0])['subscribed']
    assert delivery.deliver(setup.ids[0], setup.month, adapter=Mock())['status'] == 'not_subscribed'


def test_unsubscribe_tampering_expiry_and_resubscription_revocation(setup):
    token = unsubscribe_link(setup)
    assert setup.client.post('/newsletter/unsubscribe', params={'token': token + 'x'}).status_code == 422
    expired = security.sign('unsubscribe', security.nonce(), lifetime=-1)
    assert setup.client.get('/newsletter/unsubscribe', params={'token': expired}).status_code == 400
    preferences.update_preference(setup.ids[0], False); preferences.update_preference(setup.ids[0], True)
    assert setup.client.post('/newsletter/unsubscribe', params={'token': token}).status_code == 200
    assert preferences.read_preference(setup.ids[0])['subscribed']


def test_default_dry_run_persists_status_never_calls_provider_and_can_transition(setup):
    preferences.update_preference(setup.ids[0], True)
    provider = Mock()
    assert Settings.load().dry_run
    for _ in range(2): assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == 'dry_run'
    provider.send.assert_not_called()
    assert delivery.get_delivery(setup.ids[0], setup.month)['status'] == 'dry_run'
    setup.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    provider.send.return_value = 'mock-provider-id'
    assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == 'accepted'
    assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == 'accepted'
    provider.send.assert_called_once()
    message = provider.send.call_args.args[0]
    assert '<html' in message.html and 'Job Opportunities' in message.text
    assert 'Unsubscribe' in message.text and message.unsubscribe_url in message.text
    assert 'Example test address' in message.html and 'explicitly subscribed' in message.text
    assert 'EXAMPLE EVENT' in message.html
    token = parse_qs(urlsplit(message.unsubscribe_url).query)['token'][0]
    assert security.verify(token, 'unsubscribe')
    assert str(setup.ids[0]) not in message.idempotency_key


@pytest.mark.parametrize('failure,status,retryable', [
    (ProviderFailure('provider_rate_limited', retryable=True), 'retryable', True),
    (ProviderFailure('provider_rejected'), 'failed', False),
    (ProviderFailure('provider_network_unknown', uncertain=True), 'unknown', False),
    (RuntimeError('private provider error body'), 'unknown', False),
])
def test_delivery_failures_are_sanitized_and_never_automatically_resent(setup, failure, status, retryable):
    preferences.update_preference(setup.ids[0], True)
    setup.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    provider = Mock(); provider.send.side_effect = failure
    r = delivery.deliver(setup.ids[0], setup.month, adapter=provider)
    assert r['status'] == status and r['retryable'] == retryable and 'private' not in str(r)
    assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == status
    provider.send.assert_called_once()


def test_live_delivery_requires_demo_consent_allowlist_and_sender_configuration(setup):
    setup.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    provider = Mock()
    assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == 'not_subscribed'
    preferences.update_preference(setup.ids[1], True)
    with pytest.raises(PermissionError): delivery.deliver(setup.ids[1], setup.month, adapter=provider)
    with pytest.raises(PermissionError): delivery.deliver(setup.ids[2], setup.month, adapter=provider)
    preferences.update_preference(setup.ids[0], True)
    setup.monkeypatch.delenv('NEWSLETTER_POSTAL_ADDRESS')
    with pytest.raises(ValueError): delivery.deliver(setup.ids[0], setup.month, adapter=provider)
    provider.send.assert_not_called()


def test_opt_out_during_generation_suppresses_send(setup):
    preferences.update_preference(setup.ids[0], True)
    setup.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    def generating(*args, **kwargs):
        preferences.update_preference(setup.ids[0], False)
        return demo_newsletter()
    setup.monkeypatch.setattr(delivery, 'generate_newsletter', generating)
    provider = Mock()
    assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == 'not_subscribed'
    provider.send.assert_not_called()


def test_durable_attempt_claim_is_not_retried_and_unique_constraint_exists(setup):
    preferences.update_preference(setup.ids[0], True)
    with setup.db.Session.begin() as s:
        s.add(NewsletterDelivery(alumni_id=setup.ids[0], month=delivery.month_start(setup.month), status='attempting'))
    provider = Mock()
    assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == 'attempting'
    provider.send.assert_not_called()
    with pytest.raises(IntegrityError), setup.db.Session.begin() as s:
        s.add(NewsletterDelivery(alumni_id=setup.ids[0], month=delivery.month_start(setup.month), status='accepted'))


@pytest.mark.parametrize('code,expected,uncertain', [(429, 'provider_rate_limited', False), (500, 'provider_server_unknown', True), (401, 'provider_rejected', False)])
def test_adapter_error_classification_uses_no_real_network(code, expected, uncertain):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(code, json={'private': 'never expose'})))
    with client, pytest.raises(ProviderFailure) as error:
        ResendAdapter('fake', client=client).send(Message('demo@example.org', 'sender@example.org', 'Subject', '<p>HTML</p>', 'Text', 'https://example.org/unsubscribe', 'example-key'))
    assert error.value.code == expected and error.value.uncertain == uncertain


def test_adapter_sends_both_formats_unsubscribe_headers_and_idempotency_to_mock_only():
    def handler(request):
        import json
        body = json.loads(request.content)
        assert body['html'] == '<p>HTML</p>' and body['text'] == 'Text'
        assert body['headers']['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'
        assert request.headers['Idempotency-Key'] == 'example-key'
        return httpx.Response(200, json={'id': 'mock-provider-id'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert ResendAdapter('fake', client=client).send(Message('demo@example.org', 'sender@example.org', 'Subject', '<p>HTML</p>', 'Text', 'https://example.org/unsubscribe', 'example-key')) == 'mock-provider-id'


def test_missing_migration_is_actionable_without_breaking_authentication(setup):
    original = preferences.SessionLocal
    failure = ProgrammingError('hidden statement', {}, SimpleNamespace(sqlstate='42P01'))
    setup.monkeypatch.setattr(preferences, 'SessionLocal', Mock(side_effect=failure))
    assert setup.client.get('/newsletter/preferences', headers=headers(setup.ids[0])).status_code == 503
    setup.monkeypatch.setattr(preferences, 'SessionLocal', original)


def test_email_only_login_only_issues_newsletter_session_for_demo_records(setup):
    connection = Mock(); cursor = Mock()
    connection.__enter__ = Mock(return_value=connection); connection.__exit__ = Mock(return_value=False)
    cursor.__enter__ = Mock(return_value=cursor); cursor.__exit__ = Mock(return_value=False)
    connection.cursor.return_value = cursor
    setup.monkeypatch.setattr(auth, 'get_conn', Mock(return_value=connection))
    for demo in [True, False]:
        cursor.fetchone.return_value = {'id': setup.ids[0], 'is_demo': demo, 'email': 'demo@example.org'}
        result = auth.alumni_login(auth.AlumniLogin(email='demo@example.org'))
        assert bool(result['newsletter_token']) == demo


def test_delivery_empty_sections_keep_working_unsubscribe_and_formats(setup):
    from backend.app.newsletter.render import render
    setup.monkeypatch.setattr(selection, 'events_for', lambda *args: {})
    content = selection.compose(selection.Profile(is_demo=True), None, [], None,
                                app_url='https://app.example.org', today=datetime.now(timezone.utc).date())
    setup.monkeypatch.setattr(delivery, 'generate_newsletter', Mock(return_value=render(content)))
    setup.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    preferences.update_preference(setup.ids[0], True)
    provider = Mock(); provider.send.return_value = 'mock-id'
    assert delivery.deliver(setup.ids[0], setup.month, adapter=provider)['status'] == 'accepted'
    message = provider.send.call_args.args[0]
    for body in [message.html, message.text]:
        assert 'No eligible job listings' in body and 'No upcoming event' in body
        assert message.unsubscribe_url in body


def test_live_validation_fails_closed_on_unsafe_urls_and_admin_defaults(setup):
    settings = Settings.load()
    setup.monkeypatch.delenv('ADMIN_TOKEN_SECRET')
    with pytest.raises(ValueError, match='admin authentication'): settings.validate_live('demo@example.org')
    setup.monkeypatch.setenv('ADMIN_TOKEN_SECRET', 'test-only-strong-enough-admin-key-12345678')
    setup.monkeypatch.setenv('NEWSLETTER_PUBLIC_API_URL', 'http://localhost:8000')
    with pytest.raises(ValueError, match='HTTPS'): Settings.load().validate_live('demo@example.org')
    setup.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'invalid-configuration')
    assert Settings.load().dry_run


def test_adapter_network_timeout_is_unknown_not_automatically_retryable():
    def timeout(request):
        raise httpx.ReadTimeout('private error never exposed', request=request)
    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(ProviderFailure) as error:
            ResendAdapter('fake', client=client).send(Message('demo@example.org', 'sender@example.org', 'Subject', '<p>HTML</p>', 'Text', 'https://example.org/unsubscribe', 'example-key'))
    assert error.value.uncertain and not error.value.retryable and 'private' not in str(error.value)
