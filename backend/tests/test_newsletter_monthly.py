"""Monthly lifecycle: isolated SQLite + real content engine + fake delivery only."""
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import json
import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import func, select

from backend.tests.test_newsletter_delivery import setup, headers  # reuse blocked production DB fixture
from backend.app.newsletter import calendar, content, delivery, monthly, preferences, service
from backend.app.newsletter.provider import ProviderFailure
from work.database.models import Alumni, Job, NewsletterDelivery, ResumeUpload, WorkExperience


@pytest.fixture
def lifecycle(setup, monkeypatch):
    from backend.app.analytics import router as analytics
    from work.database import database
    monkeypatch.setattr(database, 'readonly_session', analytics.readonly_session)
    monkeypatch.setattr(delivery, 'generate_newsletter', service.generate_newsletter)
    with setup.db.Session.begin() as s:
        person = s.get(Alumni, setup.ids[0]); person.cohort = '2022'; person.city = 'New York'
        s.add(WorkExperience(alumni_id=person.id, title='Software Engineer', employer='Synthetic Employer',
                             start_date=date(2020, 1, 1), is_current=True))
        s.add(Job(board_token='example', greenhouse_job_id='monthly', title='Software Engineer',
                  company='Example Company', location='New York', absolute_url='https://example.org/jobs/monthly'))
        s.add(ResumeUpload(alumni_id=person.id, file_name='private.pdf', confirmed=True, parsed_data={'private': 'never disclose'}))
        for i in range(4):
            s.add(Alumni(id=uuid.UUID(int=8200+i), first_name='PRIVATE_PEER', last_name='Example',
                         email=f'private-{i}@example.org', cohort='2022', is_demo=True))
    return setup


def test_complete_api_subscription_monthly_content_delivery_rerun_and_unsubscribe(lifecycle):
    state = lifecycle
    # The frontend's exact preference method/body/header, through the real router.
    r = state.client.put('/newsletter/preferences', json={'subscribed': True}, headers=headers(state.ids[0]))
    assert r.status_code == 200 and r.json()['subscribed']
    assert preferences.read_preference(state.ids[0])['subscribed']
    state.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    provider = Mock(); provider.send.return_value = 'mock-monthly-id'
    result = monthly.run_month(state.month, live=True, adapter=provider, batch_size=1, sleep=lambda _: None)
    assert result.success == 1 and result.failed == 0
    message = provider.send.call_args.args[0]
    for body in [message.html, message.text]:
        assert 'Software Engineer' in body and 'Similar role' in body
        assert 'EXAMPLE EVENT' in body and '5 alumni on record' in body
        assert 'PRIVATE_PEER' not in body and 'private.pdf' not in body
        assert '?section=jobs' in body and '?section=events' in body and '?section=profile' in body
    assert delivery.get_delivery(state.ids[0], state.month)['status'] == 'accepted'
    again = monthly.run_month(state.month, live=True, adapter=provider)
    assert again.success == 0 and again.skipped == 1
    provider.send.assert_called_once()
    from urllib.parse import parse_qs, urlsplit
    token = parse_qs(urlsplit(message.unsubscribe_url).query)['token'][0]
    assert state.client.post('/newsletter/unsubscribe', params={'token': token+'x'}).status_code == 422
    assert state.client.post('/newsletter/unsubscribe', params={'token': token}).status_code == 200
    assert monthly.run_month(state.month).eligible == 0


def test_dry_run_overrides_live_environment_and_never_writes_ledger(lifecycle):
    preferences.update_preference(lifecycle.ids[0], True)
    lifecycle.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    provider = Mock(side_effect=AssertionError('No email in dry run'))
    result = monthly.run_month(lifecycle.month, adapter=provider)
    assert result.mode == 'dry_run' and result.success == 1
    provider.assert_not_called()
    with lifecycle.db.Session() as s:
        assert s.scalar(select(func.count()).select_from(NewsletterDelivery)) == 0


def test_empty_subscribers_and_empty_content_do_not_fail(lifecycle):
    assert monthly.run_month(lifecycle.month).eligible == 0
    preferences.update_preference(lifecycle.ids[1], True)  # no roles/cohort/jobs for this person
    lifecycle.monkeypatch.setattr(content, 'events_for', lambda *args: {})
    report = monthly.run_month(lifecycle.month, batch_size=1)
    assert report.success == 1 and report.failed == 0


def test_rate_limit_retries_bounded_and_success_never_resent(lifecycle):
    preferences.update_preference(lifecycle.ids[0], True)
    lifecycle.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    provider = Mock(); provider.send.side_effect = [ProviderFailure('provider_rate_limited', retryable=True), 'mock-success']
    delay = Mock()
    report = monthly.run_month(lifecycle.month, live=True, adapter=provider, sleep=delay)
    assert report.success == 1 and report.retries == 1 and report.failed == 0
    delay.assert_called_once_with(1)
    keys = [call.args[0].idempotency_key for call in provider.send.call_args_list]
    assert keys[0] != keys[1]  # New request only after explicit rejection.
    assert monthly.run_month(lifecycle.month, live=True, retry_failed=True, adapter=provider).skipped == 1
    assert provider.send.call_count == 2


