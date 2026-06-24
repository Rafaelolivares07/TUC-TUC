import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.environ.get(
    'AGENDA_MERLIN_URL',
    'https://admin.tuc-tuc.co/agenda/merlin',
)
TOKEN = os.environ.get('AGENDA_MERLIN_TOKEN', 'merlin-agenda-2026')


def solicitar(payload=None):
    if payload is None:
        url = f'{BASE_URL}?{urllib.parse.urlencode({"token": TOKEN})}'
        request = urllib.request.Request(url)
    else:
        body = json.dumps({'token': TOKEN, **payload}).encode('utf-8')
        request = urllib.request.Request(
            BASE_URL,
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read())
            error = data.get('error', str(exc))
        except (json.JSONDecodeError, UnicodeDecodeError):
            error = str(exc)
        raise SystemExit(f'Error: {error}') from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f'Error de conexión: {exc.reason}') from exc

    if not data.get('ok'):
        raise SystemExit(f"Error: {data.get('error', 'respuesta no válida')}")
    return data


def mostrar_agenda():
    data = solicitar()
    pendientes = [item for item in data['items'] if not item['completado']]
    completados = [item for item in data['items'] if item['completado']]

    print(f'=== AGENDA ({len(pendientes)} pendientes) ===')
    for item in pendientes:
        fecha = f"  [{item['fecha_limite']}]" if item['fecha_limite'] else ''
        print(f"[{item['id']}] {item['texto']}{fecha}")
    if completados:
        print(f'\n--- Completadas ({len(completados)}) ---')
        for item in completados:
            print(f"[{item['id']}] {item['texto']}")


def crear_parser():
    parser = argparse.ArgumentParser(description='Consulta y administra la agenda.')
    subparsers = parser.add_subparsers(dest='comando')

    agregar = subparsers.add_parser('agregar', help='Agrega un pendiente.')
    agregar.add_argument('texto')
    agregar.add_argument('--categoria', default='')
    agregar.add_argument('--fecha-limite', default='')

    completar = subparsers.add_parser('completar', help='Marca un ítem como completado.')
    completar.add_argument('id', type=int)

    reabrir = subparsers.add_parser('reabrir', help='Vuelve a marcar un ítem como pendiente.')
    reabrir.add_argument('id', type=int)
    return parser


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    args = crear_parser().parse_args()

    if not args.comando:
        mostrar_agenda()
        return

    if args.comando == 'agregar':
        data = solicitar({
            'accion': 'agregar',
            'texto': args.texto,
            'categoria': args.categoria,
            'fecha_limite': args.fecha_limite,
        })
        print(f"Agregado: [{data['id']}] {args.texto}")
        return

    data = solicitar({'accion': args.comando, 'id': args.id})
    estado = 'completado' if data['completado'] else 'pendiente'
    print(f"Actualizado: [{data['id']}] {estado}")


if __name__ == '__main__':
    main()
