from mcp.server.fastmcp import FastMCP
import json
import os
import logging
import time

# ---------------------------------------------------------
# Configuration via environment variables (with sensible defaults)
# ---------------------------------------------------------
HOST = os.getenv("MCP_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_PORT", "8000"))
RATE_LIMIT = int(os.getenv("MCP_RATE_LIMIT", "60"))  # max requests per minute
# Transport used to actually serve the tools over the network.
# FastMCP's run() defaults to "stdio" (which ignores host/port entirely),
# so this must be set explicitly for host/port to take effect.
TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")  # "streamable-http" | "sse" | "stdio"

# ---------------------------------------------------------
# Logging setup
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("StudyPlannerMCP")

# ---------------------------------------------------------
# Simple in-memory token-bucket rate limiter
# ---------------------------------------------------------
class RateLimiter:
    """Allows up to `limit` calls per minute, refilling one token/second."""
    def __init__(self, limit: int):
        self.limit = limit
        self.tokens = limit
        self.last_refill = int(time.time())

    def allow(self) -> bool:
        now = int(time.time())
        if now != self.last_refill:
            self.tokens = min(self.limit, self.tokens + (now - self.last_refill))
            self.last_refill = now
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False

rate_limiter = RateLimiter(RATE_LIMIT)

# ---------------------------------------------------------
# Create the FastMCP server
# ---------------------------------------------------------
mcp = FastMCP(
    name="StudyPlannerMCP",
    host=HOST,
    port=PORT,
    instructions=(
        "Study Planner MCP Server – exposes tools for calendar events, "
        "syllabus data, task management, and weather lookups. "
        "Use these tools to help students plan their study schedules."
    ),
    log_level="INFO",
)

# ---------------------------------------------------------
# Tool definitions (exposed via MCP protocol)
# ---------------------------------------------------------
@mcp.tool(name="get_calendar_events", description="Retrieve Google Calendar events for a date range (mock data for Phase 2).")
def get_calendar_events(start_date: str, end_date: str) -> str:
    """Return mock calendar events as JSON.
    Replace with real Google Calendar API calls for production.

    Args:
        start_date: ISO date string (e.g. '2026-10-01')
        end_date: ISO date string (e.g. '2026-10-31')
    """
    if not rate_limiter.allow():
        return json.dumps({"error": "Rate limit exceeded. Try again shortly."})
    log.info(f"get_calendar_events called: {start_date} -> {end_date}")
    events = [
        {"summary": "Dentist Appointment", "date": "2026-10-10", "hours": 2},
        {"summary": "Team Meeting", "date": "2026-10-12", "hours": 1},
    ]
    return json.dumps(events)


@mcp.tool(name="get_syllabus_data", description="Retrieve syllabus topics, estimated study hours, and exam dates.")
def get_syllabus_data() -> str:
    """Return mock syllabus data as JSON."""
    if not rate_limiter.allow():
        return json.dumps({"error": "Rate limit exceeded. Try again shortly."})
    log.info("get_syllabus_data called")
    data = [
        {"topic": "React Basics", "hours_needed": 5, "exam_date": "2026-10-15"},
    ]
    return json.dumps(data)


@mcp.tool(name="add_task", description="Create a new study task with a title and due date.")
def add_task(title: str, due: str) -> str:
    """Add a study task (placeholder implementation).

    Args:
        title: Task title (e.g. 'Review Chapter 5')
        due: Due date in ISO format (e.g. '2026-11-01')
    """
    if not rate_limiter.allow():
        return json.dumps({"error": "Rate limit exceeded. Try again shortly."})
    log.info(f"add_task called: title={title}, due={due}")
    return json.dumps({"success": True, "title": title, "due": due})


@mcp.tool(name="get_weather", description="Get weather forecast for a city (placeholder data).")
def get_weather(city: str) -> str:
    """Return dummy weather data for the given city.

    Args:
        city: City name (e.g. 'Hyderabad')
    """
    if not rate_limiter.allow():
        return json.dumps({"error": "Rate limit exceeded. Try again shortly."})
    log.info(f"get_weather called: city={city}")
    weather = {"city": city, "forecast": "sunny", "temp_c": 25}
    return json.dumps(weather)


@mcp.tool(name="health_check", description="Returns server health status.")
def health_check() -> str:
    """Check if the MCP server is running and healthy."""
    return json.dumps({"status": "ok", "server": "StudyPlannerMCP", "tools": 5})


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------
if __name__ == "__main__":
    if TRANSPORT == "stdio":
        log.info("Starting StudyPlannerMCP server over stdio (host/port unused)")
    else:
        log.info(f"Starting StudyPlannerMCP server on {HOST}:{PORT} via {TRANSPORT}")
    mcp.run(transport=TRANSPORT)