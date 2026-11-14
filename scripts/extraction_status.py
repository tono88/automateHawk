"""Local operator status, counts only; no credentials, IDs, names or values."""
import json,os
from pathlib import Path
import psycopg

def main():
    private=Path(os.environ['LOCALAPPDATA'])/'automateHawk'
    with psycopg.connect((private/'database-host.dsn').read_text().strip(),connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM hub.opportunities')
            mirrored=cursor.fetchone()[0]
            cursor.execute("""WITH latest AS (
                SELECT DISTINCT ON (opportunity_number) opportunity_number,state,updated_at
                FROM hub.detail_read_progress ORDER BY opportunity_number,updated_at DESC)
                SELECT state,count(*) FROM latest GROUP BY state""")
            states=dict(cursor.fetchall())
            cursor.execute("""SELECT count(DISTINCT opportunity_number)
                FROM hub.user_permissions WHERE read_until>now()""")
            allowed=cursor.fetchone()[0]
            cursor.execute("""SELECT round(extract(epoch FROM now()-max(updated_at)))::int
                FROM hub.detail_read_progress WHERE state='completed'""")
            age=cursor.fetchone()[0]
            cursor.execute("SELECT value FROM hub.settings WHERE key LIKE 'listing_coverage:%' ORDER BY value->>'started_at' DESC LIMIT 1")
            manifest=cursor.fetchone()
            coverage={k:manifest[0].get(k) for k in ('year','complete','row_count','partitions_finished','partitions_pending','finished_at')} if manifest else None
            cursor.execute("""SELECT o.payload->>'status',count(*) FROM hub.opportunities o
                WHERE o.payload->>'close_date' BETWEEN '2026-01-01' AND '2026-12-31'
                AND EXISTS(SELECT 1 FROM hub.user_permissions p WHERE p.opportunity_number=o.opportunity_number AND p.read_until>now())
                GROUP BY o.payload->>'status'""")
            year_states=dict(cursor.fetchall())
    print(json.dumps({'global_mirror_records':mirrored,'records_with_active_list_grant':allowed,
        'unique_record_read_states':states,'annual_inventory':coverage,'active_2026_by_status':year_states,'seconds_since_last_completed_read':age,
        'note':'Global operator counts; not a certification of total CRM coverage.'}))

if __name__=='__main__':main()
