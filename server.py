#!/usr/bin/env python3
"""Optional local server: saves review decisions, never edits LaTeX files."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent


def make_handler(directory):
    directory=Path(directory).resolve()
    data=json.loads((directory/'review-data.json').read_text())
    blocks={b['id']:b for b in data['blocks']}
    lock=Lock()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(directory),**kwargs)

        def send_json(self,value,status=200):
            body=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            if urlparse(self.path).path=='/api/review':
                path=directory/'review-state.json'
                with lock:
                    state=json.loads(path.read_text()) if path.exists() else dict(version=1,paperId=data['paperId'],sourceHash=data['sourceHash'],proposals=data['initialProposals'],notes={})
                self.send_json(state);return
            super().do_GET()

        def do_POST(self):
            if urlparse(self.path).path!='/api/review': self.send_json({'error':'Not found'},404);return
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):
                self.send_json({'error':'Origin mismatch'},403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=2_000_000:raise ValueError('Invalid body size')
                state=json.loads(self.rfile.read(size))
                if state.get('version')!=1 or state.get('paperId')!=data['paperId'] or state.get('sourceHash')!=data['sourceHash']:
                    raise ValueError('Paper version mismatch')
                proposals=state.get('proposals');notes=state.get('notes',{})
                if not isinstance(proposals,list) or len(proposals)>len(blocks):raise ValueError('Invalid proposals')
                seen=set()
                for p in proposals:
                    b=blocks.get(p.get('blockId'))
                    if not b or p.get('originalHash')!=b['sourceHash'] or p['blockId'] in seen:raise ValueError('Block mismatch')
                    if p.get('status') not in ('pending','accepted','rejected','needs_changes'):raise ValueError('Invalid decision')
                    if not isinstance(p.get('proposedLatex'),str) or len(p['proposedLatex'])>50000 or not isinstance(p.get('reason'),str):raise ValueError('Invalid proposal text')
                    seen.add(p['blockId'])
                if not isinstance(notes,dict) or any(k not in blocks or not isinstance(v,str) or len(v)>50000 for k,v in notes.items()):raise ValueError('Invalid notes')
                with lock:
                    tmp=directory/'review-state.json.tmp'
                    tmp.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
                    tmp.replace(directory/'review-state.json')
                self.send_json({'saved':True,'file':'review-state.json'})
            except (ValueError,TypeError,KeyError,AttributeError) as error:
                self.send_json({'error':str(error)},400)

    return Handler


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--directory',type=Path,default=HERE)
    args=parser.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),make_handler(args.directory))
    print(f'Paper review: http://{args.host}:{server.server_port}',flush=True)
    print(f'Decisiones: {args.directory.resolve() / "review-state.json"}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
