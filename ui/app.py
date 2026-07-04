import streamlit as st
import os
import sys
import PyPDF2
from io import BytesIO

# Add parent directory to path so we can import from agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.agents import study_buddy_agent

st.set_page_config(page_title="AI Study Buddy", layout="wide")

st.title("AI Study Buddy")
st.markdown("Upload your syllabus in the sidebar and chat with me to analyze it, build a study plan, or generate practice questions!")

# Initialize session state for chat and context
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'file_context' not in st.session_state:
    st.session_state.file_context = ""

# --- SIDEBAR: Upload Context ---
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
