/* ============================================================
   AudionLabs — Unified Frontend Logic
   Auto-detects page via pathname and binds the right handlers.
   ============================================================ */

(function () {
  "use strict";

  var page = window.location.pathname;

  // --- Nav indicator (all pages) ---
  function positionNavIndicator() {
    var active = document.querySelector(".nav-item.active");
    var indicator = document.querySelector(".nav-indicator");
    if (!active || !indicator) return;
    indicator.style.width = active.offsetWidth + "px";
    indicator.style.left = active.offsetLeft + "px";
  }
  positionNavIndicator();
  window.addEventListener("resize", positionNavIndicator);

  // ================================================================
  //  STEMS + SLOWED-REVERB PAGES (upload → /process_audio)
  // ================================================================
  if (page === "/stems" || page === "/slowed-reverb") {
    var dropZone      = document.getElementById("drop-zone");
    var fileInput     = document.getElementById("file-input");
    var browseBtn     = document.getElementById("browse-btn");
    var fileInfo      = document.getElementById("file-info");
    var fileNameEl    = document.getElementById("file-name");
    var removeFileBtn = document.getElementById("remove-file-btn");

    var optionsCard   = document.getElementById("options-card");
    var optStems      = document.getElementById("opt-stems");
    var optSlowed     = document.getElementById("opt-slowed");
    var processBtn    = document.getElementById("process-btn");

    var statusCard    = document.getElementById("status-card");
    var statusStage   = document.getElementById("status-stage");
    var statusText    = document.getElementById("status-text");
    var progressFill  = document.getElementById("progress-fill");

    var resultsCard   = document.getElementById("results-card");
    var resultStems   = document.getElementById("results-stems");
    var resultSlowed  = document.getElementById("results-slowed");
    var newUploadBtn  = document.getElementById("new-upload-btn");

    var errorCard     = document.getElementById("error-card");
    var errorText     = document.getElementById("error-text");
    var errorRetryBtn = document.getElementById("error-retry-btn");

    var selectedFile = null;
    var progressTimer = null;

    function show(el) { el.hidden = false; }
    function hide(el) { el.hidden = true; }

    function setProgress(pct) {
      progressFill.style.width = Math.min(pct, 100) + "%";
    }

    function clearProgressTimer() {
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
    }

    function resetToUpload() {
      selectedFile = null;
      fileInput.value = "";
      clearProgressTimer();
      setProgress(0);

      hide(fileInfo);
      hide(optionsCard);
      hide(statusCard);
      hide(resultsCard);
      hide(errorCard);
      show(dropZone);

      resultStems.querySelector(".result-links").innerHTML = "";
      resultSlowed.querySelector(".result-links").innerHTML = "";
      hide(resultStems);
      hide(resultSlowed);

      if (optStems) optStems.checked = page === "/stems";
      if (optSlowed) optSlowed.checked = page === "/slowed-reverb";
    }

    function setFile(file) {
      if (!file) return;
      var ext = file.name.split(".").pop().toLowerCase();
      if (ext !== "mp3" && ext !== "wav") {
        showUploadError("Only MP3 and WAV files are supported.");
        return;
      }
      selectedFile = file;
      fileNameEl.textContent = file.name;
      show(fileInfo);
      show(optionsCard);
    }

    function showUploadError(message) {
      clearProgressTimer();
      hide(statusCard);
      hide(resultsCard);
      errorText.textContent = message;
      show(errorCard);
    }

    function makeDownloadLink(url, label) {
      var a = document.createElement("a");
      a.href = url;
      a.textContent = label;
      return a;
    }

    // --- Progress simulation ---
    function startProgressSimulation(wantsStems, wantsSlowed) {
      var stages = [
        ["Uploading your track...", 8, 1500]
      ];

      if (wantsStems) {
        stages.push(["Separating stems...", 62, 50000]);
      }
      if (wantsSlowed) {
        stages.push(["Applying slowed reverb...", wantsStems ? 82 : 78, 10000]);
      }
      stages.push(["Finalizing...", 94, 3000]);

      var stageIndex = 0;
      var currentPct = 0;

      function runStage() {
        if (stageIndex >= stages.length) return;

        var label = stages[stageIndex][0];
        var targetPct = stages[stageIndex][1];
        var duration = stages[stageIndex][2];
        statusStage.textContent = label;

        var startPct = currentPct;
        var delta = targetPct - startPct;
        var intervalMs = 120;
        var steps = Math.max(1, Math.round(duration / intervalMs));
        var step = 0;

        clearProgressTimer();
        progressTimer = setInterval(function () {
          step++;
          var t = step / steps;
          var eased = 1 - Math.pow(1 - t, 2);
          currentPct = startPct + delta * eased;
          setProgress(currentPct);

          if (step >= steps) {
            clearProgressTimer();
            stageIndex++;
            runStage();
          }
        }, intervalMs);
      }

      runStage();
    }

    // --- Drag & Drop ---
    dropZone.addEventListener("click", function () { fileInput.click(); });

    browseBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      fileInput.click();
    });

    fileInput.addEventListener("change", function () {
      if (fileInput.files.length > 0) setFile(fileInput.files[0]);
    });

    dropZone.addEventListener("dragover", function (e) {
      e.preventDefault();
      dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", function () {
      dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", function (e) {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
      if (e.dataTransfer.files.length > 0) setFile(e.dataTransfer.files[0]);
    });

    removeFileBtn.addEventListener("click", resetToUpload);

    // --- Process ---
    processBtn.addEventListener("click", async function () {
      if (!selectedFile) return;

      var wantsStems = optStems ? optStems.checked : false;
      var wantsSlowed = optSlowed ? optSlowed.checked : false;

      if (!wantsStems && !wantsSlowed) {
        showUploadError("Select at least one processing option.");
        return;
      }

      hide(optionsCard);
      hide(dropZone);
      hide(fileInfo);
      hide(errorCard);
      hide(resultsCard);

      setProgress(0);
      statusStage.textContent = "Uploading your track...";
      statusText.textContent = "This may take a minute";
      show(statusCard);

      startProgressSimulation(wantsStems, wantsSlowed);

      var form = new FormData();
      form.append("file", selectedFile);
      form.append("split_stems_flag", wantsStems.toString());
      form.append("slowed_reverb_flag", wantsSlowed.toString());

      try {
        var res = await fetch("/process_audio", {
          method: "POST",
          body: form,
        });

        if (!res.ok) {
          var body = await res.json().catch(function () { return {}; });
          throw new Error(body.detail || "Server error (" + res.status + ")");
        }

        var data = await res.json();

        clearProgressTimer();
        statusStage.textContent = "Done!";
        setProgress(100);

        setTimeout(function () { renderUploadResults(data); }, 400);
      } catch (err) {
        showUploadError(err.message || "Something went wrong. Please try again.");
      }
    });

    // --- Render results ---
    function renderUploadResults(data) {
      hide(statusCard);

      if (data.stems) {
        var container = resultStems.querySelector(".result-links");
        container.innerHTML = "";
        var labels = { vocals: "Vocals", drums: "Drums", bass: "Bass", other: "Other" };
        for (var key in data.stems) {
          var stem = data.stems[key];
          var a = makeDownloadLink(stem.url, labels[key] || key);
          a.download = stem.download_name || "";
          container.appendChild(a);
        }
        show(resultStems);
      }

      if (data.slowed_mix) {
        var container2 = resultSlowed.querySelector(".result-links");
        container2.innerHTML = "";
        var a2 = makeDownloadLink(data.slowed_mix.url, "Slowed + Reverb Mix");
        a2.download = data.slowed_mix.download_name || "";
        container2.appendChild(a2);
        show(resultSlowed);
      }

      show(resultsCard);
    }

    newUploadBtn.addEventListener("click", resetToUpload);
    errorRetryBtn.addEventListener("click", resetToUpload);
  }

  // ================================================================
  //  YOUTUBE DOWNLOADER PAGE
  // ================================================================
  if (page === "/youtube-downloader") {
    var urlInput          = document.getElementById("url-input");
    var downloadBtn       = document.getElementById("download-btn");
    var formatBtns        = document.querySelectorAll(".format-btn");
    var progressContainer = document.getElementById("progress-container");
    var dlProgressFill    = document.getElementById("progress-fill");
    var progressTextEl    = document.getElementById("progress-text");
    var errorMsg          = document.getElementById("error-msg");
    var resultCard        = document.getElementById("result-card");
    var resultIcon        = document.getElementById("result-icon");
    var resultFilename    = document.getElementById("result-filename");
    var resultDownload    = document.getElementById("result-download");
    var audionlabsCard    = document.getElementById("audionlabs-card");
    var dlProcessBtn      = document.getElementById("process-btn");
    var flagStems         = document.getElementById("flag-stems");
    var flagSlowed        = document.getElementById("flag-slowed");
    var audionlabsResults = document.getElementById("audionlabs-results");
    var alResultsStems    = document.getElementById("al-results-stems");
    var alResultsSlowed   = document.getElementById("al-results-slowed");
    var alProgressContainer = document.getElementById("al-progress-container");
    var alProgressFill      = document.getElementById("al-progress-fill");
    var alProgressText      = document.getElementById("al-progress-text");
    var alProgressTimer     = null;

    var selectedFormat = "mp3";
    var lastFilePath = null;
    var lastBlobUrl = null;

    // --- Format toggle ---
    formatBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        formatBtns.forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        selectedFormat = btn.dataset.format;
      });
    });

    // --- Helpers ---
    function showDlError(msg) {
      errorMsg.textContent = msg;
      errorMsg.classList.remove("hidden");
    }

    function clearDlError() {
      errorMsg.classList.add("hidden");
      errorMsg.textContent = "";
    }

    async function downloadFromUrl(url, filename) {
      try {
        var resp = await fetch(url);
        if (!resp.ok) throw new Error("Download failed");
        var blob = await resp.blob();
        var blobUrl = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
      } catch (e) {
        showDlError("Failed to download: " + filename);
      }
    }

    function resetDlResults() {
      resultCard.classList.add("hidden");
      audionlabsCard.classList.add("hidden");
      audionlabsResults.classList.add("hidden");
      alResultsStems.classList.add("hidden");
      alResultsSlowed.classList.add("hidden");
      if (lastBlobUrl) {
        URL.revokeObjectURL(lastBlobUrl);
        lastBlobUrl = null;
      }
      lastFilePath = null;
    }

    function setDlLoading(active) {
      downloadBtn.disabled = active;
      downloadBtn.textContent = active ? "Downloading..." : "Download";
      if (active) {
        progressContainer.classList.remove("hidden");
        dlProgressFill.style.width = "0%";
        requestAnimationFrame(function () {
          dlProgressFill.style.width = "90%";
        });
        progressTextEl.textContent = "Downloading...";
      } else {
        dlProgressFill.style.width = "100%";
        progressTextEl.textContent = "Complete";
        setTimeout(function () {
          progressContainer.classList.add("hidden");
          dlProgressFill.style.width = "0%";
        }, 800);
      }
    }

    // --- Download ---
    downloadBtn.addEventListener("click", async function () {
      var url = urlInput.value.trim();
      clearDlError();
      resetDlResults();

      if (!url) {
        showDlError("Paste a YouTube URL to get started.");
        return;
      }

      setDlLoading(true);

      try {
        var resp = await fetch("/download", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: url, format: selectedFormat }),
        });

        if (!resp.ok) {
          var err = await resp.json().catch(function () { return {}; });
          throw new Error(err.detail || "Download failed (status " + resp.status + ")");
        }

        var data = await resp.json();
        lastFilePath = data.file_path;
        var filename = data.filename;

        var fileResp = await fetch("/file?path=" + encodeURIComponent(lastFilePath));
        if (!fileResp.ok) {
          throw new Error("Failed to fetch file from server");
        }

        var blob = await fileResp.blob();
        lastBlobUrl = URL.createObjectURL(blob);

        resultIcon.textContent = selectedFormat === "mp3" ? "\uD83C\uDFB5" : "\uD83C\uDFAC";
        resultFilename.textContent = filename;
        resultDownload.href = lastBlobUrl;
        resultDownload.download = filename;
        resultCard.classList.remove("hidden");

        if (selectedFormat === "mp3") {
          audionlabsCard.classList.remove("hidden");
        }
      } catch (e) {
        showDlError(e.message);
      } finally {
        setDlLoading(false);
      }
    });

    // --- AudionLabs progress simulation ---
    function startAlProgress(wantsStems, wantsSlowed) {
      var stages = [["Uploading...", 8, 1500]];
      if (wantsStems) stages.push(["Separating stems...", 62, 50000]);
      if (wantsSlowed) stages.push(["Applying slowed reverb...", wantsStems ? 82 : 78, 10000]);
      stages.push(["Finalizing...", 94, 3000]);

      var stageIndex = 0;
      var currentPct = 0;

      function runStage() {
        if (stageIndex >= stages.length) return;
        var label = stages[stageIndex][0];
        var targetPct = stages[stageIndex][1];
        var duration = stages[stageIndex][2];
        alProgressText.textContent = label;

        var startPct = currentPct;
        var delta = targetPct - startPct;
        var intervalMs = 120;
        var steps = Math.max(1, Math.round(duration / intervalMs));
        var step = 0;

        if (alProgressTimer) clearInterval(alProgressTimer);
        alProgressTimer = setInterval(function () {
          step++;
          var t = step / steps;
          var eased = 1 - Math.pow(1 - t, 2);
          currentPct = startPct + delta * eased;
          alProgressFill.style.width = Math.min(currentPct, 100) + "%";
          if (step >= steps) {
            clearInterval(alProgressTimer);
            alProgressTimer = null;
            stageIndex++;
            runStage();
          }
        }, intervalMs);
      }
      runStage();
    }

    function stopAlProgress() {
      if (alProgressTimer) { clearInterval(alProgressTimer); alProgressTimer = null; }
    }

    // --- Process with AudionLabs (calls /process_audio directly) ---
    dlProcessBtn.addEventListener("click", async function () {
      if (!lastFilePath) return;

      var wantsStems = flagStems.checked;
      var wantsSlowed = flagSlowed.checked;

      if (!wantsStems && !wantsSlowed) {
        showDlError("Select at least one processing option.");
        return;
      }

      clearDlError();
      dlProcessBtn.disabled = true;
      dlProcessBtn.textContent = "Processing...";

      alProgressFill.style.width = "0%";
      alProgressContainer.classList.remove("hidden");
      startAlProgress(wantsStems, wantsSlowed);

      audionlabsResults.classList.add("hidden");
      alResultsStems.classList.add("hidden");
      alResultsSlowed.classList.add("hidden");

      try {
        // Fetch the downloaded file as a blob, then send to /process_audio
        var fileResp = await fetch("/file?path=" + encodeURIComponent(lastFilePath));
        if (!fileResp.ok) throw new Error("Failed to read downloaded file");
        var blob = await fileResp.blob();

        var filename = lastFilePath.split(/[/\\]/).pop();
        var form = new FormData();
        form.append("file", blob, filename);
        form.append("split_stems_flag", wantsStems.toString());
        form.append("slowed_reverb_flag", wantsSlowed.toString());

        var resp = await fetch("/process_audio", {
          method: "POST",
          body: form,
        });

        if (!resp.ok) {
          var err = await resp.json().catch(function () { return {}; });
          throw new Error(err.detail || "Processing failed");
        }

        var data = await resp.json();

        stopAlProgress();
        alProgressText.textContent = "Done!";
        alProgressFill.style.width = "100%";

        if (data.stems) {
          var container = alResultsStems.querySelector(".result-links");
          container.innerHTML = "";
          var labels = { vocals: "Vocals", drums: "Drums", bass: "Bass", other: "Other" };
          for (var key in data.stems) {
            var stem = data.stems[key];
            var btn = document.createElement("button");
            btn.className = "result-link-btn";
            btn.textContent = labels[key] || key;
            btn.addEventListener("click", (function (u, n) {
              return function () { downloadFromUrl(u, n); };
            })(stem.url, stem.download_name || key + ".wav"));
            container.appendChild(btn);
          }
          alResultsStems.classList.remove("hidden");
        }

        if (data.slowed_mix) {
          var container2 = alResultsSlowed.querySelector(".result-links");
          container2.innerHTML = "";
          var btn2 = document.createElement("button");
          btn2.className = "result-link-btn";
          btn2.textContent = "Slowed + Reverb Mix";
          btn2.addEventListener("click", function () {
            downloadFromUrl(data.slowed_mix.url,
              data.slowed_mix.download_name || "slowed_reverb.wav");
          });
          container2.appendChild(btn2);
          alResultsSlowed.classList.remove("hidden");
        }

        audionlabsResults.classList.remove("hidden");
      } catch (e) {
        stopAlProgress();
        showDlError(e.message);
      } finally {
        dlProcessBtn.textContent = "Process with AudionLabs \u2192";
        dlProcessBtn.disabled = false;
        setTimeout(function () {
          alProgressContainer.classList.add("hidden");
          alProgressFill.style.width = "0%";
        }, 600);
      }
    });

    // --- Enter key triggers download ---
    urlInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") downloadBtn.click();
    });
  }

})();