def test_partial_failures_manual_retry_progresses_without_duplicate_success(lifecycle):
    for identifier in lifecycle.ids[:2]: preferences.update_preference(identifier, True)
    lifecycle.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    lifecycle.monkeypatch.setenv('NEWSLETTER_DEMO_RECIPIENTS', 'demo@example.org,other@example.org')
    provider = Mock(); provider.send.side_effect = ['mock-first', ProviderFailure('provider_rate_limited', retryable=True)]
    first = monthly.run_month(lifecycle.month, live=True, batch_size=1, adapter=provider, max_retries=0)
    assert (first.success, first.failed, first.status) == (1, 1, 'partial_failure')
    assert monthly.run_month(lifecycle.month, live=True, adapter=provider).skipped == 2
    provider.send.side_effect = None; provider.send.return_value = 'mock-second'
    final = monthly.run_month(lifecycle.month, live=True, retry_failed=True, adapter=provider)
    assert final.success == 1 and final.skipped == 1
    assert provider.send.call_count == 3


def test_limited_rerun_moves_past_already_accepted_recipients(lifecycle):
    for identifier in lifecycle.ids[:2]: preferences.update_preference(identifier, True)
    lifecycle.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    lifecycle.monkeypatch.setenv('NEWSLETTER_DEMO_RECIPIENTS', 'demo@example.org,other@example.org')
    provider = Mock(); provider.send.return_value = 'mock-success'
    first = monthly.run_month(lifecycle.month, live=True, limit=1, batch_size=1, adapter=provider)
    assert first.success == 1 and first.deferred == 1
    second = monthly.run_month(lifecycle.month, live=True, limit=1, batch_size=1, adapter=provider)
    assert second.success == 1 and second.skipped == 1
    assert [call.args[0].recipient for call in provider.send.call_args_list] == ['demo@example.org','other@example.org']


@pytest.mark.parametrize('status,error', [('accepted',None),('attempting',None),('unknown','provider_network_unknown'),('failed','provider_rejected')])
def test_retry_flag_never_resets_unsafe_or_successful_claims(lifecycle, status, error):
    preferences.update_preference(lifecycle.ids[0], True)
    lifecycle.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    with lifecycle.db.Session.begin() as s:
        s.add(NewsletterDelivery(alumni_id=lifecycle.ids[0], month=delivery.month_start(lifecycle.month), status=status,error_code=error))
    provider = Mock()
    report = monthly.run_month(lifecycle.month, live=True, retry_failed=True, adapter=provider)
    assert report.skipped == 1 and report.processed == 0
    provider.send.assert_not_called()


def test_retry_limit_and_unsubscribe_between_attempts(lifecycle):
    preferences.update_preference(lifecycle.ids[0], True)
    lifecycle.monkeypatch.setenv('NEWSLETTER_DRY_RUN', 'false')
    provider=Mock(); provider.send.side_effect=ProviderFailure('provider_rate_limited',retryable=True)
    def opt_out(_): preferences.update_preference(lifecycle.ids[0],False)
    report=monthly.run_month(lifecycle.month, live=True,adapter=provider,sleep=opt_out)
    assert report.skipped == 1 and provider.send.call_count == 1
    preferences.update_preference(lifecycle.ids[0],True)
    report=monthly.run_month(lifecycle.month, live=True,adapter=provider,retry_failed=True,max_retries=2,sleep=lambda _:None)
    assert report.failed==1 and report.retries==2 and provider.send.call_count==4


def test_real_accounts_excluded_even_with_consent_and_allowlist(lifecycle):
    from work.database.models import NewsletterSubscription
    with lifecycle.db.Session.begin() as s:
        s.add(NewsletterSubscription(alumni_id=lifecycle.ids[2], subscribed=True, token_nonce='real-is-still-blocked'))
    lifecycle.monkeypatch.setenv('NEWSLETTER_DEMO_RECIPIENTS','real@example.org')
    assert monthly.run_month(lifecycle.month).eligible == 0


def test_individual_failure_does_not_leak_or_stop_other_recipients(lifecycle, capsys):
    for identifier in lifecycle.ids[:2]: preferences.update_preference(identifier, True)
    generate = Mock(side_effect=[RuntimeError('SECRET DATABASE_URL hidden'), service.generate_newsletter(lifecycle.ids[1],app_url='https://example.org')])
    lifecycle.monkeypatch.setattr(service,'generate_newsletter',generate)
    result=monthly.run_month(lifecycle.month,batch_size=1)
    assert result.failed==1 and result.success==1
    assert 'SECRET' not in str(asdict(result)) and capsys.readouterr().out==''


