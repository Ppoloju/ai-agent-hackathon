import streamlit as st
import os
import sys
import PyPDF2
from io import BytesIO
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

load_dotenv()

# Add parent directory to path so we can import from agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.agents import study_buddy_agent

st.set_page_config(page_title="AI Study Buddy", layout="wide")

# Check for OAuth callback code in query parameters
if "code" in st.query_params:
    auth_code = st.query_params["code"]
    # Clear query params to clean up the URL
    st.query_params.clear()
    
    # Retrieve credentials
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if client_id and client_secret:
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
                scopes=['https://www.googleapis.com/auth/calendar.readonly'],
                redirect_uri='http://localhost:8501/'
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
        st.error("Client ID/Secret missing from environment when handling callback.")

st.title("AI Study Buddy")
st.markdown("Upload your syllabus in the sidebar and chat with me to analyze it, build a study plan, or generate practice questions!")

# Initialize session state for chat and context
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'file_context' not in st.session_state:
    st.session_state.file_context = ""

# --- SIDEBAR: Upload Context & Google Calendar ---
with st.sidebar:
    st.header("Upload Context")
    uploaded_file = st.file_uploader("Upload Syllabus (PDF/TXT)", type=["pdf", "txt"])
    
    if uploaded_file is not None:
        if st.button("Process File", use_container_width=True, type="primary"):
            with st.spinner("Extracting text..."):
                text = ""
                if uploaded_file.name.endswith('.txt'):
                    text = uploaded_file.getvalue().decode("utf-8")
                elif uploaded_file.name.endswith('.pdf'):
                    pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.getvalue()))
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                
                if text.strip():
                    st.session_state.file_context = text
                    st.success("File processed! You can now ask me about it.")
                else:
                    st.error("Could not extract text from the file.")

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
                    "   - Add the scope: `.../auth/calendar.readonly`.\n"
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
            # We have config, generate authorization url
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
                    scopes=['https://www.googleapis.com/auth/calendar.readonly'],
                    redirect_uri='http://localhost:8501/'
                )
                auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
                
                st.markdown(f"[👉 Click here to authorize access]({auth_url})")
                st.caption("You will be redirected back here after authorizing.")
            except Exception as e:
                st.error(f"Error preparing authorization: {e}")

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
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)
    
    # Construct prompt with context
    context_block = f"Uploaded Syllabus Content:\n{st.session_state.file_context}\n\n" if st.session_state.file_context else "No syllabus uploaded yet.\n\n"
    full_prompt = context_block + f"User Request: {prompt}"
    
    # Fetch AI Response
    with chat_container:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = study_buddy_agent.run(full_prompt)
                st.markdown(response)
                
    # Save AI response to history
    st.session_state.chat_history.append({"role": "assistant", "content": response})
