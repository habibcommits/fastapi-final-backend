// frontend/js/app.js

// ===== Configuration =====
const API_BASE_URL = "http://localhost:8000";

// ===== State Management =====
const state = {
  convert: {
    files: [],
  },
  merge: {
    files: [],
  },
  compress: {
    file: null,
  },
  currentBlob: null,
  currentFilename: null,
};

// ===== Utility Functions =====
function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function generateId() {
  return Math.random().toString(36).substring(2, 9);
}

// ===== Toast Notifications =====
function showToast(type, title, message) {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const icons = {
    success: "fa-check-circle",
    error: "fa-times-circle",
    warning: "fa-exclamation-triangle",
  };

  toast.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "slideIn 0.3s ease reverse";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ===== Modal Functions =====
function showProgressModal(title, text) {
  const modal = document.getElementById("progressModal");
  document.getElementById("progressTitle").textContent = title;
  document.getElementById("progressText").textContent = text;
  document.getElementById("progressFill").style.width = "30%";
  modal.classList.add("visible");

  // Animate progress
  let width = 30;
  const interval = setInterval(() => {
    if (width < 90) {
      width += Math.random() * 10;
      document.getElementById("progressFill").style.width = width + "%";
    }
  }, 500);

  return () => clearInterval(interval);
}

function hideProgressModal() {
  document.getElementById("progressFill").style.width = "100%";
  setTimeout(() => {
    document.getElementById("progressModal").classList.remove("visible");
  }, 300);
}

function showResultModal(success, title, details) {
  const modal = document.getElementById("resultModal");
  const icon = document.getElementById("resultIcon");
  const titleEl = document.getElementById("resultTitle");
  const detailsEl = document.getElementById("resultDetails");

  icon.innerHTML = success
    ? '<i class="fas fa-check-circle"></i>'
    : '<i class="fas fa-times-circle"></i>';
  icon.className = `result-icon ${success ? "success" : "error"}`;

  titleEl.textContent = title;

  let detailsHtml = "";
  for (const [label, value] of Object.entries(details)) {
    const highlight =
      label.includes("Ratio") || label.includes("Saved") ? "highlight" : "";
    detailsHtml += `
            <div class="detail-row">
                <span class="detail-label">${label}</span>
                <span class="detail-value ${highlight}">${value}</span>
            </div>
        `;
  }
  detailsEl.innerHTML = detailsHtml;

  document.getElementById("downloadBtn").style.display = success
    ? "flex"
    : "none";

  modal.classList.add("visible");
}

function hideResultModal() {
  document.getElementById("resultModal").classList.remove("visible");
}

// ===== Tab Navigation =====
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.dataset.tab;

      tabBtns.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(tabId).classList.add("active");
    });
  });
}

// ===== Drag and Drop =====
function initDropZone(dropZoneId, inputId, handleFiles, multiple = true) {
  const dropZone = document.getElementById(dropZoneId);
  const input = document.getElementById(inputId);

  ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, preventDefaults);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, () =>
      dropZone.classList.add("dragover")
    );
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, () =>
      dropZone.classList.remove("dragover")
    );
  });

  dropZone.addEventListener("drop", (e) => {
    const files = multiple
      ? [...e.dataTransfer.files]
      : [e.dataTransfer.files[0]];
    handleFiles(files);
  });

  input.addEventListener("change", (e) => {
    const files = multiple ? [...e.target.files] : [e.target.files[0]];
    handleFiles(files);
    input.value = "";
  });

  dropZone.addEventListener("click", (e) => {
    if (!e.target.closest(".file-input-label")) {
      input.click();
    }
  });
}

// ===== File List Rendering =====
function renderFileList(containerId, files, type, onRemove) {
  const container = document.getElementById(containerId);

  if (files.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = files
    .map(
      (file, index) => `
        <div class="file-item" data-id="${file.id}">
            ${
              type === "merge"
                ? '<i class="fas fa-grip-vertical drag-handle"></i>'
                : ""
            }
            ${
              file.preview
                ? `<img src="${file.preview}" class="file-preview" alt="${file.name}">`
                : `<div class="file-icon ${type === "convert" ? "image" : ""}">
                    <i class="fas ${
                      type === "convert" ? "fa-image" : "fa-file-pdf"
                    }"></i>
                   </div>`
            }
            <div class="file-details">
                <div class="file-name">${file.name}</div>
                <div class="file-size">${formatFileSize(file.size)}</div>
            </div>
            <button class="remove-btn" data-index="${index}">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `
    )
    .join("");

  // Add remove handlers
  container.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const index = parseInt(btn.dataset.index);
      onRemove(index);
    });
  });

  // Add drag-and-drop sorting for merge
  if (type === "merge") {
    initSortable(container);
  }
}

