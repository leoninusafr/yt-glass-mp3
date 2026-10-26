const SERVER_URL = 'http://127.0.0.1:48123';

let currentVideoUrl = '';
let isDownloading = false;
let pollInterval = null;

// DOM
const videoTitleEl = document.getElementById('videoTitle');
const manualWrapper = document.getElementById('manualWrapper');
const manualUrlInput = document.getElementById('manualUrl');
const downloadBtn = document.getElementById('downloadBtn');
const pillProgress = document.getElementById('pillProgress');
const pillLabel = document.getElementById('pillLabel');

document.addEventListener('DOMContentLoaded', async () => {
  setupEvents();
  await detectTab();
});

function setupEvents() {
  downloadBtn.addEventListener('click', handleDownload);

  manualUrlInput.addEventListener('input', () => {
    const val = manualUrlInput.value.trim();
    if (isValidYoutubeUrl(val)) {
      currentVideoUrl = val;
      videoTitleEl.textContent = 'Link bereit zum Download';
    }
  });
}

async function checkServer() {
  try {
    const res = await fetch(`${SERVER_URL}/ping`, { method: 'GET', cache: 'no-cache' });
    if (res.ok) return true;
  } catch (e) {}
  return false;
}

async function detectTab() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url && isValidYoutubeUrl(tab.url)) {
      currentVideoUrl = tab.url;
      const cleanTitle = (tab.title || 'YouTube Audio').replace(/ - YouTube$/, '').trim();
      videoTitleEl.textContent = cleanTitle;
      manualWrapper.style.display = 'none';
    } else {
      currentVideoUrl = '';
      videoTitleEl.textContent = 'Kein YouTube-Tab';
      manualWrapper.style.display = 'block';
    }
  } catch (e) {
    console.error(e);
  }
}

function isValidYoutubeUrl(url) {
  return typeof url === 'string' && (url.includes('youtube.com/watch') || url.includes('youtu.be/') || url.includes('youtube.com/shorts/'));
}

async function handleDownload() {
  if (isDownloading) return;

  const url = currentVideoUrl || manualUrlInput.value.trim();
  if (!isValidYoutubeUrl(url)) {
    videoTitleEl.textContent = 'Bitte YouTube-URL eingeben';
    return;
  }

  const online = await checkServer();
  if (!online) {
    pillLabel.textContent = 'start.bat starten';
    setTimeout(() => { pillLabel.textContent = 'MP3 herunterladen'; }, 3000);
    return;
  }

  isDownloading = true;
  downloadBtn.classList.add('disabled');
  setProgress(10, 'Wird geladen...');

  try {
    const res = await fetch(`${SERVER_URL}/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, format: 'mp3', quality: '320' })
    });

    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.message || 'Fehler');

    startPolling();
  } catch (err) {
    finishDownload(false, 'Fehler aufgetreten');
  }
}

function startPolling() {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`${SERVER_URL}/status`, { cache: 'no-cache' });
      if (!res.ok) return;

      const job = await res.json();
      if (!job) return;

      if (job.status === 'downloading') {
        const pct = Math.max(15, Math.round(job.progress || 0));
        setProgress(pct, `${pct}%`);
      } else if (job.status === 'converting') {
        setProgress(92, 'Konvertiere...');
      } else if (job.status === 'finished') {
        clearInterval(pollInterval);
        finishDownload(true, '✓ In Downloads');
      } else if (job.status === 'error') {
        clearInterval(pollInterval);
        finishDownload(false, 'Fehler beim Laden');
      }
    } catch (e) {}
  }, 500);
}

function setProgress(pct, label) {
  pillProgress.style.width = `${pct}%`;
  pillLabel.textContent = label;
}

function finishDownload(success, msg) {
  isDownloading = false;
  downloadBtn.classList.remove('disabled');

  if (success) {
    setProgress(100, '✓ In Downloads');
    setTimeout(() => {
      setProgress(0, 'MP3 herunterladen');
    }, 3000);
  } else {
    setProgress(0, msg);
    setTimeout(() => {
      setProgress(0, 'MP3 herunterladen');
    }, 3000);
  }
}
