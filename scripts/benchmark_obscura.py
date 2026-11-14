"""Compatibility gate for a local Obscura binary; never sends credentials.

Only the institutional public sign-in page is loaded. Output is aggregate
timing/control availability, never HTML, console messages, cookies or URLs
returned by authentication redirects.
"""
import argparse,json,statistics,subprocess,time

TARGET='https://ehvs.fa.us6.oraclecloud.com/hcmUI/faces/FuseWelcome'
PROBE='JSON.stringify({password:!!document.querySelector("input[type=password]"),username:!!document.querySelector("#userid,[id*=username]")})'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('binary');parser.add_argument('--repeats',type=int,choices=range(1,6),default=3)
    args=parser.parse_args();samples=[]
    for _ in range(args.repeats):
        start=time.monotonic()
        try:
            result=subprocess.run([args.binary,'fetch',TARGET,'--timeout','40','--quiet','--eval',PROBE],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=50)
            try:probe=json.loads(result.stdout.strip().splitlines()[-1])
            except (ValueError,IndexError):probe={}
            ready=bool(probe.get('username') and probe.get('password'))
            code='ready' if ready else 'javascript-stack-overflow' if 'Maximum call stack size exceeded' in result.stderr else 'login-not-rendered'
        except subprocess.TimeoutExpired:ready=False;code='timeout'
        samples.append({'seconds':round(time.monotonic()-start,2),'ready':ready,'code':code})
    print(json.dumps({'engine':'obscura','stage':'public-login-only','credentials_sent':False,'samples':samples,'median_seconds':statistics.median(s['seconds'] for s in samples),'compatible':all(s['ready'] for s in samples)}))

if __name__=='__main__':main()
