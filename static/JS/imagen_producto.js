function procesarImagen(file, maxSize, quality, callback, onError = () => {}, fondo = null) {
    const reader = new FileReader();
    reader.onerror = onError;
    reader.onload = e => {
        const img = new Image();
        img.onerror = onError;
        img.onload = () => {
            const canvas = document.createElement('canvas');
            let w = img.width, h = img.height;
            if (w > maxSize || h > maxSize) {
                if (w > h) { h = h * maxSize / w; w = maxSize; }
                else { w = w * maxSize / h; h = maxSize; }
            }
            canvas.width = w; canvas.height = h;
            const ctx = canvas.getContext('2d');
            if (fondo) {
                ctx.fillStyle = fondo;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            }
            ctx.drawImage(img, 0, 0, w, h);
            callback(canvas.toDataURL('image/jpeg', quality));
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}
