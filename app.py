import streamlit as st
import requests
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import base64
import os

import base64
import os

def show_pdf_inline(filename, folder="uploaded_docs"):
    file_path = os.path.join(folder, filename)
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500px" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.warning("File not found.")

# Page config
PROJECT_NAME = "Scaigent"
API_BASE_URL = "http://localhost:8000"
st.set_page_config(page_title=f"🤖 {PROJECT_NAME}", layout="wide")
st.markdown("""
    <style>
        .main-header {
            font-size: 32px;
            font-weight: bold;
            margin-top: -20px;
            padding-bottom: 10px;
        }
        .stApp {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown(f"<div class='main-header'>🤖 {PROJECT_NAME}</div>", unsafe_allow_html=True)

# Utility to clean thinker sections
def clean_thinker_section(raw: str) -> str:
    return re.sub(r"(\*\*)?<think>.*?</think>(\*\*)?", "", raw, flags=re.DOTALL).strip()

# Build chat history as context
def build_context_from_history():
    context = ""
    for turn in st.session_state.history[:-1]:
        if turn["a"] != "...":
            context += f"User: {turn['q']}\nAgent: {turn['a']}\n"
    return context.strip()

# Initialize session state
if "history" not in st.session_state:
    st.session_state.history = []

# Create two tabs: Chat and Document Management
tab1, tab2 = st.tabs(["💬 Ask a Question", "📤 Upload & View Documents"])

# —— Tab 1: Chat ——
with tab1:
    st.markdown("""
    <style>
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
    .chat-row {
        display: flex;
        width: 100%;
    }
    .user-row { justify-content: flex-end; }
    .bot-row { justify-content: flex-start; }
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

    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    chat_box = st.container()
    with chat_box:
        st.markdown('<div class="chat-box">', unsafe_allow_html=True)
        if not st.session_state.get("history"):
            st.markdown("<span style='color:#888'>Start the conversation...</span>", unsafe_allow_html=True)
        else:
            for i, turn in enumerate(st.session_state.history):
                st.markdown(f"""
                <div class='chat-row user-row'>
                    <div class='chat-msg user-msg'><strong>👤</strong> {turn['q']}</div>
                </div>
                """, unsafe_allow_html=True)

                if turn["a"] == "...":
                    st.markdown("""
                    <div class='chat-row bot-row'>
                        <div class='chat-msg bot-msg'>
                            <strong>🤖</strong> <span class='dot-loader'></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class='chat-row bot-row'>
                        <div class='chat-msg bot-msg'>
                            <strong>🤖</strong> {turn['a']}
                            <div style='display: flex; justify-content: flex-end; gap: 20px; margin-top: 6px;'>
                                <span style='font-size: 13px;'>
                                    👍 <input type='radio' name='feedback_{i}' id='yes_{i}'>
                                </span>
                                <span style='font-size: 13px;'>
                                    👎 <input type='radio' name='feedback_{i}' id='no_{i}'>
                                </span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Show doc source
                    # if turn.get("source"):
                    #     st.markdown(f"""
                    #         <div style='margin: 4px 0 12px 0;'>
                    #             📄 source document: <a  style='color: #0d6efd; font-weight: 600;'>
                    #             {turn['source']}</a>
                    #         </div>
                    #     """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        with col1:
            question = st.text_input("Type a message:", key="input_text", label_visibility="collapsed")
        with col2:
            send = st.form_submit_button("Send", use_container_width=True)

    if send and question.strip():
        if not st.session_state.history or st.session_state.history[-1]["a"] != "...":
            st.session_state.history.append({"q": question, "a": "..."})
            st.rerun()

    if st.session_state.get("history") and st.session_state.history[-1]["a"] == "...":
        last_q = st.session_state.history[-1]["q"]
        context = build_context_from_history()
        try:
            r = requests.post(f"{API_BASE_URL}/query/", json={"question": last_q, "context": context})
            data = r.json()
        except Exception as e:
            data = {"message": f"API error"}

        if data.get("answer"):
            answer = clean_thinker_section(data["answer"])
        elif data.get("message"):
            answer = data["message"]
        else:
            answer = "Sorry, I couldn't find an exact answer in my knowledge base."

        st.session_state.history[-1]["a"] = answer
        if "source" in data:
            st.session_state.history[-1]["source"] = data["source"]
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# —— Tab 2: Upload & View Documents ——
with tab2:
    st.subheader("📤 Upload a Document")
    uploaded_file = st.file_uploader("Upload PDF or DOCX", type=["pdf"])
    if uploaded_file:
        if uploaded_file.size > 5 * 1024 * 1024:
            st.error("File too large! Max 5MB.")
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
                st.error(f"Upload error")

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
        st.error(f"Failed to load documents")