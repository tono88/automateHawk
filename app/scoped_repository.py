"""One global mirror with persistent, expiring per-user permissions."""
import os
from datetime import datetime,timezone,timedelta
from psycopg.types.json import Jsonb
from .persistence import PostgresRepository
from .domain import ConflictError

def read_grant_minutes(key,default):
    value=int(os.environ.get(key,str(default)))
    if not 15<=value<=480:raise ValueError('Read permission lifetime must be between 15 and 480 minutes')
    return value

class ScopedRepository(PostgresRepository):
    def __init__(self,dsn,principal):
        self.principal=principal;self.observed_fields={}
        self.basic_minutes=read_grant_minutes('HUB_LIST_GRANT_MINUTES',60)
        self.detail_minutes=read_grant_minutes('HUB_DETAIL_GRANT_MINUTES',30)
        # The worker re-validates permission and current value on the live form before
        # every save, so the edit window may follow the detail window.
        self.edit_minutes=read_grant_minutes('HUB_EDIT_GRANT_MINUTES',self.detail_minutes)
        # Incremental sync: a completed detail is read again only when Oracle reports a
        # change in the list (version, including "Última actualización"), when the read
        # failed, or as a safety net after this many hours (0 disables the age rule).
        self.detail_max_age_hours=int(os.environ.get('HUB_DETAIL_MAX_AGE_HOURS','168'))
        # Last-copy view: records this user saw in Oracle within this many days are shown
        # at login while the inventory re-confirms them; revoked ones never are. 0 = off.
        self.stale_view_days=int(os.environ.get('HUB_STALE_VIEW_DAYS','7'))
        super().__init__(dsn)
    def fingerprint(self):
        """Shared copy plus this user's permissions and read progress. Time-based expiries are
        included (counts of grants still valid now), so a lapse also triggers a reload."""
        with self.connect() as c:
            row=c.execute("""SELECT
                (SELECT coalesce(max(checked_at)::text,'')||':'||count(*)||':'||count(revoked_at)||':'||
                   count(*) FILTER (WHERE read_until>now())||':'||count(*) FILTER (WHERE detail_until>now())||':'||
                   count(*) FILTER (WHERE edit_until>now())||':'||count(*) FILTER (WHERE read_until>now()-make_interval(days => %s))
                 FROM user_permissions WHERE principal=%s) AS p,
                (SELECT coalesce(max(updated_at)::text,'')||':'||count(*) FROM detail_read_progress WHERE principal=%s) AS r""",
                (self.stale_view_days,self.principal,self.principal)).fetchone()
        return super().fingerprint()+(row['p'],row['r'])
    def visible_grants(self):
        """Confirmed grants plus recently expired, non-revoked ones (shown as unconfirmed)."""
        with self.connect() as c:
            rows=c.execute("""SELECT * FROM user_permissions WHERE principal=%s AND
              (read_until>now() OR (%s>0 AND revoked_at IS NULL AND read_until>now()-make_interval(days => %s)))""",
              (self.principal,self.stale_view_days,self.stale_view_days)).fetchall()
        return {r['opportunity_number']:r for r in rows}
    def grants(self):
        with self.connect() as c:
            rows=c.execute('SELECT * FROM user_permissions WHERE principal=%s AND read_until>now()',(self.principal,)).fetchall()
        return {r['opportunity_number']:r for r in rows}
    def require(self,number,field=None):
        grant=self.grant(number)
        if not grant:raise PermissionError()
        now=datetime.now(timezone.utc)
        if field and (not grant['detail_until'] or grant['detail_until']<now or not grant['edit_until'] or grant['edit_until']<now or not grant['capabilities'].get(field)):raise PermissionError()
        return grant
    def grant(self,number):
        with self.connect() as c:
            return c.execute('SELECT * FROM user_permissions WHERE principal=%s AND opportunity_number=%s AND read_until>now()',
                             (self.principal,number)).fetchone()
    def save_snapshot(self,rows,scope):
        # Preserve globally known fields not exposed by this user's list.
        original={r['opportunity_number']:r for r in super().load()['records']};merged=[]
        for row in rows:
            number=row['opportunity_number'];allowed=self.observed_fields.get(number,list(row))
            previous={k:v for k,v in original.get(number,{}).items() if not k.startswith('_')}
            previous.update({k:v for k,v in row.items() if k in allowed});merged.append(previous)
        result=super().save_snapshot(merged,scope)
        with self.connect() as c:
            for row in rows:
                number=row['opportunity_number'];fields=self.observed_fields.get(number,list(row))
                c.execute("""INSERT INTO user_permissions(principal,opportunity_number,basic_fields,read_until,basic_checked_at)
                  VALUES(%s,%s,%s,now()+make_interval(mins => %s),now()) ON CONFLICT(principal,opportunity_number)
                  DO UPDATE SET basic_fields=excluded.basic_fields,read_until=excluded.read_until,
                  basic_checked_at=excluded.basic_checked_at,revoked_at=NULL,checked_at=now()""",(self.principal,number,Jsonb(fields),self.basic_minutes))
            # The list export just re-confirmed that this user sees these records. When a
            # record did not change since its completed detail read, the detail and edit
            # windows are renewed instead of re-reading the whole form from Oracle.
            c.execute("""UPDATE user_permissions p
              SET detail_until=now()+make_interval(mins => %s),edit_until=now()+make_interval(mins => %s),checked_at=now()
              FROM detail_read_progress r,opportunities o
              WHERE p.principal=%s AND p.opportunity_number=ANY(%s::text[])
              AND r.principal=p.principal AND r.opportunity_number=p.opportunity_number
              AND o.opportunity_number=p.opportunity_number
              AND r.state='completed' AND r.schema_version>=2 AND r.source_version=o.version
              AND p.revoked_at IS NULL AND p.detail_fields<>'[]'::jsonb AND p.detail_checked_at IS NOT NULL""",
              (self.detail_minutes,self.edit_minutes,self.principal,[r['opportunity_number'] for r in rows]))
        self.observed_fields={};return result
    def reconcile_visible_inventory(self,numbers):
        """Expire this principal's missing grants; retain shared data and history."""
        with self.connect() as c:
            c.execute("""UPDATE user_permissions SET read_until=now(),detail_until=now(),edit_until=now(),revoked_at=now(),
              detail_fields='[]'::jsonb,capabilities='{}'::jsonb,activities_visible=false
              WHERE principal=%s AND NOT(opportunity_number=ANY(%s::text[]))""",
              (self.principal,list(numbers)))
    def extend_observed_detail_reads(self):
        """Operator-only policy transition; never changes field scope or editing.

        Requires a recent list observation and a completed per-user detail read
        inside the configured window. There is deliberately no public API route.
        """
        with self.connect() as c:
            changed=c.execute("""UPDATE user_permissions p
              SET detail_until=p.detail_checked_at+make_interval(mins => %s)
              FROM detail_read_progress r
              WHERE p.principal=%s AND r.principal=p.principal AND r.opportunity_number=p.opportunity_number
              AND r.state='completed' AND r.schema_version>=2
              AND r.updated_at>=p.detail_checked_at-interval '1 minute'
              AND p.read_until>now() AND p.revoked_at IS NULL
              AND p.basic_checked_at>=now()-interval '1 hour' AND p.basic_checked_at<=now()
              AND p.detail_fields<>'[]'::jsonb
              AND p.detail_checked_at>=now()-make_interval(mins => %s) AND p.detail_checked_at<=now()
              AND p.detail_until<p.detail_checked_at+make_interval(mins => %s)""",
              (self.detail_minutes,self.principal,self.detail_minutes,self.detail_minutes)).rowcount
            c.execute("INSERT INTO audit_events(actor,action,metadata) VALUES(%s,'read_window_policy_applied',%s)",
              (self.principal,Jsonb({'read_minutes':self.detail_minutes,'changed_permissions':changed,
                'observation_preserved':True,'field_scope_unchanged':True,'editing_unchanged':True})))
        return changed
    def load(self):
        result=super().load();grants=self.visible_grants();now=datetime.now(timezone.utc)
        confirmed=lambda g:g['read_until']>now
        records=[]
        for r in result['records']:
            g=grants.get(r['opportunity_number'])
            if not g:continue
            row={k:v for k,v in r.items() if k in g['basic_fields'] or k.startswith('_') or k=='opportunity_number'}
            if not confirmed(g):row['_unconfirmed']=True
            records.append(row)
        result['records']=records
        details={};states={}
        for r in records:
            number=r['opportunity_number'];g=grants[number];d=result['details'].get(number)
            if not d:states[number]='not_loaded';continue
            if not g['detail_until'] or not g['detail_checked_at']:states[number]='permission_required';continue
            current=confirmed(g) and g['detail_until']>now
            if not current and g['detail_until']<now-timedelta(days=self.stale_view_days):states[number]='permission_expired';continue
            edit_valid=current and bool(g['edit_until'] and g['edit_until']>now)
            details[number]=dict(d,fields={k:v for k,v in d['fields'].items() if k in g['detail_fields']},capabilities={k:bool(v and edit_valid) for k,v in g['capabilities'].items()},activities=d.get('activities') if g['activities_visible'] else {'queried':False,'rows':[]},loaded_at=min(d['loaded_at'],g['detail_checked_at'].isoformat()))
            if not current:details[number]['unconfirmed']=True
            states[number]='available' if current else 'unconfirmed'
        result['details']=details;result['detail_states']=states
        result['unconfirmed']=sum('_unconfirmed' in r for r in records)
        if not grants:result.update(loaded_at=None,scope='Verificación de permisos pendiente con tu sesión de Oracle')
        return result
    def save_detail(self,number,detail):
        grant=self.require(number)
        with self.connect() as c:
            row=c.execute('SELECT payload FROM record_details WHERE opportunity_number=%s',(number,)).fetchone()
        old=row['payload'] if row else {}
        detail=dict(detail);partial=detail.pop('partial_read',False)
        merged=dict(detail,fields=dict(old.get('fields',{}),**detail['fields']))
        fields=list(detail['fields']);capabilities=dict(detail['capabilities']);activities=detail['activities']['queried']
        if partial:
            # A confirmation after a write reads only the edited section. Keep the rest
            # of the stored detail and of this user's observed scope instead of shrinking it.
            for key in ('activities','pending_modules','module_reason','validation_field','schema_version'):
                if key in old:merged[key]=old[key]
            fields=sorted(set(grant.get('detail_fields') or [])|set(fields))
            capabilities=dict(grant.get('capabilities') or {},**capabilities)
            activities=bool(grant.get('activities_visible')) or activities
        super().save_detail(number,merged)
        with self.connect() as c:
            c.execute("""UPDATE user_permissions SET detail_fields=%s,capabilities=%s,activities_visible=%s,
              detail_until=now()+make_interval(mins => %s),edit_until=now()+make_interval(mins => %s),
              detail_checked_at=now(),checked_at=now() WHERE principal=%s AND opportunity_number=%s""",(Jsonb(fields),Jsonb(capabilities),activities,self.detail_minutes,self.edit_minutes,self.principal,number))
    def confirm_write(self,identifier,actor,detail):
        super().confirm_write(identifier,actor,detail)
        # The record was just re-read in Oracle after the save: keep its completed detail
        # current so the incremental sync does not read it again.
        with self.connect() as c:
            c.execute("""UPDATE detail_read_progress r SET source_version=o.version,updated_at=now()
              FROM change_requests q,opportunities o
              WHERE q.id=%s AND o.opportunity_number=q.opportunity_number AND r.opportunity_number=q.opportunity_number
              AND r.principal=%s AND r.state='completed'""",(identifier,self.principal))
    def creations(self,actor=None):
        return super().creations(self.principal)
    def changes(self,number=None):
        if number:self.require(number)
        rows=super().changes(number)
        if not rows:return []
        grants=self.visible_grants()
        def visible(row):
            g=grants.get(row['opportunity_number'])
            return bool(g and row['field'] in (g['basic_fields']+(g['detail_fields'] if g['detail_checked_at'] else [])))
        return [r for r in rows if visible(r) and r['actor']==self.principal]
    def trace_activity(self,numbers,days=30):
        visible=set(self.visible_grants())
        return super().trace_activity([n for n in numbers if n in visible],days)
    def opportunity_trace(self,number):
        grant=self.require(number)
        result=super().opportunity_trace(number)
        allowed=set(grant['basic_fields'])|{'opportunity_number'}
        for version in result['versions']:version['payload']={k:v for k,v in version['payload'].items() if k in allowed}
        return result
    def propose(self,number,field,*args):
        self.require(number,field);return super().propose(number,field,*args)
    def cancel(self,identifier,actor):
        if not any(r['id']==identifier for r in self.changes()):raise PermissionError()
        return super().cancel(identifier,actor)
    def local_activities(self):
        items=super().local_activities()
        if not items:return []
        grants=self.grants()
        rows=[r for r in items if r['opportunity_number'] in grants and (r['actor']==self.principal or (grants[r['opportunity_number']]['activities_visible'] and grants[r['opportunity_number']]['detail_until'] and grants[r['opportunity_number']]['detail_until']>datetime.now(timezone.utc)))]
        for r in rows:r['can_edit']=r.pop('actor')==self.principal
        return rows
    def save_local_activity(self,item,actor):
        self.require(item['opportunity_number'])
        with self.connect() as c:
            existing=c.execute('SELECT actor FROM local_activities WHERE id=%s',(item['id'],)).fetchone()
        if existing and existing['actor']!=self.principal:raise PermissionError()
        return super().save_local_activity(item,actor)
    def summary(self):
        with self.connect() as c:
            count=c.execute('SELECT count(*) AS n FROM user_permissions WHERE principal=%s AND read_until>now()', (self.principal,)).fetchone()['n']
        return dict(engine='postgresql',persistent=True,records=count,historical_versions=None,sync_runs=None,global_mirror=True)

    def read_progress(self):
        with self.connect() as c:
            rows=c.execute('''SELECT r.opportunity_number,r.state,r.attempts,r.error_code,r.schema_version,r.source_version,
              (p.detail_until IS NULL OR p.detail_until<=now()) AS permission_refresh_required,
              (r.state='completed' AND (
                (%s>0 AND r.updated_at<now()-make_interval(hours => %s))
                OR (r.source_version IS NOT NULL AND r.source_version<>o.version)
                OR (r.source_version IS NULL AND EXISTS(
                  SELECT 1 FROM opportunity_history h WHERE h.opportunity_number=o.opportunity_number
                  AND h.source_version=o.version AND h.observed_at>r.updated_at)))) AS needs_refresh
              FROM detail_read_progress r JOIN user_permissions p
              ON p.principal=r.principal AND p.opportunity_number=r.opportunity_number
              JOIN opportunities o ON o.opportunity_number=r.opportunity_number
              WHERE r.principal=%s AND p.revoked_at IS NULL AND p.read_until>now()-make_interval(days => %s)''',(self.detail_max_age_hours,self.detail_max_age_hours,self.principal,self.stale_view_days)).fetchall()
        return {r['opportunity_number']:{k:v for k,v in r.items() if k!='opportunity_number'} for r in rows}
    def save_read_progress(self,number,state,attempts=0,error_code='',source_version=None):
        self.require(number)
        if state not in ('reading','completed','partial','failed') or error_code not in ('','timeout','layout','permission','unavailable','contact-unavailable'):raise ValueError('Invalid read outcome')
        if source_version is not None and (type(source_version)!=int or source_version<1):raise ValueError('Invalid source version')
        with self.connect() as c:
            if state=='reading' and source_version is None:
                source_version=c.execute('SELECT version FROM opportunities WHERE opportunity_number=%s',(number,)).fetchone()['version']
            c.execute("""INSERT INTO detail_read_progress(principal,opportunity_number,state,attempts,error_code,source_version)
              VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(principal,opportunity_number) DO UPDATE
              SET state=excluded.state,attempts=detail_read_progress.attempts+excluded.attempts,
                  error_code=excluded.error_code,schema_version=2,updated_at=now(),
                  source_version=coalesce(excluded.source_version,detail_read_progress.source_version)""",(self.principal,number,state,attempts,error_code,source_version))
