(() => {
  const form = document.getElementById('search');
  const input = form.elements.q;
  const menu = document.getElementById('market-menu');
  const list = document.getElementById('market-sugerencias');
  const empty = document.getElementById('market-sin-sugerencias');
  const todos = document.getElementById('market-todos');
  const scope = form.elements.categoria?.value || '';
  const titles = ['Productos y servicios', 'Categorías', 'Negocios'];
  const types = { productos: 0, platos: 0, categorias: 1, tiendas: 2, restaurantes: 2 };
  const marks = ['·', '▦', '⌂'];
  let options = [];
  let active = -1;
  let timer;
  let pending;

  function close() {
    clearTimeout(timer);
    pending?.abort();
    menu.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    active = -1;
  }

  function select(index) {
    active = index;
    options.forEach((option, i) => option.setAttribute('aria-selected', String(i === index)));
    input.setAttribute('aria-activedescendant', options[index].id);
    options[index].scrollIntoView({ block: 'nearest' });
  }

  function option(item, group, index) {
    const enlace = document.createElement('a');
    enlace.href = item.enlace;
    enlace.className = 'market-option';
    enlace.id = 'market-opcion-' + index;
    enlace.setAttribute('role', 'option');
    enlace.setAttribute('aria-selected', 'false');
    const thumb = document.createElement('span');
    thumb.className = 'market-thumb';
    thumb.setAttribute('aria-hidden', 'true');
    thumb.textContent = marks[group];
    if (item.imagen) {
      const img = document.createElement('img');
      img.alt = '';
      img.width = 35;
      img.height = 35;
      img.referrerPolicy = 'no-referrer';
      img.addEventListener('error', () => img.remove(), { once: true });
      thumb.replaceChildren(img, marks[group]);
      img.src = item.imagen;
    }
    const text = document.createElement('span');
    const name = document.createElement('strong');
    name.textContent = item.nombre;
    text.append(name);
    const context = group === 0 ? item.negocio : group === 2 ? item.categoria : '';
    if (context) {
      const sub = document.createElement('small');
      sub.textContent = context;
      text.append(sub);
    }
    enlace.append(thumb, text);
    if (item.precio) {
      const precio = document.createElement('b');
      precio.textContent = item.precio;
      enlace.append(precio);
    }
    return enlace;
  }

  function show(items, query) {
    list.replaceChildren();
    options = [];
    active = -1;
    input.removeAttribute('aria-activedescendant');
    titles.forEach((title, group) => {
      const matches = items.filter(item => types[item.tipo] === group);
      if (!matches.length) return;
      const section = document.createElement('div');
      section.className = 'market-group';
      section.setAttribute('role', 'group');
      section.setAttribute('aria-label', title);
      const heading = document.createElement('h3');
      heading.textContent = title;
      section.append(heading);
      for (const item of matches) {
        const row = option(item, group, options.length);
        options.push(row);
        section.append(row);
      }
      list.append(section);
    });
    empty.hidden = options.length > 0;
    const destino = new URL(form.action);
    destino.searchParams.set('q', query);
    if (scope) destino.searchParams.set('categoria', scope);
    todos.href = destino.href;
    menu.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  }

  async function buscar(query) {
    const controller = new AbortController();
    pending = controller;
    try {
      const url = new URL(form.dataset.sugerencias, window.location.href);
      url.searchParams.set('q', query);
      if (scope) url.searchParams.set('categoria', scope);
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) return;
      const data = await response.json();
      if (!controller.signal.aborted && query === input.value.trim()) show(data.sugerencias, query);
    } catch {
      // El formulario sigue disponible para una búsqueda completa.
    }
  }

  function schedule() {
    close();
    const query = input.value.trim();
    if (query.length >= 2) timer = setTimeout(() => buscar(query), 280);
  }

  input.addEventListener('input', schedule);
  input.addEventListener('focus', schedule);
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !menu.hidden) {
      event.preventDefault();
      close();
      return;
    }
    if (menu.hidden || !options.length) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      const index = active === -1 && step === -1 ? options.length - 1
        : (active + step + options.length) % options.length;
      select(index);
    }
  });
  form.addEventListener('submit', event => {
    if (!menu.hidden && options[active]) {
      event.preventDefault();
      options[active].click();
    }
  });
  const surface = form.closest('.market-search');
  document.addEventListener('pointerdown', event => {
    if (!surface.contains(event.target)) close();
  });
  surface.addEventListener('focusout', event => {
    if (!surface.contains(event.relatedTarget)) close();
  });
})();
