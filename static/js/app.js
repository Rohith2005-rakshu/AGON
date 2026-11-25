(() => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const errorBanner = document.getElementById("errorBanner");
  const loadingPanel = document.getElementById("loadingPanel");
  const loadingTitle = document.getElementById("loadingTitle");
  const loadingSubtitle = document.getElementById("loadingSubtitle");
  const resultsSection = document.getElementById("resultsSection");

  const settingsDrawer = document.getElementById("settingsDrawer");
  const toggleSettingsBtn = document.getElementById("toggleSettingsBtn");
  const closeSettingsBtn = document.getElementById("closeSettingsBtn");
  const hfTokenInput = document.getElementById("hfTokenInput");
  const hfModelInput = document.getElementById("hfModelInput");

  const mediaTypeBadge = document.getElementById("mediaTypeBadge");
  const resultFilename = document.getElementById("resultFilename");
  const resultStats = document.getElementById("resultStats");
  const exportJsonBtn = document.getElementById("exportJsonBtn");
  const scanAnotherBtn = document.getElementById("scanAnotherBtn");

  const gaugeProgress = document.getElementById("gaugeProgress");
  const gaugePercent = document.getElementById("gaugePercent");
  const verdictBadge = document.getElementById("verdictBadge");
  const verdictTitle = document.getElementById("verdictTitle");
  const verdictDesc = document.getElementById("verdictDesc");
  const mlBadgeRow = document.getElementById("mlBadgeRow");
  const signalsList = document.getElementById("signalsList");

  const c2paChip = document.getElementById("c2paChip");
  const metaSummary = document.getElementById("metaSummary");
  const signatureTags = document.getElementById("signatureTags");
  const metaTableWrap = document.getElementById("metaTableWrap");

  const visualTabs = document.getElementById("visualTabs");
  const forensicGrid = document.getElementById("forensicGrid");
  const visualSubtitle = document.getElementById("visualSubtitle");
  const imgOriginal = document.getElementById("imgOriginal");
  const imgFft = document.getElementById("imgFft");
  const imgEla = document.getElementById("imgEla");
  const imgNoise = document.getElementById("imgNoise");

  const videoStage = document.getElementById("videoStage");
  const videoPreview = document.getElementById("videoPreview");
  const videoInfoPills = document.getElementById("videoInfoPills");
  const videoTimelineCard = document.getElementById("videoTimelineCard");
  const timelineCanvas = document.getElementById("timelineCanvas");
  const frameStrip = document.getElementById("frameStrip");

  const historySection = document.getElementById("historySection");
  const historyGrid = document.getElementById("historyGrid");
  const clearHistoryBtn = document.getElementById("clearHistoryBtn");

  const CIRCUMFERENCE = 2 * Math.PI * 58; // 364.424
  let currentReport = null;
  let currentVideoObjectUrl = null;
  const scanHistory = [];

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.classList.remove("hidden");
  }

  function clearError() {
    errorBanner.textContent = "";
    errorBanner.classList.add("hidden");
  }

  function setLoading(active, isVideo = false) {
    if (active) {
      clearError();
      loadingTitle.textContent = isVideo
        ? "Decoding video & analyzing temporal frames..."
        : "Running multi-signal image forensics...";
      loadingSubtitle.textContent = isVideo
        ? "Sampling keyframes, computing inter-frame flicker, 2D FFT spectra, ELA, and container metadata."
        : "Computing 2D FFT power spectrum, sensor noise residuals, ELA, and EXIF/C2PA metadata.";
      loadingPanel.classList.remove("hidden");
    } else {
      loadingPanel.classList.add("hidden");
    }
  }

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  function colorForScore(score) {
    if (score >= 0.68) return "#f43f5e";
    if (score >= 0.42) return "#f59e0b";
    return "#10b981";
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function analyzeFile(file) {
    if (!file) return;
    const isVideo =
      (file.type && file.type.startsWith("video/")) ||
      /\.(mp4|mov|webm|avi|mkv|m4v)$/i.test(file.name);

    setLoading(true, isVideo);
    const formData = new FormData();
    formData.append("file", file);
    if (hfTokenInput.value.trim()) {
      formData.append("hf_token", hfTokenInput.value.trim());
    }
    if (hfModelInput.value.trim()) {
      formData.append("hf_model", hfModelInput.value.trim());
    }

    if (currentVideoObjectUrl) {
      URL.revokeObjectURL(currentVideoObjectUrl);
      currentVideoObjectUrl = null;
    }
    const localVideoUrl = isVideo ? URL.createObjectURL(file) : null;
    if (localVideoUrl) currentVideoObjectUrl = localVideoUrl;

    try {
      const resp = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || `Server error (${resp.status})`);
      }
      renderReport(data, localVideoUrl);
      pushHistory(data, localVideoUrl);
    } catch (err) {
      showError(err.message || "Failed to analyze media.");
    } finally {
      setLoading(false);
    }
  }

  async function analyzeDemo(sampleType) {
    const isVideo = sampleType === "ai_video";
    setLoading(true, isVideo);
    const formData = new FormData();
    if (hfTokenInput.value.trim()) {
      formData.append("hf_token", hfTokenInput.value.trim());
    }
    if (hfModelInput.value.trim()) {
      formData.append("hf_model", hfModelInput.value.trim());
    }

    try {
      const resp = await fetch(`/api/demo/${sampleType}`, {
        method: "POST",
        body: formData,
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || `Demo failed (${resp.status})`);
      }
      const videoUrl = isVideo ? data.demo_media_uri : null;
      renderReport(data, videoUrl);
      pushHistory(data, videoUrl);
    } catch (err) {
      showError(err.message || "Demo request failed.");
    } finally {
      setLoading(false);
    }
  }

  function renderReport(data, videoSourceUrl = null) {
    currentReport = data;
    resultsSection.classList.remove("hidden");

    const isVideo = data.media_type === "video";
    mediaTypeBadge.textContent = isVideo ? "VIDEO" : "IMAGE";
    resultFilename.textContent = data.filename || "Uploaded Media";

    const dims = isVideo ? data.video_info : data.dimensions;
    const dimText = dims ? `${dims.width} × ${dims.height}` : "";
    const extraText = isVideo && data.video_info
      ? ` • ${data.video_info.duration_sec ?? "?"}s @ ${data.video_info.fps} fps`
      : "";
    resultStats.textContent = `${dimText}${extraText} • ${formatBytes(data.file_size_bytes)} • ${data.processing_time_ms} ms`;

    // Gauge
    const prob = Number(data.ai_probability || 0);
    const pct = Number(data.ai_percentage ?? Math.round(prob * 100));
    const offset = CIRCUMFERENCE * (1 - Math.min(Math.max(prob, 0), 1));
    const strokeColor = colorForScore(prob);
    gaugeProgress.style.strokeDashoffset = String(offset);
    gaugeProgress.style.stroke = strokeColor;
    gaugePercent.textContent = `${pct.toFixed(1)}%`;
    gaugePercent.style.color = strokeColor;

    const verdict = data.verdict || { label: "Unknown", tone: "warning", description: "" };
    verdictBadge.className = `verdict-pill tone-${verdict.tone}`;
    verdictBadge.textContent = verdict.tone === "danger" ? "Synthetic Detected" : verdict.tone === "success" ? "Authentic Signals" : "Inconclusive";
    verdictTitle.textContent = verdict.label;
    verdictDesc.textContent = verdict.description;

    // External ML / Mode pills
    mlBadgeRow.innerHTML = "";
    const modePill = document.createElement("span");
    modePill.className = "mini-pill";
    modePill.textContent = `Forensic Score: ${(data.forensic_composite_score * 100).toFixed(1)}%`;
    mlBadgeRow.appendChild(modePill);

    if (data.external_ml && data.external_ml.available) {
      const mlPill = document.createElement("span");
      mlPill.className = "mini-pill";
      mlPill.textContent = `${data.external_ml.provider}: ${(data.external_ml.ai_probability * 100).toFixed(1)}%`;
      mlBadgeRow.appendChild(mlPill);
    } else if (data.external_ml && data.external_ml.error) {
      const errPill = document.createElement("span");
      errPill.className = "mini-pill";
      errPill.textContent = `ML fallback: ${data.external_ml.error.slice(0, 48)}`;
      mlBadgeRow.appendChild(errPill);
    }

    // Signals breakdown
    renderSignals(data.signals || {}, data.metadata || {});

    // Metadata
    renderMetadata(data.metadata || {});

    // Visual forensic images
    const visuals = data.visuals || {};
    imgOriginal.src = visuals.original || "";
    imgFft.src = visuals.fft_spectrum || "";
    imgEla.src = visuals.ela_heatmap || "";
    imgNoise.src = visuals.noise_residual || "";

    if (isVideo) {
      visualSubtitle.textContent = "Showing playable video plus forensic maps of the highest-scoring frame";
      videoStage.classList.remove("hidden");
      if (videoSourceUrl) {
        videoPreview.src = videoSourceUrl;
      } else {
        videoPreview.removeAttribute("src");
      }
      renderVideoInfoPills(data.video_info || {});
      videoTimelineCard.classList.remove("hidden");
      renderVideoTimeline(data.timeline || []);
    } else {
      visualSubtitle.textContent = "Inspect pixel-level anomalies across frequency, compression, and noise domains";
      videoStage.classList.add("hidden");
      videoPreview.pause();
      videoPreview.removeAttribute("src");
      videoTimelineCard.classList.add("hidden");
    }

    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderSignals(signals, metadata) {
    const items = [];
    if (signals.frequency_fft) {
      items.push({
        name: "2D FFT Frequency Spectrum",
        score: signals.frequency_fft.score,
        desc: signals.frequency_fft.finding,
        metrics: `HF/Mid Ratio: ${signals.frequency_fft.hf_to_mid_ratio} | Slope: ${signals.frequency_fft.spectral_slope} | Peak Excess: ${signals.frequency_fft.periodic_peak_excess}`,
      });
    }
    if (signals.noise_residual) {
      items.push({
        name: "Sensor Noise Floor & Smoothness",
        score: signals.noise_residual.score,
        desc: signals.noise_residual.finding,
        metrics: `Noise σ: ${signals.noise_residual.global_noise_std} | Smooth Patches: ${Math.round((signals.noise_residual.smooth_patch_ratio || 0) * 100)}% | RGB Corr: ${signals.noise_residual.rgb_residual_correlation}`,
      });
    }
    if (signals.error_level_ela) {
      items.push({
        name: "Error Level Analysis (ELA)",
        score: signals.error_level_ela.score,
        desc: signals.error_level_ela.finding,
        metrics: `Mean ELA: ${signals.error_level_ela.mean_ela} | P95: ${signals.error_level_ela.p95_ela} | Spatial CV: ${signals.error_level_ela.spatial_cv}`,
      });
    }
    if (signals.color_texture) {
      items.push({
        name: "Color & Edge-Texture Coherence",
        score: signals.color_texture.score,
        desc: signals.color_texture.finding,
        metrics: `Mean Sat: ${signals.color_texture.mean_saturation} | Edge/Tex: ${signals.color_texture.edge_to_texture_ratio}`,
      });
    }
    if (signals.temporal_consistency) {
      items.push({
        name: "Video Temporal Flicker Consistency",
        score: signals.temporal_consistency.score,
        desc: signals.temporal_consistency.finding,
        metrics: `HF/LF Motion Ratio: ${signals.temporal_consistency.avg_hf_to_lf_ratio} | Variance: ${signals.temporal_consistency.flicker_variance}`,
      });
    }
    if (typeof metadata.metadata_score === "number") {
      items.push({
        name: "Metadata & Provenance Signal",
        score: metadata.metadata_score,
        desc: metadata.summary,
        metrics: `AI Tags: ${(metadata.ai_signatures || []).length} | Camera Tags: ${(metadata.camera_fields || []).length}`,
      });
    }

    signalsList.innerHTML = items
      .map((item) => {
        const pct = Math.round(item.score * 100);
        const col = colorForScore(item.score);
        return `
          <div class="signal-item">
            <div class="signal-top">
              <span class="signal-name">${escapeHtml(item.name)}</span>
              <span class="signal-score" style="color:${col}">${pct}%</span>
            </div>
            <div class="signal-bar-track">
              <div class="signal-bar-fill" style="width:${pct}%; background:${col}"></div>
            </div>
            <p class="signal-desc">${escapeHtml(item.desc || "")}</p>
            <div class="signal-metrics">${escapeHtml(item.metrics)}</div>
          </div>
        `;
      })
      .join("");
  }

  function renderMetadata(meta) {
    metaSummary.textContent = meta.summary || "No metadata summary available.";
    if (meta.has_c2pa) {
      c2paChip.textContent = "C2PA / JUMBF Detected";
      c2paChip.classList.add("active");
    } else {
      c2paChip.textContent = "No C2PA Header";
      c2paChip.classList.remove("active");
    }

    const badges = [];
    (meta.ai_signatures || []).forEach((sig) => {
      badges.push(`<span class="sig-badge tone-danger">AI Tag: ${escapeHtml(sig.generator)}</span>`);
    });
    (meta.camera_fields || []).slice(0, 5).forEach((field) => {
      badges.push(`<span class="sig-badge tone-success">Camera: ${escapeHtml(field)}</span>`);
    });
    (meta.encoders || []).slice(0, 4).forEach((enc) => {
      badges.push(`<span class="sig-badge mini-pill">${escapeHtml(enc)}</span>`);
    });
    signatureTags.innerHTML = badges.join("");

    // Raw metadata table
    const rows = [];
    const exif = meta.exif || {};
    const pngChunks = meta.png_chunks || {};
    Object.entries(pngChunks).forEach(([k, v]) => rows.push([`PNG:${k}`, v]));
    Object.entries(exif).forEach(([k, v]) => rows.push([`EXIF:${k}`, v]));

    if (rows.length === 0) {
      metaTableWrap.innerHTML = `<div style="padding:12px;font-size:0.78rem;color:var(--text-dim)">No EXIF or PNG text chunks found in file.</div>`;
    } else {
      metaTableWrap.innerHTML = `
        <table class="meta-table">
          <tbody>
            ${rows.map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`).join("")}
          </tbody>
        </table>
      `;
    }
  }

  function renderVideoInfoPills(info) {
    const pills = [
      `Resolution: ${info.width}×${info.height}`,
      `FPS: ${info.fps}`,
      `Frames: ${info.total_frames}`,
      `Sampled: ${info.sampled_frames}`,
    ];
    videoInfoPills.innerHTML = pills.map((p) => `<span class="mini-pill">${escapeHtml(p)}</span>`).join("");
  }

  function renderVideoTimeline(timeline) {
    drawTimelineChart(timeline);
    frameStrip.innerHTML = timeline
      .map((f) => {
        const col = colorForScore(f.ai_probability);
        return `
          <div class="frame-thumb-card" data-time="${f.timestamp_sec}" title="Click to seek video to ${f.timestamp_sec}s">
            <img src="${f.thumbnail}" alt="Frame ${f.frame_index}" />
            <div class="frame-thumb-meta">
              <span>${f.timestamp_sec}s</span>
              <span style="color:${col};font-weight:700">${f.ai_percentage}%</span>
            </div>
          </div>
        `;
      })
      .join("");

    frameStrip.querySelectorAll(".frame-thumb-card").forEach((card) => {
      card.addEventListener("click", () => {
        const t = parseFloat(card.dataset.time || "0");
        if (!Number.isNaN(t) && videoPreview.src) {
          videoPreview.currentTime = t;
          videoPreview.play().catch(() => {});
        }
      });
    });
  }

  function drawTimelineChart(timeline) {
    const dpr = window.devicePixelRatio || 1;
    const width = timelineCanvas.clientWidth || 640;
    const height = 170;
    timelineCanvas.width = width * dpr;
    timelineCanvas.height = height * dpr;
    const ctx = timelineCanvas.getContext("2d");
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);
    const pad = { top: 18, right: 20, bottom: 26, left: 38 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    // Grid lines (0%, 50%, 100%)
    ctx.strokeStyle = "rgba(148,163,184,0.16)";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#64748b";
    ctx.font = "11px JetBrains Mono, monospace";
    [0, 0.5, 1.0].forEach((val) => {
      const y = pad.top + plotH * (1 - val);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotW, y);
      ctx.stroke();
      ctx.fillText(`${Math.round(val * 100)}%`, 4, y + 4);
    });

    if (!timeline.length) return;

    const pts = timeline.map((f, idx) => {
      const x = timeline.length === 1 ? pad.left + plotW / 2 : pad.left + (idx / (timeline.length - 1)) * plotW;
      const y = pad.top + plotH * (1 - f.ai_probability);
      return { x, y, f };
    });

    // Area gradient
    const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotH);
    grad.addColorStop(0, "rgba(56, 189, 248, 0.35)");
    grad.addColorStop(1, "rgba(56, 189, 248, 0.0)");

    ctx.beginPath();
    ctx.moveTo(pts[0].x, pad.top + plotH);
    pts.forEach((p) => ctx.lineTo(p.x, p.y));
    ctx.lineTo(pts[pts.length - 1].x, pad.top + plotH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    pts.forEach((p, idx) => {
      if (idx === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Points + X labels
    pts.forEach((p, idx) => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = colorForScore(p.f.ai_probability);
      ctx.fill();
      ctx.strokeStyle = "#070b14";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (idx === 0 || idx === pts.length - 1 || idx % 2 === 0) {
        ctx.fillStyle = "#94a3b8";
        ctx.fillText(`${p.f.timestamp_sec}s`, p.x - 10, height - 6);
      }
    });
  }

  function pushHistory(report, videoUrl) {
    const thumb = report.visuals?.original || (report.timeline && report.timeline[0]?.thumbnail) || "";
    scanHistory.unshift({ report, videoUrl, thumb });
    if (scanHistory.length > 8) scanHistory.pop();
    renderHistory();
  }

  function renderHistory() {
    if (scanHistory.length === 0) {
      historySection.classList.add("hidden");
      return;
    }
    historySection.classList.remove("hidden");
    historyGrid.innerHTML = scanHistory
      .map((entry, idx) => {
        const col = colorForScore(entry.report.ai_probability);
        return `
          <div class="history-card" data-idx="${idx}">
            <img class="history-thumb" src="${entry.thumb}" alt="Scan thumbnail" />
            <div class="history-info">
              <span class="history-name">${escapeHtml(entry.report.filename)}</span>
              <span class="history-meta">
                <strong style="color:${col}">${entry.report.ai_percentage}% AI</strong>
                &bull; ${entry.report.media_type.toUpperCase()}
              </span>
            </div>
          </div>
        `;
      })
      .join("");

    historyGrid.querySelectorAll(".history-card").forEach((card) => {
      card.addEventListener("click", () => {
        const item = scanHistory[Number(card.dataset.idx)];
        if (item) renderReport(item.report, item.videoUrl);
      });
    });
  }

  // Visual Tabs switching
  visualTabs.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      visualTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const view = btn.dataset.view;
      const tiles = forensicGrid.querySelectorAll(".forensic-tile");
      if (view === "grid") {
        forensicGrid.classList.remove("single-view");
        tiles.forEach((t) => t.classList.remove("hidden"));
      } else {
        forensicGrid.classList.add("single-view");
        tiles.forEach((t) => {
          t.classList.toggle("hidden", t.dataset.panel !== view);
        });
      }
    });
  });

  // Dropzone events
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files[0]) {
      analyzeFile(fileInput.files[0]);
      fileInput.value = "";
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    const file = e.dataTransfer?.files?.[0];
    if (file) analyzeFile(file);
  });

  // Demo sample buttons
  document.querySelectorAll("[data-demo]").forEach((btn) => {
    btn.addEventListener("click", () => analyzeDemo(btn.dataset.demo));
  });

  // Settings Drawer
  toggleSettingsBtn.addEventListener("click", () => {
    settingsDrawer.classList.toggle("hidden");
  });
  closeSettingsBtn.addEventListener("click", () => {
    settingsDrawer.classList.add("hidden");
  });

  // Actions
  scanAnotherBtn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    fileInput.click();
  });

  exportJsonBtn.addEventListener("click", () => {
    if (!currentReport) return;
    // Strip large base64 images from JSON export for readability
    const cleanReport = structuredClone(currentReport);
    if (cleanReport.visuals) {
      cleanReport.visuals = Object.fromEntries(
        Object.keys(cleanReport.visuals).map((k) => [k, "[omitted base64 PNG]"])
      );
    }
    if (Array.isArray(cleanReport.timeline)) {
      cleanReport.timeline = cleanReport.timeline.map(({ thumbnail, ...rest }) => rest);
    }
    delete cleanReport.demo_media_uri;

    const blob = new Blob([JSON.stringify(cleanReport, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agon_report_${(currentReport.filename || "media").replace(/[^\w.-]+/g, "_")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  clearHistoryBtn.addEventListener("click", () => {
    scanHistory.length = 0;
    renderHistory();
  });

  // Redraw timeline on resize if video results visible
  window.addEventListener("resize", () => {
    if (currentReport && currentReport.media_type === "video" && currentReport.timeline) {
      drawTimelineChart(currentReport.timeline);
    }
  });
})();
