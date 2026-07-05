import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(PROJECT_ROOT, 'token.json')

def load_calendar_credentials():
    """Loads Google Calendar OAuth credentials from token.json and refreshes them if expired."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            print(f"Error loading credentials from {TOKEN_PATH}: {e}")
            creds = None
            
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'w') as token_file:
                token_file.write(creds.to_json())
        except Exception as e:
            print(f"Error refreshing credentials: {e}")
            creds = None
            
    return creds

def get_calendar_events(start_date: str, end_date: str) -> str:
    """
    Retrieves Google Calendar events between start_date and end_date.
    Use this to understand the user's current schedule, busy slots, and commitments
    to build an appropriate study plan.
    
    Args:
        start_date: ISO format date or datetime string (e.g. '2026-07-04T00:00:00Z' or '2026-07-04').
        end_date: ISO format date or datetime string (e.g. '2026-07-11T23:59:59Z' or '2026-07-11').
        
    Returns:
        A JSON string containing a list of events with summary, start time, end time, and description.
    """
    creds = load_calendar_credentials()
    if not creds:
        return json.dumps({
            "error": "Google Calendar is not connected. The user must authenticate first via the sidebar in the UI."
        })
        
    try:
        # Format dates properly for Google Calendar API
        start_iso = start_date if 'T' in start_date else f"{start_date}T00:00:00Z"
        end_iso = end_date if 'T' in end_date else f"{end_date}T23:59:59Z"
        
        # Build the service
        service = build('calendar', 'v3', credentials=creds)
        
        # Call the API
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_iso,
            timeMax=end_iso,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        formatted_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            formatted_events.append({
                "summary": event.get("summary", "No Title"),
                "start": start,
                "end": end,
                "description": event.get("description", "")
            })
            
        return json.dumps(formatted_events)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to retrieve calendar events: {str(e)}"
        })

def create_calendar_event(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """
    Creates a new calendar event in the user's primary Google Calendar.
    Use this to add study slots, deadlines, exams, or study plans to their schedule.
    
    Args:
        summary: The title/name of the study session or event.
        start_time: ISO 8601 format datetime string (e.g. '2026-07-06T10:00:00Z' or '2026-07-06T14:30:00+05:30').
        end_time: ISO 8601 format datetime string (e.g. '2026-07-06T11:00:00Z' or '2026-07-06T15:30:00+05:30').
        description: A brief description or syllabus topics to cover during this study session.
        
    Returns:
        A JSON string confirming success and the created event ID/link, or an error message.
    """
    creds = load_calendar_credentials()
    if not creds:
        return json.dumps({
            "error": "Google Calendar is not connected. The user must authenticate first via the sidebar in the UI."
        })
        
    try:
        service = build('calendar', 'v3', credentials=creds)
        event = {
            'summary': summary,
            'description': description,
        }
        
        # Handle timezone offsets if present, otherwise default to UTC
        if '+' in start_time or '-' in start_time[10:]:
            event['start'] = {'dateTime': start_time}
            event['end'] = {'dateTime': end_time}
        else:
            event['start'] = {'dateTime': start_time, 'timeZone': 'UTC'}
            event['end'] = {'dateTime': end_time, 'timeZone': 'UTC'}
            
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return json.dumps({
            "status": "success",
            "message": f"Event '{summary}' successfully created.",
            "event_id": created_event.get("id"),
            "htmlLink": created_event.get("htmlLink")
        })
    except Exception as e:
        return json.dumps({
            "error": f"Failed to create calendar event: {str(e)}"
        })
