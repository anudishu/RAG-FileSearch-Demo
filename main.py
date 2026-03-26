"""FastAPI UI + API for doc Q&A via Gemini File Search (dev API key)."""

from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import logging
import os

from config import Config, api_configured

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: / /api/v1/upload /api/v1/query")
    yield


app = FastAPI(
    title="File Search RAG demo",
    description="Upload docs, query with File Search tool",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_services: dict = {}


def get_file_search_rag():
    if "file_search_rag" not in _services:
        try:
            from file_search_service import FileSearchRAG

            _services["file_search_rag"] = FileSearchRAG()
            logger.info("✓ FileSearchRAG loaded")
        except Exception as e:
            logger.error("Failed to load FileSearchRAG: %s", e)
            _services["file_search_rag"] = None
    return _services["file_search_rag"]


@app.get("/health")
def health_check():
    return {"status": "ok"}


FRONTEND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Search RAG</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary: #0f172a;
            --secondary: #1e293b;
            --accent: #a855f7;
            --accent-dark: #6d28d9;
            --accent-light: #c084fc;
            --success: #10b981;
            --danger: #ef4444;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --border: #334155;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, var(--primary) 0%, #0c0518 100%);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }
        body::before {
            content: '';
            position: fixed; inset: 0;
            background-image:
                linear-gradient(rgba(168, 85, 247, 0.04) 1px, transparent 1px),
                linear-gradient(90deg, rgba(168, 85, 247, 0.04) 1px, transparent 1px);
            background-size: 50px 50px;
            pointer-events: none;
            z-index: -1;
        }
        header {
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
            padding: 20px 0;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 24px;
            font-weight: bold;
            background: linear-gradient(135deg, var(--accent-light) 0%, var(--accent) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .logo::before { content: '✦'; font-size: 26px; }
        .status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: var(--text-secondary);
        }
        .status-indicator {
            width: 10px;
            height: 10px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        .hero { text-align: center; margin-bottom: 50px; }
        .hero h1 {
            font-size: 44px;
            font-weight: 700;
            margin-bottom: 12px;
            background: linear-gradient(135deg, var(--accent-light) 0%, var(--accent) 50%, #7c3aed 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .hero p { font-size: 17px; color: var(--text-secondary); margin-bottom: 8px; }
        .hero-badge {
            display: inline-block;
            margin-top: 14px;
            padding: 8px 18px;
            border-radius: 20px;
            font-size: 13px;
            border: 1px solid var(--accent);
            background: rgba(168, 85, 247, 0.12);
            color: var(--accent-light);
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 28px;
            margin-bottom: 36px;
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .hero h1 { font-size: 30px; }
        }
        .card {
            background: rgba(30, 41, 59, 0.85);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 28px;
            backdrop-filter: blur(10px);
            position: relative;
            overflow: hidden;
        }
        .card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
        }
        .card-icon { font-size: 30px; margin-bottom: 12px; }
        .card h2 { font-size: 22px; margin-bottom: 12px; }
        .card p { color: var(--text-secondary); font-size: 14px; margin-bottom: 18px; line-height: 1.5; }
        .upload-area {
            border: 2px dashed var(--border);
            border-radius: 8px;
            padding: 36px 16px;
            text-align: center;
            cursor: pointer;
            transition: all 0.25s ease;
            background: rgba(168, 85, 247, 0.04);
        }
        .upload-area:hover, .upload-area.dragover {
            border-color: var(--accent);
            background: rgba(168, 85, 247, 0.1);
        }
        .upload-icon { font-size: 44px; margin-bottom: 10px; }
        #fileInput { display: none; }
        .file-list { margin-top: 16px; max-height: 200px; overflow-y: auto; }
        .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            margin-bottom: 8px;
            border-radius: 6px;
            border: 1px solid var(--accent);
            background: rgba(168, 85, 247, 0.1);
        }
        .file-name { font-size: 14px; }
        .file-size { font-size: 12px; color: var(--text-secondary); }
        .btn {
            padding: 12px 22px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
            color: white;
            width: 100%;
            justify-content: center;
        }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-secondary {
            background: rgba(168, 85, 247, 0.15);
            color: var(--accent-light);
            border: 1px solid var(--accent);
            padding: 6px 12px;
            font-size: 12px;
        }
        .input-group { margin-bottom: 16px; }
        .input-group label {
            display: block;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .input-group textarea {
            width: 100%;
            min-height: 120px;
            padding: 12px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: rgba(15, 23, 42, 0.55);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 14px;
            resize: vertical;
        }
        .input-group textarea:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 12px rgba(168, 85, 247, 0.25);
        }
        .hint {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: -8px;
            margin-bottom: 14px;
            line-height: 1.4;
        }
        .results {
            display: none;
            margin-top: 18px;
            padding: 18px;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: rgba(15, 23, 42, 0.45);
        }
        .results.show { display: block; animation: slideIn 0.3s ease; }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .result-header { color: var(--accent-light); font-weight: 600; margin-bottom: 10px; }
        .result-content {
            line-height: 1.65;
            padding: 12px;
            border-left: 3px solid var(--accent);
            background: rgba(15, 23, 42, 0.4);
            border-radius: 0 6px 6px 0;
            white-space: pre-wrap;
        }
        .citations-pre {
            font-size: 11px;
            color: var(--text-secondary);
            overflow-x: auto;
            max-height: 220px;
            padding: 10px;
            border-radius: 6px;
            background: rgba(0,0,0,0.25);
            margin-top: 10px;
        }
        .stat {
            text-align: center;
            padding: 14px;
            border-radius: 8px;
            border: 1px solid var(--accent);
            background: rgba(168, 85, 247, 0.1);
        }
        .stat-value { font-size: 26px; font-weight: 700; color: var(--accent-light); }
        .stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
        .message { padding: 12px; border-radius: 6px; margin-bottom: 10px; font-size: 14px; }
        .message.success { background: rgba(16, 185, 129, 0.12); border: 1px solid var(--success); color: #6ee7b7; }
        .message.error { background: rgba(239, 68, 68, 0.12); border: 1px solid var(--danger); color: #fca5a5; }
        .message.info { background: rgba(168, 85, 247, 0.12); border: 1px solid var(--accent); color: var(--accent-light); }
        .loading {
            width: 18px;
            height: 18px;
            border: 3px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.75s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        footer {
            text-align: center;
            padding: 36px 20px;
            color: var(--text-secondary);
            font-size: 13px;
            border-top: 1px solid var(--border);
            margin-top: 48px;
        }
        .footer-links { display: flex; justify-content: center; gap: 20px; margin-bottom: 12px; flex-wrap: wrap; }
        .footer-links a { color: var(--accent-light); text-decoration: none; }
        .footer-links a:hover { text-decoration: underline; }
        #configBanner {
            display: none;
            max-width: 1200px;
            margin: 0 auto;
            padding: 12px 20px;
            background: rgba(239, 68, 68, 0.15);
            border-bottom: 1px solid var(--danger);
            color: #fecaca;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div id="configBanner"></div>
    <header>
        <div class="header-content">
            <div class="logo">Document Q&amp;A</div>
            <div class="status">
                <div class="status-indicator"></div>
                <span>Gemini API</span>
            </div>
        </div>
    </header>
    <div class="container">
        <div class="hero">
            <h1>Doc Q&amp;A</h1>
            <p>Upload PDFs, Office docs, text, CSV. Ask questions; answers use File Search over your store.</p>
            <p style="font-size:15px;opacity:0.85">Chunking + embeddings are handled by File Search — no separate vector DB in this repo.</p>
            <div class="hero-badge">Gemini · File Search</div>
        </div>
        <div class="grid">
            <div class="card">
                <div class="card-icon">📤</div>
                <h2>Upload &amp; index</h2>
                <p>PDF, Office, text, and CSV. Each file is imported into your File Search store.</p>
                <div class="upload-area" id="uploadArea">
                    <div class="upload-icon">☁️</div>
                    <div style="font-size:16px;margin-bottom:4px">Drag &amp; drop files here</div>
                    <div style="font-size:13px;color:var(--text-secondary)">or click to browse</div>
                    <input type="file" id="fileInput" accept=".pdf,.doc,.docx,.txt,.md,.csv" multiple>
                </div>
                <div id="fileList" class="file-list"></div>
                <div id="uploadMessage"></div>
                <button class="btn btn-primary" id="uploadBtn" style="margin-top:14px"><span>Index files</span></button>
                <div id="uploadStats" style="display:none;margin-top:16px">
                    <div class="stat">
                        <div class="stat-value" id="docCount">0</div>
                        <div class="stat-label">Documents in File Search store</div>
                    </div>
                </div>
                <div id="uploadSuccess" style="display:none;margin-top:16px;padding:14px;border-radius:8px;border:1px solid var(--success);background:rgba(16,185,129,0.1);color:#6ee7b7;font-size:14px">
                    ✅ Indexed successfully. Ask questions in the panel on the right.
                </div>
            </div>
            <div class="card">
                <div class="card-icon">🔮</div>
                <h2>Ask with retrieval</h2>
                <p>Questions use the File Search tool: relevant chunks are retrieved automatically and passed to the model.</p>
                <div class="input-group">
                    <label for="queryInput">Your question</label>
                    <textarea id="queryInput" placeholder="What do the uploaded materials say about…?"></textarea>
                </div>
                <p class="hint">Retrieval depth is managed by File Search (no manual top‑k). Responses may include citations when the model surfaces them.</p>
                <button class="btn btn-primary" id="queryBtn"><span>Generate answer</span></button>
                <div id="queryMessage"></div>
                <div id="queryResults" class="results">
                    <div class="result-header">Answer</div>
                    <div class="result-content" id="answer"></div>
                    <div id="citationsWrap" style="display:none;margin-top:14px">
                        <div class="result-header">Citations &amp; grounding</div>
                        <pre class="citations-pre" id="citationsPre"></pre>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <footer>
        <div class="footer-links">
            <a href="https://ai.google.dev/gemini-api/docs/file-search" target="_blank" rel="noopener">File Search docs</a>
            <a href="/docs" target="_blank" rel="noopener">OpenAPI /docs</a>
            <a href="https://ai.google.dev/gemini-api/docs" target="_blank" rel="noopener">Gemini API</a>
        </div>
        <p>Demo / internal use — lock down before production</p>
    </footer>
    <script>
        const API = '/api/v1';
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        const uploadBtn = document.getElementById('uploadBtn');
        const uploadMessage = document.getElementById('uploadMessage');
        const uploadStats = document.getElementById('uploadStats');
        const uploadSuccess = document.getElementById('uploadSuccess');
        const queryBtn = document.getElementById('queryBtn');
        const queryInput = document.getElementById('queryInput');
        const queryResults = document.getElementById('queryResults');
        const queryMessage = document.getElementById('queryMessage');
        const answerEl = document.getElementById('answer');
        const citationsWrap = document.getElementById('citationsWrap');
        const citationsPre = document.getElementById('citationsPre');
        const configBanner = document.getElementById('configBanner');

        let selectedFiles = [];

        fetch('/api/v1/status').then(r => r.json()).then(s => {
            if (!s.api_key_configured) {
                configBanner.style.display = 'block';
                configBanner.textContent = 'Set GEMINI_API_KEY in the environment to enable uploads and queries.';
            }
        }).catch(() => {});

        uploadArea.addEventListener('click', () => fileInput.click());
        uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('dragover'); });
        uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
        uploadArea.addEventListener('drop', e => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            selectedFiles = Array.from(e.dataTransfer.files);
            renderFiles();
        });
        fileInput.addEventListener('change', e => {
            selectedFiles = Array.from(e.target.files);
            renderFiles();
        });

        function renderFiles() {
            fileList.innerHTML = '';
            selectedFiles.forEach((file, i) => {
                const row = document.createElement('div');
                row.className = 'file-item';
                row.innerHTML = `<div><div class="file-name">📎 ${file.name}</div><div class="file-size">${(file.size/1024/1024).toFixed(2)} MB</div></div>
                    <button type="button" class="btn btn-secondary" data-i="${i}">Remove</button>`;
                row.querySelector('button').onclick = () => { selectedFiles.splice(i, 1); renderFiles(); };
                fileList.appendChild(row);
            });
        }

        function msg(container, text, type) {
            const d = document.createElement('div');
            d.className = 'message ' + type;
            d.textContent = text;
            container.appendChild(d);
        }

        uploadBtn.addEventListener('click', async () => {
            if (!selectedFiles.length) { msg(uploadMessage, 'Select at least one file', 'error'); return; }
            uploadBtn.disabled = true;
            uploadBtn.innerHTML = '<div class="loading"></div> <span>Indexing…</span>';
            uploadMessage.innerHTML = '';
            uploadSuccess.style.display = 'none';

            let ok = 0;
            for (const file of selectedFiles) {
                const fd = new FormData();
                fd.append('file', file);
                try {
                    const res = await fetch(API + '/upload', { method: 'POST', body: fd });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || res.statusText);
                    document.getElementById('docCount').textContent = data.documents_in_store ?? '—';
                    uploadStats.style.display = 'block';
                    msg(uploadMessage, `Indexed: ${file.name}`, 'success');
                    ok++;
                } catch (e) {
                    msg(uploadMessage, `${file.name}: ${e.message}`, 'error');
                }
            }
            if (ok === selectedFiles.length) {
                uploadSuccess.style.display = 'block';
                selectedFiles = [];
                renderFiles();
                fileInput.value = '';
            }
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<span>Index files</span>';
        });

        queryBtn.addEventListener('click', async () => {
            const q = queryInput.value.trim();
            if (!q) { msg(queryMessage, 'Enter a question', 'error'); return; }
            queryBtn.disabled = true;
            queryBtn.innerHTML = '<div class="loading"></div> <span>Thinking…</span>';
            queryMessage.innerHTML = '';
            queryResults.classList.remove('show');
            citationsWrap.style.display = 'none';

            try {
                const res = await fetch(API + '/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: q })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || res.statusText);
                answerEl.textContent = data.answer || '';
                queryResults.classList.add('show');
                const cite = data.citations && data.citations.length;
                const ground = data.grounding_metadata;
                if (cite || ground) {
                    citationsWrap.style.display = 'block';
                    citationsPre.textContent = JSON.stringify({
                        citations: data.citations || [],
                        grounding_metadata: ground || null
                    }, null, 2);
                }
                msg(queryMessage, 'Answer generated with File Search retrieval', 'success');
            } catch (e) {
                msg(queryMessage, e.message, 'error');
            }
            queryBtn.disabled = false;
            queryBtn.innerHTML = '<span>Generate answer</span>';
        });
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def root():
    return FRONTEND_HTML


@app.get("/api/v1/status")
def api_status():
    return {
        "service": "file-search-rag-demo",
        "api_key_configured": api_configured(),
        "model": Config.GEMINI_MODEL,
        "file_search_store_env": bool(Config.FILE_SEARCH_STORE_NAME),
    }


@app.post("/api/v1/upload")
async def upload_document(file: UploadFile = File(...)):
    if not api_configured():
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured",
        )
    if not file.filename or "." not in file.filename:
        raise HTTPException(status_code=400, detail="Filename must include an extension (e.g. report.pdf)")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type .{ext}. Allowed: {', '.join(sorted(Config.ALLOWED_EXTENSIONS))}",
        )
    try:
        data = await file.read()
        svc = get_file_search_rag()
        if not svc:
            raise HTTPException(status_code=500, detail="Service failed to initialize")
        result = svc.upload_file_bytes(data, file.filename or f"upload.{ext}")
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("upload failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/query")
async def query(payload: dict = Body(...)):
    if not api_configured():
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured")
    q = (payload or {}).get("query")
    if not q or not str(q).strip():
        raise HTTPException(status_code=400, detail="query is required")
    try:
        svc = get_file_search_rag()
        if not svc:
            raise HTTPException(status_code=500, detail="Service failed to initialize")
        out = svc.query(str(q).strip())
        return {
            "success": True,
            "query": q,
            "answer": out["answer"],
            "citations": out["citations"],
            "grounding_metadata": out["grounding_metadata"],
            "file_search_store": out["file_search_store"],
            "model": out["model"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("query failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
