# -*- coding: utf-8 -*-
"""Voz de Muse: sintetiza texto con edge-tts (SalomeNeural es-CO, +50%).
Uso: habla_edge.py <txt> <mp3> [voz] [volumen]
Reproducir con: powershell -File muse_voz/reproducir.ps1 <mp3>
"""
import asyncio
import ctypes
import sys

import edge_tts

# Mismo mutex que reproducir.ps1: sintetizar y reproducir comparten el turno
MUTEX = 'Local\\TucTucVoz'


async def main():
    txt, mp3 = sys.argv[1], sys.argv[2]
    voz = sys.argv[3] if len(sys.argv) > 3 else 'es-CO-SalomeNeural'
    vol = sys.argv[4] if len(sys.argv) > 4 else '+50%'
    texto = open(txt, encoding='utf-8-sig').read().strip()
    await edge_tts.Communicate(texto, voz, volume=vol).save(mp3)


def _con_turno():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    h = k.CreateMutexW(None, False, MUTEX)
    try:
        r = k.WaitForSingleObject(h, 180000)
        tomado = (r == 0 or r == 0x80)
        if not tomado:
            print('muse_voz: turno ocupado, sintetizo de todos modos', file=sys.stderr)
        asyncio.run(main())
        if tomado:
            k.ReleaseMutex(h)
    finally:
        k.CloseHandle(h)


_con_turno()
