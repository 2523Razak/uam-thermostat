document.addEventListener('DOMContentLoaded', () => {

  // ---- Apparition fluide des sections au défilement ----
  const revealItems = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });

  revealItems.forEach((item) => observer.observe(item));

  // ---- Retour à la page de connexion ----
  // Sur la plateforme réelle, remplacez '#' (dans le HTML) par
  // l'URL Flask, ex. : {{ url_for('connections') }}
  const backBtn = document.getElementById('backToLogin');
  if (backBtn) {
    backBtn.addEventListener('click', (e) => {
      if (backBtn.getAttribute('href') === '#') {
        e.preventDefault();
        window.history.back();
      }
    });
  }

  // ---- Galerie : ouverture en grand format (lightbox) ----
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = document.getElementById('lightboxImg');
  const lightboxCaption = document.getElementById('lightboxCaption');
  const lightboxClose = document.getElementById('lightboxClose');

  document.querySelectorAll('.plate').forEach((plate) => {
    plate.addEventListener('click', () => {
      const fullSrc = plate.getAttribute('data-full');
      const caption = plate.querySelector('figcaption')?.textContent || '';
      lightboxImg.setAttribute('src', fullSrc);
      lightboxCaption.textContent = caption;
      lightbox.classList.add('open');
    });
  });

  function closeLightbox() {
    lightbox.classList.remove('open');
    lightboxImg.setAttribute('src', '');
  }

  lightboxClose.addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) closeLightbox();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
  });

});