// ===== Simple Sortable =====
function initSortable(container) {
  let draggedItem = null;

  container.querySelectorAll(".file-item").forEach((item) => {
    const handle = item.querySelector(".drag-handle");

    handle.addEventListener("mousedown", () => {
      item.setAttribute("draggable", true);
    });

    item.addEventListener("dragstart", (e) => {
      draggedItem = item;
      item.classList.add("sortable-ghost");
    });

    item.addEventListener("dragend", () => {
      item.classList.remove("sortable-ghost");
      item.setAttribute("draggable", false);

      // Update state based on new order
      const newOrder = [...container.querySelectorAll(".file-item")].map(
        (el) => el.dataset.id
      );

      state.merge.files = newOrder.map((id) =>
        state.merge.files.find((f) => f.id === id)
      );
    });

    item.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (item !== draggedItem) {
        const rect = item.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (e.clientY < midY) {
          item.parentNode.insertBefore(draggedItem, item);
        } else {
          item.parentNode.insertBefore(draggedItem, item.nextSibling);
        }
      }
    });
  });
}

// ===== Convert: Images to PDF =====
function initConvert() {
  const btn = document.getElementById("convertBtn");

  function handleFiles(files) {
    const validFiles = files.filter((f) => f.type.startsWith("image/"));

    if (validFiles.length !== files.length) {
      showToast(
        "warning",
        "Invalid Files",
        "Some files were skipped (not images)"
      );
    }

    validFiles.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        state.convert.files.push({
          id: generateId(),
          file: file,
          name: file.name,
          size: file.size,
          preview: e.target.result,
        });
        updateConvertUI();
      };
      reader.readAsDataURL(file);
    });
  }

  function removeFile(index) {
    state.convert.files.splice(index, 1);
    updateConvertUI();
  }

  function updateConvertUI() {
    renderFileList(
      "convertFileList",
      state.convert.files,
      "convert",
      removeFile
    );
    btn.disabled = state.convert.files.length === 0;
  }

  initDropZone("convertDropZone", "convertFiles", handleFiles);

  btn.addEventListener("click", async () => {
    if (state.convert.files.length === 0) return;

    const stopProgress = showProgressModal(
      "Converting Images",
      "Creating your PDF..."
    );

    try {
      const formData = new FormData();
      state.convert.files.forEach((f) => formData.append("files", f.file));
      formData.append("page_size", document.getElementById("pageSize").value);
      formData.append(
        "orientation",
        document.getElementById("orientation").value
      );
      formData.append("margin", document.getElementById("margin").value);

      const response = await fetch(`${API_BASE_URL}/api/v1/images-to-pdf`, {
        method: "POST",
        body: formData,
      });

      stopProgress();
      hideProgressModal();

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Conversion failed");
      }

      const blob = await response.blob();
      state.currentBlob = blob;
      state.currentFilename = "converted.pdf";

      const processingTime = response.headers.get("X-Processing-Time-Ms");
      const pagesCount = response.headers.get("X-Pages-Count");

      showResultModal(true, "Conversion Complete!", {
        "Images Converted": state.convert.files.length,
        "Total Pages": pagesCount || state.convert.files.length,
        "Output Size": formatFileSize(blob.size),
        "Processing Time": `${parseFloat(processingTime).toFixed(0)}ms`,
      });

      // Clear files
      state.convert.files = [];
      updateConvertUI();
    } catch (error) {
      stopProgress();
      hideProgressModal();
      showToast("error", "Conversion Failed", error.message);
    }
  });
}

// ===== Merge: PDFs =====
function initMerge() {
  const btn = document.getElementById("mergeBtn");

  function handleFiles(files) {
    const validFiles = files.filter(
      (f) =>
        f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
    );

    if (validFiles.length !== files.length) {
      showToast(
        "warning",
        "Invalid Files",
        "Some files were skipped (not PDFs)"
      );
    }

    validFiles.forEach((file) => {
      state.merge.files.push({
        id: generateId(),
        file: file,
        name: file.name,
        size: file.size,
      });
    });
    updateMergeUI();
  }

  function removeFile(index) {
    state.merge.files.splice(index, 1);
    updateMergeUI();
  }

  function updateMergeUI() {
    renderFileList("mergeFileList", state.merge.files, "merge", removeFile);
    btn.disabled = state.merge.files.length < 2;
  }

  initDropZone("mergeDropZone", "mergeFiles", handleFiles);

  btn.addEventListener("click", async () => {
    if (state.merge.files.length < 2) return;

    const stopProgress = showProgressModal(
      "Merging PDFs",
      "Combining your documents..."
    );

    try {
      const formData = new FormData();
      state.merge.files.forEach((f) => formData.append("files", f.file));
      formData.append(
        "output_filename",
        document.getElementById("outputFilename").value
      );
      formData.append(
        "add_bookmarks",
        document.getElementById("addBookmarks").checked
      );

      const response = await fetch(`${API_BASE_URL}/api/v1/merge-pdfs`, {
        method: "POST",
        body: formData,
      });

      stopProgress();
      hideProgressModal();

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Merge failed");
      }

      const blob = await response.blob();
      state.currentBlob = blob;
      state.currentFilename =
        document.getElementById("outputFilename").value || "merged.pdf";

      const processingTime = response.headers.get("X-Processing-Time-Ms");
      const totalPages = response.headers.get("X-Total-Pages");
      const filesMerged = response.headers.get("X-Files-Merged");

      showResultModal(true, "Merge Complete!", {
        "Files Merged": filesMerged || state.merge.files.length,
        "Total Pages": totalPages || "-",
        "Output Size": formatFileSize(blob.size),
        "Processing Time": `${parseFloat(processingTime).toFixed(0)}ms`,
      });

      // Clear files
      state.merge.files = [];
      updateMergeUI();
    } catch (error) {
      stopProgress();
      hideProgressModal();
      showToast("error", "Merge Failed", error.message);
    }
  });
}

