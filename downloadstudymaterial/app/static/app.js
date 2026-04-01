document.addEventListener("DOMContentLoaded", () => {
  const downloadFolderBtn = document.getElementById("download-btn");
  const downloadSelectedBtn = document.getElementById("download-selected-btn");
  const statusBox = document.getElementById("status");
  const statusText = document.getElementById("status-text");
  const progress = document.getElementById("progress");
  const selectAll = document.getElementById("select-all");
  const selectedCount = document.getElementById("selected-count");
  const itemCheckboxes = Array.from(document.querySelectorAll(".item-checkbox"));

  if (!downloadFolderBtn) return;

  const updateSelectionState = () => {
    const checked = itemCheckboxes.filter((c) => c.checked);
    selectedCount.textContent = checked.length;
    if (downloadSelectedBtn) {
      downloadSelectedBtn.disabled = checked.length === 0;
    }
    if (selectAll) {
      selectAll.checked = checked.length > 0 && checked.length === itemCheckboxes.length;
      selectAll.indeterminate = checked.length > 0 && checked.length < itemCheckboxes.length;
    }
  };

  itemCheckboxes.forEach((cb) => cb.addEventListener("change", updateSelectionState));
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      itemCheckboxes.forEach((cb) => {
        cb.checked = selectAll.checked;
      });
      updateSelectionState();
    });
  }
  updateSelectionState();

  const showStatus = (text) => {
    statusBox.classList.remove("hidden");
    statusText.textContent = text;
  };

  const pollJob = (statusUrl, downloadUrl, onDone) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(statusUrl);
        if (!res.ok) return;
        const data = await res.json();
        if (data.total) {
          progress.textContent = `${data.completed}/${data.total} items`;
        }
        if (data.current_file) {
          progress.textContent += ` — ${data.current_file}`;
        }
        if (data.status === "ready") {
          clearInterval(interval);
          showStatus("ZIP ready! Starting download...");
          window.location = downloadUrl;
          onDone();
        }
        if (data.status === "error") {
          clearInterval(interval);
          showStatus(`Error: ${data.message}`);
          onDone();
        }
      } catch (err) {
        console.error(err);
      }
    }, 1500);
  };

  const startJob = async (endpoint, payload, button) => {
    downloadFolderBtn.disabled = true;
    if (downloadSelectedBtn) downloadSelectedBtn.disabled = true;
    progress.textContent = "";
    showStatus("Preparing ZIP...");
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let detail = "";
        try { detail = (await res.json()).detail; } catch (e) { /* ignore */ }
        showStatus(`Error: ${detail || res.statusText}`);
        downloadFolderBtn.disabled = false;
        updateSelectionState();
        return;
      }
      const data = await res.json();
      showStatus("Working... this can take a while for large folders.");
      pollJob(data.status_url, data.download_url, () => {
        downloadFolderBtn.disabled = false;
        updateSelectionState();
      });
    } catch (err) {
      console.error(err);
      showStatus("Something went wrong. Please try again.");
      downloadFolderBtn.disabled = false;
      updateSelectionState();
    }
  };

  downloadFolderBtn.addEventListener("click", async () => {
    const payload = {
      folder_id: downloadFolderBtn.dataset.folderId,
      folder_name: downloadFolderBtn.dataset.folderName,
    };
    await startJob("/api/download-zip", payload, downloadFolderBtn);
  });

  if (downloadSelectedBtn) {
    downloadSelectedBtn.addEventListener("click", async () => {
      const selected = itemCheckboxes.filter((c) => c.checked).map((c) => ({ id: c.dataset.id, type: c.dataset.type }));
      if (selected.length === 0) return;
      const payload = {
        current_folder_id: downloadSelectedBtn.dataset.folderId,
        current_folder_name: downloadSelectedBtn.dataset.folderName,
        items: selected,
      };
      await startJob("/api/download-zip-selected", payload, downloadSelectedBtn);
    });
  }
});

