import streamlit as st
import os
import sys
import PyPDF2
import json
from io import BytesIO
import re

from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load .env explicitly
load_dotenv(dotenv_path=ENV_PATH, override=True)

# Add parent directory to path so we can import from agent
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)
from agent.agents import study_buddy_agent

def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Transcribe audio bytes to text using the Gemini API."""
    try:
        from google import genai
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return "__TRANSCRIPTION_ERROR__"
        client = genai.Client(api_key=api_key)
        # Use the correct model for transcription
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Please transcribe the following audio. Return only the transcribed text, nothing else.", genai.types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)]
        )
        text = response.text.strip() if response.text else ""
        return text if text else "__TRANSCRIPTION_ERROR__"
    except Exception as e:
        print(f"Transcription error: {e}")
        if "quota" in str(e).lower() or "rate" in str(e).lower():
            return "__RATE_LIMIT__"
        return f"__ERROR__: {str(e)}"

def clean_markdown_for_tts(text: str) -> str:
    # Remove markdown headers
    text = re.sub(r'#+\s+', '', text)
    # Remove bold/italic markers
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'_+', '', text)
    # Remove link brackets but keep text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove bullet points
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    # Remove numbered list prefixes
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove backticks and code blocks
    text = re.sub(r'```[\s\S]*?```', '[Code block omitted]', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return text.strip()

FIREBASE_CREDS_PATH = os.path.join(PROJECT_ROOT, "firebase-credentials.json")

# Initialize Firebase only once
try:
    if not firebase_admin._apps:
        if os.path.exists(FIREBASE_CREDS_PATH):
            try:
                cred = credentials.Certificate(FIREBASE_CREDS_PATH)
                firebase_admin.initialize_app(cred)
                print("Firebase initialized successfully")
            except Exception as e:
                print(f"Firebase init error: {e}")
except Exception as e:
    print(f"Firebase initialization check error: {e}")

def get_db():
    try:
        if firebase_admin._apps:
            return firestore.client()
    except Exception as e:
        print(f"Firestore client error: {e}")
    return None

def load_all_sessions():
    db = get_db()
    if db:
        try:
            doc = db.collection("users").document("default_user").get()
            if doc.exists:
                data = doc.to_dict()
                if "sessions" in data:
                    return data["sessions"]
                elif "chats" in data: # Migration
                    return {"default": {"title": "Old Chat", "messages": data["chats"]}}
        except Exception as e:
            print(f"Error loading from Firestore: {e}")
    return {}

def save_all_sessions(sessions):
    sessions_for_db = {}
    
    for sid, sdata in sessions.items():
        msgs_for_db = []
        for msg in sdata.get("messages", []):
            msgs_for_db.append(msg.copy()) # Keep bytes for Firestore if any
            
        sessions_for_db[sid] = {"title": sdata.get("title", "Chat"), "messages": msgs_for_db}
            
    db = get_db()
    if db:
        try:
            db.collection("users").document("default_user").set({"sessions": sessions_for_db}, merge=True)
        except Exception as e:
            print(f"Error saving to Firestore: {e}")
            st.error(f"Failed to save to Firebase: {e}")

st.set_page_config(page_title="AI Study Planner", page_icon="LOGO.png", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR CHATGPT STYLE ---
st.markdown("""
<style>
/* Main container max-width for chat-like feel */
.main .block-container {
    max-width: 800px;
    padding-top: 2rem;
    padding-bottom: 5rem;
}
/* User and Assistant avatars */
[data-testid="stChatMessageAvatarUser"] {
    background-color: #5436DA !important;
}
[data-testid="stChatMessageAvatarAssistant"] {
    background-color: #10a37f !important;
}

