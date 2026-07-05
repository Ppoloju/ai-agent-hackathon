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
                "id": event.get("id"),
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

def delete_calendar_event(event_id: str) -> str:
    """
    Deletes an event from the user's primary Google Calendar.
    Use this when the user requests to cancel, delete, or remove a study slot, exam, or other scheduled event.
    
    Args:
        event_id: The unique ID of the event to delete.
        
    Returns:
        A JSON string confirming success or an error message.
    """
    creds = load_calendar_credentials()
    if not creds:
        return json.dumps({
            "error": "Google Calendar is not connected. The user must authenticate first via the sidebar in the UI."
        })
        
    try:
        service = build('calendar', 'v3', credentials=creds)
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return json.dumps({
            "status": "success",
            "message": f"Event '{event_id}' successfully deleted."
        })
    except Exception as e:
        return json.dumps({
            "error": f"Failed to delete calendar event: {str(e)}"
        })

def update_calendar_event(event_id: str, summary: str = None, start_time: str = None, end_time: str = None, description: str = None) -> str:
    """
    Updates/modifies details of an existing event in the user's primary Google Calendar.
    Use this to reschedule, rename, or update the description of a study session, exam, or schedule slot.
    
    Args:
        event_id: The unique ID of the event to update.
        summary: Optional new title/name of the event.
        start_time: Optional new ISO 8601 format start datetime string.
        end_time: Optional new ISO 8601 format end datetime string.
        description: Optional new description.
        
    Returns:
        A JSON string confirming success and updated event details, or an error message.
    """
    creds = load_calendar_credentials()
    if not creds:
        return json.dumps({
            "error": "Google Calendar is not connected. The user must authenticate first via the sidebar in the UI."
        })
        
    try:
        service = build('calendar', 'v3', credentials=creds)
        # Fetch existing event details first
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        if summary is not None:
            event['summary'] = summary
        if description is not None:
            event['description'] = description
            
        if start_time is not None:
            if '+' in start_time or '-' in start_time[10:]:
                event['start'] = {'dateTime': start_time}
            else:
                event['start'] = {'dateTime': start_time, 'timeZone': 'UTC'}
                
        if end_time is not None:
            if '+' in end_time or '-' in end_time[10:]:
                event['end'] = {'dateTime': end_time}
            else:
                event['end'] = {'dateTime': end_time, 'timeZone': 'UTC'}
                
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return json.dumps({
            "status": "success",
            "message": f"Event '{event_id}' successfully updated.",
            "htmlLink": updated_event.get("htmlLink")
        })
    except Exception as e:
        return json.dumps({
            "error": f"Failed to update calendar event: {str(e)}"
        })
