/* Toggles .is-scrolled on the nav once the page has scrolled a little, so
   the bar tightens up and its background solidifies. Purely a polish
   detail — the nav works fine with plain CSS if this never runs. */
(function () {
    var nav = document.querySelector('.site-nav');
    if (!nav) return;

    function onScroll() {
        if (window.scrollY > 40) {
            nav.classList.add('is-scrolled');
        } else {
            nav.classList.remove('is-scrolled');
        }
    }

    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
})();
