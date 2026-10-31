import streamlit as st
import os
import shutil
import uuid
import pandas as pd
from backend.config import settings
from database.crud import list_documents, save_document_record, delete_document_record
from retrieval.document_processor import process_file
from retrieval.retriever import retriever
from evaluations.benchmark import seed_sample_documents

def render_documents():
    st.markdown("### 📁 Policy Document Management")
    st.markdown("Upload banking and insurance policies (PDF/TXT) into the ChromaDB vector index. Documents are chunked into semantic passages with page tracking and metadata.")

    col_upload, col_seed = st.columns([2, 1])

    with col_upload:
        st.markdown("##### 📤 Upload New Document")
        uploaded_file = st.file_uploader("Select PDF or TXT file", type=["pdf", "txt", "md"])
        if uploaded_file is not None:
            if st.button("Index Document into ChromaDB", use_container_width=True):
                filename = uploaded_file.name
                doc_id = str(uuid.uuid4())
                save_path = os.path.join(settings.DOCS_DIR, f"{doc_id}_{filename}")
                
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                file_size_kb = round(os.path.getsize(save_path) / 1024.0, 2)
                ext = os.path.splitext(filename)[1].replace(".", "").upper()

                try:
                    with st.spinner(f"Extracting passages from '{filename}'..."):
                        chunks = process_file(save_path, filename)
                        retriever.add_chunks(chunks)
                        save_document_record(
                            doc_id=doc_id,
                            filename=filename,
                            file_type=ext,
                            file_size_kb=file_size_kb,
                            chunk_count=len(chunks)
                        )
                    st.success(f"Successfully processed and indexed '{filename}' ({len(chunks)} passages).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing file: {e}")

    with col_seed:
        st.markdown("##### ⚡ Quick Demonstration Documents")
        st.caption("Re-index standard ApexBank Retail Policy (PDF) and Zenith Health Policy (PDF) for immediate testing.")
        if st.button("🔄 Seed / Reset Sample Documents", use_container_width=True):
            with st.spinner("Indexing sample policy PDFs..."):
                seed_sample_documents()
            st.success("Sample documents indexed!")
            st.rerun()

    st.markdown("<hr style='border: 1px solid #1e293b; margin: 24px 0;'>", unsafe_allow_html=True)

    # Document Table
    st.markdown("##### 📑 Active Indexed Documents")
    docs = list_documents()
    indexed_chunks = retriever.count_chunks()

    st.info(f"Total vector database passages active: **{indexed_chunks} chunks** across **{len(docs)} document(s)**.")

    if docs:
        for d in docs:
            col_info, col_del = st.columns([5, 1])
            with col_info:
                st.markdown(f"""
                <div style="background: #0d1527; border: 1px solid #1e293b; border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                    <div style="font-weight: 600; color: #ffffff;">📄 {d.filename}</div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">
                        Type: <span class="citation-tag">{d.file_type}</span> | 
                        Size: {d.file_size_kb} KB | 
                        Chunks: <b>{d.chunk_count}</b> | 
                        Uploaded: {d.upload_time[:19]}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️ Delete", key=f"del_{d.id}", use_container_width=True):
                    retriever.delete_document(d.filename)
                    delete_document_record(d.id)
                    st.warning(f"Deleted {d.filename}")
                    st.rerun()
    else:
        st.warning("No documents indexed yet. Click 'Seed / Reset Sample Documents' above to populate.")

