# -*- coding: utf-8 -*-
"""Sintetizador y reproductor de voz multi-agente con edge-tts y reproduccion nativa.
Lee la configuracion de voces desde `voces_config.json` en el mismo directorio.

Perfiles predeterminados:
  - anti:   es-CO-GonzaloNeural (+50% volumen) - Antigravity
  - muse:   es-CO-SalomeNeural (+50% volumen) - Muse
  - merlin: es-MX-JorgeNeural (+50% volumen) - Merlin

Uso rapido:
  python habla_agente.py "Texto a hablar" [--agente anti|muse|merlin] [--bloqueante]
"""
import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
import uuid

import edge_tts
import av
import winsound

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_CONFIG = os.path.join(DIR_ACTUAL, 'voces_config.json')

CONFIG_DEFAULT = {
    'anti': {'voz': 'es-CO-GonzaloNeural', 'volumen': '+50%'},
    'muse': {'voz': 'es-CO-SalomeNeural', 'volumen': '+50%'},
    'merlin': {'voz': 'es-MX-JorgeNeural', 'volumen': '+50%'},
}


def cargar_config() -> dict:
    if os.path.exists(RUTA_CONFIG):
        try:
            with open(RUTA_CONFIG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return CONFIG_DEFAULT


def limpiar_texto_para_voz(texto: str) -> str:
    """Remueve formato markdown, bloques de codigo, URLs y caracteres especiales."""
    if not texto:
        return ''
    # Quitar bloques de codigo ```...```
    texto = re.sub(r'```[\s\S]*?```', '', texto)
    # Quitar fragmentos de codigo inline `...`
    texto = re.sub(r'`[^`]*`', '', texto)
    # Convertir enlaces markdown [texto](url) a solo texto
    texto = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', texto)
    # Quitar URLs planas
    texto = re.sub(r'https?://\S+', '', texto)
    # Quitar imagenes ![alt](url)
    texto = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', texto)
    # Quitar encabezados markdown (#, ##, etc.)
    texto = re.sub(r'^\s*#{1,6}\s+', '', texto, flags=re.MULTILINE)
    # Quitar negritas y cursivas
    texto = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', texto)
    # Quitar lineas separadoras (--- o ***)
    texto = re.sub(r'^\s*[-*_]{3,}\s*$', '', texto, flags=re.MULTILINE)
    # Quitar viñetas y numeraciones al inicio de linea
    texto = re.sub(r'^\s*[-*+]\s+', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'^\s*\d+\.\s+', '', texto, flags=re.MULTILINE)
    # Normalizar espacios en blanco
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n{2,}', '\n', texto)
    return texto.strip()


async def sintetizar(texto: str, ruta_mp3: str, voz: str, volumen: str = '+50%'):
    com = edge_tts.Communicate(texto, voz, volume=volumen)
    await com.save(ruta_mp3)


def mp3_a_wav(ruta_mp3: str, ruta_wav: str):
    """Convierte MP3 a WAV usando PyAV para reproduccion 100% nativa sin depender de WPF."""
    in_container = av.open(ruta_mp3)
    out_container = av.open(ruta_wav, mode='w', format='wav')
    in_stream = in_container.streams.audio[0]
    out_stream = out_container.add_stream('pcm_s16le', rate=in_stream.rate)
    out_stream.layout = in_stream.layout

    for frame in in_container.decode(in_stream):
        for packet in out_stream.encode(frame):
            out_container.mux(packet)
    for packet in out_stream.encode():
        out_container.mux(packet)

    in_container.close()
    out_container.close()


def reproducir_nativo(ruta_wav: str, bloqueante: bool = True):
    """Reproduce WAV usando la API nativa de Windows (winsound / winmm)."""
    flags = winsound.SND_FILENAME
    if not bloqueante:
        flags |= winsound.SND_ASYNC
    winsound.PlaySound(ruta_wav, flags)


def main():
    parser = argparse.ArgumentParser(description='Voz de agentes para TucTuc')
    parser.add_argument('texto', nargs='?', default='', help='Texto a hablar (o usar --archivo)')
    parser.add_argument('--archivo', '-f', default=None, help='Ruta a archivo con el texto')
    parser.add_argument('--agente', '-a', default='anti', help='Perfil de agente (anti, muse, merlin)')
    parser.add_argument('--voz', '-v', default=None, help='Sobrescribir nombre de voz edge-tts')
    parser.add_argument('--volumen', default=None, help='Sobrescribir volumen (ej: +50%%)')
    parser.add_argument('--bloqueante', action='store_true', default=True, help='Esperar a que termine de reproducir')
    parser.add_argument('--no-limpiar', action='store_true', help='No limpiar formato markdown')

    args = parser.parse_args()

    texto = ''
    if args.archivo and os.path.exists(args.archivo):
        with open(args.archivo, 'r', encoding='utf-8', errors='ignore') as f:
            texto = f.read()
    elif args.texto:
        texto = args.texto
    elif not sys.stdin.isatty():
        texto = sys.stdin.read()

    texto = texto.strip()
    if not texto:
        return

    if not args.no_limpiar:
        texto = limpiar_texto_para_voz(texto)

    if not texto:
        return

    config = cargar_config()
    cfg_agente = config.get(args.agente, CONFIG_DEFAULT.get(args.agente, {}))

    voz = args.voz or cfg_agente.get('voz', 'es-CO-GonzaloNeural')
    volumen = args.volumen or cfg_agente.get('volumen', '+50%')

    uid = uuid.uuid4().hex[:6]
    temp_dir = tempfile.gettempdir()
    archivo_mp3 = os.path.join(temp_dir, f'{args.agente}_habla_{int(time.time()*1000)}_{os.getpid()}_{uid}.mp3')
    archivo_wav = os.path.join(temp_dir, f'{args.agente}_habla_{int(time.time()*1000)}_{os.getpid()}_{uid}.wav')

    try:
        asyncio.run(sintetizar(texto, archivo_mp3, voz, volumen))
        mp3_a_wav(archivo_mp3, archivo_wav)
        reproducir_nativo(archivo_wav, bloqueante=True)
    except Exception as e:
        sys.stderr.write(f'Error en habla_agente: {e}\n')
    finally:
        for p in (archivo_mp3, archivo_wav):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


if __name__ == '__main__':
    main()
