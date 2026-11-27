(() => {
  const form = document.getElementById('market-publicacion');
  const picker = document.getElementById('market-fotos');
  const preview = document.getElementById('market-fotos-preview');
  const feedback = document.getElementById('market-fotos-error');
  const iconPicker = document.getElementById('market-icono');
  const iconValue = document.getElementById('market-icono-valor');
  const iconPreview = document.getElementById('market-icono-preview');
  const iconImage = iconPreview.querySelector('img');
  const iconRemove = document.getElementById('market-icono-quitar');
  const iconFeedback = document.getElementById('market-icono-error');
  const submit = form.querySelector('button[type=submit]');
  const fotos = Array.from(preview.querySelectorAll('input[name=fotos]'), input => input.value);
  let occupied = false;

  function render() {
    preview.replaceChildren();
    fotos.forEach((foto, i) => {
      const item = document.createElement('li');
      const img = document.createElement('img');
      img.src = foto;
      img.alt = i === 0 ? 'Foto de portada' : 'Foto ' + (i + 1);
      const hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'fotos';
      hidden.value = foto;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'btn clear';
      remove.textContent = 'Quitar';
      remove.setAttribute('aria-label', 'Quitar ' + img.alt.toLowerCase());
      remove.addEventListener('click', () => {
        fotos.splice(i, 1);
        feedback.textContent = '';
        render();
        picker.focus();
      });
      item.append(img);
      if (i === 0) {
        const label = document.createElement('small');
        label.textContent = 'Portada';
        item.append(label);
      }
      item.append(remove, hidden);
      preview.append(item);
    });
  }

  function busy(value) {
    occupied = value;
    submit.disabled = value;
    picker.disabled = value;
    iconPicker.disabled = value;
    iconRemove.disabled = value;
  }

  function renderIcon() {
    const image = iconValue.value;
    if (image) iconImage.src = image;
    else iconImage.removeAttribute('src');
    iconPreview.hidden = !image;
  }

  render();
  renderIcon();
  iconRemove.hidden = false;
  busy(false);

  iconPicker.addEventListener('change', async () => {
    const file = iconPicker.files[0];
    if (!file) return;
    busy(true);
    iconFeedback.textContent = '';
    try {
      const size = Number(iconPicker.dataset.dimension);
      const image = await new Promise((resolve, reject) => procesarImagen(file, size, 0.8, resolve, reject, "#fff"));
      if (image.length > Number(iconPicker.dataset.limite)) {
        iconFeedback.textContent = 'El ícono es demasiado pesado. Prueba con otra imagen.';
        return;
      }
      iconValue.value = image;
      iconValue.disabled = false;
      renderIcon();
    } catch {
      iconFeedback.textContent = 'No se pudo leer el ícono. Prueba con JPEG, PNG o WebP.';
    } finally {
      iconPicker.value = '';
      busy(false);
    }
  });

  iconRemove.addEventListener('click', () => {
    iconValue.value = '';
    iconValue.disabled = false;
    iconFeedback.textContent = '';
    renderIcon();
    iconPicker.focus();
  });

  picker.addEventListener('change', async () => {
    const files = Array.from(picker.files);
    if (!files.length) return;
    busy(true);
    feedback.textContent = '';
    let total = fotos.reduce((sum, image) => sum + image.length, 0);
    try {
      for (const file of files) {
        const image = await new Promise((resolve, reject) => procesarImagen(file, 800, 0.8, resolve, reject));
        if (image.length > Number(picker.dataset.limiteFoto) ||
            total + image.length > Number(picker.dataset.limiteFotos)) {
          feedback.textContent = 'Se alcanzó el límite de tamaño. Puedes quitar una foto y seguir agregando.';
          break;
        }
        fotos.push(image);
        total += image.length;
      }
    } catch {
      feedback.textContent = 'No se pudo leer una de las fotos. Prueba con JPEG, PNG o WebP.';
    } finally {
      picker.value = '';
      render();
      busy(false);
    }
  });

  form.addEventListener('submit', async event => {
    if (occupied) {
      event.preventDefault();
      return;
    }
    if (!fotos.length) return;
    event.preventDefault();
    feedback.textContent = '';
    const data = new FormData(form);
    busy(true);
    try {
      const response = await fetch(form.action, { method: 'POST', body: data });
      if (response.ok && response.redirected) {
        window.location.assign(response.url);
        return;
      }
      const html = new DOMParser().parseFromString(await response.text(), 'text/html');
      feedback.textContent = html.querySelector('.publication .error')?.textContent
        || 'No pudimos enviar la publicación. Intenta de nuevo.';
    } catch {
      feedback.textContent = 'No pudimos enviar la publicación. Revisa tu conexión y vuelve a intentar.';
    } finally {
      busy(false);
    }
  });
})();
