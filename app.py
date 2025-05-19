import streamlit as st
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pymysql
import re

# ---- Configuration ----
API_BASE_URL = "http://localhost:8000"
DATABASE_URL = "mysql+pymysql://root:12345678@localhost/practice_document_rag_qa"

st.set_page_config(page_title="🤖 SciAgent", layout="wide")
st.title("🤖 SciAgent - Document Q&A Assistant")

def clean_thinker_section(raw_response: str) -> str:
    # Remove <think>...</think> or **<think>...</think>** if present
    return re.sub(r"(\*\*)?<think>.*?</think>(\*\*)?", "", raw_response, flags=re.DOTALL).strip()


# ---- Tabs: Q&A | Upload Docs ----
tab1, tab2 = st.tabs(["💬 Ask a Question", "📤 Upload & View Documents"])


# ============================
# 💬 Tab 1: Ask a Question
# ============================
with tab1:
    st.subheader("🔎 Ask a question about uploaded documents")

    with st.form("question_form"):
        question = st.text_input("Type your question:")
        submit = st.form_submit_button("Ask")

    if submit:
        if not question.strip():
            st.error("❌ Please enter a valid question.")
        else:
            try:
                res = requests.get(f"{API_BASE_URL}/query/", params={"question": question})
                data = res.json()

                if "message" in data:
                    st.warning(data["message"])
                elif "exact_answer" in data and data["exact_answer"].strip():
                    cleaned_answer = clean_thinker_section(data["exact_answer"])
                    st.success("✅ Answer")
                    st.markdown(f"**🧠 {cleaned_answer}**")

                    if data.get("retrieved_documents"):
                        st.markdown("📚 **Reference Documents:**")
                        uniquedoc = set(data["retrieved_documents"])
                        for doc in uniquedoc:
                            st.write(f"• `{doc}`")
                else:
                    st.warning("🙏 Sorry, we couldn't find an answer to your question.")
            except Exception as e:
                st.error(f"⚠️ Error: {str(e)}")


# ============================
# 📤 Tab 2: Upload & View Docs
# ============================
with tab2:
    st.subheader("📤 Upload a Document")
    uploaded_file = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])

    if uploaded_file:
        if uploaded_file.size > 5 * 1024 * 1024:
            st.error("❌ File too large! Max 5MB.")
        else:
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                response = requests.post(f"{API_BASE_URL}/upload/", files=files)
                result = response.json()

                if "message" in result:
                    st.success(f"✅ {result['message']}")
                else:
                    st.error(result.get("error", "Upload failed."))
            except Exception as e:
                st.error(f"🚨 Upload error: {str(e)}")

    st.divider()
    st.subheader("📁 Uploaded Documents")

    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        docs = db.execute(text("SELECT filename, faiss_index FROM documents ORDER BY id DESC")).fetchall()
        db.close()

        seen = set()
        for doc in docs:
            if doc.filename in seen:
                continue
            seen.add(doc.filename)

            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"📄 `{doc.filename}` ")
            # Optional: Add delete functionality
            # with col2:
            #     if st.button("❌ Delete", key=doc.filename):
            #         try:
            #             res = requests.delete(f"{API_BASE_URL}/delete/", params={"filename": doc.filename})
            #             result = res.json()
            #             st.success(result.get("message", "Deleted"))
            #             st.experimental_rerun()
            #         except Exception as e:
            #             st.error(f"⚠️ Delete failed: {str(e)}")
    except Exception as e:
        st.error(f"⚠️ Failed to load documents: {str(e)}")