// ========== SEARCH PAGE LOGIC ==========
document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("search-input");
  if (!searchInput) return; // Not on search page

  const clearBtn = document.getElementById("clear-btn");
  const emptyState = document.getElementById("empty-state");
  const loadingSkeleton = document.getElementById("loading-skeleton");
  const noResults = document.getElementById("no-results");
  const searchTerm = document.getElementById("search-term");
  const resultsList = document.getElementById("results-list");
  const loadMoreBtn = document.getElementById("load-more-btn");
  const filterTabs = Array.from(document.querySelectorAll(".tab"));
  const selectionBar = document.getElementById("selection-bar");
  const selectedCountSpan = document.getElementById("selected-count");
  const downloadSearchBtn = document.getElementById("download-search-btn");
  const statusBox = document.getElementById("status");
  const statusText = document.getElementById("status-text");
  const progressText = document.getElementById("progress");

  let debounceTimer = null;
  let currentPageToken = null;
  let activeFilter = "all";
  let currentQuery = "";
  let itemCheckboxes = [];

  const showStatus = (text) => {
    statusBox.classList.remove("hidden");
    statusText.textContent = text;
  };

  const pollJob = (statusUrl, downloadUrl, onDone) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(statusUrl);
        if (!res.ok) return;
        const data = await res.json();
        if (data.total) {
          progressText.textContent = `${data.completed}/${data.total} items`;
        }
        if (data.current_file) {
          progressText.textContent += ` — ${data.current_file}`;
        }
        if (data.status === "ready") {
          clearInterval(interval);
          showStatus("ZIP ready! Starting download...");
          window.location = downloadUrl;
          onDone();
        }
        if (data.status === "error") {
          clearInterval(interval);
          showStatus(`Error: ${data.message}`);
          onDone();
        }
      } catch (err) {
        console.error(err);
      }
    }, 1500);
  };

  const startJob = async (endpoint, payload) => {
    downloadSearchBtn.disabled = true;
    progressText.textContent = "";
    showStatus("Preparing ZIP...");
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        let detail = "";
        try { detail = (await res.json()).detail; } catch (e) { /* ignore */ }
        showStatus(`Error: ${detail || res.statusText}`);
        updateSelectionState();
        return;
      }
      const data = await res.json();
      showStatus("Working... this can take a while for large selections.");
      pollJob(data.status_url, data.download_url, () => {
        updateSelectionState();
      });
    } catch (err) {
      console.error(err);
      showStatus("Something went wrong. Please try again.");
      updateSelectionState();
    }
  };

  const updateSelectionState = () => {
    const checked = itemCheckboxes.filter((c) => c.checked);
    selectedCountSpan.textContent = checked.length;
    downloadSearchBtn.disabled = checked.length === 0;
    if (checked.length > 0) {
      selectionBar.classList.remove("hidden");
    } else {
      selectionBar.classList.add("hidden");
    }
  };

  const rewireCheckboxes = () => {
    itemCheckboxes = Array.from(document.querySelectorAll(".item-checkbox"));
    itemCheckboxes.forEach((cb) => {
      cb.removeEventListener("change", updateSelectionState);
      cb.addEventListener("change", updateSelectionState);
    });
    updateSelectionState();
  };

  const applyFilter = (filter) => {
    activeFilter = filter;
    filterTabs.forEach((tab) => {
      if (tab.dataset.filter === filter) {
        tab.classList.add("active");
      } else {
        tab.classList.remove("active");
      }
    });
    const rows = Array.from(resultsList.querySelectorAll(".result-row"));
    rows.forEach((row) => {
      const type = row.dataset.type;
      if (filter === "all" || filter === type) {
        row.style.display = "flex";
      } else {
        row.style.display = "none";
      }
    });
    updateSelectionState();
  };

  const formatSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const highlightMatch = (name, query) => {
    const index = name.toLowerCase().indexOf(query.toLowerCase());
    if (index === -1) return name;
    const before = name.substring(0, index);
    const match = name.substring(index, index + query.length);
    const after = name.substring(index + query.length);
    return `${before}<mark>${match}</mark>${after}`;
  };

  const renderResults = (items, append) => {
    if (!append) {
      resultsList.innerHTML = "";
    }

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "result-row";
      row.dataset.type = item.isFolder ? "folder" : "file";
      row.dataset.mimeType = item.mimeType;

      const icon = item.isFolder ? "📁" : "📄";
      const sizeText = item.isFolder ? "" : formatSize(item.size);
      const highlightedName = highlightMatch(item.name, currentQuery);

      row.innerHTML = `
        <input type="checkbox" class="item-checkbox" data-id="${item.id}" data-type="${item.isFolder ? 'folder' : 'file'}" data-name="${item.name}">
        <span class="result-icon">${icon}</span>
        <div class="result-meta">
          <div class="result-name">${highlightedName}</div>
          <div class="result-path muted">${item.path}</div>
        </div>
        ${sizeText ? `<div class="result-size muted">${sizeText}</div>` : ''}
      `;
      
      // Add preview button for files if previewable
      if (!item.isFolder && isPreviewable(item.mimeType)) {
        const previewBtn = document.createElement("button");
        previewBtn.className = "btn btn-small preview-btn";
        previewBtn.textContent = "👁 Preview";
        previewBtn.style.flexShrink = "0";
        previewBtn.dataset.id = item.id;
        previewBtn.dataset.name = item.name;
        previewBtn.dataset.mime = item.mimeType;
        row.appendChild(previewBtn);
      }
      
      resultsList.appendChild(row);
    });

    rewireCheckboxes();
    applyFilter(activeFilter);
  };

  const fetchResults = async (query, pageToken, append) => {
    emptyState.classList.add("hidden");
    noResults.classList.add("hidden");
    
    if (!append) {
      loadingSkeleton.classList.remove("hidden");
      resultsList.innerHTML = "";
    }

    try {
      let url = `/api/search?q=${encodeURIComponent(query)}`;
      if (pageToken) {
        url += `&page_token=${encodeURIComponent(pageToken)}`;
      }

      const res = await fetch(url);
      loadingSkeleton.classList.add("hidden");

      if (!res.ok) {
        let detail = res.statusText;
        try {
          const payload = await res.json();
          if (payload && payload.detail) {
            detail = payload.detail;
          }
        } catch (e) {
          // ignore parse failures
        }
        showStatus(`Search failed: ${detail}`);
        noResults.classList.remove("hidden");
        searchTerm.textContent = query;
        loadMoreBtn.classList.add("hidden");
        return;
      }

      const data = await res.json();
      currentPageToken = data.nextPageToken;

      if (data.results.length === 0 && !append) {
        noResults.classList.remove("hidden");
        searchTerm.textContent = query;
        loadMoreBtn.classList.add("hidden");
      } else {
        renderResults(data.results, append);
        if (currentPageToken) {
          loadMoreBtn.classList.remove("hidden");
        } else {
          loadMoreBtn.classList.add("hidden");
        }
      }
    } catch (err) {
      console.error("Search error:", err);
      loadingSkeleton.classList.add("hidden");
      showStatus("Search failed due to a network or server issue.");
      noResults.classList.remove("hidden");
      searchTerm.textContent = query;
      loadMoreBtn.classList.add("hidden");
    }
  };

  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const query = searchInput.value.trim();

    if (query.length < 2) {
      resultsList.innerHTML = "";
      emptyState.classList.remove("hidden");
      noResults.classList.add("hidden");
      loadingSkeleton.classList.add("hidden");
      loadMoreBtn.classList.add("hidden");
      selectionBar.classList.add("hidden");
      return;
    }

    debounceTimer = setTimeout(() => {
      currentQuery = query;
      currentPageToken = null;
      fetchResults(query, null, false);
    }, 350);
  });

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      clearTimeout(debounceTimer);
      const query = searchInput.value.trim();
      if (query.length >= 2) {
        currentQuery = query;
        currentPageToken = null;
        fetchResults(query, null, false);
      }
    } else if (e.key === "Escape") {
      searchInput.value = "";
      searchInput.dispatchEvent(new Event("input"));
    }
  });

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    searchInput.dispatchEvent(new Event("input"));
    searchInput.focus();
  });

  filterTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      applyFilter(tab.dataset.filter);
    });
  });

  loadMoreBtn.addEventListener("click", () => {
    if (currentPageToken && currentQuery) {
      fetchResults(currentQuery, currentPageToken, true);
    }
  });

  downloadSearchBtn.addEventListener("click", async () => {
    const selected = itemCheckboxes.filter((c) => c.checked).map((c) => ({
      id: c.dataset.id,
      type: c.dataset.type,
    }));
    if (selected.length === 0) return;

    const payload = {
      current_folder_id: "root",
      current_folder_name: "Search Results",
      items: selected,
      zip_name: "search_results.zip",
    };
    await startJob("/api/download-zip-selected", payload);
  });

  // Initialize from URL if query is present
  if (searchInput.value.trim().length >= 2) {
    currentQuery = searchInput.value.trim();
    fetchResults(currentQuery, null, false);
  }
});

