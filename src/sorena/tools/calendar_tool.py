"""Google Calendar read/write -- lets an agent see what's on the calendar
and add new events/tasks to it. See sorena.calendar_auth for the OAuth flow.
"""

import datetime

from sorena.calendar_auth import get_calendar_service

LIST_EVENTS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_calendar_events",
        "description": (
            "List upcoming Google Calendar events, e.g. to answer 'what's on my plan today'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max events to return. Default 10.",
                },
                "time_min": {
                    "type": "string",
                    "description": "RFC3339 lower bound, e.g. today's start. Defaults to now.",
                },
                "time_max": {
                    "type": "string",
                    "description": "RFC3339 upper bound, e.g. today's end. Omit for none.",
                },
            },
        },
    },
}


def list_events(
    max_results: int = 10, time_min: str | None = None, time_max: str | None = None
) -> str:
    service = get_calendar_service()
    params = {
        "calendarId": "primary",
        "timeMin": time_min or datetime.datetime.now(datetime.UTC).isoformat(),
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_max:
        params["timeMax"] = time_max

    events = service.events().list(**params).execute().get("items", [])
    if not events:
        return "No events found in that range."

    lines = []
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date"))
        lines.append(f"{start}: {e.get('summary', '(no title)')}")
    return "\n".join(lines)


CREATE_EVENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_calendar_event",
        "description": "Create a new Google Calendar event or task.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title."},
                "start": {
                    "type": "string",
                    "description": "RFC3339 start datetime, e.g. 2026-07-20T09:00:00+02:00.",
                },
                "end": {"type": "string", "description": "RFC3339 end datetime."},
                "description": {"type": "string", "description": "Optional event details."},
            },
            "required": ["summary", "start", "end"],
        },
    },
}


def create_event(summary: str, start: str, end: str, description: str = "") -> str:
    service = get_calendar_service()
    body = {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}}
    if description:
        body["description"] = description

    created = service.events().insert(calendarId="primary", body=body).execute()
    return f"Created '{summary}' at {start} (event id {created['id']})."
