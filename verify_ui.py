# Integration test: requires a running backend, initialized lab and CLI monitor.
# Mutates live rules and restores defaults, not the user's previous configuration.
import urllib.request,json,re,time,pathlib
BASE='http://127.0.0.1:8765'
token=re.search("const token='([^']+)'",urllib.request.urlopen(BASE).read().decode()).group(1)
def post(path,data):
    r=urllib.request.Request(BASE+'/api/'+path,data=json.dumps(data).encode(),headers={'X-Lab-Token':token,'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(r,timeout=180))
default=[{'port':8000,'policy':'ALLOW'},{'port':9000,'policy':'ALERT'},{'port':8080,'policy':'BLOCK'}]
for port,expected in [(8000,'ALLOW'),(9000,'ALERT'),(8080,'BLOCK')]:
    r=post('send',{'port':port});assert r['status']==expected,r
    assert r['received']==(expected!='BLOCK'),r
    print('PASS real HTTP + receipt:',port,expected,flush=True)
try:
    for status in ['ALLOW','BLOCK','ALERT']:
        post('rules',{'rules':default+[{'port':8123,'policy':status}]})
        r=post('send',{'port':8123});assert r['status']==status,r
        print('PASS dynamic port 8123:',status,flush=True)
    post('rules',{'rules':default})
    post('rules',{'rules':default+[{'port':8123,'policy':'ALLOW'}]})
    assert post('send',{'port':8123})['status']=='ALLOW'
    print('PASS remove/re-add listener',flush=True)
finally:post('rules',{'rules':default})
try:
    post('rules',{'rules':[{'port':8000,'policy':'ALLOW'},{'port':8000,'policy':'BLOCK'}]})
    raise AssertionError('Duplicate port accepted')
except urllib.error.HTTPError as e:assert e.code==400
print('PASS duplicate port rejected',flush=True)
time.sleep(1)
state=json.load(urllib.request.urlopen(BASE+'/api/state'))
assert state['sensor'].startswith('live'),state['sensor']
# Historical events can satisfy this check; it is not per-request eBPF correlation.
assert {8000,8080,9000,8123}<={e['port'] for e in state['ebpf']}
print('PASS real eBPF events for every tested port',flush=True)
(pathlib.Path(__file__).parent/'data/verified-state.json').write_text(json.dumps(state,indent=2))
