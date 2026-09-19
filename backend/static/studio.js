/* ============================================================
   AudionLabs live Slowed + Reverb studio
   Plays the track in the browser and applies speed, reverb,
   warmth, and bass in real time. Export renders the same chain
   offline to a WAV. Nothing is uploaded.
   ============================================================ */
(function () {
  "use strict";
  if (window.location.pathname !== "/slowed-reverb") return;

  var A = window.ALAudio;
  function $(id) { return document.getElementById(id); }

  var inputCard = $("st-input-card"), loadingCard = $("st-loading-card"),
      studioCard = $("st-studio-card"), errorCard = $("st-error-card");
  var drop = $("st-drop"), fileInput = $("st-file-input"), browse = $("st-browse");
  var loadingText = $("st-loading-text"), errorText = $("st-error-text"), errorRetry = $("st-error-retry");
  var fileName = $("st-file-name"), removeBtn = $("st-remove");
  var wave = $("st-wave"), playBtn = $("st-play"), timeEl = $("st-time");
  var loopBtn = $("st-loop"), volume = $("st-volume");
  var presetsEl = $("st-presets"), exportBtn = $("st-export"), resetBtn = $("st-reset");
  var sliders = { speed: $("st-speed"), reverb: $("st-reverb"), warmth: $("st-warmth"), bass: $("st-bass") };
  var labels = { speed: $("st-speed-val"), reverb: $("st-reverb-val"), warmth: $("st-warmth-val"), bass: $("st-bass-val") };

  var MAX_BYTES = 200 * 1024 * 1024;
  var TAIL_SECONDS = 3.2;

  // Signature matches the AudionLabs server render: 0.9x speed and a 6 kHz low-pass.
  var PRESETS = {
    signature: { speed: 0.90, reverb: 30, warmth: 52, bass: 0 },
    deep:      { speed: 0.80, reverb: 45, warmth: 60, bass: 3 },
    nightcore: { speed: 1.25, reverb: 10, warmth: 0,  bass: 0 },
    spedup:    { speed: 1.15, reverb: 0,  warmth: 0,  bass: 0 },
    original:  { speed: 1.00, reverb: 0,  warmth: 0,  bass: 0 }
  };

  var params = copy(PRESETS.signature);
  var buffer = null, peaks = null, trackName = "track";
  var chain = null, volumeNode = null, src = null;
  var playing = false, offset = 0, startedAt = 0, looping = false;
  var raf = 0, scrubbing = false, scrubFrac = 0;

  function copy(o) { return { speed: o.speed, reverb: o.reverb, warmth: o.warmth, bass: o.bass }; }
  function warmthToHz(w) { return 20000 * Math.pow(0.1, w / 100); }
  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function showOnly(card) {
    [inputCard, loadingCard, studioCard, errorCard].forEach(function (c) { c.hidden = c !== card; });
  }

  function fail(message) {
    stop();
    errorText.textContent = message;
    showOnly(errorCard);
  }

  // ---- Audio graph (shared by live playback and offline export) ----
  function buildChain(context, p) {
    var input = context.createGain();
    var bass = context.createBiquadFilter();
    bass.type = "lowshelf"; bass.frequency.value = 110;
    var lp = context.createBiquadFilter();
    lp.type = "lowpass"; lp.Q.value = 0.707;
    var dry = context.createGain(), wet = context.createGain();
    var conv = context.createConvolver();
    conv.buffer = A.makeImpulse(context, TAIL_SECONDS, 2.6);
    var limiter = context.createDynamicsCompressor();
    limiter.threshold.value = -3; limiter.knee.value = 0; limiter.ratio.value = 20;
    limiter.attack.value = 0.002; limiter.release.value = 0.2;
    var output = context.createGain();
    output.gain.value = 0.92;

    input.connect(bass); bass.connect(lp);
    lp.connect(dry); dry.connect(limiter);
    lp.connect(conv); conv.connect(wet); wet.connect(limiter);
    limiter.connect(output);

    function apply(q, smooth) {
      var r = q.reverb / 100;
      var targets = [
        [bass.gain, q.bass],
        [lp.frequency, warmthToHz(q.warmth)],
        [dry.gain, 1 - 0.35 * r],
        [wet.gain, 1.25 * r]
      ];
      targets.forEach(function (t) {
        if (smooth) t[0].setTargetAtTime(t[1], context.currentTime, 0.03);
        else t[0].value = t[1];
      });
    }
    apply(p, false);
    return { input: input, output: output, apply: apply };
  }

  function ensureLiveGraph() {
    var ctx = A.getContext();
    if (!chain) {
      chain = buildChain(ctx, params);
      volumeNode = ctx.createGain();
      volumeNode.gain.value = parseFloat(volume.value) / 100;
      chain.output.connect(volumeNode);
      volumeNode.connect(ctx.destination);
    }
    return ctx;
  }

  // ---- Transport ----
  function position() {
    if (!buffer) return 0;
    if (!playing) return offset;
    var ctx = A.getContext();
    var p = offset + (ctx.currentTime - startedAt) * params.speed;
    if (looping) p = p % buffer.duration;
    return Math.min(p, buffer.duration);
  }

  function play() {
    if (!buffer || playing) return;
    var ctx = ensureLiveGraph();
    if (ctx.state === "suspended") ctx.resume();
    if (offset >= buffer.duration - 0.01) offset = 0;
    var node = ctx.createBufferSource();
    node.buffer = buffer;
    node.playbackRate.value = params.speed;
    node.loop = looping;
    node.connect(chain.input);
    node.onended = function () {
      if (src !== node) return;
      playing = false; src = null; offset = 0;
      syncTransport(); draw();
    };
    node.start(0, offset);
    src = node; startedAt = ctx.currentTime; playing = true;
    syncTransport(); tick();
  }

  function stop() {
    if (src) {
      offset = position();
      src.onended = null;
      try { src.stop(); } catch (e) {}
      try { src.disconnect(); } catch (e2) {}
      src = null;
    }
    playing = false;
    cancelAnimationFrame(raf);
    syncTransport();
  }

  function seek(seconds) {
    if (!buffer) return;
    var was = playing;
    stop();
    offset = Math.max(0, Math.min(seconds, buffer.duration - 0.01));
    if (was) play(); else draw();
  }

  function setSpeed(v) {
    if (playing && src) {
      offset = position();
      startedAt = A.getContext().currentTime;
      src.playbackRate.setValueAtTime(v, startedAt);
    }
    params.speed = v;
  }

  function syncTransport() {
    playBtn.classList.toggle("is-playing", playing);
    playBtn.setAttribute("aria-label", playing ? "Pause" : "Play");
  }

  function tick() {
    draw();
    if (playing) raf = requestAnimationFrame(tick);
  }

  function draw() {
    if (!buffer || !peaks) return;
    var frac = scrubbing ? scrubFrac : position() / buffer.duration;
    A.drawWave(wave, peaks, frac, cssVar("--accent", "#6E3FF3"), cssVar("--wave-rest", "rgba(0,0,0,.16)"));
    // Times are shown at the current speed, so the total is the length of the export.
    var shown = (scrubbing ? scrubFrac * buffer.duration : position()) / params.speed;
    timeEl.textContent = A.fmtTime(shown) + " / " + A.fmtTime(buffer.duration / params.speed);
  }

  // ---- Controls ----
  function renderLabels() {
    labels.speed.textContent = params.speed.toFixed(2) + "x";
    labels.reverb.textContent = Math.round(params.reverb) + "%";
    var hz = warmthToHz(params.warmth);
    labels.warmth.textContent = params.warmth <= 0 ? "Off" : (hz / 1000).toFixed(1) + " kHz";
    labels.bass.textContent = "+" + Math.round(params.bass) + " dB";
  }

  function syncSliders() {
    sliders.speed.value = params.speed;
    sliders.reverb.value = params.reverb;
    sliders.warmth.value = params.warmth;
    sliders.bass.value = params.bass;
    Object.keys(sliders).forEach(function (k) { A.paintRange(sliders[k]); });
    renderLabels();
  }

  function markPreset() {
    var match = null;
    Object.keys(PRESETS).forEach(function (k) {
      var p = PRESETS[k];
      if (Math.abs(p.speed - params.speed) < 0.005 && p.reverb === Math.round(params.reverb) &&
          p.warmth === Math.round(params.warmth) && p.bass === Math.round(params.bass)) match = k;
    });
    presetsEl.querySelectorAll("[data-preset]").forEach(function (b) {
      var on = b.getAttribute("data-preset") === match;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function applyParams(smooth) {
    if (chain) chain.apply(params, smooth);
    renderLabels(); markPreset(); draw();
  }

  function usePreset(name) {
    var p = PRESETS[name];
    if (!p) return;
    setSpeed(p.speed);
    params.reverb = p.reverb; params.warmth = p.warmth; params.bass = p.bass;
    syncSliders(); applyParams(true);
  }

  Object.keys(sliders).forEach(function (key) {
    sliders[key].addEventListener("input", function () {
      var v = parseFloat(sliders[key].value);
      if (key === "speed") setSpeed(v); else params[key] = v;
      A.paintRange(sliders[key]);
      applyParams(true);
    });
  });

  presetsEl.addEventListener("click", function (e) {
    var b = e.target.closest("[data-preset]");
    if (b) usePreset(b.getAttribute("data-preset"));
  });

  resetBtn.addEventListener("click", function () { usePreset("original"); });

  playBtn.addEventListener("click", function () { if (playing) stop(); else play(); });

  loopBtn.addEventListener("click", function () {
    if (playing) { offset = position(); startedAt = A.getContext().currentTime; }
    looping = !looping;
    if (src) src.loop = looping;
    loopBtn.classList.toggle("on", looping);
    loopBtn.setAttribute("aria-pressed", looping ? "true" : "false");
  });

  volume.addEventListener("input", function () {
    A.paintRange(volume);
    if (volumeNode) volumeNode.gain.setTargetAtTime(parseFloat(volume.value) / 100, A.getContext().currentTime, 0.02);
  });

  // Click or drag on the waveform to seek.
  function fracFromEvent(e) {
    var r = wave.getBoundingClientRect();
    return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
  }
  wave.addEventListener("pointerdown", function (e) {
    if (!buffer) return;
    scrubbing = true; scrubFrac = fracFromEvent(e);
    try { wave.setPointerCapture(e.pointerId); } catch (err) {}
    draw();
  });
  wave.addEventListener("pointermove", function (e) {
    if (!scrubbing) return;
    scrubFrac = fracFromEvent(e); draw();
  });
  function endScrub() {
    if (!scrubbing) return;
    scrubbing = false;
    seek(scrubFrac * buffer.duration);
  }
  wave.addEventListener("pointerup", endScrub);
  wave.addEventListener("pointercancel", endScrub);
  wave.addEventListener("keydown", function (e) {
    if (!buffer) return;
    if (e.key === "ArrowRight") { seek(position() + 5); e.preventDefault(); }
    if (e.key === "ArrowLeft") { seek(position() - 5); e.preventDefault(); }
  });

  document.addEventListener("keydown", function (e) {
    if (e.code !== "Space" || !buffer || studioCard.hidden) return;
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "button" || tag === "a" || tag === "textarea") return;
    e.preventDefault();
    if (playing) stop(); else play();
  });

  window.addEventListener("resize", draw);

  // ---- Export ----
  function exportName() {
    var suffix = "";
    if (params.speed < 0.995) suffix += "_slowed";
    else if (params.speed > 1.005) suffix += "_spedup";
    if (params.reverb > 0) suffix += "_reverb";
    return A.baseName(trackName) + (suffix || "_remix") + ".wav";
  }

  function render() {
    var OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    var rate = buffer.sampleRate;
    var tail = params.reverb > 0 ? TAIL_SECONDS : 0;
    var length = Math.ceil((buffer.duration / params.speed + tail) * rate);
    var off = new OAC(2, length, rate);
    var c = buildChain(off, params);
    var node = off.createBufferSource();
    node.buffer = buffer;
    node.playbackRate.value = params.speed;
    node.connect(c.input);
    c.output.connect(off.destination);
    node.start(0);
    return off.startRendering();
  }

  exportBtn.addEventListener("click", function () {
    if (!buffer || exportBtn.disabled) return;
    var label = exportBtn.textContent;
    exportBtn.disabled = true;
    exportBtn.textContent = "Rendering...";
    // Let the label paint before the render ties up the thread.
    setTimeout(function () {
      render().then(function (out) {
        A.downloadBlob(A.encodeWav(out), exportName());
      }).catch(function () {
        fail("The export ran out of memory. Try a shorter track or close other tabs.");
      }).then(function () {
        exportBtn.disabled = false;
        exportBtn.textContent = label;
      });
    }, 30);
  });

  // ---- Loading ----
  function unlockAudio() {
    try {
      var ctx = A.getContext();
      if (ctx.state === "suspended") ctx.resume();
    } catch (e) {}
  }

  function loadBlob(blob, name) {
    if (!A.isSupported()) { fail("This browser does not support live audio. Try Chrome, Edge, Firefox, or Safari."); return; }
    if (blob.size > MAX_BYTES) { fail("That file is over 200 MB. Try a shorter or compressed version."); return; }
    stop();
    buffer = null; peaks = null; offset = 0;
    trackName = name || "track";
    loadingText.textContent = "Reading " + trackName;
    showOnly(loadingCard);

    blob.arrayBuffer().then(A.decode).then(function (decoded) {
      buffer = decoded;
      peaks = A.computePeaks(decoded, 1400);
      fileName.textContent = trackName;
      showOnly(studioCard);
      syncSliders(); A.paintRange(volume); markPreset();
      ensureLiveGraph(); chain.apply(params, false);
      draw();
      play();
    }).catch(function () {
      fail("That file could not be read as audio. Try an MP3, WAV, M4A, OGG, or FLAC.");
    });
  }

  function reset() {
    stop();
    buffer = null; peaks = null; offset = 0;
    fileInput.value = "";
    showOnly(inputCard);
  }

  drop.addEventListener("click", function () { unlockAudio(); fileInput.click(); });
  browse.addEventListener("click", function (e) { e.stopPropagation(); unlockAudio(); fileInput.click(); });
  fileInput.addEventListener("change", function () {
    unlockAudio();
    if (fileInput.files.length) loadBlob(fileInput.files[0], fileInput.files[0].name);
  });
  drop.addEventListener("dragover", function (e) { e.preventDefault(); drop.classList.add("drag-over"); });
  drop.addEventListener("dragleave", function () { drop.classList.remove("drag-over"); });
  drop.addEventListener("drop", function (e) {
    e.preventDefault(); drop.classList.remove("drag-over"); unlockAudio();
    var f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) loadBlob(f, f.name);
  });
  removeBtn.addEventListener("click", reset);
  errorRetry.addEventListener("click", reset);

  syncSliders();
  A.paintRange(volume);

  // A mix sent over from the stem mixer.
  if (/[?&]from=mixer/.test(window.location.search)) {
    A.takeHandoff().then(function (item) {
      if (item && item.blob) loadBlob(item.blob, item.name || "mix.wav");
    }).catch(function () {});
    if (window.history.replaceState) window.history.replaceState(null, "", "/slowed-reverb");
  }

  // Test hook. Lets automated checks read state without reaching into closures.
  window.__alStudio = {
    state: function () {
      return { loaded: !!buffer, playing: playing, position: position(), duration: buffer ? buffer.duration : 0,
               params: copy(params), looping: looping };
    },
    render: function () { return render(); },
    loadBlob: loadBlob
  };
})();
