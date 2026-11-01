"""Email-friendly HTML and equivalent plain text; no provider or transport code."""
from dataclasses import dataclass
from html import escape

from .content import Content, safe_url


@dataclass(frozen=True)
class Newsletter:
    subject: str
    html: str
    text: str
    content: Content


def render(content: Content, *, unsubscribe_url: str | None = None, sender_name="The Knowledge House",
           sender_address="", preview=True) -> Newsletter:
    esc = lambda value: escape(str(value), quote=True)
    if unsubscribe_url is not None and not safe_url(unsubscribe_url):
        raise ValueError("Invalid unsubscribe URL")
    unsubscribe_url = unsubscribe_url or content.app_url + "?section=profile"
    unsubscribe_label = "Unsubscribe" if not preview else "Unsubscribe (preview — opens preferences)"
    delivery_note = "Dry-run / content preview only. No email has been sent." if preview else "You received this digest because you explicitly subscribed to Next Chapter Monthly."
    postal = sender_address or "Sender postal address must be configured before delivery."
    jobs_html, jobs_text = [], []
    for job in content.jobs:
        example = "Example job — not a live listing. " if job.example else ""
        updated = f"Employer updated: {job.updated_on.isoformat()}. " if job.updated_on else ""
        jobs_html.append(f'<li style="margin:0 0 20px"><strong>{esc(job.title)}</strong><br>'
                         f'{esc(job.company)} · {esc(job.location)}<br><span>{esc(example + updated)}</span>'
                         f'<br>{esc(job.why_matched)}<br><a href="{esc(job.apply_url)}">View opportunity</a></li>')
        jobs_text.append(f"- {job.title} | {job.company} | {job.location}\n  {example}{updated}"
                         f"{job.why_matched}\n  {job.apply_url}")
    jobs_empty = "No eligible job listings are available for your profile right now."
    events_html, events_text = [], []
    for event in content.events:
        label = "EXAMPLE EVENT — illustrative only, not a scheduled TKH event. " if event.example else ""
        events_html.append(f'<li style="margin:0 0 20px"><strong>{esc(event.title)}</strong><br>{esc(label)}'
                           f'<br>{event.date.isoformat()} · {esc(event.location)}<br>{esc(event.details)}</li>')
        events_text.append(f"- {event.title}\n  {label}\n  {event.date.isoformat()} | {event.location}\n  {event.details}")
    events_empty = "No upcoming event recommendations are available. Check the application for community updates."
    demo = "SYNTHETIC DEMO PREVIEW — not real alumni outcomes." if content.is_demo else ""
    job_link = "Open your Job Monitor in Next Chapter."
    events_link = "Explore upcoming events in Next Chapter."
    jobs_url = content.app_url + "?section=jobs"
    events_url = content.app_url + "?section=events"
    preferences_url = content.app_url + "?section=profile"
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(content.title)}</title></head>
<body style="margin:0;background:#f5f4f8;color:#292342;font-family:Arial,Helvetica,sans-serif;line-height:1.6">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#fff">
<tr><td style="padding:32px;background:#30245f;color:#fff;border-top:8px solid #f3c931">
<p style="margin:0;color:#f3c931;letter-spacing:2px;font-size:12px">THE KNOWLEDGE HOUSE</p>
<p style="margin:12px 0 4px;font-size:24px;font-weight:bold">Next Chapter Monthly</p>
<h1 style="margin:0;font-size:28px;line-height:1.25">{esc(content.title)}</h1></td></tr>
<tr><td style="padding:28px 32px"><p style="font-weight:bold">{esc(demo)}</p>
<p>Hi {esc(content.first_name)},</p><p>Your career and community, in one place. Here are picks based on your existing profile.</p>
<p style="color:#625b77;font-size:13px">Prepared {content.generated_on.isoformat()}. Availability may change.</p>
<h2 style="font-size:21px">01 · Job Opportunities</h2>
{'<ul style="padding-left:20px">' + ''.join(jobs_html) + '</ul>' if jobs_html else '<p>' + jobs_empty + '</p>'}
<p><a href="{esc(jobs_url)}">{esc(job_link)}</a></p>
<h2 style="font-size:21px">02 · Upcoming Events</h2>
{'<ul style="padding-left:20px">' + ''.join(events_html) + '</ul>' if events_html else '<p>' + events_empty + '</p>'}
<p><a href="{esc(events_url)}">{esc(events_link)}</a></p>
<h2 style="font-size:21px">03 · Cohort Updates and Summary</h2><p>{esc(content.cohort_message)}</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:28px"><tr><td bgcolor="#f3c931" style="border-radius:6px;text-align:center"><a href="{esc(content.app_url)}" style="display:inline-block;border:16px solid #f3c931;border-radius:6px;background:#f3c931;color:#292342;font-size:16px;font-weight:bold;text-decoration:none">Open Next Chapter Dashboard</a></td></tr></table>
<p>Keep your profile up to date to improve your next set of recommendations.</p></td></tr>
<tr><td style="padding:20px 32px;background:#eeecf5;font-size:12px">{esc(sender_name)} · Next Chapter<br>
{esc(postal)}<br>{esc(delivery_note)}<br><a href="{esc(preferences_url)}">Manage newsletter preference</a> · <a href="{esc(unsubscribe_url)}">{esc(unsubscribe_label)}</a></td></tr>
</table></td></tr></table></body></html>'''
    text = "\n\n".join(filter(None, [
        "The Knowledge House | Next Chapter Monthly", content.title, demo,
        f"Hi {content.first_name},", f"Prepared {content.generated_on.isoformat()}. Availability may change.",
        "01 · Job Opportunities", "\n\n".join(jobs_text) or jobs_empty, f"{job_link}\n{jobs_url}",
        "02 · Upcoming Events", "\n\n".join(events_text) or events_empty, f"{events_link}\n{events_url}",
        "03 · Cohort Updates and Summary", content.cohort_message,
        f"Keep your profile up to date. Open Next Chapter Dashboard: {content.app_url}",
        f"{sender_name}\n{postal}\n{delivery_note}\nManage newsletter preference: {preferences_url}\n{unsubscribe_label}: {unsubscribe_url}",
    ]))
    return Newsletter("Next Chapter Monthly — " + content.title, html, text, content)