// ===== Compress: PDF =====
function initCompress() {
  const btn = document.getElementById("compressBtn");
  const fileInfo = document.getElementById("compressFileInfo");

  function handleFiles(files) {
    const file = files[0];

    if (!file) return;

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      showToast("error", "Invalid File", "Please select a PDF file");
      return;
    }

    state.compress.file = file;
    updateCompressUI();
  }

  function updateCompressUI() {
    if (state.compress.file) {
      fileInfo.classList.add("visible");
      fileInfo.innerHTML = `
                <div class="info-icon">
                    <i class="fas fa-file-pdf"></i>
                </div>
                <div class="info-details">
                    <div class="info-name">${state.compress.file.name}</div>
                    <div class="info-size">${formatFileSize(
                      state.compress.file.size
                    )}</div>
                </div>
                <button class="remove-btn" id="removeCompressFile">
                    <i class="fas fa-times"></i>
                </button>
            `;

      document
        .getElementById("removeCompressFile")
        .addEventListener("click", () => {
          state.compress.file = null;
          updateCompressUI();
        });

      btn.disabled = false;
    } else {
      fileInfo.classList.remove("visible");
      fileInfo.innerHTML = "";
      btn.disabled = true;
    }
  }

  initDropZone("compressDropZone", "compressFile", handleFiles, false);

  btn.addEventListener("click", async () => {
    if (!state.compress.file) return;

    const stopProgress = showProgressModal(
      "Compressing PDF",
      "Optimizing your document..."
    );

    try {
      const formData = new FormData();
      formData.append("file", state.compress.file);
      formData.append(
        "level",
        document.querySelector('input[name="compressionLevel"]:checked').value
      );
      formData.append(
        "remove_metadata",
        document.getElementById("removeMetadata").checked
      );
      formData.append(
        "linearize",
        document.getElementById("linearize").checked
      );

      const originalSize = state.compress.file.size;

      const response = await fetch(`${API_BASE_URL}/api/v1/compress-pdf`, {
        method: "POST",
        body: formData,
      });

      stopProgress();
      hideProgressModal();

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Compression failed");
      }

      const blob = await response.blob();
      state.currentBlob = blob;
      state.currentFilename = state.compress.file.name.replace(
        ".pdf",
        "_compressed.pdf"
      );

      const processingTime = response.headers.get("X-Processing-Time-Ms");
      const compressedSize = parseInt(
        response.headers.get("X-Compressed-Size")
      );
      const compressionRatio = response.headers.get("X-Compression-Ratio");
      const savedBytes = originalSize - blob.size;

      showResultModal(true, "Compression Complete!", {
        "Original Size": formatFileSize(originalSize),
        "Compressed Size": formatFileSize(blob.size),
        "Space Saved": formatFileSize(savedBytes),
        "Compression Ratio":
          compressionRatio ||
          `${((1 - blob.size / originalSize) * 100).toFixed(1)}%`,
        "Processing Time": `${parseFloat(processingTime).toFixed(0)}ms`,
      });

      // Clear file
      state.compress.file = null;
      updateCompressUI();
    } catch (error) {
      stopProgress();
      hideProgressModal();
      showToast("error", "Compression Failed", error.message);
    }
  });
}

// ===== Download Handler =====
function initDownload() {
  document.getElementById("downloadBtn").addEventListener("click", () => {
    if (state.currentBlob && state.currentFilename) {
      const url = URL.createObjectURL(state.currentBlob);
      const a = document.createElement("a");
      a.href = url;
      a.download = state.currentFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      showToast("success", "Download Started", state.currentFilename);
      hideResultModal();
    }
  });

  document
    .getElementById("closeResultBtn")
    .addEventListener("click", hideResultModal);
}

// ===== API Health Check =====
async function checkAPIHealth() {
  const status = document.getElementById("apiStatus");
  const statusText = status.querySelector(".status-text");

  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    const data = await response.json();

    if (data.status === "healthy") {
      status.classList.add("online");
      status.classList.remove("offline");
      statusText.textContent = "API Online";
    } else {
      throw new Error("API unhealthy");
    }
  } catch (error) {
    status.classList.add("offline");
    status.classList.remove("online");
    statusText.textContent = "API Offline";
    showToast("error", "API Unavailable", "Cannot connect to the server");
  }
}

// ===== Initialize App =====
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initConvert();
  initMerge();
  initCompress();
  initDownload();
  checkAPIHealth();

  // Periodic health check
  setInterval(checkAPIHealth, 30000);
});
