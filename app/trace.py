"""Traceability dashboard: cross-tabs, consistency checks and per-opportunity timelines.

Everything is computed from the session's scoped snapshot, so a user only sees
aggregates of the opportunities and fields that Oracle allowed them to read.
"""
from datetime import datetime, timezone, date
from .catalog import DETAIL_FIELDS

DIMENSIONS = [
    ('stage', 'Etapa comercial'), ('owner', 'Asesor'), ('status', 'Estado de Oracle'),
    ('segment', 'Segmento'), ('cycle', 'Ciclo de ingreso'), ('faculty', 'Facultad'),
    ('career', 'Carrera de interés'), ('admission_status', 'Proceso de admisión'),
    ('test_call', 'Convocatoria PA'), ('test_month', 'Mes de prueba (Fecha PA)'),
    ('test_type', 'Prueba de admisión'), ('resolution', 'Resolución'),
    ('interview', 'Entrevista'), ('financial_aid', 'Asistencia económica'),
    ('lead_status', 'Estatus lead'), ('campus_status', 'Estado en Campus'),
    ('origin', 'Origen'), ('close_month', 'Mes de cierre'), ('detail_state', 'Estado de extracción'),
]
STAGE_ORDER = ['01 - Interesado', '02 - Inscrito a prueba', '03 - Presente a prueba: resolución',
               '04 - Perdida', '05 - Matriculado', '06 - Inscrito']
EMPTY = 'Sin dato'


def as_date(value):
    value = str(value or '').strip()
    for pattern in ('%Y-%m-%d', '%d/%m/%y', '%d/%m/%Y'):
        try:
            return datetime.strptime(value[:10] if pattern == '%Y-%m-%d' else value, pattern).date()
        except ValueError:
            pass
    return None


def _detail_state(number, snapshot):
    outcome = (snapshot.get('read_states') or {}).get(number) or {}
    if outcome.get('state') == 'failed':
        return 'Lectura con incidencia'
    if outcome.get('state') == 'partial':
        return 'Lectura parcial'
    if number in (snapshot.get('details') or {}):
        return 'Detalle disponible'
    state = (snapshot.get('detail_states') or {}).get(number)
    if state in ('permission_expired', 'permission_required'):
        return 'Permiso por renovar'
    return 'Detalle pendiente'


def compact_rows(snapshot):
    details = snapshot.get('details') or {}
    rows = []
    for record in snapshot.get('records', []):
        number = record['opportunity_number']
        fields = (details.get(number) or {}).get('fields') or {}
        get = lambda key: str(record.get(key) or fields.get(key) or '').strip()
        test_date = as_date(get('test_date'))
        close_date = as_date(get('close_date'))
        row = {key: get(key) for key, _ in DIMENSIONS if key not in ('test_month', 'close_month', 'detail_state')}
        row.update(
            number=number,
            name=' '.join(filter(None, [record.get('first_name'), record.get('last_name')])) or record.get('name') or number,
            test_month=test_date.strftime('%Y-%m') if test_date else '',
            close_month=close_date.strftime('%Y-%m') if close_date else '',
            detail_state=_detail_state(number, snapshot),
            close_date=close_date.isoformat() if close_date else '',
            test_date=test_date.isoformat() if test_date else '',
            last_seen=record.get('_last_seen') or '',
            amount=get('amount'),
        )
        rows.append(row)
    return rows


