/* ============================================================
   AudionLabs audio core
   Shared Web Audio helpers for the live studio and stem mixer.
   Everything here runs in the browser. No audio leaves the device.
   ============================================================ */
(function () {
  "use strict";

  var ctx = null;

  function getContext() {
    if (!ctx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) throw new Error("This browser does not support live audio. Try Chrome, Edge, Firefox, or Safari.");
      ctx = new AC();
    }
    return ctx;
  }

  function isSupported() {
    return !!(window.AudioContext || window.webkitAudioContext) &&
           !!(window.OfflineAudioContext || window.webkitOfflineAudioContext);
  }

  // decodeAudioData with both promise and callback forms (older Safari).
  function decode(arrayBuffer) {
    var c = getContext();
    return new Promise(function (resolve, reject) {
      var done = false;
      var p = c.decodeAudioData(arrayBuffer, function (buf) {
        if (!done) { done = true; resolve(buf); }
      }, function (err) {
        if (!done) { done = true; reject(err || new Error("decode failed")); }
      });
      if (p && typeof p.then === "function") {
        p.then(function (buf) { if (!done) { done = true; resolve(buf); } },
               function (err) { if (!done) { done = true; reject(err); } });
      }
    });
  }

  function decodeFile(file) {
    return file.arrayBuffer().then(decode);
  }

  // Peak envelope: max absolute sample per bucket across channels.
  function computePeaks(buffer, buckets) {
    var n = Math.max(1, buckets | 0);
    var peaks = new Float32Array(n);
    var len = buffer.length;
    var size = len / n;
    var chans = [];
    for (var c = 0; c < buffer.numberOfChannels; c++) chans.push(buffer.getChannelData(c));
    // Stride keeps this fast on long tracks without changing the shape.
    var stride = Math.max(1, Math.floor(size / 64));
    for (var i = 0; i < n; i++) {
      var start = Math.floor(i * size);
      var end = Math.min(len, Math.floor((i + 1) * size));
      var max = 0;
      for (var ch = 0; ch < chans.length; ch++) {
        var data = chans[ch];
        for (var j = start; j < end; j += stride) {
          var v = data[j];
          if (v < 0) v = -v;
          if (v > max) max = v;
        }
      }
      peaks[i] = max;
    }
    return peaks;
  }

  // Draw a bar waveform. progress is 0..1. Played bars use `color`, the rest use `rest`.
  function drawWave(canvas, peaks, progress, color, rest) {
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.clientWidth;
    var h = canvas.clientHeight;
    if (!w || !h) return;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    var g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);

    var barW = 2, gap = 2;
    var count = Math.max(1, Math.floor(w / (barW + gap)));
    var mid = h / 2;
    var norm = 0;
    for (var k = 0; k < peaks.length; k++) if (peaks[k] > norm) norm = peaks[k];
    if (norm < 0.0001) norm = 1;

    for (var i = 0; i < count; i++) {
      var idx = Math.floor(i / count * peaks.length);
      var amp = peaks[idx] / norm;
      var bh = Math.max(2, amp * (h - 4));
      var x = i * (barW + gap);
      g.fillStyle = (i / count) < progress ? color : rest;
      if (g.roundRect) {
        g.beginPath();
        g.roundRect(x, mid - bh / 2, barW, bh, 1);
        g.fill();
      } else {
        g.fillRect(x, mid - bh / 2, barW, bh);
      }
    }
  }

  // Synthetic stereo impulse response: decaying noise, darker toward the tail.
  function makeImpulse(context, seconds, decay) {
    var rate = context.sampleRate;
    var length = Math.max(1, Math.floor(rate * seconds));
    var impulse = context.createBuffer(2, length, rate);
    for (var ch = 0; ch < 2; ch++) {
      var data = impulse.getChannelData(ch);
      var last = 0;
      for (var i = 0; i < length; i++) {
        var t = i / length;
        var white = Math.random() * 2 - 1;
        // One-pole lowpass that closes over time for a warm tail.
        var a = 0.25 + 0.7 * t;
        last = last * a + white * (1 - a);
        data[i] = last * Math.pow(1 - t, decay);
      }
    }
    return impulse;
  }

  // 16-bit PCM WAV from an AudioBuffer.
  function encodeWav(buffer) {
    var chans = Math.min(2, buffer.numberOfChannels);
    var len = buffer.length;
    var rate = buffer.sampleRate;
    var bytes = 44 + len * chans * 2;
    var ab = new ArrayBuffer(bytes);
    var v = new DataView(ab);
    function str(o, s) { for (var i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); }
    str(0, "RIFF"); v.setUint32(4, bytes - 8, true); str(8, "WAVE");
    str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, chans, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * chans * 2, true); v.setUint16(32, chans * 2, true);
    v.setUint16(34, 16, true); str(36, "data"); v.setUint32(40, len * chans * 2, true);

    var data = [];
    for (var c = 0; c < chans; c++) data.push(buffer.getChannelData(c));
    var o = 44;
    for (var i = 0; i < len; i++) {
      for (var ch = 0; ch < chans; ch++) {
        var s = data[ch][i];
        if (s > 1) s = 1; else if (s < -1) s = -1;
        v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        o += 2;
      }
    }
    return new Blob([ab], { type: "audio/wav" });
  }

  function downloadBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }

  function fmtTime(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function baseName(name) {
    return String(name || "track").replace(/\.[^.]+$/, "").replace(/[^\w\-. ]+/g, "_").slice(0, 80) || "track";
  }

  // Paint the filled part of a range input.
  function paintRange(input) {
    var min = parseFloat(input.min || 0), max = parseFloat(input.max || 100);
    var p = (parseFloat(input.value) - min) / (max - min) * 100;
    input.style.setProperty("--p", p + "%");
  }

  // ---- Handoff between pages (mixer -> studio) via IndexedDB ----
  var DB = "audionlabs", STORE = "handoff";

  function openDb() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) return reject(new Error("no indexedDB"));
      var req = indexedDB.open(DB, 1);
      req.onupgradeneeded = function () { req.result.createObjectStore(STORE); };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function saveHandoff(blob, name) {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).put({ blob: blob, name: name, at: Date.now() }, "latest");
        tx.oncomplete = function () { db.close(); resolve(); };
        tx.onerror = function () { db.close(); reject(tx.error); };
      });
    });
  }

  function takeHandoff() {
    return openDb().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        var store = tx.objectStore(STORE);
        var req = store.get("latest");
        var value = null;
        req.onsuccess = function () { value = req.result || null; store.delete("latest"); };
        tx.oncomplete = function () { db.close(); resolve(value); };
        tx.onerror = function () { db.close(); reject(tx.error); };
      });
    });
  }

  window.ALAudio = {
    getContext: getContext,
    isSupported: isSupported,
    decode: decode,
    decodeFile: decodeFile,
    computePeaks: computePeaks,
    drawWave: drawWave,
    makeImpulse: makeImpulse,
    encodeWav: encodeWav,
    downloadBlob: downloadBlob,
    fmtTime: fmtTime,
    baseName: baseName,
    paintRange: paintRange,
    saveHandoff: saveHandoff,
    takeHandoff: takeHandoff
  };
})();
