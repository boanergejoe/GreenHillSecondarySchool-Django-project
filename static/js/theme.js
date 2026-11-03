document.addEventListener('DOMContentLoaded', function () {
    const button = document.getElementById('themeToggle');
    const root = document.documentElement;
    if (!button) return;
    const language = (root.lang || 'en').split('-')[0];
    const labels = {
        fr: { light: 'Passer au thème clair', dark: 'Passer au thème sombre' },
        ar: { light: 'التبديل إلى الوضع الفاتح', dark: 'التبديل إلى الوضع الداكن' }
    };
    const themeLabels = labels[language] || {
        light: 'Switch to light theme',
        dark: 'Switch to dark theme'
    };

    function updateButton(theme) {
        const dark = theme === 'dark';
        button.setAttribute('aria-label', dark ? themeLabels.light : themeLabels.dark);
        button.innerHTML = dark
            ? '<i class="bi bi-sun" aria-hidden="true"></i>'
            : '<i class="bi bi-moon-stars" aria-hidden="true"></i>';
    }

    updateButton(root.dataset.theme || 'light');
    button.addEventListener('click', function () {
        const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
        root.dataset.theme = theme;
        try {
            localStorage.setItem('ghss-theme', theme);
        } catch (error) {
            button.setAttribute('aria-label', language === 'ar'
                ? 'تعذر حفظ إعداد المظهر'
                : language === 'fr'
                    ? 'Impossible d’enregistrer le thème'
                    : 'Theme preference could not be saved');
        }
        updateButton(theme);
    });
});
