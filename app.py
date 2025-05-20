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
    # Inject custom CSS
    st.markdown("<div id='chat-wrapper'>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        #chat-container { display: flex; flex-direction: column; height: 80vh; }
        #history { flex: 1; overflow-y: auto; padding: 12px; }
        .bubble { padding: 8px 12px; border-radius: 16px; margin: 6px 0; max-width: 70%; display: inline-block; }
        .user { background-color: #fff; align-self: flex-end; }
        .bot { background-color: #dcf8c6; align-self: flex-start; }
        #input-area { display: flex; padding: 8px; border-top: 1px solid #ddd; }
        #input-area input { flex: 1; padding: 8px 12px; border-radius: 20px; border: 1px solid #ccc; }
        #input-area button { margin-left: 8px; padding: 8px 16px; border: none; border-radius: 20px;
                              background-color: #25D366; color: white; cursor: pointer; }
        .bubble_wrap { display: block; width: 100%; }
        .bubble_sub_wrap { display: flex; }
        .bubble_sub_wrap .user { margin-left: auto; }
        </style>
        """, unsafe_allow_html=True
    )

    # Build the entire HTML content for chat-container including history
    history_html = "<div id='chat-container'>"
    history_html += "<div id='history'>"
    if st.session_state.history:
        for turn in st.session_state.history:
            history_html += f"<div class='bubble_wrap'>"
            history_html += f"<div class='bubble_sub_wrap'><div class='bubble bot'><strong>Bot:</strong> {turn['a']}</div></div>"
            history_html += f"<div class='bubble_sub_wrap'><div class='bubble user'><strong>You:</strong> {turn['q']}</div></div>"
            history_html += f"</div>"
    else:
        history_html += "<div style='color:#666;'>Start the conversation...</div>"
    history_html += "</div>"  # Close #history
    history_html += "</div>"  # Close #chat-container

    # Auto-scroll JS
    auto_scroll = (
        "<script>"
        "var hist = document.getElementById('history');"
        "if(hist) { hist.scrollTop = hist.scrollHeight; }"
        "</script>"
    )

    # Render chat container and scroll script
    st.markdown(history_html + auto_scroll, unsafe_allow_html=True)

    # Input form (outside raw HTML to use Streamlit widgets)
    with st.form("chat_form", clear_on_submit=True):
        st.markdown("<div id='input-area'>", unsafe_allow_html=True)
        question = st.text_input("", placeholder="Type a message...")
        submit = st.form_submit_button("Send")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


    # Handle submission
    if submit:
        if not question or not question.strip():
            st.error("❌ Please enter a valid message.")
        else:
            data = {
                "exact_answer": "This is a test answer."
            }
            if data.get("exact_answer"):
                answer = {"message": "hi this is test"}
            elif data.get("message"):
                answer = data["message"]
            else:
                answer = "🙏 Sorry, no answer found."

            st.session_state.history.append({"q": question, "a": answer})

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
