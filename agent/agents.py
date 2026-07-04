import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from google_adk import Agent
from dotenv import load_dotenv

load_dotenv()

# --- Unified Study Buddy Agent ---
study_buddy_agent = Agent(
    name="StudyBuddyAgent",
    instructions=(
        "You are an incredibly helpful, friendly, and comprehensive Study Buddy AI. "
        "You handle all of the student's needs. You will be provided with the text of the syllabus they uploaded, "
        "and their specific request. "
        "Your tasks based on their prompt: "
        "- If they ask to analyze the syllabus, extract key topics and exam dates and present them clearly. "
        "- If they ask for a study plan, generate a detailed, manageable schedule based on the syllabus. "
        "- If they ask for practice questions, generate excellent quiz questions based on their topics. "
        "Always be conversational, encouraging, and format your output beautifully in Markdown."
    ),
    model="gemini-1.5-flash"
)
