(() => {
  const carousel = document.querySelector('.market-carousel');
  if (!carousel) return;

  const slides = [...carousel.querySelectorAll('img')];
  const controls = carousel.querySelector('.market-carousel-controls');
  const dots = [...carousel.querySelectorAll('.market-carousel-dots i')];
  const status = carousel.querySelector('.market-carousel-status');
  const toggle = controls.querySelector('.market-carousel-toggle');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let current = 0;
  let startTouch;
  let timer = null;

  function step(direction, announce = false) {
    slides[current].hidden = true;
    dots[current].classList.remove('is-current');
    current = (current + direction + slides.length) % slides.length;
    slides[current].hidden = false;
    dots[current].classList.add('is-current');
    if (announce) status.textContent = `Imagen ${current + 1} de ${slides.length}. ${slides[current].alt}`;
  }

  function setRotation(running) {
    window.clearInterval(timer);
    timer = running ? window.setInterval(() => {
      if (!document.hidden && !carousel.matches(':hover')) step(1);
    }, 7000) : null;
    toggle.setAttribute('aria-label', running ? 'Pausar carrusel' : 'Reanudar carrusel');
    toggle.firstElementChild.textContent = running ? '❚❚' : '▶';
  }

  function navigate(direction) {
    setRotation(false);
    step(direction, true);
  }

  controls.querySelector('.market-carousel-prev').addEventListener('click', () => navigate(-1));
  controls.querySelector('.market-carousel-next').addEventListener('click', () => navigate(1));
  controls.addEventListener('focusin', (event) => {
    if (event.target !== toggle && event.target.matches(':focus-visible')) setRotation(false);
  });
  toggle.addEventListener('click', () => setRotation(timer === null));
  reducedMotion.addEventListener('change', (event) => {
    if (event.matches) setRotation(false);
  });
  controls.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    navigate(event.key === 'ArrowLeft' ? -1 : 1);
  });
  carousel.addEventListener('touchstart', (event) => {
    startTouch = event.touches.length === 1 ? event.touches[0] : null;
  }, { passive: true });
  carousel.addEventListener('touchend', (event) => {
    if (!startTouch) return;
    const end = event.changedTouches[0];
    const dx = end.clientX - startTouch.clientX;
    const dy = end.clientY - startTouch.clientY;
    startTouch = null;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) navigate(dx < 0 ? 1 : -1);
  }, { passive: true });
  carousel.addEventListener('touchcancel', () => { startTouch = null; }, { passive: true });
  setRotation(!reducedMotion.matches);
  controls.hidden = false;
})();
