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


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def run_aws(args, timeout=45):
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


def get_monthly_cost(start_date, end_date):
    response = run_aws([
        'ce', 'get-cost-and-usage',
        '--time-period', f'Start={start_date},End={end_date}',
        '--granularity', 'MONTHLY',
        '--metrics', 'UnblendedCost',
        '--group-by', 'Type=DIMENSION,Key=SERVICE',
    ])
    if 'error' in response:
        return response
    services = []
    total = 0.0
    for period in response.get('ResultsByTime', []):
        for group in period.get('Groups', []):
            amount = float(group.get('Metrics', {}).get('UnblendedCost', {}).get('Amount') or 0)
            total += amount
            if abs(amount) >= 0.005:
                services.append({'service': group.get('Keys', ['Desconocido'])[0], 'cost': round(amount, 2)})
    services.sort(key=lambda item: abs(item['cost']), reverse=True)
    return {'services': services, 'total': round(total, 2)}


def get_daily_costs(now, force=False):
    today = now.strftime('%Y-%m-%d')
    if not force:
        try:
            with open(COST_CACHE_PATH, 'r', encoding='utf-8') as fh:
                cached = json.load(fh)
            if cached.get('date') == today:
                return cached
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    first_current = now.replace(day=1)
    end_current = now + timedelta(days=1)
    first_previous = (first_current - timedelta(days=1)).replace(day=1)
    with ThreadPoolExecutor(max_workers=2) as executor:
        current_future = executor.submit(
            get_monthly_cost, first_current.strftime('%Y-%m-%d'), end_current.strftime('%Y-%m-%d')
        )
        previous_future = executor.submit(
            get_monthly_cost, first_previous.strftime('%Y-%m-%d'), first_current.strftime('%Y-%m-%d')
        )
        result = {
            'date': today,
            'cached_at': now.isoformat(timespec='seconds'),
            'current': current_future.result(),
            'previous': previous_future.result(),
        }
    if 'error' not in result['current'] and 'error' not in result['previous']:
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
        '--document-name', document_name, '--comment', 'TUC TUC read-only capacity monitor',
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
                {'key': 'postgres', 'name': 'PostgreSQL compartido', 'memory_bytes': values.get('postgres_rss', 0), 'disk_bytes': None, 'protected': True},
                {'key': 'nginx', 'name': 'Nginx compartido', 'memory_bytes': values.get('nginx_rss', 0), 'disk_bytes': None, 'protected': True},
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
    if not recommendations:
        recommendations.append({'level': 'ok', 'title': 'Sin desperdicios evidentes', 'detail': 'No se detectaron NAT activos, IP libres, volúmenes sueltos ni servidores detenidos en las regiones auditadas.'})
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
    return {'level': 'healthy', 'label': 'Margen disponible'}


def collect_audit(force_costs=False):
    config = load_config()
    now = datetime.now().astimezone()
    costs = get_daily_costs(now, force=force_costs)
    data = {
        'instances': [], 'volumes': [], 'elastic_ips': [], 'nat_gateways': [], 'snapshots': [],
        'cost_current': {}, 'cost_previous': {}, 'cloudwatch': {}, 'capacity': {}, 'instance_type': {},
        'errors': [], 'regions': config['regions'], 'read_only': True,
    }
    tasks = []
    with ThreadPoolExecutor(max_workers=15) as executor:
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

    data['cost_current'] = costs.get('current', {})
    data['cost_previous'] = costs.get('previous', {})
    data['costs_cached_at'] = costs.get('cached_at')
    for key in ('cost_current', 'cost_previous'):
        if 'error' in data[key]:
            data['errors'].append(f"{key}: {data[key]['error']}")

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
        if not force and _cache['data'] and time.time() - _cache['at'] < ttl:
            return jsonify(_cache['data'])
        data = collect_audit(force_costs=force_costs)
        _cache['data'] = data
        _cache['at'] = time.time()
        return jsonify(data)


if __name__ == '__main__':
    print('AWS Infrastructure Monitor: http://127.0.0.1:5020')
    print('Modo seguro: solo lectura. No existen rutas para eliminar recursos.')
    app.run(host='127.0.0.1', port=5020, debug=False)
