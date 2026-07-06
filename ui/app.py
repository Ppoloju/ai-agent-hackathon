import streamlit as st
import os
import sys
import PyPDF2
import json
from io import BytesIO
import hashlib
import re

from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
from pathlib import Path

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
        import google.generativeai as genai
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return "__TRANSCRIPTION_ERROR__"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        audio_part = {"mime_type": mime_type, "data": audio_bytes}
        response = model.generate_content(
            ["Please transcribe the following audio. Return only the transcribed text, nothing else.", audio_part]
        )
        text = response.text.strip() if response.text else ""
        return text if text else "__TRANSCRIPTION_ERROR__"
    except Exception as e:
        print(f"Transcription error: {e}")
        if "quota" in str(e).lower() or "rate" in str(e).lower():
            return "__RATE_LIMIT__"
        return "__TRANSCRIPTION_ERROR__"

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

st.set_page_config(page_title="AI Study Buddy", layout="wide")
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

    st.markdown("---")
    st.header("🎙️ Voice Settings")
    tts_enabled = st.checkbox(
        "Enable Voice Responses (TTS)", 
        value=True, 
        help="When enabled, the AI will generate speech for its responses."
    )

# --- MAIN CHAT INTERFACE ---
chat_container = st.container(height=500)

with chat_container:
    # Always display initial greeting if empty
    if not st.session_state.chat_history:
        st.chat_message("assistant").markdown("Hello! I am your AI Study Buddy. Upload a syllabus on the left, then ask me to analyze it, create a study plan, or generate practice questions!")
        
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("audio_bytes"):
                st.audio(msg["audio_bytes"], format="audio/mp3")


# --- FLOATING MIC BUTTON (Web Speech API) ---
st.markdown("""
<style>
#voice-mic-wrap {
    position: fixed;
    bottom: 20px;
    right: 74px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
}
#voice-mic-btn {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,0.15);
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    font-size: 20px;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(102,126,234,0.45);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    outline: none;
    padding: 0;
}
#voice-mic-btn:hover {
    transform: scale(1.12);
    box-shadow: 0 6px 22px rgba(102,126,234,0.65);
}
#voice-mic-btn.vmic-listening {
    background: linear-gradient(135deg, #f5575c 0%, #c0392b 100%);
    box-shadow: 0 0 0 0 rgba(245,87,92,0.7);
    animation: vmic-pulse 1.2s ease-out infinite;
}
@keyframes vmic-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(245,87,92,0.7); }
    70%  { box-shadow: 0 0 0 13px rgba(245,87,92,0); }
    100% { box-shadow: 0 0 0 0 rgba(245,87,92,0); }
}
#voice-mic-toast {
    background: rgba(30,30,40,0.92);
    color: #fff;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 12px;
    max-width: 180px;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: none;
    box-shadow: 0 2px 8px rgba(0,0,0,0.35);
    backdrop-filter: blur(6px);
}
#voice-mic-toast.vmic-show { display: block; }
</style>

<div id="voice-mic-wrap">
  <button id="voice-mic-btn" title="Click to speak" onclick="vmicToggle()">🎤</button>
  <div id="voice-mic-toast"></div>
</div>

<script>
(function(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, active = false;

  function toast(msg, keep) {
    const el = document.getElementById('voice-mic-toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('vmic-show');
    if (!keep) setTimeout(() => el.classList.remove('vmic-show'), 3000);
  }

  function injectText(text) {
    const selectors = [
      '[data-testid="stChatInputTextArea"]',
      '[data-testid="stChatInput"] textarea',
      'textarea[aria-label]'
    ];
    let input = null;
    for (const s of selectors) { input = document.querySelector(s); if (input) break; }
    if (!input) { toast('❌ Could not find chat input'); return; }
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(input, text);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
  }

  window.vmicToggle = function() {
    if (!SR) { alert('Speech recognition not supported. Use Chrome or Edge.'); return; }
    if (active && rec) { rec.stop(); return; }

    rec = new SR();
    rec.lang = 'en-US';
    rec.continuous = false;
    rec.interimResults = true;

    const btn = document.getElementById('voice-mic-btn');

    rec.onstart = () => {
      active = true;
      btn.classList.add('vmic-listening');
      btn.innerHTML = '&#9209;';
      toast('🔴 Listening...', true);
    };

    rec.onresult = (e) => {
      let interim = '', final = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        (e.results[i].isFinal ? (s => final += s) : (s => interim += s))(e.results[i][0].transcript);
      }
      const txt = final || interim;
      if (txt) {
        toast(txt.length > 35 ? txt.slice(0, 35) + '…' : txt, !final);
        injectText(txt);
      }
    };

    rec.onerror = (e) => {
      active = false; btn.classList.remove('vmic-listening'); btn.innerHTML = '🎤';
      toast('❌ ' + e.error);
    };

    rec.onend = () => {
      active = false; btn.classList.remove('vmic-listening'); btn.innerHTML = '🎤';
      setTimeout(() => document.getElementById('voice-mic-toast').classList.remove('vmic-show'), 2500);
    };

    rec.start();
  };
})();
</script>
""", unsafe_allow_html=True)


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
                            st.audio(tts_bytes, format="audio/mp3")
                    except Exception as e:
                        st.error(f"Error generating text-to-speech: {e}")
                        
    # Save AI response to history
    st.session_state.chat_history.append({
        "role": "assistant", 
        "content": response,
        "audio_bytes": tts_bytes
    })
    st.rerun()
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    save_history()
