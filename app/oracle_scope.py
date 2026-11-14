"""Bounded, calendar-partitioned UI inventory. No Oracle APIs or credentials."""
from calendar import monthrange
from datetime import date,datetime,timedelta,timezone
from .domain import ValidationError

QUERY_YEAR=2026
STATES=['Abierta','Inscrito','Perdida']
# Below the size of the previously verified 795-row UI export. A full leaf
# never relies on the parser's 1,000-row ceiling as proof of completeness.
PARTITION_LIMIT=500

def month_queries(year=QUERY_YEAR):
    if type(year)!=int or year!=QUERY_YEAR:raise ValidationError('Año de consulta no autorizado.')
    return [{'from':date(year,m,1).isoformat(),'to':date(year,m,monthrange(year,m)[1]).isoformat(),'states':list(STATES)} for m in range(1,13)]

def split_query(query):
    start=date.fromisoformat(query['from']);end=date.fromisoformat(query['to'])
    if start<end:
        mid=start+timedelta(days=(end-start).days//2)
        return [dict(query,to=mid.isoformat()),dict(query,**{'from':(mid+timedelta(days=1)).isoformat()})]
    if len(query['states'])>1:return [dict(query,states=[state]) for state in query['states']]
    return []

def inventory(fetch,ingest,progress,year=QUERY_YEAR):
    pending=month_queries(year);seen=set();leaves=[];unresolved=[]
    started=datetime.now(timezone.utc).isoformat()
    def report(complete=False):
        result={'year':year,'states':list(STATES),'complete':complete,'row_count':len(seen),
          'partitions_finished':len(leaves),'partitions_pending':len(pending),
          'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat() if not pending else None,
          'partitions':leaves,'unresolved':unresolved}
        progress(result);return result
    report()
    while pending:
        query=pending.pop(0);payload=fetch(query);rows=payload.get('records')
        if not isinstance(rows,list):raise ValidationError('Respuesta de inventario inválida.')
        if not rows and payload.get('empty_verified') is not True:raise ValidationError('No se confirmó la consulta vacía en Oracle.')
        for row in rows:
            try:closed=date.fromisoformat(row['close_date'])
            except (KeyError,TypeError,ValueError):raise ValidationError('No se pudo verificar la fecha de cierre exportada.')
            if not date.fromisoformat(query['from'])<=closed<=date.fromisoformat(query['to']) or row.get('status') not in query['states']:
                raise ValidationError('Oracle devolvió filas fuera del alcance solicitado; no se certifica el inventario.')
        if len(rows)>=PARTITION_LIMIT:
            children=split_query(query)
            if children:pending=children+pending;report();continue
            unresolved.append(dict(query,reason='export-limit'))
        if rows:
            ingest(dict(payload,scope=f'Todos los registros que puedo ver · todos los estados · cierre en {year}'))
            seen.update(row['opportunity_number'] for row in rows)
        leaves.append(dict(query,rows=len(rows),bounded=len(rows)<PARTITION_LIMIT));report()
    return report(complete=not unresolved)
