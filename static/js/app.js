'use strict';

// ── Theme ──
const html = document.documentElement;
const themeToggle = document.getElementById('themeToggle');

function applyTheme(theme) {
  html.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}

themeToggle.addEventListener('click', () => {
  applyTheme(html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
});

applyTheme(localStorage.getItem('theme') || 'dark');

// ── Elements ──
const dropZone    = document.getElementById('dropZone');
const fileInput   = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileListEl  = document.getElementById('fileList');
const btnAddMore  = document.getElementById('btnAddMore');
const errorMsg    = document.getElementById('errorMsg');
const btnConvert  = document.getElementById('btnConvert');
const btnText     = btnConvert.querySelector('.btn-text');
const btnSpinner  = btnConvert.querySelector('.btn-spinner');
const statsText   = document.getElementById('statsText');
const pixKey      = document.getElementById('pixKey');
const btnCopyPix  = document.getElementById('btnCopyPix');
const copyLabel   = btnCopyPix.querySelector('.copy-label');
const copyIcon    = btnCopyPix.querySelector('.copy-icon');
const checkIcon   = btnCopyPix.querySelector('.check-icon');

const ALLOWED_EXTS = new Set(['.zpl', '.txt', '.zip']);
const MAX_BYTES = 10 * 1024 * 1024;

// List of selected File objects
let selectedFiles = [];

// ── Helpers ──
function getExt(name) {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx).toLowerCase() : '';
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file) {
  const ext = getExt(file.name);
  if (!ALLOWED_EXTS.has(ext)) return `Tipo não permitido: "${ext}". Use .zpl, .txt ou .zip`;
  if (file.size === 0) return `Arquivo vazio: ${file.name}`;
  if (file.size > MAX_BYTES) return `Muito grande (${formatBytes(file.size)}): ${file.name}. Limite 10 MB`;
  return null;
}

// ── Error ──
function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.hidden = true;
  errorMsg.textContent = '';
}

// ── File list management ──
function isDuplicate(file) {
  return selectedFiles.some(f => f.name === file.name && f.size === file.size);
}

function addFiles(incoming) {
  let addedAny = false;
  for (const file of incoming) {
    if (isDuplicate(file)) continue;
    const err = validateFile(file);
    if (err) { showError(err); continue; }
    selectedFiles.push(file);
    addedAny = true;
  }
  if (addedAny) clearError();
  renderFileList();
  syncUI();
}

function removeFileAt(idx) {
  selectedFiles.splice(idx, 1);
  renderFileList();
  syncUI();
}

function renderFileList() {
  fileListEl.innerHTML = '';
  selectedFiles.forEach((file, idx) => {
    const li = document.createElement('li');
    li.className = 'file-item';

    li.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <div class="file-item-info">
        <span class="file-name">${escapeHtml(file.name)}</span>
        <span class="file-size">${formatBytes(file.size)}</span>
      </div>
      <button class="remove-file" aria-label="Remover ${escapeHtml(file.name)}" data-idx="${idx}">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    `;

    li.querySelector('.remove-file').addEventListener('click', () => removeFileAt(idx));
    fileListEl.appendChild(li);
  });
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function syncUI() {
  const hasFiles = selectedFiles.length > 0;
  filePreview.hidden = !hasFiles;
  dropZone.hidden = hasFiles;
  btnConvert.disabled = !hasFiles;
  if (!hasFiles) fileInput.value = '';
}

// ── Drop zone ──
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  addFiles(Array.from(e.dataTransfer.files));
});

fileInput.addEventListener('change', () => {
  addFiles(Array.from(fileInput.files));
  fileInput.value = '';
});

btnAddMore.addEventListener('click', () => fileInput.click());

// ── Convert ──
btnConvert.addEventListener('click', async () => {
  if (!selectedFiles.length) return;
  clearError();
  setConverting(true);

  const form = new FormData();
  selectedFiles.forEach(f => form.append('file', f));

  try {
    const resp = await fetch('/api/convert', { method: 'POST', body: form });

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({ error: `Erro ${resp.status}` }));
      showError(data.error || 'Erro desconhecido na conversão');
      return;
    }

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'etiquetas.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    loadStats();
  } catch (_) {
    showError('Falha na conexão. Verifique sua internet e tente novamente.');
  } finally {
    setConverting(false);
  }
});

function setConverting(active) {
  btnConvert.disabled = active;
  btnText.hidden = active;
  btnSpinner.hidden = !active;
}

// ── Stats + PIX ──
async function loadStats() {
  try {
    const resp = await fetch('/api/stats');
    if (!resp.ok) return;
    const data = await resp.json();

    const n = data.total_conversions || 0;
    statsText.textContent = `${n.toLocaleString('pt-BR')} etiqueta${n !== 1 ? 's' : ''} convertida${n !== 1 ? 's' : ''}`;

    if (data.pix_key) {
      pixKey.textContent = data.pix_key;
      btnCopyPix.disabled = false;
    }
  } catch (_) {
    statsText.textContent = 'Ferramenta gratuita e sem cadastro';
  }
}

loadStats();

// ── Copy PIX ──
btnCopyPix.addEventListener('click', async () => {
  const key = pixKey.textContent;
  if (!key || key === '—') return;

  try {
    await navigator.clipboard.writeText(key);
    copyIcon.hidden = true;
    checkIcon.hidden = false;
    copyLabel.textContent = 'Copiado!';

    setTimeout(() => {
      copyIcon.hidden = false;
      checkIcon.hidden = true;
      copyLabel.textContent = 'Copiar';
    }, 2000);
  } catch (_) {
    const range = document.createRange();
    range.selectNode(pixKey);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
  }
});