def test_calendar_month_boundary_dst_and_event_cutoff(monkeypatch):
    assert calendar.current_month(datetime(2026,11,1,2,tzinfo=timezone.utc))=='2026-10'
    assert calendar.current_month(datetime(2026,11,1,14,tzinfo=timezone.utc))=='2026-11'
    assert calendar.scheduled_at('2026-01').astimezone(timezone.utc).hour == 14
    assert calendar.scheduled_at('2026-07').astimezone(timezone.utc).hour == 13
    scheduled=date(2026,11,1)
    data=content.events_for('New York','software',date(2026,10,17))
    data['local']=[{**data['local'][0],'date':'2026-10-31'},{**data['local'][1],'date':'2026-11-02'}];data['online']=[]
    monkeypatch.setattr(content,'events_for',lambda *args:data)
    digest=content.compose(content.Profile(city='New York'),None,[],None,app_url='https://example.org',today=date(2026,10,17),events_after=scheduled)
    assert [e.date for e in digest.events] == [date(2026,11,2)]


@pytest.mark.parametrize('options',[{'limit':0},{'batch_size':0},{'batch_size':501},{'max_retries':6}])
def test_invalid_batch_configuration_rejected(lifecycle,options):
    with pytest.raises(ValueError):monthly.run_month(lifecycle.month,**options)


def test_cli_defaults_dry_run_and_scheduling_kill_switch(monkeypatch,capsys):
    runner=Mock(return_value=monthly.Result('2026-10','dry_run'))
    monkeypatch.setattr(monthly,'run_month',runner)
    monkeypatch.setenv('NEWSLETTER_DRY_RUN','false')
    assert monthly.main(['--month','2026-10'])==0
    assert runner.call_args.kwargs['live'] is False
    runner.reset_mock();monkeypatch.delenv('NEWSLETTER_SCHEDULING_ENABLED',raising=False)
    assert monthly.main(['--scheduled','--authorize-live'])==0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['status']=='disabled'
    runner.assert_not_called()


def test_cli_partial_failures_and_sanitized_startup_errors(monkeypatch,capsys):
    monkeypatch.setattr(monthly,'run_month',Mock(return_value=monthly.Result('2026-10','dry_run',failed=1)))
    assert monthly.main(['--month','2026-10'])==1
    monkeypatch.setattr(monthly,'run_month',Mock(side_effect=RuntimeError('private password secret')))
    assert monthly.main(['--month','2026-10'])==2
    assert 'private password' not in capsys.readouterr().out


def test_unapplied_migration_has_safe_actionable_cli_result(monkeypatch,capsys):
    from sqlalchemy.exc import ProgrammingError
    from types import SimpleNamespace
    error=ProgrammingError('private SQL',{},SimpleNamespace(sqlstate='42P01'))
    monkeypatch.setattr(monthly,'run_month',Mock(side_effect=error))
    assert monthly.main(['--month','2026-10'])==2
    result=json.loads(capsys.readouterr().out)
    assert result['reason']=='newsletter_schema_pending' and 'private SQL' not in str(result)


def test_enabled_schedule_does_not_run_before_nine_am(monkeypatch,capsys):
    monkeypatch.setenv('NEWSLETTER_SCHEDULING_ENABLED','true')
    monkeypatch.setattr(monthly,'current_month',lambda:'2026-10')
    monkeypatch.setattr(monthly,'local_now',lambda:calendar.scheduled_at('2026-10').replace(hour=8))
    runner=Mock();monkeypatch.setattr(monthly,'run_month',runner)
    assert monthly.main(['--scheduled','--dry-run'])==0
    assert json.loads(capsys.readouterr().out)['status']=='not_due'
    runner.assert_not_called()


def test_live_requires_environment_opt_in_and_current_calendar(lifecycle):
    with pytest.raises(ValueError,match='NEWSLETTER_DRY_RUN'):
        monthly.run_month(lifecycle.month,live=True,adapter=Mock())
    lifecycle.monkeypatch.setenv('NEWSLETTER_DRY_RUN','false')
    with pytest.raises(ValueError,match='current America/New_York month'):
        monthly.run_month('2000-01',live=True,adapter=Mock())


def test_preview_and_help_are_offline_without_valid_database_config(tmp_path):
    env={**os.environ,'DATABASE_URL':'invalid-database-never-connect','PYTHONDONTWRITEBYTECODE':'1'}
    root=Path(__file__).resolve().parents[2]
    command=[sys.executable,'-B','-m','backend.app.newsletter.monthly']
    assert subprocess.run(command+['--help'],cwd=root,env=env,capture_output=True).returncode==0
    result=subprocess.run(command+['--preview','--month','2026-10','--output-dir',str(tmp_path)],cwd=root,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['emails_sent']==0
    assert 'EXAMPLE EVENT' in (tmp_path/'next-chapter-2026-10.html').read_text(encoding='utf-8')
    assert '?section=profile' in (tmp_path/'next-chapter-2026-10.txt').read_text(encoding='utf-8')


def test_scheduled_run_is_paused_when_the_admin_switched_the_newsletter_off(monkeypatch, capsys):
    from backend.app.newsletter import monthly
    monkeypatch.setenv("NEWSLETTER_SCHEDULING_ENABLED", "true")
    monkeypatch.setattr(monthly, "monthly_enabled", lambda: False)
    monkeypatch.setattr(monthly, "run_month", lambda *a, **k: pytest.fail("a paused newsletter must not run"))
    assert monthly.main(["--scheduled", "--month", monthly.current_month()]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "paused_by_admin"
