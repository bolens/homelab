const search = document.querySelector('#search');
const category = document.querySelector('#category');
const cards = [...document.querySelectorAll('.app-card')];
const status = document.querySelector('#results-status');
const empty = document.querySelector('#empty-state');

const initialCategory = new URLSearchParams(window.location.search).get('category');
if (initialCategory && [...category.options].some((option) => option.value === initialCategory)) {
  category.value = initialCategory;
}

function filterCatalog() {
  const query = search.value.trim().toLocaleLowerCase();
  let visible = 0;
  for (const card of cards) {
    const text = `${card.dataset.name} ${card.dataset.summary}`.toLocaleLowerCase();
    const matches = (!query || text.includes(query)) && (!category.value || card.dataset.category === category.value);
    card.hidden = !matches;
    visible += Number(matches);
  }
  status.textContent = visible === cards.length
    ? `Showing all ${visible} applications.`
    : `Showing ${visible} of ${cards.length} applications.`;
  empty.hidden = visible !== 0;
}

search.addEventListener('input', filterCatalog);
category.addEventListener('change', filterCatalog);
filterCatalog();
