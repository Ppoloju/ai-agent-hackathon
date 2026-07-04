# Project File Structure

Here is a breakdown of every file currently in your project and exactly what it does!

### ⚙️ Core Application
* **`ui/app.py`**
  * **What it does:** This is the "Frontend" of your application. It uses Streamlit to build the web interface. It handles rendering the sidebar, accepting file uploads (PDF and TXT), extracting the text from those files, and displaying the main chat window where you talk to the AI.
  
* **`agent/agents.py`**
  * **What it does:** This is where the AI's "brain" is defined. It contains the `StudyBuddyAgent` configuration. This file tells the AI exactly what its job is (to analyze syllabi, create study plans, and generate quizzes) and gives it a friendly, encouraging personality.
  
* **`google_adk.py`**
  * **What it does:** This is the underlying engine that connects your code to the real Gemini AI. It acts as a wrapper around the official `google.generativeai` package, taking the prompt from your app, sending it to Google's servers securely using your API key, and returning the response to Streamlit.

### 🔒 Security & Configuration
* **`.env`**
  * **What it does:** This is a hidden file on your local computer that safely stores your top-secret `GEMINI_API_KEY`. It should **never** be pushed to GitHub.
  
* **`.env.example`**
  * **What it does:** A safe, empty template version of your `.env` file. You commit this to GitHub so that when someone else clones your repo, they know they need to create their own `.env` file and insert their own API key.
  
* **`.gitignore`**
  * **What it does:** This tells Git (and GitHub) which files to completely ignore. It ensures your `.env` file and messy Python cache files aren't accidentally uploaded to the internet.

### 📚 Documentation & Extras
* **`README.md`**
  * **What it does:** The front page of your project! When judges or other developers look at your GitHub repository, this is the first thing they read to understand what the project is, the problem it solves, and how to install it.
  
* **`mcp_server/server.py`**
  * **What it does:** This was built during Phase 2 to satisfy the Model Context Protocol (MCP) requirement of the hackathon stack. Currently, the app works without it because we wired Gemini directly, but it serves as a mock server for external data APIs.
