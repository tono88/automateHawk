"""Local-only test lab server. Deliberately refuses real Oracle operation."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .domain import DemoStore, ValidationError, ConflictError

STATIC=Path(__file__).parent/'static'
STORE=DemoStore()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass  # No request bodies, search terms or personal data in logs.
    def respond(self,status,data,kind='application/json; charset=utf-8'):
        payload=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(payload)

    def allowed(self):
        try: return urlsplit('http://'+self.headers.get('Host','')).hostname in ['localhost','127.0.0.1','[::1]','::1']
        except ValueError: return False

    def do_GET(self):
        if not self.allowed(): return self.respond(403,{'error':'Solo acceso local al laboratorio.'})
        path=urlsplit(self.path).path
        if path=='/health': return self.respond(200,{'status':'ok','mode':'demo'})
        if path=='/api/snapshot': return self.respond(200,STORE.snapshot())
        routes={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if path not in routes: return self.respond(404,{'error':'Recurso inexistente.'})
        filename,kind=routes[path]
        self.respond(200,(STATIC/filename).read_bytes(),kind)

    def mutate(self):
        if not self.allowed(): return self.respond(403,{'error':'Solo acceso local.'})
        origin=self.headers.get('Origin')
        if origin and (urlsplit(origin).netloc!=self.headers.get('Host') or urlsplit(origin).scheme!='http'):
            return self.respond(403,{'error':'Origen no permitido.'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json': return self.respond(415,{'error':'Se requiere JSON.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=32768: return self.respond(413,{'error':'Solicitud demasiado grande o vacía.'})
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict): raise ValidationError('Solicitud inválida.')
            parts=urlsplit(self.path).path.strip('/').split('/')
            if len(parts) not in (2,3) or parts[0]!='api': raise KeyError()
            entity=parts[1]
            if entity not in STORE.tables: raise KeyError()
            if self.command=='POST' and len(parts)==2:
                result=STORE.save(entity,body.get('data',{}))
            elif self.command=='PATCH' and len(parts)==3:
                result=STORE.save(entity,body.get('data',{}),parts[2],body.get('version'))
            elif self.command=='DELETE' and len(parts)==3:
                STORE.delete(entity,parts[2],body.get('version')); result={'deleted':True}
            else: raise KeyError()
            return self.respond(201 if self.command=='POST' else 200,result)
        except KeyError: return self.respond(404,{'error':'Registro o ruta inexistente.'})
        except ConflictError as e: return self.respond(409,{'error':str(e)})
        except (ValidationError,ValueError,TypeError,AttributeError): return self.respond(400,{'error':'Datos inválidos. Revisa los campos requeridos, fechas, relaciones y correo de prueba.'})

    do_POST=mutate
    do_PATCH=mutate
    do_DELETE=mutate

def main():
    if os.environ.get('HUB_MODE','demo')!='demo': raise SystemExit('Conector real no habilitado. Este ejecutable solo admite HUB_MODE=demo.')
    p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=8765); a=p.parse_args()
    http=ThreadingHTTPServer((a.host,a.port),Handler)
    print(f'UNIS laboratorio sintético: http://127.0.0.1:{a.port}',flush=True)
    http.serve_forever()

if __name__=='__main__': main()
