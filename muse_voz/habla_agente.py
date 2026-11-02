# -*- coding: utf-8 -*-
"""Sintetizador y reproductor de voz multi-agente con edge-tts.
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
import subprocess
import sys
import tempfile
import time
import uuid

import edge_tts

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
    # Quitar emoticones y caracteres no verbales comunes si causan ruido
    # Normalizar espacios en blanco
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n{2,}', '\n', texto)
    return texto.strip()


async def sintetizar(texto: str, ruta_mp3: str, voz: str, volumen: str = '+50%'):
    com = edge_tts.Communicate(texto, voz, volume=volumen)
    await com.save(ruta_mp3)


def reproducir(ruta_mp3: str, script_reproducir: str, bloqueante: bool = True, borrar_al_final: bool = True):
    cmd = [
        'powershell',
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', script_reproducir,
        ruta_mp3
    ]
    if borrar_al_final:
        cmd.append('-deleteAfter')
    if bloqueante:
        subprocess.run(cmd, check=False)
    else:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description='Voz de agentes para TucTuc')
    parser.add_argument('texto', nargs='?', default='', help='Texto a hablar (o usar --archivo)')
    parser.add_argument('--archivo', '-f', default=None, help='Ruta a archivo con el texto')
    parser.add_argument('--agente', '-a', default='anti', help='Perfil de agente (anti, muse, merlin)')
    parser.add_argument('--voz', '-v', default=None, help='Sobrescribir nombre de voz edge-tts')
    parser.add_argument('--volumen', default=None, help='Sobrescribir volumen (ej: +50%%)')
    parser.add_argument('--bloqueante', action='store_true', help='Esperar a que termine de reproducir')
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

    script_reproducir = os.path.join(DIR_ACTUAL, 'reproducir.ps1')
    uid = uuid.uuid4().hex[:6]
    archivo_mp3 = os.path.join(tempfile.gettempdir(), f'{args.agente}_habla_{int(time.time()*1000)}_{os.getpid()}_{uid}.mp3')

    try:
        asyncio.run(sintetizar(texto, archivo_mp3, voz, volumen))
        reproducir(archivo_mp3, script_reproducir, bloqueante=True, borrar_al_final=True)
    except Exception as e:
        sys.stderr.write(f'Error en habla_agente: {e}\n')


if __name__ == '__main__':
    main()