def consistency_checks(rows, changes, today=None):
    today = today or date.today()
    pending_changes = {c['opportunity_number'] for c in changes if c.get('state') in ('pending_validation', 'queued', 'applying')}
    doubtful_changes = {c['opportunity_number'] for c in changes if c.get('state') in ('uncertain', 'conflict', 'failed')}
    has_detail = lambda r: r['detail_state'] == 'Detalle disponible'
    checks = [
        ('no-owner', 'Sin asesor asignado', 'La oportunidad no tiene Responsable en la lista de Oracle.',
         lambda r: not r['owner']),
        ('overdue-open', 'Fecha de cierre vencida y abierta', 'Estado de Oracle abierto con fecha de cierre anterior a hoy.',
         lambda r: r['close_date'] and r['close_date'] < today.isoformat() and r['status'].lower().startswith('abiert')),
        ('test-without-call', 'Inscrito a prueba sin convocatoria', 'Etapa 02 o 03 sin Convocatoria PA en el detalle.',
         lambda r: has_detail(r) and r['stage'][:2] in ('02', '03') and not r['test_call']),
        ('test-without-date', 'Presente a prueba sin fecha PA', 'Etapa 03 sin Fecha PA registrada en el detalle.',
         lambda r: has_detail(r) and r['stage'][:2] == '03' and not r['test_date']),
        ('enrolled-without-resolution', 'Matriculado/inscrito sin resolución', 'Etapa 05 o 06 sin Resolución registrada.',
         lambda r: has_detail(r) and r['stage'][:2] in ('05', '06') and not r['resolution']),
        ('lost-with-future-test', 'Perdida con prueba futura', 'Etapa 04 con Fecha PA posterior a hoy.',
         lambda r: r['stage'][:2] == '04' and r['test_date'] and r['test_date'] > today.isoformat()),
        ('detail-missing', 'Sin detalle extraído', 'Los cruces de pruebas, ayuda y matrícula no incluyen estos registros.',
         lambda r: r['detail_state'] != 'Detalle disponible'),
        ('change-pending', 'Cambios en curso hacia Oracle', 'Cambios solicitados desde el portal aún no confirmados.',
         lambda r: r['number'] in pending_changes),
        ('change-doubtful', 'Cambios inciertos o en conflicto', 'Requieren verificación en Oracle antes de reintentar.',
         lambda r: r['number'] in doubtful_changes),
    ]
    result = []
    for key, title, description, test in checks:
        matched = [r['number'] for r in rows if test(r)]
        result.append({'id': key, 'title': title, 'description': description, 'count': len(matched), 'numbers': matched})
    return result


def freshness(rows, now=None):
    now = now or datetime.now(timezone.utc)
    buckets = {'Menos de 1 día': 0, '1 a 7 días': 0, 'Más de 7 días': 0, 'Sin observación': 0}
    for row in rows:
        try:
            seen = datetime.fromisoformat(row['last_seen'])
        except (TypeError, ValueError):
            buckets['Sin observación'] += 1
            continue
        age = (now - seen).total_seconds() / 86400
        buckets['Menos de 1 día' if age < 1 else '1 a 7 días' if age <= 7 else 'Más de 7 días'] += 1
    return [{'label': k, 'count': v} for k, v in buckets.items()]


def funnel(rows):
    counts = {}
    for row in rows:
        counts[row['stage'] or EMPTY] = counts.get(row['stage'] or EMPTY, 0) + 1
    ordered = [s for s in STAGE_ORDER if s in counts] + sorted(k for k in counts if k not in STAGE_ORDER)
    return [{'label': s, 'count': counts[s]} for s in ordered]


def dashboard(snapshot, changes, activity=None):
    rows = compact_rows(snapshot)
    change_states = {}
    for change in changes:
        change_states[change['state']] = change_states.get(change['state'], 0) + 1
    with_detail = sum(r['detail_state'] == 'Detalle disponible' for r in rows)
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'dimensions': [{'key': k, 'label': l} for k, l in DIMENSIONS],
        'stage_order': STAGE_ORDER,
        'rows': rows,
        'kpis': {
            'opportunities': len(rows),
            'with_detail': with_detail,
            'owners': len({r['owner'] for r in rows if r['owner']}),
            'changes_confirmed': change_states.get('confirmed', 0),
            'changes_open': sum(n for s, n in change_states.items() if s in ('pending_validation', 'queued', 'applying', 'uncertain', 'conflict')),
        },
        'funnel': funnel(rows),
        'freshness': freshness(rows),
        'checks': consistency_checks(rows, changes),
        'change_states': change_states,
        'activity': activity or {'by_day': [], 'recent': []},
        'field_labels': {k: v[0] for k, v in DETAIL_FIELDS.items()},
        'loaded_at': snapshot.get('loaded_at'),
        'job': snapshot.get('job'),
    }


def diff_versions(versions):
    """Field-level differences between consecutive observed versions (oldest first)."""
    timeline = []
    previous = None
    for version in versions:
        payload = version['payload']
        if previous is None:
            timeline.append({'at': version['observed_at'], 'version': version['source_version'], 'kind': 'first_seen', 'changes': []})
        else:
            changed = [{'field': k, 'before': previous.get(k, ''), 'after': payload.get(k, '')}
                       for k in sorted(set(previous) | set(payload)) if str(previous.get(k, '')) != str(payload.get(k, ''))]
            if changed:
                timeline.append({'at': version['observed_at'], 'version': version['source_version'], 'kind': 'oracle_change', 'changes': changed})
        previous = payload
    return timeline
