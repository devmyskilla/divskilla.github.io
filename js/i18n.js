const i18n = {
  currentLang: 'ar',
  translations: {},
};

async function loadLanguage(lang) {
  i18n.currentLang = lang;
  const res = await fetch(`lang/${lang}.json`);
  i18n.translations = await res.json();

  document.documentElement.lang = lang;
  document.documentElement.dir = i18n.translations.dir;

  document.body.dir = i18n.translations.dir;
  if (i18n.translations.dir === 'ltr') {
    document.body.setAttribute('dir', 'ltr');
  } else {
    document.body.removeAttribute('dir');
  }

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const value = key.split('.').reduce((obj, k) => obj?.[k], i18n.translations);
    if (value) {
      if (el.tagName === 'INPUT' && el.type === 'text') {
        el.placeholder = value;
      } else {
        el.textContent = value;
      }
    }
  });

  document.title = keyValue(i18n.translations, 'site.title');

  document.dispatchEvent(new CustomEvent('languageChanged', { detail: lang }));
}

function keyValue(obj, path) {
  return path.split('.').reduce((o, k) => o?.[k], obj) || '';
}

function t(path) {
  return keyValue(i18n.translations, path);
}

document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('lang') || 'ar';
  document.getElementById('langSwitcher').value = saved;

  document.getElementById('langSwitcher').addEventListener('change', async (e) => {
    const lang = e.target.value;
    localStorage.setItem('lang', lang);
    await loadLanguage(lang);
  });

  loadLanguage(saved);
});
