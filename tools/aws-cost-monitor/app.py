import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'monitor_config.json')
COST_CACHE_PATH = os.path.join(BASE_DIR, 'cost_cache.json')
app = Flask(__name__)

_cache = {'at': 0.0, 'data': None}
_cache_lock = threading.Lock()

MONTH_NAMES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
MONTH_SHORT = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


def format_month_label(date_str, short=False):
    try:
        parts = date_str.split('-')
        m = int(parts[1])
        y = parts[0]
        return f"{MONTH_SHORT[m]} {y}" if short else f"{MONTH_NAMES[m]} {y}"
    except Exception:
        return date_str


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def run_aws(args, timeout=90):
    """Run AWS CLI without a shell and return parsed JSON."""
    try:
        profile = load_config().get('aws_profile')
        command = ['aws']
        if profile:
            command.extend(['--profile', profile])
        command.extend(args)
        command.extend(['--output', 'json'])
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        if result.returncode != 0:
            return {'error': result.stderr.strip() or f'AWS CLI termino con codigo {result.returncode}'}
        if not result.stdout.strip():
            return {}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {'error': f'AWS CLI excedio {timeout} segundos'}
    except Exception as exc:
        return {'error': str(exc)}


def tag_name(resource):
    for tag in resource.get('Tags', []):
        if tag.get('Key') == 'Name':
            return tag.get('Value') or ''
    return ''


def get_instances(region):
    response = run_aws(['ec2', 'describe-instances', '--region', region])
    if 'error' in response:
        return {'region': region, 'error': response['error']}
    instances = []
    for reservation in response.get('Reservations', []):
        for item in reservation.get('Instances', []):
            instances.append({
                'id': item.get('InstanceId'),
                'name': tag_name(item),
                'type': item.get('InstanceType'),
                'state': item.get('State', {}).get('Name'),
                'public_ip': item.get('PublicIpAddress'),
                'private_ip': item.get('PrivateIpAddress'),
                'launch_time': item.get('LaunchTime'),
                'region': region,
            })
    return {'region': region, 'data': instances}


def get_volumes(region):
    response = run_aws(['ec2', 'describe-volumes', '--region', region])
    if 'error' in response:
        return {'region': region, 'error': response['error']}
    volumes = []
    for item in response.get('Volumes', []):
        attachments = item.get('Attachments', [])
        volumes.append({
            'id': item.get('VolumeId'),
            'name': tag_name(item),
            'size_gb': item.get('Size'),
            'type': item.get('VolumeType'),
            'state': item.get('State'),
            'attached_to': attachments[0].get('InstanceId') if attachments else None,
            'encrypted': bool(item.get('Encrypted')),
            'region': region,
        })
    return {'region': region, 'data': volumes}


def get_elastic_ips(region):
    response = run_aws(['ec2', 'describe-addresses', '--region', region])
    if 'error' in response:
        return {'region': region, 'error': response['error']}
    addresses = []
    for item in response.get('Addresses', []):
        addresses.append({
            'public_ip': item.get('PublicIp'),
            'allocation_id': item.get('AllocationId'),
            'association_id': item.get('AssociationId'),
            'instance_id': item.get('InstanceId'),
            'network_interface_id': item.get('NetworkInterfaceId'),
            'region': region,
        })
    return {'region': region, 'data': addresses}


def get_nat_gateways(region):
    response = run_aws(['ec2', 'describe-nat-gateways', '--region', region])
    if 'error' in response:
        return {'region': region, 'error': response['error']}
    gateways = []
    for item in response.get('NatGateways', []):
        if item.get('State') != 'deleted':
            gateways.append({
                'id': item.get('NatGatewayId'),
                'vpc_id': item.get('VpcId'),
                'state': item.get('State'),
                'region': region,
            })
    return {'region': region, 'data': gateways}