/* Make chat input floating at the bottom */
[data-testid="stChatInput"] {
    border-radius: 20px;
}
/* Icon button styling */
.icon-btn {
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 1.4rem;
    padding: 0;
}
.icon-btn:hover { opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

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

import uuid

# Initialize session state for chat and context
if 'all_sessions' not in st.session_state:
    st.session_state.all_sessions = load_all_sessions()
if 'current_session_id' not in st.session_state:
    if st.session_state.all_sessions:
        st.session_state.current_session_id = list(st.session_state.all_sessions.keys())[-1]
    else:
        new_id = str(uuid.uuid4())
        st.session_state.current_session_id = new_id
        st.session_state.all_sessions[new_id] = {"title": "New Chat", "messages": []}

if 'file_context' not in st.session_state:
    st.session_state.file_context = ""

def get_current_messages():
    return st.session_state.all_sessions[st.session_state.current_session_id]["messages"]

def append_to_current_session(msg):
    msgs = st.session_state.all_sessions[st.session_state.current_session_id]["messages"]
    if len(msgs) == 0 and msg["role"] == "user":
        title = msg["content"][:30] + ("..." if len(msg["content"]) > 30 else "")
        st.session_state.all_sessions[st.session_state.current_session_id]["title"] = title
    msgs.append(msg)
    save_all_sessions(st.session_state.all_sessions)

# --- SIDEBAR: Upload Context & Google Calendar ---
with st.sidebar:
    col_img, col_title = st.columns([1, 3])
    with col_img:
        st.image("LOGO.png", width=55)
    with col_title:
        st.markdown(
            "<h2 style='margin:0; padding-top:8px; line-height:1.2;'>AI Study Planner</h2>",
            unsafe_allow_html=True
        )
    st.markdown("---")
    st.header("Upload Context")
    uploaded_files = st.file_uploader("Upload Syllabus (PDF/TXT)", type=["pdf", "txt"], accept_multiple_files=True)

    
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
                    st.session_state.auto_trigger = True
                    st.rerun()
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
                
    # Merge Chats and Actions in a single section for a cleaner UI
    st.markdown("---")
    st.header("💬 Chats & Actions")
    
    # New Chat button
    if st.button("➕ New Chat", use_container_width=True):
        new_id = str(uuid.uuid4())
        st.session_state.all_sessions[new_id] = {"title": "New Chat", "messages": []}
        st.session_state.current_session_id = new_id
        save_all_sessions(st.session_state.all_sessions)
        st.rerun()

    # List existing chats with normal delete button
    for sid, sdata in list(st.session_state.all_sessions.items()):
        col_main, col_del, col_rename = st.columns([0.8, 0.1, 0.1])
        with col_main:
            btn_type = "primary" if sid == st.session_state.current_session_id else "secondary"
            if st.button(sdata.get("title", "Chat"), key=f"load_{sid}", use_container_width=True, type=btn_type):
                st.session_state.current_session_id = sid
                st.rerun()
        with col_del:
            # Delete button with trash‑can icon (consistent UI)
            if st.button("🗑️", key=f"del_{sid}", help="Delete this chat"):
                del st.session_state.all_sessions[sid]
                # If the deleted chat was active, switch to another or create new
                if sid == st.session_state.current_session_id:
                    if st.session_state.all_sessions:
                        st.session_state.current_session_id = list(st.session_state.all_sessions.keys())[-1]
                    else:
                        new_id = str(uuid.uuid4())
                        st.session_state.all_sessions[new_id] = {"title": "New Chat", "messages": []}
                        st.session_state.current_session_id = new_id
                save_all_sessions(st.session_state.all_sessions)
                st.rerun()
        with col_rename:
            if st.button("✏️", key=f"rename_{sid}", help="Rename this chat"):
                st.session_state[f"show_rename_{sid}"] = True
        
        # Show rename input if rename button was clicked
        if st.session_state.get(f"show_rename_{sid}"):
            new_title = st.text_input("New name", value=sdata.get("title", "Chat"), key=f"rename_input_{sid}")
            col_save, col_cancel = st.columns([0.5, 0.5])
            with col_save:
                if st.button("Save", key=f"save_rename_{sid}"):
                    if new_title.strip():
                        st.session_state.all_sessions[sid]["title"] = new_title.strip()
                        save_all_sessions(st.session_state.all_sessions)
                    st.session_state[f"show_rename_{sid}"] = False
                    st.rerun()
            with col_cancel:
                if st.button("Cancel", key=f"cancel_rename_{sid}"):
                    st.session_state[f"show_rename_{sid}"] = False
                    st.rerun()

    # Clear all chats button (still normal style)
    if st.button("Clear All Chats", use_container_width=True, help="Delete all chat history"):
        # Clear local session state
        st.session_state.all_sessions = {}
        new_id = str(uuid.uuid4())
        st.session_state.all_sessions[new_id] = {"title": "New Chat", "messages": []}
        st.session_state.current_session_id = new_id
        # Delete Firestore data for the user (if connected)
        db = get_db()
        if db:
            try:
                db.collection("users").document("default_user").delete()
            except Exception as e:
                st.warning(f"Failed to delete Firestore data: {e}")
        # Persist empty sessions locally (and recreate document)
        save_all_sessions(st.session_state.all_sessions)
        st.success("All chat history cleared!")
        st.rerun()

    st.markdown("---")
    st.header("🎙️ Voice Settings")
    tts_enabled = st.checkbox(
        "Enable Voice Responses (TTS)", 
        value=True, 
        help="When enabled, the AI will generate speech for its responses."
    )
    
    pass # End of sidebar

# --- MAIN CHAT INTERFACE ---
chat_container = st.container()

with chat_container:
    current_msgs = get_current_messages()
    if not current_msgs:
        st.chat_message("assistant").markdown("Hello! I am your AI Study Buddy. Upload a syllabus on the left, then ask me to analyze it, create a study plan, or generate practice questions!")
        
    for idx, msg in enumerate(current_msgs):
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                col1, col2, col3 = st.columns([0.15, 0.15, 0.7])
                with col1:
                    if st.button("🔊", key=f"listen_{idx}"):
                        st.session_state[f"play_{idx}"] = True
                with col2:
                    if st.button("📋", key=f"copy_{idx}"):
                        st.session_state[f"copy_{idx}"] = True
                        components.html(
                            f'''
                            <script>
                            navigator.clipboard.writeText(`{msg['content'].replace('`', '\\`').replace('\\', '\\\\').replace('"', '&quot;').replace('\n', '\\n')}`);
                            </script>
                            ''',
                            height=0
                        )
            
            st.markdown(msg["content"])
            
            if st.session_state.get(f"play_{idx}") and msg.get("audio_bytes"):
                st.audio(msg["audio_bytes"], format="audio/mp3", autoplay=True)
                st.session_state[f"play_{idx}"] = False # Reset after playing


# Use CSS to style the audio input to sit nicely on the right side
st.markdown("""
<style>
div[data-testid="stAudioInput"] {
    max-width: 300px;
    margin-left: auto;
    margin-right: 0px;
}
</style>
""", unsafe_allow_html=True)

# Audio input right above chat input
audio_val = st.audio_input("Record Voice", label_visibility="collapsed")
audio_prompt = None
if audio_val:
    if 'last_audio_hash' not in st.session_state or st.session_state.last_audio_hash != hash(audio_val.getvalue()):
        st.session_state.last_audio_hash = hash(audio_val.getvalue())
        with st.spinner("Transcribing audio..."):
            transcribed_text = transcribe_audio(audio_val.getvalue(), audio_val.type)
            if not transcribed_text.startswith("__ERROR__") and transcribed_text not in ["__TRANSCRIPTION_ERROR__", "__RATE_LIMIT__"]:
                audio_prompt = transcribed_text
            else:
                st.error(f"Failed to transcribe audio. Reason: {transcribed_text}")

# Combine chat input and audio prompt
chat_input = st.chat_input("Ask me to create a plan, analyze the syllabus, or generate questions...")

if st.session_state.get("auto_trigger", False):
    final_prompt = "I just uploaded my syllabus. Please extract the key topics, deadlines, and exam dates from it and provide a brief overview."
    st.session_state.auto_trigger = False
else:
    final_prompt = chat_input or audio_prompt

if final_prompt:
    # Clear audio state if user submitted via chat to avoid loop
    if chat_input and 'last_audio_hash' in st.session_state:
        st.session_state.last_audio_hash = None

    # Append user message to UI immediately
    append_to_current_session({"role": "user", "content": final_prompt})
    with chat_container:
        with st.chat_message("user"):
            st.markdown(final_prompt)
    
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
        
    full_prompt = context_block + f"User Request: {final_prompt}"
    
    # Fetch AI Response
    with chat_container:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = study_buddy_agent.run(full_prompt)
                st.markdown(response)
                
                # Generate TTS if enabled
                tts_bytes = None
                if tts_enabled:
                    try:
                        from gtts import gTTS
                        import io
                        clean_text = clean_markdown_for_tts(response)
                        if clean_text:
                            tts = gTTS(text=clean_text, lang='en')
                            fp = io.BytesIO()
                            tts.write_to_fp(fp)
                            fp.seek(0)
                            tts_bytes = fp.read()
                            st.audio(tts_bytes, format="audio/mp3", autoplay=True)
                    except Exception as e:
                        st.error(f"Error generating text-to-speech: {e}")
                        
    # Save AI response to history and rerun
    append_to_current_session({
        "role": "assistant", 
        "content": response,
        "audio_bytes": tts_bytes
    })
    st.rerun()
