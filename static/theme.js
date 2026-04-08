/**
 * Kalyan College Management System
 * Shared Theme Logic Helper
 * Generates and applies fully dynamic CSS variables based on themes.json
 */

let themeSettings = { active_mode: 'light', active_theme: 'forest', themes: [] };

// ═══ COLOR GENERATION UTILS ═══
function hexToRGB(hex) {
    if (!hex) return [0, 0, 0];
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    let r = parseInt(hex.slice(0, 2), 16);
    let g = parseInt(hex.slice(2, 4), 16);
    let b = parseInt(hex.slice(4, 6), 16);
    return [r, g, b];
}

function mixColors(color1, color2, weight1) {
    let w1 = weight1 / 100;
    let w2 = 1 - w1;
    let r = Math.round(color1[0] * w1 + color2[0] * w2);
    let g = Math.round(color1[1] * w1 + color2[1] * w2);
    let b = Math.round(color1[2] * w1 + color2[2] * w2);
    return `rgb(${r}, ${g}, ${b})`;
}

function generateShades(hex) {
    const base = hexToRGB(hex);
    const white = [255, 255, 255];
    const black = [0, 0, 0];
    return {
        '50': mixColors(base, white, 10),
        '100': mixColors(base, white, 20),
        '200': mixColors(base, white, 40),
        '300': mixColors(base, white, 60),
        '400': mixColors(base, white, 80),
        '500': hex,
        '600': mixColors(base, black, 80),
        '700': mixColors(base, black, 60),
        '800': mixColors(base, black, 40),
        '900': mixColors(base, black, 20),
    };
}

// ═══ THEME LOGIC ═══
async function initTheme() {
    try {
        const response = await fetch('/api/settings/themes');
        themeSettings = await response.json();
        const mode = themeSettings.active_mode || 'light';
        const themeId = themeSettings.active_theme || 'forest';
        
        applyMode(mode, false);
        applyColor(themeId, false);
        
        // Notify other scripts (like settings.html) that theme has loaded
        document.dispatchEvent(new Event('themeLoaded'));
    } catch (e) {
        console.error('Failed to load theme settings', e);
        const savedMode = localStorage.getItem('theme-mode') || 'light';
        const savedColor = localStorage.getItem('theme-color') || 'forest';
        applyMode(savedMode, false);
        applyColor(savedColor, false);
    }
}

async function setMode(mode) {
    applyMode(mode, true);
    themeSettings.active_mode = mode;
    saveThemeSettings();
}

function applyMode(mode, reapplyColor = true) {
    document.documentElement.setAttribute('data-theme', mode);
    localStorage.setItem('theme-mode', mode);

    const lightBtn = document.getElementById('mode-light-btn');
    const darkBtn = document.getElementById('mode-dark-btn');
    if (lightBtn && darkBtn) {
        if (mode === 'dark') {
            darkBtn.classList.add('active');
            lightBtn.classList.remove('active');
        } else {
            lightBtn.classList.add('active');
            darkBtn.classList.remove('active');
        }
    }

    if (reapplyColor) {
        applyColor(themeSettings.active_theme, false);
    }
}

async function setThemeColor(themeId) {
    applyColor(themeId, true);
    themeSettings.active_theme = themeId;
    localStorage.setItem('theme-color', themeId);
    saveThemeSettings();
}

function applyColor(themeId, renderPreviewOnly = false) {
    const theme = themeSettings.themes.find(t => t.id === themeId);
    if (!theme) return;

    const root = document.documentElement;
    const mode = root.getAttribute('data-theme') || 'light';

    const primaryShades = generateShades(theme.primary || '#4a7c4a');
    const accentShades = generateShades(theme.accent || '#b8944a');

    // Store generated shades for runtime
    theme.generated_primary = primaryShades;
    theme.generated_accent = accentShades;

    // Apply primary & accent palette shades as CSS vars
    Object.entries(primaryShades).forEach(([shade, color]) => {
        root.style.setProperty(`--primary-${shade}`, color);
    });
    Object.entries(accentShades).forEach(([shade, color]) => {
        root.style.setProperty(`--accent-${shade}`, color);
    });

    // Dynamically generate Surface and Text colors based on mode and primary color
    if (mode === 'dark') {
        const darkSurface = mixColors(hexToRGB(theme.primary || '#4a7c4a'), [0,0,0], 12);
        const darkerSurface = mixColors(hexToRGB(theme.primary || '#4a7c4a'), [0,0,0], 8);
        root.style.setProperty('--surface-bg', darkSurface);
        root.style.setProperty('--ivory-100', darkerSurface);
        root.style.setProperty('--ivory-200', mixColors(hexToRGB(theme.primary), [0,0,0], 10));
        root.style.setProperty('--ivory-300', mixColors(hexToRGB(theme.primary), [0,0,0], 15));
        root.style.setProperty('--ivory-400', mixColors(hexToRGB(theme.primary), [0,0,0], 20));
        root.style.setProperty('--text-dark', mixColors(hexToRGB(theme.primary), [255,255,255], 10)); // Soft white
        root.style.setProperty('--text-body', mixColors(hexToRGB(theme.primary), [255,255,255], 20)); // Muted white
        root.style.setProperty('--text-muted', mixColors(hexToRGB(theme.primary), [255,255,255], 40)); 
    } else {
        root.style.setProperty('--surface-bg', '#fff');
        root.style.setProperty('--text-dark', primaryShades['900']);
        root.style.setProperty('--text-body', primaryShades['800']);
        root.style.setProperty('--text-muted', primaryShades['600']);
        // Restore default Ivory background vars to allow contrast
        root.style.setProperty('--ivory-100', '#faf8f4');
        root.style.setProperty('--ivory-200', '#f5f1ea');
        root.style.setProperty('--ivory-300', '#ede8df');
        root.style.setProperty('--ivory-400', '#ddd6c9');
    }

    // Apply semantic colors if they exist
    if (theme.colors?.semantic) {
        Object.entries(theme.colors.semantic).forEach(([key, val]) => {
            root.style.setProperty(`--${key.replace(/_/g, '-')}`, val);
        });
    }

    // Apply specific mode tokens if defined
    const modeTokens = theme[mode] || {};
    Object.entries(modeTokens).forEach(([key, val]) => {
        root.style.setProperty(`--theme-${key.replace(/_/g, '-')}`, val);
    });

    // Update active state on settings cards
    document.querySelectorAll('.theme-card').forEach(card => {
        card.classList.toggle('active', card.getAttribute('data-theme-val') === themeId);
    });

    if (typeof renderPreview === 'function') {
        renderPreview(theme, mode);
    }
}

async function saveThemeSettings() {
    try {
        await fetch('/api/settings/themes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(themeSettings)
        });
    } catch (e) {
        console.error('Failed to save theme settings', e);
    }
}
