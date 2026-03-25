const revealItems = document.querySelectorAll(".reveal");
const parallaxItems = document.querySelectorAll("[data-parallax], [data-zoom]");

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    },
    {
      threshold: 0.18,
      rootMargin: "0px 0px -5% 0px"
    }
  );

  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

let parallaxFrame = null;

function updateParallax() {
  const viewportHeight = window.innerHeight || 1;

  parallaxItems.forEach((item) => {
    const speed = parseFloat(item.dataset.parallax || "0");
    const zoom = parseFloat(item.dataset.zoom || "0");
    const rect = item.getBoundingClientRect();
    const progress = clamp((viewportHeight - rect.top) / (viewportHeight + rect.height), 0, 1);
    const centered = (progress - 0.5) * 2;
    const offset = centered * viewportHeight * speed;
    const scale = 1 + progress * zoom;

    item.style.setProperty("--parallax-y", `${offset.toFixed(2)}px`);
    item.style.setProperty("--parallax-scale", scale.toFixed(3));
  });

  parallaxFrame = null;
}

function requestParallax() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }

  if (parallaxFrame === null) {
    parallaxFrame = window.requestAnimationFrame(updateParallax);
  }
}

requestParallax();
window.addEventListener("scroll", requestParallax, { passive: true });
window.addEventListener("resize", requestParallax);
window.addEventListener("load", requestParallax);

const galleries = document.querySelectorAll("[data-gallery]");

galleries.forEach((gallery) => {
  const section = gallery.closest(".gallery-layout") || gallery.parentElement;
  const slides = Array.from(gallery.querySelectorAll(".gallery-slide"));
  const prevButton = section.querySelector("[data-gallery-prev]");
  const nextButton = section.querySelector("[data-gallery-next]");
  const title = section.querySelector("[data-gallery-title]");
  const copy = section.querySelector("[data-gallery-copy]");
  const current = section.querySelector("[data-gallery-current]");
  const total = section.querySelector("[data-gallery-total]");
  let index = slides.findIndex((slide) => slide.classList.contains("is-active"));
  let wheelReady = true;

  if (index < 0) {
    index = 0;
  }

  const render = () => {
    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle("is-active", slideIndex === index);
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
  };

  const step = (direction) => {
    index = (index + direction + slides.length) % slides.length;
    render();
  };

  prevButton?.addEventListener("click", () => step(-1));
  nextButton?.addEventListener("click", () => step(1));

  gallery.addEventListener(
    "wheel",
    (event) => {
      if (!wheelReady || Math.abs(event.deltaY) < 12) {
        return;
      }

      event.preventDefault();
      wheelReady = false;
      step(event.deltaY > 0 ? 1 : -1);
      window.setTimeout(() => {
        wheelReady = true;
      }, 420);
    },
    { passive: false }
  );

  window.addEventListener("keydown", (event) => {
    if (document.body.contains(gallery)) {
      if (event.key === "ArrowLeft") {
        step(-1);
      }
      if (event.key === "ArrowRight") {
        step(1);
      }
    }
  });

  render();
});
