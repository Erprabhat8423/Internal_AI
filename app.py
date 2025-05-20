import streamlit as st
import requests
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Page config
PROJECT_NAME = "Scaigent"
API_BASE_URL = "http://localhost:8000"
st.set_page_config(page_title=f"🤖 {PROJECT_NAME}", layout="wide")
st.title(f"🤖 {PROJECT_NAME}")

# Utility to clean thinker sections
def clean_thinker_section(raw: str) -> str:
    return re.sub(r"(\*\*)?<think>.*?</think>(\*\*)?", "", raw, flags=re.DOTALL).strip()

# Initialize session state
if "history" not in st.session_state:
    st.session_state.history = []

# Create two tabs: Chat and Document Management
tab1, tab2 = st.tabs(["💬 Ask a Question", "📤 Upload & View Documents"])

# —— Tab 1: WhatsApp-style Chat UI ——
with tab1:
    # Inject clean styles
    st.markdown("""
    <style>
    .stMainBlockContainer { padding-top: 0px; padding-bottom: 0px; }
    .chat-box {
        background: #f8f9fa;
        padding: 12px;
        border-radius: 12px;
        max-height: 60vh;
        overflow-y: auto;
        margin-bottom: 12px;
        display: flex;
        flex-direction: column;
    }
    .chat-msg {
        padding: 10px 16px;
        margin: 4px 0;
        border-radius: 16px;
        max-width: 75%;
        word-wrap: break-word;
    }
    .user-msg {
        background-color: #ffffff;
        align-self: flex-end;
        border: 1px solid #ddd;
    }
    .bot-msg {
        background-color: #dcf8c6;
        align-self: flex-start;
        border: 1px solid #c8e6c9;
    }
    .dot-loader {
        display: inline-block;
        width: 32px;
        height: 8px;
    }
    .dot-loader::after {
        content: '';
        display: inline-block;
        width: 8px;
        height: 8px;
        margin-left: 2px;
        background-color: #555;
        border-radius: 50%;
        animation: blink 1.4s infinite both;
    }
    @keyframes blink {
        0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
        40% { transform: scale(1); opacity: 1; }
    }
    .chat-box {
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-height: 60vh;
        overflow-y: auto;
        margin-bottom: 12px;
    }

    .chat-row {
        display: flex;
        width: 100%;
    }

    .user-row {
        justify-content: flex-end;
    }

    .bot-row {
        justify-content: flex-start;
    }

    .chat-msg {
        padding: 10px 16px;
        border-radius: 16px;
        max-width: 70%;
        word-wrap: break-word;
        font-size: 15px;
    }

    .user-msg {
        background-color: #fff;
        border: 1px solid #ddd;
        color: #000;
    }

    .bot-msg {
        background-color: #dcf8c6;
        border: 1px solid #c8e6c9;
        color: #000;
    }

    /* Loader animation */
    .dot-loader {
        display: inline-block;
        width: 24px;
        height: 8px;
    }
    .dot-loader::after {
        content: '';
        display: inline-block;
        width: 6px;
        height: 6px;
        margin-left: 2px;
        background-color: #555;
        border-radius: 50%;
        animation: blink 1.4s infinite both;
    }
    @keyframes blink {
        0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
        40% { transform: scale(1); opacity: 1; }
    }
    </style>
    """, unsafe_allow_html=True)


    # Chat container
    chat_box = st.container()
    with chat_box:
        st.markdown('<div class="chat-box">', unsafe_allow_html=True)
        if not st.session_state.get("history"):
            st.markdown("<span style='color:#888'>Start the conversation...</span>", unsafe_allow_html=True)
        else:
            for turn in st.session_state.history:
                # User message (right-aligned)
                st.markdown(f"""
                <div class='chat-row user-row'>
                    <div class='chat-msg user-msg'><strong>You:</strong> {turn['q']}</div>
                </div>
                """, unsafe_allow_html=True)

                # Bot message with loader or answer
                if turn["a"] == "...":
                    st.markdown("""
                    <div class='chat-row bot-row'>
                        <div class='chat-msg bot-msg'>
                            <strong>Agent:</strong> <span class='dot-loader'></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class='chat-row bot-row'>
                        <div class='chat-msg bot-msg'><strong>Agent:</strong> {turn['a']}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # Input row
    col1, col2 = st.columns([6, 1])
    with col1:
        question = st.text_input("Type a message:", key="input_text", label_visibility="collapsed")
    with col2:
        send = st.button("Send", use_container_width=True)

    # Handle message send
    if send and question.strip():
        st.session_state.history.append({"q": question, "a": "..."})
        st.rerun()

    # Handle response
    if st.session_state.get("history") and st.session_state.history[-1]["a"] == "...":
        last_q = st.session_state.history[-1]["q"]
        try:
            r = requests.get(f"{API_BASE_URL}/query/", params={"question": last_q})
            data = r.json()
        except Exception as e:
            data = {"message": f"⚠️ API error: {e}"}

        if data.get("exact_answer"):
            answer = clean_thinker_section(data["exact_answer"])
        elif data.get("message"):
            answer = data["message"]
        else:
            answer = "🙏 Sorry, I couldn’t find an exact answer in my knowledge base."

        st.session_state.history[-1]["a"] = answer
        st.rerun()
# —— Tab 2: Upload & View Documents ——
with tab2:
    st.subheader("📤 Upload a Document")
    uploaded_file = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])
    if uploaded_file:
        if uploaded_file.size > 5 * 1024 * 1024:
            st.error("❌ File too large! Max 5MB.")
        else:
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                resp = requests.post(f"{API_BASE_URL}/upload/", files=files)
                res = resp.json()
                if res.get("message"):
                    st.success(f"✅ {res['message']}")
                else:
                    st.error(res.get("error", "Upload failed."))
            except Exception as e:
                st.error(f"🚨 Upload error: {e}")

    st.markdown("---")
    st.subheader("📁 Uploaded Documents")
    try:
        engine = create_engine("mysql+pymysql://root:12345678@localhost/practice_document_rag_qa")
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        docs = db.execute(text("SELECT filename FROM documents ORDER BY id DESC")).fetchall()
        db.close()

        seen = set()
        for (fn,) in docs:
            if fn in seen:
                continue
            seen.add(fn)
            st.write(f"📄 `{fn}`")
    except Exception as e:
        st.error(f"⚠️ Failed to load documents: {e}")
