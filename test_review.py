#!/usr/bin/env python3
"""Behavior checks for the review model and local persistence, without paper edits."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request

HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'review-data.json').read_text())
paper=Path(data['sourceDirectory'])
before={p:hashlib.sha256((paper/p).read_bytes()).hexdigest() for p in data['sourceFiles']}
assert before==data['sourceFiles'], 'The reading view is out of date'
blocks={b['id']:b for b in data['blocks']}
assert len(blocks)==len(data['blocks'])
assert {b['source'] for b in blocks.values() if b['source'].startswith('sections/')}=={str(p.relative_to(paper)) for p in (paper/'sections').glob('*.tex')}
assert len(data['initialProposals'])==10
p=data['initialProposals'][0]
for index,proposal in enumerate(data['initialProposals']):
    assert proposal['status']==('accepted' if index<8 else 'pending') and proposal['originalHash']==blocks[proposal['blockId']]['sourceHash']
for b in blocks.values():
    assert b['sourceHash']==hashlib.sha256(b['latex'].encode()).hexdigest()
    assert b['html'].strip()
    assert b['line']>0
assert sum(b['kind']=='table' for b in blocks.values())==9
assert sum(b['kind']=='figure' for b in blocks.values())==4
assert sum(b['kind']=='reference' and not b.get('proposedOnly') for b in blocks.values())==77
assert sum(b['kind']=='reference' and b.get('proposedOnly',False) for b in blocks.values())==2

js=r'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const model=require('./review-model.js');
const data=JSON.parse(fs.readFileSync('./review-data.json','utf8'));
for (const [a,b] of [['same text','same text'],['an old paragraph','a shorter paragraph'],['','new'],['gone',''],['κ > μ and c ≥ h','κ > μ and c > h']]) {
  const result=model.diffWords(a,b);
  assert.equal(result.left.map(x=>x.text).join(''),a);
  assert.equal(result.right.map(x=>x.text).join(''),b);
}
const state={proposals:structuredClone(data.initialProposals),notes:{}};
state.proposals[0].status='needs_changes';state.notes[state.proposals[0].blockId]='Revisar el texto; conservar las referencias.';
const exp=model.exportState(data,state);
assert.equal(model.validateImport(data,exp).proposals[0].status,'needs_changes');
assert.equal(exp.proposals[0].originalLatex,data.blocks.find(b=>b.id===exp.proposals[0].blockId).latex);
assert.match(exp.proposals[0].comment,/Revisar/);
assert.throws(()=>model.validateImport(data,{...exp,sourceHash:'another-version'}));
assert.throws(()=>model.validateImport(data,{...exp,proposals:[{...exp.proposals[0],originalHash:'bad'}]}));
assert.throws(()=>model.validateImport(data,{...exp,proposals:[{...exp.proposals[0],status:'automatically_applied'}]}));
assert.throws(()=>model.validateImport(data,{...exp,notes:{missing:'comment'}}));
assert(!model.editableHtml('<script>alert(1)</script>').includes('<script>'));
console.log('JS model: diff, decisions, export/import, version guards and HTML escaping passed');
'''
subprocess.run(['node','-e',js],cwd=HERE,check=True)

spec=importlib.util.spec_from_file_location('review_server',HERE/'server.py')
server_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(server_module)
with tempfile.TemporaryDirectory(prefix='autocusum_review_test_') as directory:
    directory=Path(directory)
    for name in ('review-data.json','index.html','app.js','review-model.js','review-data.js','styles.css'):
        shutil.copy2(HERE/name,directory/name)
    server=server_module.ThreadingHTTPServer(('127.0.0.1',0),server_module.make_handler(directory))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def request(path,body=None,headers=None):
        encoded=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(base+path,data=encoded,headers=headers or {'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()
    try:
        assert request('/')[0]==200
        assert request('/app.js')[0]==200
        status,body=request('/api/review');assert status==200
        initial=json.loads(body);assert initial['proposals'][0]['status']=='accepted'
        initial['proposals'][0]['status']='needs_changes';initial['notes'][p['blockId']]='Revisar desde la interfaz'
        assert request('/api/review',initial)[0]==200
        stored=json.loads((directory/'review-state.json').read_text())
        assert stored['proposals'][0]['status']=='needs_changes'
        assert json.loads(request('/api/review')[1])['notes'][p['blockId']]=='Revisar desde la interfaz'
        bad={**initial,'sourceHash':'another-paper'};assert request('/api/review',bad)[0]==400
        assert request('/api/review',initial,{'Content-Type':'application/json','Origin':'https://different.example'})[0]==403
        assert request('/somewhere-else',initial)[0]==404
        assert json.loads((directory/'review-state.json').read_text())==stored
    finally:
        server.shutdown();server.server_close();thread.join()
assert before=={p:hashlib.sha256((paper/p).read_bytes()).hexdigest() for p in before}
print('Source coverage, HTTP persistence, invalid writes and unchanged manuscript: passed')
