import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('templates/caja.html', 'r', encoding='utf-8') as f:
    html = f.read()

old_card = """        return `
            <div onclick="tocarProductoFlash(${p.id})"
                 class="flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 ${selClass} flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none">
                
                <!-- Badge de Cantidad -->
                ${cant > 0 ? `
                    <div class="absolute -top-2.5 -right-2 bg-emerald-600 text-white font-black text-xs px-2.5 py-0.5 rounded-full shadow-md flex items-center gap-1 animate-in zoom-in duration-100">
                        <span>x${cant}</span>
                    </div>
                ` : ''}

                <!-- Nombre y Stock -->
                <div class="min-w-0 flex-1 mb-1">
                    <h3 class="font-black text-gray-900 text-xs sm:text-sm md:text-base leading-tight break-words">${p.nombre}</h3>
                    ${p.stock !== undefined && p.stock !== null && p.stock < 10 ? `
                        <span class="text-[10px] text-amber-600 font-bold block mt-0.5">Stock: ${p.stock}</span>
                    ` : ''}
                </div>

                <!-- Precio y Botón Restar -->
                <div class="flex items-center justify-between mt-auto pt-1.5 border-t border-gray-100/90">
                    <span class="text-sm sm:text-base font-black font-mono text-emerald-700">${formattedPrice}</span>
                    ${cant > 0 ? `
                        <button type="button" onclick="event.stopPropagation(); cambiarCantidadFlash(${p.id}, -1)" 
                                class="w-7 h-7 bg-red-100 hover:bg-red-200 text-red-700 rounded-full font-black text-sm flex items-center justify-center transition active:scale-90 shadow-2xs cursor-pointer"
                                title="Restar 1">
                            -
                        </button>
                    ` : `
                        <span class="text-xs text-gray-400 font-bold">+1</span>
                    `}
                </div>
            </div>
        `;"""

new_card = """        return `
            <div id="flash-card-${p.id}" onclick="tocarProductoFlash(${p.id})"
                 class="flash-card relative p-3.5 sm:p-4 rounded-3xl border-2 ${selClass} flex flex-col justify-between min-h-[118px] sm:min-h-[132px] cursor-pointer transition select-none">
                
                <!-- Badge de Cantidad (Persistente para cero toques perdidos) -->
                <div id="flash-badge-${p.id}" class="absolute -top-2.5 -right-2 bg-emerald-600 text-white font-black text-xs sm:text-sm px-2.5 py-0.5 rounded-full shadow-md flex items-center gap-1 animate-in zoom-in duration-100 ${cant > 0 ? '' : 'hidden'}">
                    <span>x${cant}</span>
                </div>

                <!-- Nombre y Stock -->
                <div class="min-w-0 flex-1 mb-1">
                    <h3 class="font-black text-gray-900 text-xs sm:text-sm md:text-base leading-tight break-words">${p.nombre}</h3>
                    ${p.stock !== undefined && p.stock !== null && p.stock < 10 ? `
                        <span class="text-[10px] text-amber-600 font-bold block mt-0.5">Stock: ${p.stock}</span>
                    ` : ''}
                </div>

                <!-- Precio y Botón Restar -->
                <div class="flex items-center justify-between mt-auto pt-1.5 border-t border-gray-100/90">
                    <span class="text-sm sm:text-base font-black font-mono text-emerald-700">${formattedPrice}</span>
                    <button type="button" id="flash-btn-minus-${p.id}" onclick="event.stopPropagation(); cambiarCantidadFlash(${p.id}, -1)" 
                            class="w-7 h-7 bg-red-100 hover:bg-red-200 text-red-700 rounded-full font-black text-sm flex items-center justify-center transition active:scale-90 shadow-2xs cursor-pointer ${cant > 0 ? '' : 'hidden'}"
                            title="Restar 1">
                        -
                    </button>
                </div>
            </div>
        `;"""

if old_card in html:
    html = html.replace(old_card, new_card, 1)
    print("Card template IDs updated successfully!")
else:
    old_card_n = old_card.replace('\r\n', '\n')
    html_n = html.replace('\r\n', '\n')
    if old_card_n in html_n:
        html = html_n.replace(old_card_n, new_card.replace('\r\n', '\n'), 1)
        print("Card template IDs updated successfully (normalized)!")
    else:
        print("ERROR: old_card not found")

with open('templates/caja.html', 'w', encoding='utf-8') as f:
    f.write(html)
