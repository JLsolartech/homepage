(() => {
  "use strict";

  const page = document.querySelector(".page-products");
  const dialog = document.querySelector("[data-product-lightbox]");
  if (!page || !dialog || typeof dialog.showModal !== "function") {
    return;
  }

  const dialogImage = dialog.querySelector("[data-product-lightbox-image]");
  const dialogTitle = dialog.querySelector("#products-lightbox-title");
  const closeButton = dialog.querySelector("[data-product-lightbox-close]");
  const lightboxViewport = dialog.querySelector("[data-lightbox-viewport]");
  const zoomInButton = dialog.querySelector("[data-zoom-in]");
  const zoomOutButton = dialog.querySelector("[data-zoom-out]");
  const zoomResetButton = dialog.querySelector("[data-zoom-reset]");
  const zoomStatus = dialog.querySelector("[data-zoom-status]");
  const lightboxAvif = dialog.querySelector("[data-product-lightbox-avif]");
  const lightboxWebp = dialog.querySelector("[data-product-lightbox-webp]");
  const imageLinks = Array.from(page.querySelectorAll("[data-product-lightbox-link]"));

  if (!dialogImage || !dialogTitle || !closeButton || !lightboxViewport ||
      !zoomInButton || !zoomOutButton || !zoomResetButton || !zoomStatus ||
      !lightboxAvif || !lightboxWebp || imageLinks.length === 0) {
    return;
  }

  const selectedFile = /^[A-Z0-9_]+$/;
  let lightboxTrigger = null;
  let zoom = 1;
  let panX = 0;
  let panY = 0;
  let dragStart = null;
  let highResolutionFallbackUsed = false;

  const asset = (file, extension) => `../assets/optimized/${file}-${extension}`;

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

  for (const link of imageLinks) {
    link.addEventListener("click", (event) => {
      const file = link.dataset.productFile;
      const thumbnail = link.querySelector("img");
      if (!selectedFile.test(file) || !thumbnail) {
        console.error("The selected product profile image could not be opened.");
        return;
      }

      event.preventDefault();
      lightboxTrigger = link;
      dialogTitle.textContent = link.dataset.productLabel || "Profile image";
      dialogImage.alt = thumbnail.alt;
      lightboxAvif.srcset = `${asset(file, "1600.avif")} 1600w, ${asset(file, "2400.avif")} 2400w`;
      lightboxWebp.srcset = `${asset(file, "1600.webp")} 1600w, ${asset(file, "2400.webp")} 2400w`;
      dialogImage.src = thumbnail.currentSrc || thumbnail.src;
      highResolutionFallbackUsed = false;
      resetZoom();
      dialog.showModal();
      closeButton.focus();
    });
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
    if (!dialog.open || !lightboxTrigger || highResolutionFallbackUsed) {
      if (dialog.open && highResolutionFallbackUsed) {
        console.error("The profile image and its display-size fallback could not be loaded.");
      }
      return;
    }
    highResolutionFallbackUsed = true;
    lightboxAvif.removeAttribute("srcset");
    lightboxWebp.removeAttribute("srcset");
    dialogImage.src = lightboxTrigger.querySelector("img").currentSrc;
    updateZoom();
  });

  closeButton.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    resetZoom();
    lightboxAvif.removeAttribute("srcset");
    lightboxWebp.removeAttribute("srcset");
    dialogImage.removeAttribute("src");
    dialogImage.alt = "";
    if (lightboxTrigger && lightboxTrigger.isConnected) {
      lightboxTrigger.focus();
    }
    lightboxTrigger = null;
  });

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });

  page.classList.add("products-interactive");
})();
