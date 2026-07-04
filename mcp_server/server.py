from mcp.server.fastmcp import FastMCP
import json

# Create a FastMCP server
mcp = FastMCP("StudyPlannerMCP")

@mcp.tool()
def get_calendar_events(start_date: str, end_date: str) -> str:
    """
    Get Google Calendar events for a given date range. 
    (Currently returning dummy data for Phase 2)
    """
    # Mock data to simulate calendar API response
    events = [
        {"summary": "Dentist Appointment", "date": "2026-10-10", "hours": 2},
        {"summary": "Team Meeting", "date": "2026-10-12", "hours": 1}
    ]
    return json.dumps(events)

@mcp.tool()
def get_syllabus_data() -> str:
    """
    Retrieves syllabus data. 
    """
    data = [
        {"topic": "React Basics", "hours_needed": 5, "exam_date": "2026-10-15"},
    ]
    return json.dumps(data)

if __name__ == "__main__":
    # Start the server (listens on stdio by default for MCP)
    print("Starting MCP Server on stdio...")
    mcp.run()
