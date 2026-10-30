# Demo HTTP target running inside the server container.
import http.server, json, pathlib, threading, time
ROOT=pathlib.Path('/data')
servers={}
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # The URL path contains the request ID used by app.py to verify delivery.
        event={'time':time.time(),'port':self.server.server_port,'path':self.path,'source':self.client_address[0]}
        with (ROOT/'received.jsonl').open('a') as f: f.write(json.dumps(event)+'\n')
        body=json.dumps({'message':'Request reached the server','port':self.server.server_port}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args): pass
while True:
    try:
        # Listen even on BLOCK ports: the client firewall, not this server, enforces policy.
        ports={r['port'] for r in json.loads((ROOT/'config.json').read_text())}
        for p in list(servers):
            if p not in ports:
                old=servers.pop(p);old.shutdown();old.server_close()
        for p in ports-set(servers):
            s=http.server.ThreadingHTTPServer(('0.0.0.0',p),Handler);s.daemon_threads=True
            servers[p]=s;threading.Thread(target=s.serve_forever,daemon=True).start()
    except Exception as e: print(str(e),flush=True)
    time.sleep(.3)
