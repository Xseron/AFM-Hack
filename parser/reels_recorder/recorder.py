"""In-page MediaRecorder of the active reel's <video> element."""
from __future__ import annotations

import base64

from playwright.sync_api import Page

# JS that selects the video the watch loop should measure. It prefers the exact
# element the recorder locked onto at start() (window.__rec.video), so progress is
# read from the video being recorded — not a neighbor. TikTok keeps several
# <video> elements in the DOM and pre-plays the next one (muted) while the current
# reel is still on screen; re-resolving "most visible / first playing" every poll
# would jump between videos, making the watch loop think the clip looped or ended
# and scroll away early. We only fall back to a fresh pick if the locked element is
# gone from the DOM.
_ACTIVE_VIDEO = """
() => {
  const visArea = (v) => {
    const r = v.getBoundingClientRect();
    const w = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
    const h = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
    return w * h;
  };
  let locked = (window.__rec && window.__rec.video) || null;
  if (locked && locked.isConnected) return locked;
  const vids = Array.from(document.querySelectorAll('video'));
  if (!vids.length) return null;
  return vids.find(v => !v.paused && v.readyState > 2)
      || vids.slice().sort((a, b) => visArea(b) - visArea(a))[0]
      || null;
}
"""

_INSTALL = """
() => {
  window.__rec = {
    recorder: null,
    chunks: [],
    video: null,
    pickVideo() {
      const vids = Array.from(document.querySelectorAll('video'));
      if (!vids.length) return null;
      const visArea = (v) => {
        const r = v.getBoundingClientRect();
        const w = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
        const h = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
        return w * h;
      };
      return vids.find(v => !v.paused && v.readyState > 2)
          || vids.slice().sort((a, b) => visArea(b) - visArea(a))[0]
          || null;
    },
    start() {
      const v = this.pickVideo();
      if (!v) return false;
      this.video = v;
      let stream;
      try { stream = v.captureStream ? v.captureStream() : v.mozCaptureStream(); }
      catch (e) { return false; }
      if (!stream) return false;
      this.chunks = [];
      let mime = 'video/webm;codecs=vp9';
      if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/webm;codecs=vp8';
      if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/webm';
      try { this.recorder = new MediaRecorder(stream, { mimeType: mime }); }
      catch (e) { return false; }
      this.recorder.ondataavailable = (e) => { if (e.data && e.data.size) this.chunks.push(e.data); };
      try { this.recorder.start(250); } catch (e) { return false; }
      return true;
    },
    stop() {
      return new Promise((resolve) => {
        const r = this.recorder;
        this.recorder = null;
        this.video = null;
        if (!r || r.state === 'inactive') { resolve(''); return; }
        r.onstop = async () => {
          const blob = new Blob(this.chunks, { type: 'video/webm' });
          this.chunks = [];
          if (!blob.size) { resolve(''); return; }
          const bytes = new Uint8Array(await blob.arrayBuffer());
          let bin = '';
          const step = 0x8000;
          for (let i = 0; i < bytes.length; i += step) {
            bin += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
          }
          resolve(btoa(bin));
        };
        try { r.stop(); } catch (e) { resolve(''); }
      });
    }
  };
  return true;
}
"""


def install(page: Page) -> None:
    page.evaluate(_INSTALL)


def start_recording(page: Page) -> bool:
    try:
        return bool(page.evaluate("() => window.__rec && window.__rec.start()"))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] start_recording failed: {e}")
        return False


def stop_recording(page: Page) -> bytes:
    """Stop and return the recorded clip bytes (empty on tainted/failed stream)."""
    try:
        b64 = page.evaluate("() => window.__rec ? window.__rec.stop() : ''")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] stop_recording failed: {e}")
        return b""
    if not b64:
        return b""
    try:
        return base64.b64decode(b64)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not decode clip: {e}")
        return b""


def video_progress(page: Page) -> dict | None:
    """Return {currentTime, duration, ended, paused} for the active reel video."""
    js = (
        "() => { const v = (" + _ACTIVE_VIDEO + ")(); if (!v) return null;"
        " return {currentTime: v.currentTime, duration: isFinite(v.duration) ? v.duration : 0,"
        " ended: v.ended, paused: v.paused}; }"
    )
    try:
        return page.evaluate(js)
    except Exception:  # noqa: BLE001
        return None


def ensure_video_playing(page: Page) -> dict | None:
    """Best-effort resume for the active video, returning fresh progress."""
    js = (
        "() => { const v = (" + _ACTIVE_VIDEO + ")(); if (!v) return null;"
        " if (v.paused) { try { const p = v.play(); if (p && p.catch) p.catch(() => {}); } catch (_) {} }"
        " return {currentTime: v.currentTime, duration: isFinite(v.duration) ? v.duration : 0,"
        " ended: v.ended, paused: v.paused}; }"
    )
    try:
        return page.evaluate(js)
    except Exception:  # noqa: BLE001
        return None
