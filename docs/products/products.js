(() => {
  "use strict";

  const page = document.querySelector(".page-products");
  const picker = document.querySelector("[data-product-picker]");
  const mainPicture = document.querySelector("[data-product-main-picture]");
  const mainImage = document.querySelector("[data-product-main-image]");
  const mainLink = document.querySelector("[data-product-lightbox-link]");
  const title = document.querySelector("[data-product-sample-title]");
  const copy = document.querySelector("[data-product-sample-copy]");
  const dialog = document.querySelector("[data-product-lightbox]");
  const dialogImage = document.querySelector("[data-product-lightbox-image]");
  const dialogTitle = document.querySelector("#products-lightbox-title");
  const closeButton = document.querySelector("[data-product-lightbox-close]");
  const lightboxViewport = document.querySelector("[data-lightbox-viewport]");
  const zoomInButton = document.querySelector("[data-zoom-in]");
  const zoomOutButton = document.querySelector("[data-zoom-out]");
  const zoomResetButton = document.querySelector("[data-zoom-reset]");
  const zoomStatus = document.querySelector("[data-zoom-status]");

  if (!page || !picker || !mainPicture || !mainImage || !mainLink ||
      !title || !copy || !dialog || !dialogImage || !dialogTitle || !closeButton ||
      !lightboxViewport || !zoomInButton || !zoomOutButton || !zoomResetButton || !zoomStatus) {
    return;
  }

  const avifSource = mainPicture.querySelector('source[type="image/avif"]');
  const webpSource = mainPicture.querySelector('source[type="image/webp"]');
  const lightboxAvif = dialog.querySelector("[data-product-lightbox-avif]");
  const lightboxWebp = dialog.querySelector("[data-product-lightbox-webp]");
  const samples = Array.from(picker.querySelectorAll("[data-product-sample]"));
  const selectedFile = /^[A-Z0-9_]+$/;
  let lightboxTrigger = null;
  let activeSample = "R5_L6213";
  let zoom = 1;
  let panX = 0;
  let panY = 0;
  let dragStart = null;
  let highResolutionFallbackUsed = false;

  if (!avifSource || !webpSource || !lightboxAvif || !lightboxWebp || samples.length === 0) {
    return;
  }

  const asset = (file, extension) => `../assets/optimized/${file}-${extension}`;
  const srcset = (file, extension, widths) =>
    widths.map((width) => `${asset(file, `${width}.${extension}`)} ${width}w`).join(", ");

  const selectSample = (button) => {
    const file = button.dataset.productSample;
    if (!selectedFile.test(file)) {
      console.error(`Invalid product sample reference: ${file}`);
      return;
    }

    const alt = button.dataset.sampleAlt;
    const label = button.dataset.sampleLabel;
    avifSource.srcset = srcset(file, "avif", [480, 800, 1200]);
    webpSource.srcset = srcset(file, "webp", [480, 800, 1200]);
    mainImage.src = asset(file, "1200.png");
    mainImage.alt = alt;
    mainLink.href = asset(file, "1600.webp");
    mainLink.setAttribute("aria-label", `Open larger image: ${label.toLowerCase()}`);
    title.textContent = label;
    copy.textContent = button.dataset.sampleCopy;
    dialogTitle.textContent = label;
    dialogImage.alt = alt;
    activeSample = file;

    for (const sample of samples) {
      sample.setAttribute("aria-pressed", String(sample === button));
    }
  };

  const clampPan = () => {
    const maxX = Math.max(0, (dialogImage.offsetWidth * zoom - lightboxViewport.clientWidth) / 2);
    const maxY = Math.max(0, (dialogImage.offsetHeight * zoom - lightboxViewport.clientHeight) / 2);
    panX = Math.max(-maxX, Math.min(maxX, panX));
    panY = Math.max(-maxY, Math.min(maxY, panY));
  };

  const updateZoom = () => {
    clampPan();
    dialogImage.style.transform = `translate3d(${panX}px, ${panY}px, 0) scale(${zoom})`;
    zoomStatus.value = `${Math.round(zoom * 100)}%`;
    zoomOutButton.disabled = zoom <= 1;
    zoomInButton.disabled = zoom >= 2.5;
    lightboxViewport.style.cursor = zoom > 1 ? "grab" : "default";
  };

  const resetZoom = () => {
    zoom = 1;
    panX = 0;
    panY = 0;
    updateZoom();
  };

  const changeZoom = (amount) => {
    zoom = Math.max(1, Math.min(2.5, zoom + amount));
    if (zoom === 1) {
      panX = 0;
      panY = 0;
    }
    updateZoom();
  };

  for (const sample of samples) {
    sample.addEventListener("click", () => selectSample(sample));
  }

  zoomInButton.addEventListener("click", () => changeZoom(0.25));
  zoomOutButton.addEventListener("click", () => changeZoom(-0.25));
  zoomResetButton.addEventListener("click", resetZoom);

  lightboxViewport.addEventListener("pointerdown", (event) => {
    if (zoom <= 1 || (event.pointerType === "mouse" && event.button !== 0)) {
      return;
    }
    event.preventDefault();
    dragStart = { x: event.clientX, y: event.clientY, panX, panY };
    lightboxViewport.setPointerCapture(event.pointerId);
    lightboxViewport.classList.add("is-dragging");
  });

  lightboxViewport.addEventListener("pointermove", (event) => {
    if (!dragStart) {
      return;
    }
    panX = dragStart.panX + event.clientX - dragStart.x;
    panY = dragStart.panY + event.clientY - dragStart.y;
    updateZoom();
  });

  const stopDragging = () => {
    dragStart = null;
    lightboxViewport.classList.remove("is-dragging");
  };
  lightboxViewport.addEventListener("pointerup", stopDragging);
  lightboxViewport.addEventListener("pointercancel", stopDragging);
  lightboxViewport.addEventListener("lostpointercapture", stopDragging);

  dialogImage.addEventListener("load", updateZoom);
  dialogImage.addEventListener("error", () => {
    if (!dialog.open || !mainImage.currentSrc || highResolutionFallbackUsed) {
      if (dialog.open && highResolutionFallbackUsed) {
        console.error("The product sample image and its display-size fallback could not be loaded.");
      }
      return;
    }
    highResolutionFallbackUsed = true;
    lightboxAvif.removeAttribute("srcset");
    lightboxWebp.removeAttribute("srcset");
    dialogImage.src = mainImage.currentSrc;
    updateZoom();
  });

  closeButton.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    resetZoom();
    if (lightboxTrigger && lightboxTrigger.isConnected) {
      lightboxTrigger.focus();
    }
    lightboxTrigger = null;
  });

  mainLink.addEventListener("click", (event) => {
    if (typeof dialog.showModal !== "function") {
      return;
    }
    event.preventDefault();
    lightboxTrigger = mainLink;
    dialogImage.src = mainImage.currentSrc || mainImage.src;
    dialogImage.alt = mainImage.alt;
    lightboxAvif.srcset = `${asset(activeSample, "1600.avif")} 1600w, ${asset(activeSample, "2400.avif")} 2400w`;
    lightboxWebp.srcset = `${asset(activeSample, "1600.webp")} 1600w, ${asset(activeSample, "2400.webp")} 2400w`;
    highResolutionFallbackUsed = false;
    resetZoom();
    dialog.showModal();
    closeButton.focus();
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });

  picker.hidden = false;
  page.classList.add("products-interactive");
})();
