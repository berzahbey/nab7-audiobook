import os
import re
import subprocess
import requests
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
import fitz
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from app.cleaner import TextNormalizer

app = FastAPI(title="NAB7 Local Read-to-Podcast Engine")

BOOKS_DIR = Path("/app/books")
AUDIO_DIR = Path("/app/audio")
MODEL_DIR = Path("/root/.cache/piper")
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

job_status = {}

VOICES = {
    "tr_TR-dfki-medium": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json"
    }
}

def ensure_voice_model(voice: str):
    if voice not in VOICES:
        return
    onnx_path = MODEL_DIR / f"{voice}.onnx"
    json_path = MODEL_DIR / f"{voice}.onnx.json"
    
    if not onnx_path.exists():
        r = requests.get(VOICES[voice]["onnx"])
        onnx_path.write_bytes(r.content)
    if not json_path.exists():
        r = requests.get(VOICES[voice]["json"])
        json_path.write_bytes(r.content)

def parse_epub(file_path: Path) -> list[tuple[str, str]]:
    book = epub.read_epub(str(file_path))
    chapters = []
    idx = 1
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            clean_text = TextNormalizer.normalize(text)
            if len(clean_text) > 100:
                title = f"Bolum_{idx:02d}"
                h1 = soup.find('h1')
                if h1 and h1.text.strip():
                    slug = re.sub(r'\W+', '_', h1.text.strip())[:30]
                    title = f"Bolum_{idx:02d}_{slug}"
                chapters.append((title, clean_text))
                idx += 1
    return chapters

def parse_pdf(file_path: Path) -> list[tuple[str, str]]:
    doc = fitz.open(str(file_path))
    full_text = [page.get_text() for page in doc]
    combined = "\n".join(full_text)
    chunks = [combined[i:i+5000] for i in range(0, len(combined), 5000)]
    return [(f"Parca_{i+1:02d}", c) for i, c in enumerate(chunks)]

def synthesize_chapter(text: str, output_path: Path, voice: str):
    ensure_voice_model(voice)
    model_file = str(MODEL_DIR / f"{voice}.onnx")
    raw_wav = output_path.with_suffix('.raw.wav')
    
    cmd = [
        "piper",
        "--model", model_file,
        "--output_file", str(raw_wav)
    ]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate(input=text)
    
    if process.returncode != 0:
        raise RuntimeError(f"Piper error: {stderr}")
    
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_wav),
        "-codec:a", "libmp3lame", "-b:a", "192k",
        "-filter:a", "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(output_path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if raw_wav.exists():
        raw_wav.unlink()

def process_book_pipeline(filename: str, voice: str):
    file_path = BOOKS_DIR / filename
    job_status[filename] = {"status": "processing", "progress": "Başlıyor..."}
    try:
        out_book_dir = AUDIO_DIR / file_path.stem
        out_book_dir.mkdir(parents=True, exist_ok=True)
        
        chapters = parse_epub(file_path) if file_path.suffix.lower() == '.epub' else parse_pdf(file_path)
        total = len(chapters)
        
        for i, (title, text) in enumerate(chapters):
            out_mp3 = out_book_dir / f"{title}.mp3"
            if not out_mp3.exists():
                synthesize_chapter(text, out_mp3, voice)
            job_status[filename] = {"status": "processing", "progress": f"Bölüm {i+1}/{total} bitti"}
        
        job_status[filename] = {"status": "completed", "progress": f"Bitti! Klasör: {file_path.stem}"}
    except Exception as e:
        job_status[filename] = {"status": "error", "progress": str(e)}

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), voice: str = "tr_TR-dfki-medium"):
    file_path = BOOKS_DIR / file.filename
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
        
    job_status[file.filename] = {"status":age_status if False else "queued", "progress": "Kuyruğa alındı..."}
    job_status[file.filename] = {"status": "queued", "progress": "Kuyruğa alındı..."}
    background_tasks.add_task(process_book_pipeline, file.filename, voice)
    return {"filename": file.filename, "status": "queued"}

@app.get("/status")
def get_status():
    return job_status

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>NAB7 Read-to-Podcast UI</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }
            .container { max-width: 600px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; }
            h1 { color: #38bdf8; font-size: 20px; }
            .dropzone { border: 2px dashed #475569; padding: 40px; text-align: center; border-radius: 8px; cursor: pointer; background: #0f172a; transition: 0.2s; }
            .dropzone.dragover { border-color: #38bdf8; background: #334155; }
            input[type="file"] { display: none; }
            button { background: #0284c7; color: white; border: none; padding: 12px; border-radius: 6px; width: 100%; margin-top: 15px; font-weight: bold; cursor: pointer; }
            button:hover { background: #0369a1; }
            .status-list { margin-top: 25px; border-top: 1px solid #334155; padding-top: 15px; font-size: 13px; }
            .job-item { background: #0f172a; padding: 10px; border-radius: 6px; margin-bottom: 6px; display: flex; justify-content: space-between; }
            a { color: #38bdf8; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎧 NAB7 Yerel Kitap Seslendirici</h1>
            <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
                <p id="fileLabel">EPUB/PDF sürükle veya tıkla seç</p>
                <input type="file" id="fileInput" accept=".epub,.pdf" onchange="fileSelected()">
            </div>
            <button onclick="uploadFile()">Dönüşümü Başlat</button>
            <div class="status-list" id="statusList">Aktif işlem yok</div>
            <div style="margin-top:20px; text-align:center;">Audiobookshelf: <a href="http://localhost:13378" target="_blank">Aç</a></div>
        </div>
        <script>
            let selectedFile = null;
            const dropzone = document.getElementById('dropzone');
            const fileInput = document.getElementById('fileInput');

            dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
            dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    fileInput.files = e.dataTransfer.files;
                    fileSelected();
                }
            });

            function fileSelected() {
                if (fileInput.files.length > 0) {
                    selectedFile = fileInput.files[0];
                    document.getElementById('fileLabel').innerText = "Seçilen: " + selectedFile.name;
                }
            }
            async function uploadFile() {
                if(!selectedFile) return alert("Dosya seç!");
                const fd = new FormData(); fd.append('file', selectedFile);
                await fetch('/upload', { method: 'POST', body: fd });
                alert("Kuyruğa eklendi!");
            }
            async function pollStatus() {
                const res = await fetch('/status'); const data = await res.json();
                const list = document.getElementById('statusList');
                const keys = Object.keys(data);
                list.innerHTML = keys.length === 0 ? 'Aktif işlem yok' : keys.map(k => `<div class="job-item"><b>${k}</b><span>${data[k].progress}</span></div>`).join('');
            }
            setInterval(pollStatus, 3000); pollStatus();
        </script>
    </body>
    </html>
    """
