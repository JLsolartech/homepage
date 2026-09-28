(() => {
  "use strict";

  const root = document.documentElement;
  const startedAt = typeof performance !== "undefined" && performance.now ? performance.now() : 0;
  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const noopQuery = { matches: false, addEventListener() {}, addListener() {} };
  const query = (text) => (window.matchMedia ? window.matchMedia(text) : noopQuery);
  const onQueryChange = (mql, handler) => {
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", handler);
    } else if (typeof mql.addListener === "function") {
      mql.addListener(handler);
    }
  };

  const reducedMotion = query("(prefers-reduced-motion: reduce)");
  const smallScreen = query("(max-width: 760px)");
  const stickyCapable = query("(min-width: 1081px) and (min-height: 640px)");

  // One rAF-throttled scroll/resize pipeline shared by every effect.
  const scrollHandlers = [];
  const measureHandlers = [];
  let frame = null;
  let needsMeasure = true;

  const runFrame = () => {
    frame = null;
    if (needsMeasure) {
      needsMeasure = false;
      measureHandlers.forEach((fn) => fn());
    }
    const scrollY = window.scrollY || window.pageYOffset || 0;
    const viewportHeight = window.innerHeight || root.clientHeight || 1;
    scrollHandlers.forEach((fn) => fn(scrollY, viewportHeight));
  };

  const requestFrame = () => {
    if (frame === null) {
      frame = window.requestAnimationFrame(runFrame);
    }
  };

  const requestMeasure = () => {
    needsMeasure = true;
    requestFrame();
  };

  const absoluteTop = (element) => element.getBoundingClientRect().top + (window.scrollY || window.pageYOffset || 0);

  function initReveal() {
    const items = Array.from(document.querySelectorAll(".reveal"));
    const showAll = () => items.forEach((item) => item.classList.add("is-visible"));

    // If the CSS failsafe has probably already revealed content, do not hide it again.
    if (!("IntersectionObserver" in window) || reducedMotion.matches || startedAt > 3000) {
      showAll();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.18, rootMargin: "0px 0px -5% 0px" }
    );

    items.forEach((item) => observer.observe(item));
    onQueryChange(reducedMotion, () => {
      if (reducedMotion.matches) {
        observer.disconnect();
        showAll();
      }
    });
  }

  function initParallax() {
    const items = Array.from(document.querySelectorAll("[data-parallax]")).map((el) => ({
      el,
      container: el.closest(".scene") || el.parentElement,
      speed: parseFloat(el.dataset.parallax || "0") || 0,
      zoom: parseFloat(el.dataset.zoom || "0") || 0,
      top: 0,
      height: 0,
      fillHeight: 0,
      active: false
    }));

    if (!items.length) {
      return;
    }

    let enabled = false;

    const reset = () => {
      items.forEach((item) => {
        item.el.style.removeProperty("--parallax-y");
        item.el.style.removeProperty("--parallax-scale");
        item.active = false;
      });
    };

    const measure = () => {
      if (!enabled) {
        return;
      }
      items.forEach((item) => {
        item.top = absoluteTop(item.container);
        item.height = item.container.offsetHeight;
        item.fillHeight = item.el.offsetHeight;
      });
    };

    const update = (scrollY, viewportHeight) => {
      if (!enabled) {
        return;
      }
      items.forEach((item) => {
        const rectTop = item.top - scrollY;
        if (rectTop > viewportHeight || rectTop + item.height < 0) {
          return;
        }
        const progress = clamp((viewportHeight - rectTop) / (viewportHeight + item.height), 0, 1);
        const scale = 1 + progress * item.zoom;
        // Never shift further than the image overscan, so no edge can ever be exposed.
        const overscan = Math.max(0, (item.fillHeight * scale - item.height) / 2 - 1);
        const offset = clamp((progress - 0.5) * 2 * viewportHeight * item.speed, -overscan, overscan);
        item.el.style.setProperty("--parallax-y", `${offset.toFixed(2)}px`);
        item.el.style.setProperty("--parallax-scale", scale.toFixed(4));
        item.active = true;
      });
    };

    const applyMode = () => {
      const next = !reducedMotion.matches && !smallScreen.matches;
      if (next === enabled) {
        return;
      }
      enabled = next;
      root.classList.toggle("parallax-on", enabled);
      if (!enabled) {
        reset();
      }
      requestMeasure();
    };

    measureHandlers.push(measure);
    scrollHandlers.push(update);
    onQueryChange(reducedMotion, applyMode);
    onQueryChange(smallScreen, applyMode);
    applyMode();
  }

  function initProcess() {
    const section = document.querySelector("[data-process]");
    if (!section) {
      return;
    }
    const layout = section.querySelector(".process-layout") || section;
    const steps = Array.from(section.querySelectorAll("[data-process-step]"));
    const media = Array.from(section.querySelectorAll("[data-process-media]"));
    const bar = section.querySelector("[data-process-bar]");
    if (!steps.length || steps.length !== media.length) {
      return;
    }

    let enhanced = false;
    let activeIndex = -1;
    let centers = [];

    const setActive = (index) => {
      if (index === activeIndex) {
        return;
      }
      activeIndex = index;
      steps.forEach((step, i) => step.classList.toggle("is-active", i === index));
      media.forEach((figure, i) => figure.classList.toggle("is-active", i === index));
      section.dataset.activeStep = String(index + 1);
    };

    const measure = () => {
      if (!enhanced) {
        return;
      }
      // offsetTop ignores transforms, so the measurement is stable while steps animate.
      const layoutTop = absoluteTop(layout);
      centers = steps.map((step) => layoutTop + step.offsetTop + step.offsetHeight / 2);
    };

    const update = (scrollY, viewportHeight) => {
      if (!enhanced || !centers.length) {
        return;
      }
      const focusLine = scrollY + viewportHeight * 0.55;
      let index = 0;
      centers.forEach((center, i) => {
        if (center - viewportHeight * 0.1 <= focusLine) {
          index = i;
        }
      });
      setActive(index);
      if (bar) {
        const first = centers[0];
        const last = centers[centers.length - 1];
        const progress = last > first ? clamp((focusLine - first) / (last - first), 0, 1) : 1;
        bar.style.transform = `scaleY(${progress.toFixed(4)})`;
        section.style.setProperty("--process-progress", progress.toFixed(4));
      }
    };

    const applyMode = () => {
      const next = stickyCapable.matches && !reducedMotion.matches;
      if (next === enhanced) {
        return;
      }
      enhanced = next;
      section.classList.toggle("is-enhanced", enhanced);
      if (!enhanced) {
        activeIndex = -1;
        centers = [];
        steps.forEach((step) => step.classList.remove("is-active"));
        media.forEach((figure) => figure.classList.remove("is-active"));
        delete section.dataset.activeStep;
        section.style.removeProperty("--process-progress");
        if (bar) {
          bar.style.removeProperty("transform");
        }
      } else {
        setActive(0);
      }
      requestMeasure();
    };

    measureHandlers.push(measure);
    scrollHandlers.push(update);
    onQueryChange(stickyCapable, applyMode);
    onQueryChange(reducedMotion, applyMode);
    applyMode();
  }

  function initGalleries() {
    document.querySelectorAll("[data-gallery]").forEach((gallery) => {
      const section = gallery.closest("[data-gallery-root]") || gallery.parentElement;
      const slides = Array.from(gallery.querySelectorAll(".gallery-slide"));
      if (!slides.length) {
        return;
      }
      const prevButton = section.querySelector("[data-gallery-prev]");
      const nextButton = section.querySelector("[data-gallery-next]");
      const title = section.querySelector("[data-gallery-title]");
      const copy = section.querySelector("[data-gallery-copy]");
      const current = section.querySelector("[data-gallery-current]");
      const total = section.querySelector("[data-gallery-total]");
      let index = Math.max(0, slides.findIndex((slide) => slide.classList.contains("is-active")));
      let touchStartX = null;
      let touchStartY = null;

      slides.forEach((slide, i) => {
        slide.setAttribute("role", "group");
        slide.setAttribute("aria-roledescription", "slide");
        slide.setAttribute("aria-label", `${i + 1} of ${slides.length}`);
      });

      const render = () => {
        slides.forEach((slide, i) => {
          const active = i === index;
          slide.classList.toggle("is-active", active);
          slide.setAttribute("aria-hidden", active ? "false" : "true");
        });
        const active = slides[index];
        if (title) {
          title.textContent = active.dataset.title || "";
        }
        if (copy) {
          copy.textContent = active.dataset.copy || "";
        }
        if (current) {
          current.textContent = String(index + 1).padStart(2, "0");
        }
        if (total) {
          total.textContent = String(slides.length).padStart(2, "0");
        }
        gallery.dataset.index = String(index);
      };

      const step = (direction) => {
        index = (index + direction + slides.length) % slides.length;
        render();
      };

      if (prevButton) {
        prevButton.addEventListener("click", () => step(-1));
      }
      if (nextButton) {
        nextButton.addEventListener("click", () => step(1));
      }

      // Vertical wheel is intentionally NOT intercepted: page scrolling always stays native.

      gallery.addEventListener(
        "touchstart",
        (event) => {
          const touch = event.changedTouches[0];
          touchStartX = touch.clientX;
          touchStartY = touch.clientY;
        },
        { passive: true }
      );

      gallery.addEventListener(
        "touchend",
        (event) => {
          if (touchStartX === null || touchStartY === null) {
            return;
          }
          const touch = event.changedTouches[0];
          const deltaX = touch.clientX - touchStartX;
          const deltaY = touch.clientY - touchStartY;
          touchStartX = null;
          touchStartY = null;
          if (Math.abs(deltaX) > 48 && Math.abs(deltaX) > Math.abs(deltaY) * 1.5) {
            step(deltaX < 0 ? 1 : -1);
          }
        },
        { passive: true }
      );

      gallery.addEventListener(
        "touchcancel",
        () => {
          touchStartX = null;
          touchStartY = null;
        },
        { passive: true }
      );

      // Arrow keys only act while focus is inside the gallery component.
      section.addEventListener("keydown", (event) => {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
          return;
        }
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
          event.preventDefault();
          step(event.key === "ArrowLeft" ? -1 : 1);
        }
      });

      render();
    });
  }

  const safely = (fn) => {
    try {
      fn();
      return true;
    } catch (error) {
      if (window.console && console.error) {
        console.error(error);
      }
      return false;
    }
  };

  const revealOk = safely(initReveal);
  if (!revealOk) {
    // Never leave content hidden if the reveal effect could not start.
    root.classList.remove("js");
  }
  safely(initParallax);
  safely(initProcess);
  safely(initGalleries);

  window.addEventListener("scroll", requestFrame, { passive: true });
  window.addEventListener("resize", requestMeasure, { passive: true });
  window.addEventListener("orientationchange", requestMeasure, { passive: true });
  window.addEventListener("load", requestMeasure);
  window.addEventListener("pageshow", requestMeasure);
  if ("ResizeObserver" in window) {
    const main = document.querySelector(".site-main");
    if (main) {
      new ResizeObserver(requestMeasure).observe(main);
    }
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(requestMeasure, () => {});
  }

  requestMeasure();
  root.classList.add("js-ready");
})();
