/**
 * Cursor Glow — A soft radial spotlight that follows the mouse,
 * plus a subtle trailing ripple on click.
 */
(function () {
    // ── Glow element ──
    const glow = document.createElement('div');
    glow.className = 'cursor-glow';
    document.body.appendChild(glow);

    let mouseX = -200, mouseY = -200;
    let glowX = -200, glowY = -200;

    document.addEventListener('mousemove', function (e) {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    // Smooth follow via requestAnimationFrame
    function animate() {
        glowX += (mouseX - glowX) * 0.15;
        glowY += (mouseY - glowY) * 0.15;
        glow.style.left = glowX + 'px';
        glow.style.top = glowY + 'px';
        requestAnimationFrame(animate);
    }
    animate();

    // ── Click ripple ──
    document.addEventListener('click', function (e) {
        // Don't create ripple on buttons/inputs to avoid visual clutter
        const tag = e.target.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

        const ripple = document.createElement('div');
        ripple.className = 'cursor-ripple';
        ripple.style.left = e.clientX + 'px';
        ripple.style.top = e.clientY + 'px';
        document.body.appendChild(ripple);
        ripple.addEventListener('animationend', () => ripple.remove());
        setTimeout(() => { if (ripple.parentNode) ripple.remove(); }, 800);
    });

    // Hide glow when mouse leaves the window
    document.addEventListener('mouseleave', () => {
        glow.style.opacity = '0';
    });
    document.addEventListener('mouseenter', () => {
        glow.style.opacity = '1';
    });

    // Re-resolve colors on theme change
    const observer = new MutationObserver(() => {
        // Colors are handled via CSS variables, so nothing to do here — just works!
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] });
})();
