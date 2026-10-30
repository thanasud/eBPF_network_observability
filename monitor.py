"""Run in Ubuntu WSL: sudo python3 -u monitor.py. Ctrl+C detaches eBPF."""
# Import shares functions, not memory with the separately running web backend.
import app,datetime,fcntl,json,signal,time
# Prevent competing writers to sensor-live.json.
lock=(app.DATA/'monitor.lock').open('w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Monitor already running. Use its CLI window.')
print('eBPF TCP CONNECT MONITOR — client container only',flush=True)
print('Kernel return is not HTTP success. Policy labels are Python annotations.',flush=True)
app.sensor()
seen=set();last=None
try:
    while True:
        if app.state['sensor']!=last:
            last=app.state['sensor'];print('SENSOR:',last,flush=True)
        for e in reversed(list(app.state['ebpf'])):
            key=(e['time'],e['pid'],e['port'])
            if key in seen:continue
            seen.add(key)
            # Policy is read at display time and does not originate from the eBPF program.
            try:rules=json.loads((app.DATA/'config.json').read_text())
            except (OSError,ValueError):rules=[]
            policy=next((r['policy'] for r in rules if r['port']==e['port']),'UNCONFIGURED')
            stamp=datetime.datetime.fromtimestamp(e['time']).strftime('%H:%M:%S')
            print(f"{stamp} TCP_CONNECT pid={e['pid']} cgroup={e['cgroup']} port={e['port']} kernel_return={e['return']} policy={policy}",flush=True)
        # Atomic snapshot is the IPC contract consumed by GET /api/state.
        temp=app.DATA/'sensor-live.tmp'
        temp.write_text(json.dumps({'heartbeat':time.time(),'sensor':app.state['sensor'],'events':list(app.state['ebpf'])}))
        temp.replace(app.DATA/'sensor-live.json')
        if app.traceproc is None or app.traceproc.poll() is not None:break
        time.sleep(.3)
except KeyboardInterrupt:pass
finally:
    # Stop tracing on exit; firewall rules and containers remain active.
    if app.traceproc and app.traceproc.poll() is None:
        app.traceproc.send_signal(signal.SIGINT);app.traceproc.wait(timeout=10)
    (app.DATA/'sensor-live.json').write_text(json.dumps({'heartbeat':0,'sensor':'offline','events':[]}))
    print('Monitor stopped; probes detached.',flush=True)
