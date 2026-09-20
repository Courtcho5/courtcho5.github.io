/* Two small scroll-driven effects, both purely visual polish — the page
   works fine with plain CSS/HTML if this never runs:
     1. Toggles .is-scrolled on the nav once the page has scrolled a little,
        so the bar tightens up and its background solidifies.
     2. Fills the progress bar at the top of the viewport to match how far
        down the page you've scrolled. */
(function () {
    var nav = document.querySelector('.site-nav');
    var fill = document.querySelector('.progress-bar__fill');

    function onScroll() {
        if (nav) {
            if (window.scrollY > 40) {
                nav.classList.add('is-scrolled');
            } else {
                nav.classList.remove('is-scrolled');
            }
        }

        if (fill) {
            var doc = document.documentElement;
            var scrollable = doc.scrollHeight - doc.clientHeight;
            var pct = scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0;
            fill.style.width = pct + '%';
        }
    }

    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
})();
