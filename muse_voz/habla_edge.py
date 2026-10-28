# -*- coding: utf-8 -*-
"""Voz de Muse: sintetiza texto con edge-tts (SalomeNeural es-CO, +50%).
Uso: habla_edge.py <txt> <mp3> [voz] [volumen]
Reproducir con: powershell -File muse_voz/reproducir.ps1 <mp3>
"""
import asyncio
import sys

import edge_tts


async def main():
    txt, mp3 = sys.argv[1], sys.argv[2]
    voz = sys.argv[3] if len(sys.argv) > 3 else 'es-CO-SalomeNeural'
    vol = sys.argv[4] if len(sys.argv) > 4 else '+50%'
    texto = open(txt, encoding='utf-8-sig').read().strip()
    await edge_tts.Communicate(texto, voz, volume=vol).save(mp3)

asyncio.run(main())