// ========== PREVIEW FUNCTIONALITY ==========

// Supported previewable MIME types
const PREVIEWABLE_TYPES = {
  "application/pdf": "pdf",
  "image/jpeg": "image",
  "image/jpg": "image",
  "image/pjpeg": "image",
  "image/png": "image",
  "image/gif": "image",
  "image/webp": "image",
  "image/svg+xml": "image",
  "application/vnd.google-apps.document": "pdf", // Exported to PDF
  "application/vnd.google-apps.presentation": "pdf", // Exported to PDF
  "application/vnd.google-apps.drawing": "pdf", // Exported to PDF
};

function isPreviewable(mimeType) {
  return PREVIEWABLE_TYPES.hasOwnProperty(mimeType);
}

function getPreviewType(mimeType) {
  return PREVIEWABLE_TYPES[mimeType] || null;
}

function openPreview(fileId, fileName, mimeType) {
  const modal = document.getElementById("preview-modal");
  const overlay = document.getElementById("preview-overlay");
  const container = document.getElementById("preview-container");
  const filenameEl = document.getElementById("preview-filename");
  const driveLink = document.getElementById("preview-drive-link");

  filenameEl.textContent = fileName;
  container.innerHTML = "";
  driveLink.style.display = "none";

  const previewType = getPreviewType(mimeType);

  if (!previewType) {
    // Video or other type - offer Drive link
    container.innerHTML = `<p class="preview-unavailable">Preview not available for this file type. <a href="https://drive.google.com/file/d/${fileId}/view" target="_blank">Click here to view in Google Drive.</a></p>`;
  } else if (previewType === "image") {
    // Image preview
    const img = document.createElement("img");
    img.src = `/api/preview/${fileId}`;
    img.className = "preview-image";
    img.onerror = () => {
      container.innerHTML = `<p class="preview-error">Failed to load image. <a href="https://drive.google.com/file/d/${fileId}/view" target="_blank">View in Google Drive</a></p>`;
    };
    container.appendChild(img);
  } else if (previewType === "pdf") {
    // PDF preview with PDF.js
    container.innerHTML = '<div class="pdf-viewer"><canvas id="pdf-canvas"></canvas></div><div id="pdf-controls"><button onclick="previousPdfPage()" id="prev-btn">← Previous</button><span><input type="number" id="page-num" value="1" min="1"> / <span id="page-count">0</span></span><button onclick="nextPdfPage()" id="next-btn">Next →</button></div>';
    
    const canvas = document.getElementById("pdf-canvas");
    const pageNumInput = document.getElementById("page-num");
    const pageCountSpan = document.getElementById("page-count");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    
    // Initialize PDF.js
    pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;
    pdfjsLib.getDocument(`/api/preview/${fileId}`).promise.then((pdf) => {
      window.currentPdfDoc = pdf;
      window.currentPdfPage = 1;
      pageCountSpan.textContent = pdf.numPages;
      pageNumInput.setAttribute("max", pdf.numPages);
      renderPdfPage(1, canvas);
      
      pageNumInput.addEventListener("change", (e) => {
        const pageNum = parseInt(e.target.value, 10);
        if (pageNum >= 1 && pageNum <= pdf.numPages) {
          window.currentPdfPage = pageNum;
          renderPdfPage(pageNum, canvas);
        }
      });
    }).catch(() => {
      container.innerHTML = `<p class="preview-error">Failed to load PDF. <a href="https://drive.google.com/file/d/${fileId}/view" target="_blank">View in Google Drive</a></p>`;
    });
  }

  modal.classList.remove("hidden");
  overlay.classList.remove("hidden");
}

