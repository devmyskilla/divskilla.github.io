const AIRTABLE_TOKEN = 'patSA2AaZP0HcqAHm.62251e1628dcbde75dd160c72bd93d0dcea14dde64ed0fa85c95478a6e69a41d';
const AIRTABLE_BASE = 'appewcUGXqErxkd8m';
const AIRTABLE_TABLE = 'Table%201';

const AIRTABLE_URL = `https://api.airtable.com/v0/${AIRTABLE_BASE}/${AIRTABLE_TABLE}`;

async function fetchAllFromAirtable() {
  const records = [];
  let offset = null;

  do {
    const params = new URLSearchParams({ view: 'Grid view' });
    if (offset) params.set('offset', offset);

    const res = await fetch(`${AIRTABLE_URL}?${params}`, {
      headers: { Authorization: `Bearer ${AIRTABLE_TOKEN}` }
    });

    if (!res.ok) {
      throw new Error(`Airtable API error: ${res.status}`);
    }

    const data = await res.json();
    data.records.forEach(r => records.push(mapRecord(r)));
    offset = data.offset || null;
  } while (offset);

  return records;
}

function mapRecord(record) {
  const f = record.fields || {};
  const thumbnails = f.Thumbnail || [];
  let thumbnailUrl = '';
  if (thumbnails.length && typeof thumbnails[0] === 'object') {
    const t = thumbnails[0];
    const large = t.thumbnails?.large;
    thumbnailUrl = large?.url || t.url || '';
  }

  return {
    id: record.id || '',
    name: f['Course Name'] || '',
    category: f['Catgoery'] || '',
    platform: f['Plarform'] || '',
    free: !!f['Free'],
    certificate: !!f['Certificate'],
    duration: f['Duration'] || '',
    level: f['Level'] || '',
    language: f['Language'] || '',
    link: f['Course Link'] || '',
    thumbnail: thumbnailUrl,
    description: f['Description'] || '',
    startDate: f['Start date'] || '',
  };
}

async function fetchFilters() {
  allCourses = await fetchAllFromAirtable();

  const langs = new Set();
  const cats = new Set();
  const plats = new Set();
  const lvls = new Set();

  allCourses.forEach(c => {
    if (c.language) langs.add(c.language);
    if (c.category) cats.add(c.category);
    if (c.platform) plats.add(c.platform);
    if (c.level) lvls.add(c.level);
  });

  filtersData = {
    languages: [...langs].sort(),
    categories: [...cats].sort(),
    platforms: [...plats].sort(),
    levels: [...lvls].sort(),
  };

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

function fetchCourses() {
  let filtered = [...allCourses];
  const q = searchInput.value.toLowerCase();

  if (q) {
    filtered = filtered.filter(c =>
      c.name.toLowerCase().includes(q) ||
      c.description.toLowerCase().includes(q)
    );
  }
  if (filterLang.value) {
    filtered = filtered.filter(c => c.language === filterLang.value);
  }
  if (filterCategory.value) {
    filtered = filtered.filter(c => c.category === filterCategory.value);
  }
  if (filterPlatform.value) {
    filtered = filtered.filter(c => c.platform === filterPlatform.value);
  }
  if (filterLevel.value) {
    filtered = filtered.filter(c => c.level === filterLevel.value);
  }
  if (filterFree.checked) {
    filtered = filtered.filter(c => c.free);
  }
  if (filterCert.checked) {
    filtered = filtered.filter(c => c.certificate);
  }

  renderCourses(filtered);
}

function renderCourses(courses) {
  resultsCount.textContent = courses.length;

  if (!courses.length) {
    coursesGrid.innerHTML = `<div class="no-results">${t('course.noResults')}</div>`;
    return;
  }

  const freeText = t('course.free');
  const paidText = t('course.paid');
  const certText = t('course.certificate');
  const viewText = t('course.view');

  coursesGrid.innerHTML = courses.map(course => `
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
  fetchCourses();
});

async function init() {
  try {
    await fetchFilters();
    fetchCourses();
  } catch (err) {
    coursesGrid.innerHTML = `<div class="no-results">⚠️ ${t('course.noResults')}</div>`;
  }
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
