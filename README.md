# FlowDocs

FlowDocs is a modular document-processing platform for heterogeneous document intelligence. It composes OCR, document parsing, retrieval-augmented generation (RAG), and topic clustering into typed, directed acyclic workflows with rule-based routing.

## Features

- Typed nodes and DAG-based workflow execution
- OCR (printed and handwriting) and document parsing (PDF, DOCX, TXT, CSV, XLSX)
- RAG indexing and a QA Chat interface
- Rule-based routing: images to OCR, DOCX/PDF to the parser
- Topic clustering with multiple representations
- Self-hosted processing for local, privacy-preserving execution

## Prerequisites

- Python 3.11+
- Node.js 20+
- Ollama (optional, for local embeddings and LLM inference)

## Quick Start (Windows)

Double-click `run.bat`, or run:

```powershell
python run_flowdocs.py
```

The launcher creates a Python environment, installs dependencies, starts the backend and frontend, and opens the application.

- Frontend: <http://127.0.0.1:5173>
- Backend API: <http://127.0.0.1:8000> (docs at `/docs`)

## Manual Start

### Backend (FastAPI)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Frontend (Vite + React)

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

## Notes

- Heavy models (OCR, embeddings) are warmed up in the background at startup; the first request is slower while they load.
- The QA index is persisted to `data/storage/qa_index.json`.
- All processing runs locally by default.