function renderPdfPage(pageNum, canvas) {
  if (!window.currentPdfDoc) return;
  
  window.currentPdfDoc.getPage(pageNum).then((page) => {
    const viewport = page.getViewport({ scale: 1.5 });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    
    const context = canvas.getContext("2d");
    page.render({ canvasContext: context, viewport }).promise.then(() => {
      document.getElementById("page-num").value = pageNum;
    });
  });
}

function previousPdfPage() {
  if (window.currentPdfPage > 1) {
    window.currentPdfPage--;
    renderPdfPage(window.currentPdfPage, document.getElementById("pdf-canvas"));
  }
}

function nextPdfPage() {
  if (window.currentPdfDoc && window.currentPdfPage < window.currentPdfDoc.numPages) {
    window.currentPdfPage++;
    renderPdfPage(window.currentPdfPage, document.getElementById("pdf-canvas"));
  }
}

function closePreview() {
  const modal = document.getElementById("preview-modal");
  const overlay = document.getElementById("preview-overlay");
  modal.classList.add("hidden");
  overlay.classList.add("hidden");
  window.currentPdfDoc = null;
  document.getElementById("preview-container").innerHTML = "";
}

// Add ESC key handler to close preview
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const modal = document.getElementById("preview-modal");
    if (!modal.classList.contains("hidden")) {
      closePreview();
    }
  }
});

// Reliable delegated click handling for preview buttons (works for static + dynamic rows)
document.addEventListener("click", (event) => {
  let target = event.target;
  if (!(target instanceof Element)) {
    target = target && target.parentElement ? target.parentElement : null;
  }
  if (!(target instanceof Element)) return;
  const btn = target.closest(".preview-btn");
  if (!btn) return;
  event.preventDefault();
  event.stopPropagation();
  const fileId = btn.dataset.id;
  const fileName = btn.dataset.name || "Preview";
  const mimeType = btn.dataset.mime || "";
  if (!fileId) return;
  openPreview(fileId, fileName, mimeType);
});

// Direct fallback binding for initially rendered browse buttons
document.addEventListener("DOMContentLoaded", () => {
  const previewButtons = Array.from(document.querySelectorAll(".preview-btn"));
  previewButtons.forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const fileId = button.dataset.id;
      const fileName = button.dataset.name || "Preview";
      const mimeType = button.dataset.mime || "";
      if (!fileId) return;
      openPreview(fileId, fileName, mimeType);
    });
  });
});

