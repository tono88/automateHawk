"""Private operator coverage report: aggregate counts only, never record values."""
import json,os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from app.catalog import DETAIL_FIELDS


def main():
    private=Path(os.environ['LOCALAPPDATA'])/'automateHawk'
    with psycopg.connect((private/'database-host.dsn').read_text().strip(),row_factory=dict_row,connect_timeout=5) as c:
        # One consistent observation while the background reader continues.
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        scope="""WITH coverage_scope AS (
          SELECT o.opportunity_number,o.payload||coalesce(d.payload->'fields','{}'::jsonb) AS fields,
                 d.payload AS detail
          FROM hub.opportunities o LEFT JOIN hub.record_details d USING(opportunity_number)
          WHERE o.payload->>'close_date' BETWEEN '2026-01-01' AND '2026-12-31') """
        total=c.execute(scope+'SELECT count(*) AS n FROM coverage_scope').fetchone()['n']
        fields=c.execute(scope+"""SELECT key,
          count(*) FILTER(WHERE fields ? key) AS observed,
          count(*) FILTER(WHERE fields ? key AND coalesce(fields->>key,'')='') AS observed_blank,
          count(*) FILTER(WHERE fields ? key AND coalesce(fields->>key,'')<>'') AS populated,
          count(*) FILTER(WHERE NOT(fields ? key)) AS not_extracted
          FROM coverage_scope CROSS JOIN unnest(%s::text[]) AS keys(key)
          GROUP BY key ORDER BY key""",(list(DETAIL_FIELDS),)).fetchall()
        links=c.execute(scope+"""SELECT
          count(*) FILTER(WHERE fields->>'contact_link_status'='Contacto principal verificado desde la oportunidad') AS verified,
          count(*) FILTER(WHERE fields->>'contact_link_status'='Contacto eliminado o no accesible según Oracle') AS unavailable,
          count(*) FILTER(WHERE fields->>'contact_link_status'='No hay un contacto principal único en la relación') AS no_unique_primary,
          count(*) FILTER(WHERE fields->>'contact_link_status'='Sin acceso al módulo de contactos') AS module_unavailable,
          count(*) FILTER(WHERE NOT(fields ? 'contact_link_status')) AS not_extracted
          FROM coverage_scope""").fetchone()
        activities=c.execute(scope+"""SELECT
          count(*) FILTER(WHERE detail->'activities'->>'queried'='true') AS queried,
          coalesce(sum(jsonb_array_length(coalesce(detail->'activities'->'rows','[]'::jsonb))),0)::int AS rows_observed
          FROM coverage_scope""").fetchone()
    print(json.dumps({'year':2026,'opportunities':total,'fields':fields,'contact_links':links,
      'activities':activities,'note':'Observed blank is distinct from not extracted. Source access restrictions are retained. No personal values are emitted.'},ensure_ascii=False))


if __name__=='__main__':main()
