from fastapi import FastAPI, File, UploadFile, Query
from sentence_transformers import SentenceTransformer
import fitz  # PyMuPDF for PDF
import docx
import faiss
import os
import groq
import numpy as np
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
import dotenv
from os import getenv
dotenv.load_dotenv()
GROQ_API_KEY = getenv("GROQ_API_KEY")

# Initialize FastAPI app
app = FastAPI()

# Initialize Groq Client
groq_client = groq.Client(api_key=GROQ_API_KEY)

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dimension

FAISS_INDEX_PATH = "faiss_index.bin"
embedding_dim = 384
index = faiss.IndexFlatL2(embedding_dim)

# Database setup
DATABASE_URL = "mysql+pymysql://root:12345678@localhost/practice_document_rag_qa"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Document model
class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    faiss_index = Column(Integer, unique=True, nullable=True)

Base.metadata.create_all(bind=engine)

# Utility functions
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file, filetype="pdf")
    return "\n".join(page.get_text("text") for page in doc).strip()

def extract_text_from_docx(docx_file):
    doc = docx.Document(docx_file)
    return "\n".join(para.text for para in doc.paragraphs).strip()

def get_embedding(text):
    embedding = model.encode(text)
    return embedding / np.linalg.norm(embedding)

def save_faiss_index():
    faiss.write_index(index, FAISS_INDEX_PATH)

def load_faiss_index():
    global index
    if os.path.exists(FAISS_INDEX_PATH):
        index = faiss.read_index(FAISS_INDEX_PATH)
        print("FAISS index loaded with", index.ntotal, "entries")
    else:
        print("No FAISS index found, using fresh one.")

# Load index at startup
load_faiss_index()

# Upload document API
@app.post("/upload/")
async def upload_document(file: UploadFile = File(...)):
    save_faiss_index()  # Save current state first
    content = ""

    if file.filename.endswith(".pdf"):
        content = extract_text_from_pdf(await file.read())
    elif file.filename.endswith(".docx"):
        content = extract_text_from_docx(file.file)
    else:
        return {"error": "Unsupported file format"}

    embedding = get_embedding(content)
    load_faiss_index()
    index.add(np.array([embedding], dtype=np.float32))
    faiss_index = index.ntotal - 1
    save_faiss_index()

    db = SessionLocal()
    new_doc = Document(filename=file.filename, content=content, faiss_index=faiss_index)
    db.add(new_doc)
    db.commit()
    db.close()

    return {
        "message": "Document uploaded and embedded successfully",
        "faiss_index": faiss_index
    }

# Query API supporting multiple documents
@app.get("/query/")
async def query_document(question: str = Query(..., description="Enter your search query")):
    load_faiss_index()
    query_embedding = get_embedding(question)

    # 🔍 Retrieve top-k results
    k = 3
    distances, indices = index.search(np.array([query_embedding], dtype=np.float32), k)
    matched_indices = [int(idx) for idx in indices[0] if idx != -1]

    if not matched_indices:
        return {"message": "No relevant documents found."}

    # 📄 Get documents from DB
    db = SessionLocal()
    matched_docs = db.query(Document).filter(Document.faiss_index.in_(matched_indices)).all()
    db.close()

    if not matched_docs:
        return {"message": "No matching documents found in database."}

    # 🧠 Truncate each document content to ~1500 tokens (~4500 total)
    def truncate_text(text, max_chars=6000):
        return text[:max_chars]

    combined_content = "\n\n".join([
        f"{doc.filename}:\n{truncate_text(doc.content, 2000)}"
        for doc in matched_docs
    ])

    # 🔥 Ask Groq for answer
    try:
        response = groq_client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[
                {"role": "system", "content": "You are an AI assistant that extracts precise answers from multiple documents."},
                {"role": "user", "content": f"Documents:\n{combined_content}\n\nQuestion: {question}\n\nExtract the exact answer from relevant documents."}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        exact_answer = response.choices[0].message.content.strip()
    except groq.APIStatusError as e:
        return {"error": str(e)}

    fallback_phrases = [
        "no mention", 
        "does not appear", 
        "no information", 
        "not contain any information", 
        "there is no", 
        "unable to find"
    ]

    # Lowercase for safe matching
    if any(phrase in exact_answer.lower() for phrase in fallback_phrases):
        return {
            "message": "🙏 We're sorry, we don't have such a document to answer your query."
        }

    # ✅ Return only when confident answer is extracted
    return {
        "query": question,
        "retrieved_documents": [doc.filename for doc in matched_docs],
        "exact_answer": exact_answer
    }
