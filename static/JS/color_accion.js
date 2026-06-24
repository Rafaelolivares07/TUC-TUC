(function () {
    'use strict';

    function aplicarContraste() {
        if (!document.body) return;
        const color = getComputedStyle(document.body).getPropertyValue('--color-accion').trim();
        const hex = color.replace('#', '');
        if (!/^[0-9a-f]{3}([0-9a-f]{3})?$/i.test(hex)) return;
        const normalizado = hex.length === 3
            ? hex.split('').map(caracter => caracter + caracter).join('')
            : hex;
        const canales = [0, 2, 4].map(posicion => parseInt(normalizado.slice(posicion, posicion + 2), 16) / 255);
        const lineales = canales.map(canal => canal <= 0.03928
            ? canal / 12.92
            : Math.pow((canal + 0.055) / 1.055, 2.4));
        const luminancia = 0.2126 * lineales[0] + 0.7152 * lineales[1] + 0.0722 * lineales[2];
        document.body.style.setProperty('--color-accion-texto', luminancia > 0.48 ? '#111827' : '#ffffff');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', aplicarContraste);
    } else {
        aplicarContraste();
    }
})();
