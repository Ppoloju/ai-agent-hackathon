# AI Study Buddy

A unified AI assistant that helps students analyze their syllabi, build study schedules, and generate practice quizzes dynamically through a simple conversational interface.

## Problem Statement
Students often struggle to manually extract critical deadlines and topics from dense syllabi, and have an even harder time sticking to rigid schedules. The **AI Study Buddy** solves this by letting students upload their syllabus and chat directly with an AI orchestrator. The AI can instantly analyze dates, generate adaptive study plans, and test your knowledge with custom quiz questions.

## Architecture

```
[ User ] --(Uploads PDF/TXT & Prompts)--> [ Streamlit Chat Interface ]
                                                 |
                                                 v
                                   [ StudyBuddyAgent (Gemini 1.5) ] 
                                                 |
                                                 v
                               (Analyzes Syllabus, Plans, Quizzes)
```

- **Streamlit Interface (`ui/app.py`)**: A modern, full-screen chat interface. It extracts text from uploaded files in the background and injects it as context into the conversation.
- **StudyBuddyAgent (`agent/agents.py`)**: A powerful, unified Gemini AI agent designed to respond dynamically to user requests based on the provided file context.

## Setup Instructions
1. **Clone the repo**
2. **Set up Environment Variables**:
   Copy `.env.example` to `.env` and fill in your Gemini API Key.
   ```
   GEMINI_API_KEY=your_key_here
   ```
3. **Install Dependencies**:
   ```bash
   pip install streamlit python-dotenv PyPDF2 google-generativeai
   ```
4. **Run the Application**:
   ```bash
   streamlit run ui/app.py
   ```

## Security Overview
- API Keys are securely managed via `.env`.
- Secrets are explicitly ignored via `.gitignore`. No hardcoded keys exist in the source code.
