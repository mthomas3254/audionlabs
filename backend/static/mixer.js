/* ============================================================
   AudionLabs live stem mixer
   Loads the separated stems, plays them in sample-accurate sync,
   and lets the listener mute, solo, and rebalance each one live.
   The current balance can be exported as a WAV or sent to the
   Slowed + Reverb studio.
   ============================================================ */
(function () {
  "use strict";

  var A = window.ALAudio;
  var ORDER = ["vocals", "drums", "bass", "other"];
  var LABELS = { vocals: "Vocals", drums: "Drums", bass: "Bass", other: "Other" };
  var COLORS = { vocals: "--vocals", drums: "--drums", bass: "--bass", other: "--other" };

  var ICON_PLAY = '<svg class="i ico-play" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none"/></svg>' +
                  '<svg class="i ico-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14M16 5v14" stroke-width="3"/></svg>';

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function mount(root, stems, opts) {
    opts = opts || {};
    var trackName = A.baseName(opts.name || "track");
    // Only the four known stems are rendered, so no server text reaches the markup.
    var names = ORDER.filter(function (k) { return stems[k] && typeof stems[k].url === "string"; });

    var tracks = {};        // name -> { buffer, peaks, gain, vol, mute, solo, row, canvas, ... }
    var duration = 0, sampleRate = 44100;
    var playing = false, offset = 0, startedAt = 0, sources = [];
    var master = null, raf = 0, destroyed = false;
    var scrubbing = false, scrubFrac = 0;

    root.innerHTML = "";
    var box = el("div", "mx");
    var loadBox = el("div", "mx-load",
      '<b class="mx-load-text">Loading the live mixer</b><div class="bar"><i class="mx-load-fill"></i></div>' +
      '<small>You can download the stems below while this loads.</small>');
    var gateBox = el("div", "mx-gate",
      '<p>The live mixer holds all four stems in memory. On this device it opens when you ask for it.</p>' +
      '<button class="btn btn-ink btn-sm" type="button">Open live mixer</button>');
    var failBox = el("div", "mx-fail");
    var body = el("div", "mx-body");
    gateBox.hidden = true; failBox.hidden = true; body.hidden = true; loadBox.hidden = true;
    box.appendChild(gateBox); box.appendChild(loadBox); box.appendChild(failBox); box.appendChild(body);
    root.appendChild(box);

    // ---- Build the mixer UI ----
    var top = el("div", "mx-top");
    var playBtn = el("button", "round-btn mx-play", ICON_PLAY);
    playBtn.type = "button"; playBtn.setAttribute("aria-label", "Play");
    var timeEl = el("span", "mx-time", "0:00 / 0:00");
    var quick = el("div", "mx-quick",
      '<button type="button" class="chip-btn on" data-q="full" aria-pressed="true">Full mix</button>' +
      '<button type="button" class="chip-btn" data-q="inst" aria-pressed="false">Instrumental</button>' +
      '<button type="button" class="chip-btn" data-q="acap" aria-pressed="false">Acapella</button>');
    top.appendChild(playBtn); top.appendChild(timeEl); top.appendChild(quick);
    var rows = el("div", "mx-rows");
    var foot = el("div", "mx-foot");
    var exportBtn = el("button", "btn btn-ink", "Download this mix");
    exportBtn.type = "button";
    var sendBtn = el("button", "btn btn-ghost", "Open mix in Slowed + Reverb");
    sendBtn.type = "button";
    foot.appendChild(exportBtn); foot.appendChild(sendBtn);
    body.appendChild(top); body.appendChild(rows); body.appendChild(foot);

    names.forEach(function (name) {
      var label = LABELS[name] || name;
      var row = el("div", "mx-row");
      row.setAttribute("data-stem", name);
      var head = el("div", "mx-head",
        '<span class="mx-name"><i class="dot" style="background:var(' + (COLORS[name] || "--accent") + ')"></i>' + label + '</span>' +
        '<button type="button" class="ms" data-act="mute" aria-pressed="false" aria-label="Mute ' + label + '">M</button>' +
        '<button type="button" class="ms" data-act="solo" aria-pressed="false" aria-label="Solo ' + label + '">S</button>' +
        '<input class="range mx-vol" type="range" min="0" max="150" step="1" value="100" aria-label="' + label + ' volume">' +
        '<span class="mx-val">100%</span>');
      var canvas = el("canvas", "mx-wave");
      canvas.setAttribute("aria-hidden", "true");
      row.appendChild(head); row.appendChild(canvas);
      rows.appendChild(row);
      tracks[name] = {
        buffer: null, peaks: null, gain: null, vol: 1, mute: false, solo: false,
        row: row, canvas: canvas, slider: head.querySelector(".mx-vol"), val: head.querySelector(".mx-val"),
        muteBtn: head.querySelector('[data-act="mute"]'), soloBtn: head.querySelector('[data-act="solo"]'),
        color: COLORS[name] || "--accent"
      };
      A.paintRange(tracks[name].slider);
    });

    // ---- Gain logic ----
    function anySolo() {
      return names.some(function (n) { return tracks[n].solo; });
    }
    function effective(name) {
      var t = tracks[name];
      if (anySolo()) return t.solo ? t.vol : 0;
      return t.mute ? 0 : t.vol;
    }
    function applyGains() {
      var ctx = master ? A.getContext() : null;
      names.forEach(function (n) {
        var t = tracks[n];
        if (t.gain && ctx) t.gain.gain.setTargetAtTime(effective(n), ctx.currentTime, 0.015);
        t.muteBtn.classList.toggle("on", t.mute);
        t.muteBtn.setAttribute("aria-pressed", t.mute ? "true" : "false");
        t.soloBtn.classList.toggle("on", t.solo);
        t.soloBtn.setAttribute("aria-pressed", t.solo ? "true" : "false");
        t.row.classList.toggle("is-silent", effective(n) === 0);
      });
      markQuick();
      draw();
    }
    function mixKind() {
      var solo = names.filter(function (n) { return tracks[n].solo; });
      var muted = names.filter(function (n) { return tracks[n].mute; });
      var flat = names.every(function (n) { return tracks[n].vol === 1; });
      if (!flat) return "custom";
      if (!solo.length && !muted.length) return "full";
      if (!solo.length && muted.length === 1 && muted[0] === "vocals") return "inst";
      if (solo.length === 1 && solo[0] === "vocals") return "acap";
      return "custom";
    }
    function markQuick() {
      var kind = mixKind();
      quick.querySelectorAll("[data-q]").forEach(function (b) {
        var on = b.getAttribute("data-q") === kind;
        b.classList.toggle("on", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }
    function setQuick(kind) {
      names.forEach(function (n) {
        var t = tracks[n];
        t.vol = 1; t.mute = false; t.solo = false;
        t.slider.value = 100; t.val.textContent = "100%"; A.paintRange(t.slider);
      });
      if (kind === "inst" && tracks.vocals) tracks.vocals.mute = true;
      if (kind === "acap" && tracks.vocals) tracks.vocals.solo = true;
      applyGains();
    }

    // ---- Transport ----
    function position() {
      if (!playing) return offset;
      var p = offset + Math.max(0, A.getContext().currentTime - startedAt);
      return Math.min(p, duration);
    }
    function stopSources() {
      sources.forEach(function (s) {
        s.onended = null;
        try { s.stop(); } catch (e) {}
        try { s.disconnect(); } catch (e2) {}
      });
      sources = [];
    }
    function play() {
      if (playing || !duration) return;
      var ctx = A.getContext();
      if (ctx.state === "suspended") ctx.resume();
      if (offset >= duration - 0.01) offset = 0;
      // One shared start time keeps every stem sample-aligned.
      var when = ctx.currentTime + 0.06;
      names.forEach(function (n) {
        var t = tracks[n];
        if (!t.buffer || offset >= t.buffer.duration) return;
        var s = ctx.createBufferSource();
        s.buffer = t.buffer;
        s.connect(t.gain);
        s.start(when, offset);
        sources.push(s);
      });
      startedAt = when; playing = true;
      sync(); tick();
    }
    function pause() {
      offset = position();
      stopSources();
      playing = false;
      cancelAnimationFrame(raf);
      sync(); draw();
    }
    function seek(seconds) {
      var was = playing;
      if (was) { stopSources(); playing = false; cancelAnimationFrame(raf); }
      offset = Math.max(0, Math.min(seconds, duration - 0.01));
      if (was) play(); else draw();
    }
    function sync() {
      playBtn.classList.toggle("is-playing", playing);
      playBtn.setAttribute("aria-label", playing ? "Pause" : "Play");
    }
    function tick() {
      if (destroyed) return;
      if (playing && position() >= duration) {
        stopSources(); playing = false; offset = 0; sync(); draw();
        return;
      }
      draw();
      if (playing) raf = requestAnimationFrame(tick);
    }
    function draw() {
      if (!duration) return;
      var frac = scrubbing ? scrubFrac : position() / duration;
      var rest = cssVar("--wave-rest", "rgba(0,0,0,.16)");
      names.forEach(function (n) {
        var t = tracks[n];
        if (t.peaks) A.drawWave(t.canvas, t.peaks, frac, cssVar(t.color, "#6E3FF3"), rest);
      });
      timeEl.textContent = A.fmtTime(frac * duration) + " / " + A.fmtTime(duration);
    }

    // ---- Events ----
    playBtn.addEventListener("click", function () { if (playing) pause(); else play(); });
    quick.addEventListener("click", function (e) {
      var b = e.target.closest("[data-q]");
      if (b) setQuick(b.getAttribute("data-q"));
    });
    rows.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b) return;
      var t = tracks[b.closest(".mx-row").getAttribute("data-stem")];
      if (b.getAttribute("data-act") === "mute") { t.mute = !t.mute; if (t.mute) t.solo = false; }
      else { t.solo = !t.solo; if (t.solo) t.mute = false; }
      applyGains();
    });
    rows.addEventListener("input", function (e) {
      if (!e.target.classList.contains("mx-vol")) return;
      var t = tracks[e.target.closest(".mx-row").getAttribute("data-stem")];
      t.vol = parseFloat(e.target.value) / 100;
      t.val.textContent = Math.round(t.vol * 100) + "%";
      A.paintRange(e.target);
      applyGains();
    });
    function fracFrom(canvas, e) {
      var r = canvas.getBoundingClientRect();
      return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    }
    rows.addEventListener("pointerdown", function (e) {
      if (!e.target.classList.contains("mx-wave") || !duration) return;
      scrubbing = true; scrubFrac = fracFrom(e.target, e);
      try { e.target.setPointerCapture(e.pointerId); } catch (err) {}
      draw();
    });
    rows.addEventListener("pointermove", function (e) {
      if (!scrubbing || !e.target.classList.contains("mx-wave")) return;
      scrubFrac = fracFrom(e.target, e); draw();
    });
    function endScrub() {
      if (!scrubbing) return;
      scrubbing = false; seek(scrubFrac * duration);
    }
    rows.addEventListener("pointerup", endScrub);
    rows.addEventListener("pointercancel", endScrub);
    function onResize() { draw(); }
    window.addEventListener("resize", onResize);

    // ---- Export ----
    function renderMix() {
      var OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      var off = new OAC(2, Math.ceil(duration * sampleRate), sampleRate);
      names.forEach(function (n) {
        var t = tracks[n], g = effective(n);
        if (!t.buffer || g === 0) return;
        var s = off.createBufferSource(), gain = off.createGain();
        s.buffer = t.buffer; gain.gain.value = g;
        s.connect(gain); gain.connect(off.destination);
        s.start(0);
      });
      return off.startRendering().then(tame);
    }
    // Stems can sum past full scale, more so with volumes above 100%.
    // Scale the whole render down only when it would otherwise clip.
    function tame(buf) {
      var peak = 0, c, i, d;
      for (c = 0; c < buf.numberOfChannels; c++) {
        d = buf.getChannelData(c);
        for (i = 0; i < d.length; i++) {
          var v = d[i] < 0 ? -d[i] : d[i];
          if (v > peak) peak = v;
        }
      }
      if (peak > 0.98) {
        var k = 0.98 / peak;
        for (c = 0; c < buf.numberOfChannels; c++) {
          d = buf.getChannelData(c);
          for (i = 0; i < d.length; i++) d[i] *= k;
        }
      }
      return buf;
    }
    function mixName() {
      var kind = mixKind();
      var suffix = kind === "inst" ? "_instrumental" : kind === "acap" ? "_acapella" : "_mix";
      return trackName + suffix + ".wav";
    }
    function busy(btn, text, work) {
      if (btn.disabled) return;
      var label = btn.textContent;
      btn.disabled = true; btn.textContent = text;
      setTimeout(function () {
        work().catch(function () {
          failBox.textContent = "The mix could not be rendered. Try closing other tabs and run it again.";
          failBox.hidden = false;
        }).then(function () { btn.disabled = false; btn.textContent = label; });
      }, 30);
    }
    exportBtn.addEventListener("click", function () {
      busy(exportBtn, "Rendering...", function () {
        return renderMix().then(function (out) { A.downloadBlob(A.encodeWav(out), mixName()); });
      });
    });
    sendBtn.addEventListener("click", function () {
      busy(sendBtn, "Preparing...", function () {
        return renderMix().then(function (out) {
          return A.saveHandoff(A.encodeWav(out), mixName());
        }).then(function () {
          if (playing) pause();
          window.location.href = "/slowed-reverb?from=mixer";
        });
      });
    });

    // ---- Load stems ----
    function load() {
      gateBox.hidden = true; loadBox.hidden = false;
      var fill = loadBox.querySelector(".mx-load-fill");
      var text = loadBox.querySelector(".mx-load-text");
      var ctx;
      try { ctx = A.getContext(); } catch (e) { return showFail(e.message); }
      master = ctx.createGain();
      // A fast limiter keeps the live preview from clipping when stems sum hot.
      var limiter = ctx.createDynamicsCompressor();
      limiter.threshold.value = -2; limiter.knee.value = 0; limiter.ratio.value = 20;
      limiter.attack.value = 0.002; limiter.release.value = 0.15;
      master.connect(limiter);
      limiter.connect(ctx.destination);

      var i = 0;
      function next() {
        if (destroyed) return Promise.resolve();
        if (i >= names.length) return Promise.resolve();
        var name = names[i];
        text.textContent = "Loading " + (LABELS[name] || name).toLowerCase() + " (" + (i + 1) + " of " + names.length + ")";
        return fetch(stems[name].url).then(function (res) {
          if (!res.ok) throw new Error("fetch");
          return res.arrayBuffer();
        }).then(A.decode).then(function (buf) {
          var t = tracks[name];
          t.buffer = buf;
          t.peaks = A.computePeaks(buf, 900);
          t.gain = ctx.createGain();
          t.gain.connect(master);
          duration = Math.max(duration, buf.duration);
          sampleRate = buf.sampleRate;
          i++;
          fill.style.width = Math.round(i / names.length * 100) + "%";
          return next();
        });
      }
      next().then(function () {
        if (destroyed) return;
        loadBox.hidden = true; body.hidden = false;
        applyGains();
        requestAnimationFrame(draw);
      }).catch(function () {
        showFail("The live mixer could not load these stems. The download links below still work.");
      });
    }
    function showFail(message) {
      loadBox.hidden = true; body.hidden = true; gateBox.hidden = true;
      failBox.textContent = message; failBox.hidden = false;
    }

    function destroy() {
      destroyed = true;
      stopSources();
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      names.forEach(function (n) {
        var t = tracks[n];
        if (t.gain) { try { t.gain.disconnect(); } catch (e) {} }
        t.buffer = null; t.peaks = null;
      });
      if (master) { try { master.disconnect(); } catch (e2) {} }
      root.innerHTML = "";
    }

    if (!A.isSupported()) {
      showFail("This browser does not support the live mixer. The download links below still work.");
    } else if (navigator.deviceMemory && navigator.deviceMemory <= 2 && !opts.force) {
      gateBox.hidden = false;
      gateBox.querySelector("button").addEventListener("click", function () {
        try { var c = A.getContext(); if (c.state === "suspended") c.resume(); } catch (e) {}
        load();
      });
    } else {
      load();
    }

    return {
      destroy: destroy,
      // Test hook for automated checks.
      state: function () {
        return {
          ready: !body.hidden, playing: playing, position: position(), duration: duration,
          kind: mixKind(),
          gains: names.reduce(function (o, n) { o[n] = effective(n); return o; }, {})
        };
      },
      renderMix: renderMix
    };
  }

  window.ALMixer = { mount: mount };
})();