def get_snapshots(region):
    response = run_aws(['ec2', 'describe-snapshots', '--owner-ids', 'self', '--region', region])
    if 'error' in response:
        return {'region': region, 'error': response['error']}
    snapshots = []
    for item in response.get('Snapshots', []):
        snapshots.append({
            'id': item.get('SnapshotId'),
            'size_gb': item.get('VolumeSize'),
            'start_time': item.get('StartTime'),
            'description': item.get('Description') or '',
            'region': region,
        })
    return {'region': region, 'data': snapshots}


def get_savings_plans():
    response = run_aws(['savingsplans', 'describe-savings-plans'])
    if 'error' in response:
        return []
    plans = []
    for sp in response.get('savingsPlans', []):
        if sp.get('state') in ('active', 'payment-pending'):
            plans.append({
                'id': sp.get('savingsPlanId'),
                'description': sp.get('description'),
                'state': sp.get('state'),
                'commitment': float(sp.get('commitment') or 0),
                'start': sp.get('start'),
                'end': sp.get('end'),
                'type': sp.get('savingsPlanType'),
            })
    return plans


def get_cost_history(now, force=False):
    today = now.strftime('%Y-%m-%d')
    if not force:
        try:
            with open(COST_CACHE_PATH, 'r', encoding='utf-8') as fh:
                cached = json.load(fh)
            if cached.get('date') == today and 'history' in cached and 'usage_breakdown' in cached:
                return cached
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    # Build 6-month window: 5 previous months + current month up to first day of next month
    first_current = now.replace(day=1)
    d = first_current
    months = [d]
    for _ in range(5):
        d = (d - timedelta(days=1)).replace(day=1)
        months.append(d)
    months.reverse()
    start_date = months[0].strftime('%Y-%m-%d')
    if now.month == 12:
        end_date = now.replace(year=now.year + 1, month=1, day=1).strftime('%Y-%m-%d')
    else:
        end_date = now.replace(month=now.month + 1, day=1).strftime('%Y-%m-%d')

    # 1. Cost Explorer: 6-month historical totals and services
    service_resp = run_aws([
        'ce', 'get-cost-and-usage',
        '--time-period', f'Start={start_date},End={end_date}',
        '--granularity', 'MONTHLY',
        '--metrics', 'UnblendedCost',
        '--group-by', 'Type=DIMENSION,Key=SERVICE',
    ])

    if 'error' in service_resp:
        return {'error': service_resp['error']}

    history = []
    prev_total = None
    for period in service_resp.get('ResultsByTime', []):
        p_start = period.get('TimePeriod', {}).get('Start', '')
        p_end = period.get('TimePeriod', {}).get('End', '')
        p_estimated = bool(period.get('Estimated', False))
        services = []
        total = 0.0
        for group in period.get('Groups', []):
            amount = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount') or 0)
            total += amount
            if abs(amount) >= 0.005:
                services.append({
                    'service': group.get('Keys', ['Desconocido'])[0],
                    'cost': round(amount, 2),
                })
        services.sort(key=lambda item: abs(item['cost']), reverse=True)
        total_round = round(total, 2)
        diff_pct = None
        if prev_total is not None and prev_total > 0:
            diff_pct = round(((total_round - prev_total) / prev_total) * 100, 1)
        if not p_estimated:
            prev_total = total_round

        history.append({
            'month': p_start[:7],
            'start': p_start,
            'end': p_end,
            'label': format_month_label(p_start, short=False),
            'short_label': format_month_label(p_start, short=True),
            'total': total_round,
            'estimated': p_estimated,
            'services': services,
            'diff_pct': diff_pct,
        })

    # 2. Granular USAGE_TYPE breakdown for the last closed month
    usage_start = months[-2].strftime('%Y-%m-%d')
    usage_resp = run_aws([
        'ce', 'get-cost-and-usage',
        '--time-period', f'Start={usage_start},End={end_date}',
        '--granularity', 'MONTHLY',
        '--metrics', 'UnblendedCost',
        '--group-by', 'Type=DIMENSION,Key=USAGE_TYPE',
    ])

    usage_breakdown = []
    if 'error' not in usage_resp and usage_resp.get('ResultsByTime'):
        target_period = usage_resp['ResultsByTime'][0]
        compute_cost = 0.0
        ipv4_cost = 0.0
        ebs_cost = 0.0
        other_cost = 0.0
        for group in target_period.get('Groups', []):
            k = group.get('Keys', [''])[0]
            amt = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount') or 0)
            if 'BoxUsage' in k:
                compute_cost += amt
            elif 'PublicIPv4' in k:
                ipv4_cost += amt
            elif 'VolumeUsage' in k or 'EBS' in k:
                ebs_cost += amt
            else:
                other_cost += amt

        last_closed_total = compute_cost + ipv4_cost + ebs_cost + other_cost
        if last_closed_total > 0:
            usage_breakdown = [
                {
                    'category': 'Cómputo EC2 (t3.small)',
                    'cost': round(compute_cost, 2),
                    'pct': round(compute_cost * 100 / last_closed_total, 1),
                    'detail': 'Instancia 2 vCPU, 2 GB RAM encendida 24/7 en us-east-2.',
                    'action': 'Savings Plan ACTIVO a 1 año ($0.013/h, ~$9.67 USD/mes). Ahorro de ~$5.81 USD/mes.',
                },
                {
                    'category': 'Dirección IPv4 pública en uso',
                    'cost': round(ipv4_cost, 2),
                    'pct': round(ipv4_cost * 100 / last_closed_total, 1),
                    'detail': 'Tarifa AWS ($0.005/h por cada IPv4 pública asignada).',
                    'action': 'Pendiente por implementar: Ahorro de $3.72 USD/mes (100%) con Cloudflare Tunnel.',
                },
                {
                    'category': 'Almacenamiento EBS (8 GB gp3)',
                    'cost': round(ebs_cost, 2),
                    'pct': round(ebs_cost * 100 / last_closed_total, 1),
                    'detail': 'Volumen raíz del servidor modernizado a gp3.',
                    'action': 'EBS gp3 ACTIVO (3,000 IOPS base, 125 MB/s, tarifa 20% más económica).',
                },
                {
                    'category': 'Servicios de gestión (SSM, CE, CW)',
                    'cost': round(other_cost, 2),
                    'pct': round(other_cost * 100 / last_closed_total, 1),
                    'detail': 'Telemetría de automatización y llamadas API.',
                    'action': 'El sistema de caché del monitor minimiza cobros.',
                },
            ]

    # Summaries
    current = history[-1] if history else {'total': 0, 'services': []}
    previous = history[-2] if len(history) >= 2 else {'total': 0, 'services': []}
    closed_months = [m for m in history if not m.get('estimated')]
    peak_month = max(closed_months, key=lambda m: m['total']) if closed_months else current
    recent_closed = closed_months[-3:] if len(closed_months) >= 3 else closed_months
    avg_recent = round(sum(m['total'] for m in recent_closed) / len(recent_closed), 2) if recent_closed else previous.get('total', 0)
    monthly_savings = round(peak_month['total'] - avg_recent, 2) if peak_month['total'] > avg_recent else 0.0

    result = {
        'date': today,
        'cached_at': now.isoformat(timespec='seconds'),
        'history': history,
        'current': current,
        'previous': previous,
        'peak_month': peak_month,
        'avg_recent': avg_recent,
        'monthly_savings': monthly_savings,
        'annual_savings': round(monthly_savings * 12, 2),
        'usage_breakdown': usage_breakdown,
    }

    temp_path = COST_CACHE_PATH + '.tmp'
    with open(temp_path, 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    os.replace(temp_path, COST_CACHE_PATH)
    return result



def get_instance_type(region, instance_type):
    response = run_aws(['ec2', 'describe-instance-types', '--region', region, '--instance-types', instance_type])
    if 'error' in response or not response.get('InstanceTypes'):
        return response
    item = response['InstanceTypes'][0]
    return {
        'type': item.get('InstanceType'),
        'vcpu': item.get('VCpuInfo', {}).get('DefaultVCpus'),
        'memory_mib': item.get('MemoryInfo', {}).get('SizeInMiB'),
        'network': item.get('NetworkInfo', {}).get('NetworkPerformance'),
    }


def get_cloudwatch_capacity(region, instance_id):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    base = [
        'cloudwatch', 'get-metric-statistics', '--region', region,
        '--namespace', 'AWS/EC2', '--dimensions', f'Name=InstanceId,Value={instance_id}',
        '--start-time', start.strftime('%Y-%m-%dT%H:%M:%SZ'),
        '--end-time', end.strftime('%Y-%m-%dT%H:%M:%SZ'), '--period', '3600',
    ]
    cpu = run_aws([*base, '--metric-name', 'CPUUtilization', '--statistics', 'Average', 'Maximum'])
    network_in = run_aws([*base, '--metric-name', 'NetworkIn', '--statistics', 'Sum'])
    network_out = run_aws([*base, '--metric-name', 'NetworkOut', '--statistics', 'Sum'])
    if 'error' in cpu:
        return cpu
    points = cpu.get('Datapoints', [])
    averages = [float(point.get('Average') or 0) for point in points]
    maximums = [float(point.get('Maximum') or 0) for point in points]
    return {
        'period_days': 7,
        'cpu_average': round(sum(averages) / len(averages), 2) if averages else None,
        'cpu_peak': round(max(maximums), 2) if maximums else None,
        'network_in_gb': round(sum(float(p.get('Sum') or 0) for p in network_in.get('Datapoints', [])) / 1_073_741_824, 3),
        'network_out_gb': round(sum(float(p.get('Sum') or 0) for p in network_out.get('Datapoints', [])) / 1_073_741_824, 3),
    }


def parse_key_values(output):
    values = {}
    for line in (output or '').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        try:
            values[key] = int(value)
        except ValueError:
            try:
                values[key] = float(value)
            except ValueError:
                values[key] = value
    return values


def get_server_capacity(region, instance_id):
    document_name = load_config().get('ssm_capacity_document', 'TucTuc-ReadOnlyCapacityAudit')
    sent = run_aws([
        'ssm', 'send-command', '--region', region, '--instance-ids', instance_id,
        '--document-name', document_name, '--comment', 'TUC TUC read-only capacity monitor v2',
    ])
    if 'error' in sent:
        return sent
    command_id = sent.get('Command', {}).get('CommandId')
    if not command_id:
        return {'error': 'SSM no devolvio identificador de comando'}
    for _ in range(15):
        time.sleep(1)
        invocation = run_aws([
            'ssm', 'get-command-invocation', '--region', region,
            '--command-id', command_id, '--instance-id', instance_id,
        ])
        status = invocation.get('Status')
        if status == 'Success':
            values = parse_key_values(invocation.get('StandardOutputContent'))
            total_mem = values.get('mem_total') or 0
            available_mem = values.get('mem_available') or 0
            total_disk = values.get('disk_total') or 0
            available_disk = values.get('disk_available') or 0
            values['memory_available_pct'] = round(available_mem * 100 / total_mem, 1) if total_mem else None
            values['disk_available_pct'] = round(available_disk * 100 / total_disk, 1) if total_disk else None
            values['applications'] = [
                {'key': 'tuctuc', 'name': 'TUC TUC', 'memory_bytes': values.get('tuctuc_rss', 0), 'disk_bytes': values.get('tuctuc_disk', 0), 'protected': True},
                {'key': 'lopez', 'name': 'Lopez Refrigeration', 'memory_bytes': values.get('lopez_rss', 0), 'disk_bytes': values.get('lopez_disk', 0), 'protected': True},
                {'key': 'remote', 'name': 'Asistencia remota', 'memory_bytes': values.get('remote_rss', 0), 'disk_bytes': values.get('remote_disk', 0), 'protected': True},
                {'key': 'postgres', 'name': 'PostgreSQL compartido', 'memory_bytes': values.get('postgres_rss', 0), 'disk_bytes': values.get('postgres_disk', 0), 'protected': True},
                {'key': 'nginx', 'name': 'Nginx compartido', 'memory_bytes': values.get('nginx_rss', 0), 'disk_bytes': None, 'protected': True},
            ]
            values['storage_breakdown'] = [
                {'key': 'tuctuc', 'name': 'TUC TUC (/home/ubuntu/tuctucv2)', 'bytes': values.get('tuctuc_disk', 0), 'category': 'Aplicación'},
                {'key': 'snap', 'name': 'Paquetes Snap (/var/lib/snapd)', 'bytes': values.get('snap_disk', 0), 'category': 'Sistema'},
                {'key': 'logs', 'name': 'Logs del sistema (/var/log)', 'bytes': values.get('logs_disk', 0), 'category': 'Sistema'},
                {'key': 'postgres', 'name': 'Bases de datos (/var/lib/postgresql)', 'bytes': values.get('postgres_disk', 0), 'category': 'Base de Datos'},
                {'key': 'lopez', 'name': 'López Refrigeration (/var/www/html)', 'bytes': values.get('lopez_disk', 0), 'category': 'Aplicación'},
                {'key': 'cache', 'name': 'Caché APT (/var/cache)', 'bytes': values.get('cache_disk', 0), 'category': 'Mantenimiento'},
                {'key': 'remote', 'name': 'Asistencia remota (/home/ubuntu/remote-assist)', 'bytes': values.get('remote_disk', 0), 'category': 'Herramienta'},
            ]
            return values
        if status in ('Failed', 'Cancelled', 'TimedOut'):
            return {'error': invocation.get('StandardErrorContent') or f'SSM termino en estado {status}'}
    return {'error': 'SSM no respondio a tiempo'}


def protection_for_instance(instance, config):
    protected = config.get('protected_instances', {})
    label = protected.get(instance.get('id'))
    if label:
        return {'level': 'essential', 'label': label}
    return {'level': 'review', 'label': 'Revisar antes de cualquier cambio'}


def build_recommendations(data, config):
    recommendations = []
    protected_ids = set(config.get('protected_instances', {}).keys())

    # 1. Capacity & Storage Recommendations
    capacity = data.get('capacity', {})
    disk_pct = capacity.get('disk_available_pct')
    if disk_pct is not None:
        avail_gb = round((capacity.get('disk_available', 0) or 0) / 1073741824, 2)
        if disk_pct >= 30:
            recommendations.append({
                'level': 'ok',
                'title': 'Margen de disco saludable',
                'detail': f'El disco raíz (8 GB) cuenta con {disk_pct}% disponible (~{avail_gb} GB libres) tras la depuración. Tarea diaria de mantenimiento activa en /etc/cron.daily/tuctuc-disk-maintenance.'
            })
        elif disk_pct >= 20:
            recommendations.append({
                'level': 'warning',
                'title': 'Vigilar espacio en disco',
                'detail': f'Espacio disponible en {disk_pct}% (~{avail_gb} GB). El cron diario mantiene journals y snap limpios, pero se debe vigilar el crecimiento de PostgreSQL o logs.'
            })
        else:
            recommendations.append({
                'level': 'critical',
                'title': 'Espacio en disco crítico',
                'detail': f'Queda menos del 20% ({disk_pct}% disponible, ~{avail_gb} GB). Se recomienda ampliar el volumen EBS de 8 GB a 10–12 GB.'
            })

    # 2. Cost Reduction Status & Levers
    recommendations.append({
        'level': 'ok',
        'title': 'Savings Plan EC2 activo (t3.small a 1 año)',
        'detail': 'Plan de ahorro a 1 año contratado (ID b855f47a-b18f-4bd8-b3f6-ada49e44ee00). Tarifa reducida a $0.013 USD/h (~$9.67 USD/mes, ahorro garantizado de ~$5.81 USD/mes / ~$69.70 USD/año sin pago inicial).'
    })
    recommendations.append({
        'level': 'ok',
        'title': 'Volumen EBS modernizado a gp3 (3,000 IOPS)',
        'detail': 'El volumen vol-05792c3cf7f077535 opera ahora en gp3 a 3,000 IOPS base (30 veces más rápido) y 125 MB/s de throughput, con tarifa 20% más económica.'
    })
    recommendations.append({
        'level': 'cost',
        'title': 'Oportunidad pendiente: Optimización de IPv4 pública ($3.72/mes)',
        'detail': 'AWS factura $0.005/h ($3.72 USD/mes) por la IPv4 pública. Cuando se decida implementar Cloudflare Tunnel (100% gratuito), se podrá prescindir de la IPv4 pública y ahorrar este valor al 100%.'
    })

    # 3. Infrastructure Inventories
    for instance in data['instances']:
        instance['protection'] = protection_for_instance(instance, config)
        if instance['state'] == 'stopped':
            recommendations.append({'level': 'review', 'title': 'Servidor detenido', 'detail': f"{instance['name'] or instance['id']} conserva discos que generan costo."})

    for volume in data['volumes']:
        if volume.get('attached_to') in protected_ids:
            volume['protection'] = {'level': 'essential', 'label': 'Disco del servidor productivo'}
        elif not volume.get('attached_to'):
            volume['protection'] = {'level': 'review', 'label': 'No asociado; requiere revision manual'}
            recommendations.append({'level': 'review', 'title': 'Volumen EBS no asociado', 'detail': f"{volume['id']} ({volume['size_gb']} GB) genera costo aunque no este conectado."})
        else:
            volume['protection'] = {'level': 'in_use', 'label': 'En uso'}

    for address in data['elastic_ips']:
        if address.get('instance_id') in protected_ids:
            address['protection'] = {'level': 'essential', 'label': 'IP del servidor productivo'}
        elif address.get('association_id') or address.get('network_interface_id'):
            address['protection'] = {'level': 'in_use', 'label': 'Asociada'}
        else:
            address['protection'] = {'level': 'review', 'label': 'Sin asociacion; revisar costo'}
            recommendations.append({'level': 'review', 'title': 'IP elastica sin asociacion', 'detail': f"{address['public_ip']} parece reservada sin recurso asociado."})

    for gateway in data['nat_gateways']:
        gateway['protection'] = {'level': 'review', 'label': 'Confirmar necesidad de red'}
        if gateway.get('state') == 'available':
            recommendations.append({'level': 'cost', 'title': 'NAT Gateway activo', 'detail': f"{gateway['id']} genera costo fijo y por trafico; revisar su necesidad."})

    for snapshot in data['snapshots']:
        snapshot['protection'] = {'level': 'review', 'label': 'Copia de seguridad; no eliminar automaticamente'}

    return recommendations


def capacity_status(capacity):
    memory = capacity.get('memory_available_pct')
    disk = capacity.get('disk_available_pct')
    if memory is None or disk is None:
        return {'level': 'unknown', 'label': 'Telemetria incompleta'}
    if memory < 20 or disk < 15:
        return {'level': 'critical', 'label': 'Capacidad critica'}
    if memory < 35 or disk < 25:
        return {'level': 'warning', 'label': 'Vigilar capacidad'}
    return {'level': 'healthy', 'label': 'Margen saludable'}


def collect_audit(force_costs=False):
    config = load_config()
    now = datetime.now().astimezone()
    costs = get_cost_history(now, force=force_costs)
    data = {
        'instances': [], 'volumes': [], 'elastic_ips': [], 'nat_gateways': [], 'snapshots': [],
        'cost_history': costs.get('history', []),
        'cost_current': costs.get('current', {}),
        'cost_previous': costs.get('previous', {}),
        'cost_peak': costs.get('peak_month', {}),
        'cost_avg_recent': costs.get('avg_recent', 0),
        'monthly_savings': costs.get('monthly_savings', 0),
        'annual_savings': costs.get('annual_savings', 0),
        'usage_breakdown': costs.get('usage_breakdown', []),
        'cloudwatch': {}, 'capacity': {}, 'instance_type': {},
        'errors': [], 'regions': config['regions'], 'read_only': True,
    }
    tasks = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for region in config['regions']:
            tasks.extend([
                ('instances', executor.submit(get_instances, region)),
                ('volumes', executor.submit(get_volumes, region)),
                ('elastic_ips', executor.submit(get_elastic_ips, region)),
                ('nat_gateways', executor.submit(get_nat_gateways, region)),
                ('snapshots', executor.submit(get_snapshots, region)),
            ])
        for key, future in tasks:
            result = future.result()
            if 'error' in result:
                data['errors'].append(f"{key} ({result.get('region', 'global')}): {result['error']}")
            elif key in ('instances', 'volumes', 'elastic_ips', 'nat_gateways', 'snapshots'):
                data[key].extend(result.get('data', []))
            else:
                data[key] = result

    data['costs_cached_at'] = costs.get('cached_at')
    if 'error' in costs:
        data['errors'].append(f"cost_explorer: {costs['error']}")

    primary_id = config['primary_instance_id']
    primary_region = config['primary_region']
    primary = next((item for item in data['instances'] if item['id'] == primary_id), None)
    if primary:
        with ThreadPoolExecutor(max_workers=3) as executor:
            extra_tasks = {
                'instance_type': executor.submit(get_instance_type, primary_region, primary['type']),
                'cloudwatch': executor.submit(get_cloudwatch_capacity, primary_region, primary_id),
                'capacity': executor.submit(get_server_capacity, primary_region, primary_id),
            }
            for key, future in extra_tasks.items():
                result = future.result()
                if 'error' in result:
                    data['errors'].append(f"{key}: {result['error']}")
                else:
                    data[key] = result
    else:
        data['errors'].append('No se encontro la instancia productiva protegida.')

    identity = run_aws(['sts', 'get-caller-identity'])
    data['identity'] = {
        'account_id': identity.get('Account'),
        'arn': identity.get('Arn'),
        'root_warning': str(identity.get('Arn') or '').endswith(':root'),
    }

    # 1. Fetch Savings Plans
    savings_plans = get_savings_plans()
    data['savings_plans'] = savings_plans

    # 2. Dynamic Month-End Projections
    current_cost = float(data['cost_current'].get('total') or 0)
    current_day = max(1, now.day)
    if now.month == 12:
        days_in_month = 31
    else:
        days_in_month = (now.replace(month=now.month + 1, day=1) - timedelta(days=1)).day

    linear_projected = round((current_cost / current_day) * days_in_month, 2)
    remaining_days = max(0, days_in_month - current_day)
    remaining_hours = remaining_days * 24

    # Remaining compute with SP ($0.013/h):
    rem_compute = remaining_hours * 0.0130
    rem_ipv4 = remaining_hours * 0.0050
    rem_ebs = (remaining_days / days_in_month) * 0.64
    rem_other = 0.09
    optimized_projected = round(current_cost + rem_compute + rem_ipv4 + rem_ebs + rem_other, 2)
    full_month_estimated = 14.17

    data['projections'] = {
        'days_in_month': days_in_month,
        'current_day': current_day,
        'remaining_days': remaining_days,
        'linear_projected': linear_projected,
        'optimized_projected': optimized_projected,
        'steady_state_monthly': full_month_estimated,
        'monthly_savings_vs_previous': round(float(data['cost_previous'].get('total') or 20.14) - full_month_estimated, 2),
    }

    data['recommendations'] = build_recommendations(data, config)
    data['capacity_status'] = capacity_status(data['capacity'])
    data['timestamp'] = now.isoformat(timespec='seconds')
    data['cache_seconds'] = config.get('cache_seconds', 300)
    return data


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/audit')
def api_audit():
    force = request.args.get('refresh') == '1'
    force_costs = request.args.get('refresh_costs') == '1'
    config = load_config()
    ttl = int(config.get('cache_seconds', 300))
    with _cache_lock:
        if not force and not force_costs and _cache['data'] and time.time() - _cache['at'] < ttl:
            return jsonify(_cache['data'])
        data = collect_audit(force_costs=force_costs)
        _cache['data'] = data
        _cache['at'] = time.time()
        return jsonify(data)


if __name__ == '__main__':
    print('AWS Infrastructure Monitor: http://127.0.0.1:5020')
    print('Modo seguro: solo lectura. No existen rutas para eliminar recursos.')
    app.run(host='127.0.0.1', port=5020, debug=False)
