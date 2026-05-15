const API_BASE = '/api';

let allCourses = [];
let filtersData = { languages: [], categories: [], platforms: [], levels: [] };

const $ = id => document.getElementById(id);
const searchInput = $('searchInput');
const filterLang = $('filterLang');
const filterCategory = $('filterCategory');
const filterPlatform = $('filterPlatform');
const filterLevel = $('filterLevel');
const filterFree = $('filterFree');
const filterCert = $('filterCert');
const resetBtn = $('resetFilters');
const coursesGrid = $('coursesGrid');
const resultsCount = $('resultsCount');

function updateFirstOption() {
  const allText = t('filters.all');
  document.querySelectorAll('.filter-group select').forEach(sel => {
    const first = sel.options[0];
    if (first) first.textContent = allText;
  });
}

async function fetchFilters() {
  const res = await fetch(`${API_BASE}/filters`);
  filtersData = await res.json();
  populateSelect(filterLang, filtersData.languages);
  populateSelect(filterCategory, filtersData.categories);
  populateSelect(filterPlatform, filtersData.platforms);
  populateSelect(filterLevel, filtersData.levels);
  updateFirstOption();
}

function populateSelect(select, options) {
  const allText = t('filters.all');
  select.innerHTML = `<option value="">${allText}</option>`;
  options.forEach(opt => {
    const option = document.createElement('option');
    option.value = opt;
    option.textContent = opt;
    select.appendChild(option);
  });
}

async function fetchCourses() {
  const params = new URLSearchParams();
  if (searchInput.value) params.set('search', searchInput.value);
  if (filterLang.value) params.set('language', filterLang.value);
  if (filterCategory.value) params.set('category', filterCategory.value);
  if (filterPlatform.value) params.set('platform', filterPlatform.value);
  if (filterLevel.value) params.set('level', filterLevel.value);
  if (filterFree.checked) params.set('free', 'true');
  if (filterCert.checked) params.set('certificate', 'true');

  const res = await fetch(`${API_BASE}/courses?${params}`);
  allCourses = await res.json();
  renderCourses();
}

function renderCourses() {
  resultsCount.textContent = allCourses.length;

  if (!allCourses.length) {
    coursesGrid.innerHTML = `<div class="no-results">${t('course.noResults')}</div>`;
    return;
  }

  const freeText = t('course.free');
  const paidText = t('course.paid');
  const certText = t('course.certificate');
  const viewText = t('course.view');

  coursesGrid.innerHTML = allCourses.map(course => `
    <div class="course-card">
      ${course.thumbnail
        ? `<img class="card-thumb" src="${course.thumbnail}" alt="${escapeHtml(course.name)}" loading="lazy">`
        : `<div class="card-thumb-placeholder">📚</div>`
      }
      <div class="card-body">
        <h3 class="card-title">${escapeHtml(course.name)}</h3>
        <p class="card-desc">${escapeHtml(course.description)}</p>
        <div class="card-meta">
          <span class="tag">${escapeHtml(course.language)}</span>
          <span class="tag">${escapeHtml(course.category)}</span>
          <span class="tag level">${escapeHtml(course.level)}</span>
          <span class="tag ${course.free ? 'free' : 'paid'}">${course.free ? freeText : paidText}</span>
          ${course.certificate ? `<span class="tag cert">${certText}</span>` : ''}
          <span class="tag">${escapeHtml(course.duration)}</span>
        </div>
        <div class="card-footer">
          <span class="card-platform">${escapeHtml(course.platform)}</span>
          <a class="card-link" href="${escapeHtml(course.link)}" target="_blank" rel="noopener">${viewText}</a>
        </div>
      </div>
    </div>
  `).join('');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function resetFilters() {
  searchInput.value = '';
  filterLang.value = '';
  filterCategory.value = '';
  filterPlatform.value = '';
  filterLevel.value = '';
  filterFree.checked = false;
  filterCert.checked = false;
  fetchCourses();
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

searchInput.addEventListener('input', debounce(fetchCourses, 300));
filterLang.addEventListener('change', fetchCourses);
filterCategory.addEventListener('change', fetchCourses);
filterPlatform.addEventListener('change', fetchCourses);
filterLevel.addEventListener('change', fetchCourses);
filterFree.addEventListener('change', fetchCourses);
filterCert.addEventListener('change', fetchCourses);
resetBtn.addEventListener('click', resetFilters);

document.addEventListener('languageChanged', () => {
  updateFirstOption();
  populateSelect(filterLang, filtersData.languages);
  populateSelect(filterCategory, filtersData.categories);
  populateSelect(filterPlatform, filtersData.platforms);
  populateSelect(filterLevel, filtersData.levels);
  renderCourses();
});

async function init() {
  await fetchFilters();
  await fetchCourses();
}

document.addEventListener('DOMContentLoaded', () => {
  const checkInit = () => {
    if (typeof t !== 'undefined') {
      init();
    } else {
      setTimeout(checkInit, 50);
    }
  };
  checkInit();
});
