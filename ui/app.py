import streamlit as st
import os
import sys
import PyPDF2
import json
from io import BytesIO
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

load_dotenv()

# Add parent directory to path so we can import from agent
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
from agent.agents import study_buddy_agent

HISTORY_PATH = os.path.join(PROJECT_ROOT, "chat_history.json")

def load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading chat history: {e}")
    return []

def save_history():
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(st.session_state.chat_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving chat history: {e}")

st.set_page_config(page_title="AI Study Planner",page_icon="LOGO.png",layout="wide")

VERIFIER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".oauth_verifier.txt")

# Check for OAuth callback code in query parameters
if "code" in st.query_params:
    auth_code = st.query_params["code"]
    st.query_params.clear()
    
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    if client_id and client_secret:
        if os.path.exists(VERIFIER_PATH):
            try:
                with open(VERIFIER_PATH, "r") as f:
                    code_verifier = f.read().strip()
                os.remove(VERIFIER_PATH)
            except:
                code_verifier = None
                
            if code_verifier:
                try:
                    client_config = {
                        "web": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                        }
                    }
                    flow = Flow.from_client_config(
                        client_config,
                        scopes=['https://www.googleapis.com/auth/calendar'],
                        redirect_uri='http://localhost:8501/',
                        code_verifier=code_verifier
                    )
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    
                    # Save credentials to token.json
                    from agent.calendar_integration import TOKEN_PATH
                    with open(TOKEN_PATH, 'w') as token_file:
                        token_file.write(creds.to_json())
                        
                    st.success("Successfully connected to Google Calendar! Rerunning...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error authenticating with Google: {e}")
            else:
                st.error("Authentication verifier failed to load. Please try again.")
        else:
            st.error("Authentication session state missing. Please try connecting your calendar again.")
    else:
        st.error("Client ID/Secret missing from environment when handling callback.")

st.title("AI Study Planner")
st.markdown("Upload your syllabus in the sidebar and chat with me to analyze it, build a study plan, or generate practice questions!")

# Initialize session state for chat and context
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = load_history()
if 'file_context' not in st.session_state:
    st.session_state.file_context = ""

# --- SIDEBAR: Upload Context & Google Calendar ---
with st.sidebar:
    st.image("LOGO.png", width=50)
    st.header("Upload Context")
    uploaded_files = st.file_uploader("Upload Syllabi (PDF/TXT)", type=["pdf", "txt"], accept_multiple_files=True)

    
    if uploaded_files:
        if st.button("Process Files", use_container_width=True, type="primary"):
            with st.spinner("Extracting text..."):
                combined_text = ""
                success_count = 0
                for uploaded_file in uploaded_files:
                    text = ""
                    if uploaded_file.name.endswith('.txt'):
                        text = uploaded_file.getvalue().decode("utf-8")
                    elif uploaded_file.name.endswith('.pdf'):
                        pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.getvalue()))
                        for page in pdf_reader.pages:
                            text += page.extract_text() + "\n"
                    
                    if text.strip():
                        combined_text += f"--- CONTENT FROM FILE: {uploaded_file.name} ---\n{text}\n\n"
                        success_count += 1
                
                if combined_text.strip():
                    st.session_state.file_context = combined_text
                    st.success(f"Successfully processed {success_count} file(s)!")
                else:
                    st.error("Could not extract text from the files.")

    st.markdown("---")
    st.header("📅 Google Calendar")
    
    # Check calendar connection status
    from agent.calendar_integration import TOKEN_PATH, load_calendar_credentials
    creds = load_calendar_credentials()
    
    if creds:
        st.success("Connected to Google Calendar")
        if st.button("Disconnect Calendar", use_container_width=True):
            if os.path.exists(TOKEN_PATH):
                os.remove(TOKEN_PATH)
            st.success("Disconnected! Rerunning...")
            st.rerun()
    else:
        st.info("Google Calendar is not connected.")
        
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            st.warning("Client ID/Secret not found in .env file.")
            with st.expander("Setup Guide"):
                st.markdown(
                    "1. Go to the [Google Cloud Console](https://console.cloud.google.com/).\n"
                    "2. Create a project and search for **Google Calendar API** to enable it.\n"
                    "3. Go to the **OAuth consent screen** and select **External**.\n"
                    "   - Set the App name and user support email.\n"
                    "   - Add the scope: `.../auth/calendar`.\n"
                    "   - Add your own email as a Test User.\n"
                    "4. Go to **Credentials** -> **Create Credentials** -> **OAuth client ID**.\n"
                    "   - Select Application type: **Web application**.\n"
                    "   - Add Authorized Redirect URI: `http://localhost:8501/`.\n"
                    "5. Copy the Client ID and Client Secret into your `.env` file:\n"
                    "```env\n"
                    "GOOGLE_CLIENT_ID=your_id\n"
                    "GOOGLE_CLIENT_SECRET=your_secret\n"
                    "```\n"
                    "6. Restart the server or reload this page."
                )
        else:
            try:
                import secrets
                client_config = {
                    "web": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
                
                # Check if we already have the verifier in session state, otherwise write it
                if "oauth_verifier" not in st.session_state:
                    st.session_state.oauth_verifier = secrets.token_urlsafe(64)
                    with open(VERIFIER_PATH, "w") as f:
                        f.write(st.session_state.oauth_verifier)
                
                flow = Flow.from_client_config(
                    client_config,
                    scopes=['https://www.googleapis.com/auth/calendar'],
                    redirect_uri='http://localhost:8501/',
                    code_verifier=st.session_state.oauth_verifier
                )
                auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
                
                st.markdown("""<style>.stLinkButton > a {background-color: #E85D5A !important;color: white !important;border: none !important;width: 100%;text-align: center;border-radius: 0.5rem;padding: 0.5rem 1rem;font-weight: 500;}.stLinkButton > a:hover {background-color: #d94f4c !important;color: white !important;}</style>""", unsafe_allow_html=True)

                st.link_button("🔗 Connect Google Calendar", auth_url,use_container_width=True)
                st.caption("You will be redirected back here after authorizing.")
            except Exception as e:
                st.error(f"Error preparing authorization: {e}")
                
    st.markdown("---")
    st.header("⚙️ Actions")
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        if os.path.exists(HISTORY_PATH):
            try:
                os.remove(HISTORY_PATH)
            except Exception as e:
                print(f"Error deleting chat history: {e}")
        st.success("Chat history cleared!")
        st.rerun()

# --- MAIN CHAT INTERFACE ---
chat_container = st.container(height=500)

with chat_container:
    # Always display initial greeting if empty
    if not st.session_state.chat_history:
        st.chat_message("assistant").markdown("Hello! I am your AI Study Buddy. Upload a syllabus on the left, then ask me to analyze it, create a study plan, or generate practice questions!")
        
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

if prompt := st.chat_input("Ask me to create a plan, analyze the syllabus, or generate questions..."):
    # Append user message to UI immediately
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    save_history()
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)
    
    # Construct prompt with context, including the current date/time
    import datetime
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    day_str = now.strftime("%A")
    context_block = f"Current Local Date: {date_str}\nCurrent Local Time: {time_str}\nCurrent Day of the Week: {day_str}\n\n"
    if st.session_state.file_context:
        context_block += f"Uploaded Syllabus Content:\n{st.session_state.file_context}\n\n"
    else:
        context_block += "No syllabus uploaded yet.\n\n"
        
    full_prompt = context_block + f"User Request: {prompt}"
    
    # Fetch AI Response
    with chat_container:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = study_buddy_agent.run(full_prompt)
                st.markdown(response)
                
    # Save AI response to history
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    save_history()
