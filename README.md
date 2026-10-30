# eBPF Network Observability Lab

ห้องทดลอง IPv4 TCP บน Docker สำหรับเรียนรู้การสังเกตเหตุการณ์จาก Linux kernel และการบังคับนโยบายเครือข่าย มีหน้าเว็บภาษาไทยสำหรับตั้งกฎ ส่ง HTTP และดูผล

**eBPF สังเกตเหตุการณ์, Python จัดการและแสดงผล, iptables บล็อก traffic** — ALERT หมายถึงตรงกับนโยบายพอร์ตที่ตั้งไว้ ไม่ใช่การยืนยันว่าพบผู้บุกรุก

## Architecture

```text
Browser :8765 ── HTTP API ── app.py ── docker exec ── Client container
                               │                           │
                         configure iptables          HTTP request
                                                           │
                                                     Server container
                                                     service.py → receipt

Client TCP activity → kernel kprobe/kretprobe → bpftrace → monitor.py
                                                            │
                                                   data/sensor-live.json
                                                            │
                                                app.py → Browser polling
```

`app.py` กับ `monitor.py` เป็นคนละ process สื่อสารข้อมูล sensor ผ่านไฟล์ JSON การเปิดเว็บเพียงอย่างเดียวไม่เริ่ม tracing

## Requirements

- Windows + **WSL2**, แนะนำ Ubuntu 24.04 LTS หรือ Ubuntu Linux ที่มีคุณสมบัติ kernel ครบ
- Python 3, bpftrace และ Docker Engine; Python ใช้ standard library ไม่ต้อง `pip install`
- Linux kernel ที่มี BTF (`/sys/kernel/btf/vmlinux`), cgroup v2 และ probe `tcp_v4_connect`
- รัน backend/monitor ด้วย root (`sudo`) ตามตัวอย่าง
- Docker daemon ต้องอยู่ใน Linux environment เดียวกับ monitor เพื่ออ่าน PID/cgroup ของ container ได้
- อินเทอร์เน็ตสำหรับติดตั้ง dependencies และ build image ครั้งแรก

macOS/Windows Python แบบ native และ WSL1 ไม่ใช่ environment สำหรับ tracer นี้ โค้ดใช้การสลับไบต์สำหรับแพลตฟอร์ม little-endian เช่น x86-64/ARM64 ที่ใช้ทั่วไป

## 1. Prepare WSL2

เปิด PowerShell แบบ Administrator:

```powershell
wsl --install -d Ubuntu-24.04
wsl --update
wsl -l -v
```

ทำตามคำแนะนำเพื่อ restart และตั้งผู้ใช้ Ubuntu รายการ distro ต้องแสดง VERSION `2` ถ้าติดตั้งไว้แล้วไม่ต้อง install ซ้ำ หากเป็น WSL1 ให้แปลงด้วย `wsl --set-version Ubuntu-24.04 2` โดยใช้ชื่อจริงจาก `wsl -l -v`

ดู [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install)

## 2. Install dependencies inside Ubuntu

```bash
sudo apt update
sudo apt install -y python3 git bpftrace
```

ติดตั้ง **Docker Engine ภายใน Ubuntu** ตาม [Docker Engine installation for Ubuntu](https://docs.docker.com/engine/install/ubuntu/) หัวข้อ apt repository แล้วเริ่ม daemon:

```bash
sudo systemctl start docker
sudo docker info
```

หากใช้ Docker Desktop อยู่ ให้ปิด WSL integration ของ distro ที่ใช้ lab นี้ก่อนตั้ง local Engine อย่าให้ CLI ชี้ไป daemon ของ Docker Desktop/remote host: HTTP และ firewall อาจทำงาน แต่ sensor อาจอ่าน PID/cgroup ไม่ได้

ถ้า `systemctl` แจ้งว่า systemd ไม่ทำงาน ให้ตั้ง `[boot]` / `systemd=true` ใน `/etc/wsl.conf` โดยรักษาค่าอื่นไว้ บันทึกงานใน WSL ก่อนใช้ `wsl --shutdown` จาก PowerShell แล้วเปิด Ubuntu ใหม่ ดู [WSL systemd documentation](https://learn.microsoft.com/en-us/windows/wsl/systemd)

ตรวจ prerequisites:

```bash
python3 --version
bpftrace --version
sudo docker info
ls /sys/kernel/btf/vmlinux
cat /sys/fs/cgroup/cgroup.controllers
sudo bpftrace -l 'kprobe:tcp_v4_connect'
```

ต้องพบ probe เป้าหมาย การตรวจเหล่านี้ยังไม่ยืนยันว่าโหลด tracer และจับ event จริงได้

## 3. Clone and start the backend

ใน Ubuntu terminal:

```bash
cd ~
git clone https://github.com/thanasud/eBPF_network_observability.git
cd eBPF_network_observability
sudo python3 -u app.py
```

เปิดใน browser บน Windows:

- Server controls: http://localhost:8765/server
- Client controls: http://localhost:8765/client
- Combined view: http://localhost:8765/

กด **เริ่มระบบ Docker** ในหน้า Server และรอพร้อม ครั้งแรกจะ build image และสร้าง network/container สองตัว ค่าเริ่มต้นเมื่อยังไม่มี config:

| Port | Policy | Expected behavior |
|---|---|---|
| 8000 | ALLOW | HTTP 200 และ Server receipt |
| 9000 | ALERT | HTTP 200 และ Server receipt พร้อมป้าย ALERT |
| 8080 | BLOCK | Firewall ปฏิเสธ; ไม่มี receipt ของคำขอนั้น |

Config ถูกบันทึกใน `data/config.json` และโหลดกลับเมื่อเปิด backend ครั้งต่อไป

## 4. Start the eBPF monitor

เปิด Ubuntu terminal อีกหน้าต่าง หลังจากเริ่ม Docker lab แล้ว:

```bash
cd ~/eBPF_network_observability
sudo python3 -u monitor.py
```

เส้นทางโหลดโปรแกรม:

1. `monitor.py` เรียก `app.sensor()`
2. Python หา cgroup ของ client และสร้าง `trace.bt` จากตัวแปร `program` ใน `app.py`
3. Python เรียก `bpftrace -q -B none trace.bt`
4. bpftrace คอมไพล์เป็น eBPF และจัดการโหลด/attach probes
5. `kprobe:tcp_v4_connect` เก็บพอร์ตตอนเข้าฟังก์ชัน; `kretprobe:tcp_v4_connect` ส่ง PID/พอร์ต/return ตอนคืนค่า

**เวอร์ชันนี้ใช้ BEGIN/READY ตั้งสถานะ live ซึ่งไม่ใช่ self-test การจับ TCP** ต้องส่งคำขอแล้วตรวจว่ามี event ใหม่ใน CLI และตาราง kernel events ด้วย หน้าเว็บ poll ทุก 2 วินาที

`trace.bt` และ `btf-only/include/linux/kconfig.h` สร้างตอนรันและไม่เก็บใน Git หากจะแก้ tracer ให้แก้ตัวแปร `program` ใน `app.py` เพราะไฟล์ `.bt` จะถูกเขียนทับ ส่วน `kconfig.h` เป็น placeholder ไม่ใช่ kernel headers ทั้งชุด และไม่รับรองว่าจะทดแทน headers ได้กับ bpftrace ทุกเวอร์ชัน

## 5. Demonstrate the three policies

ส่งทีละคำขอจากหน้า Client แล้วดูทั้งหน้า Server และ monitor:

1. ส่งพอร์ต **8000**: ALLOW, HTTP 200, receipt และ kernel event
2. ส่งพอร์ต **9000**: ALERT แต่ HTTP ยังผ่าน พร้อม kernel event
3. ส่งพอร์ต **8080**: BLOCK, ไม่มี receipt และมีหลักฐาน counter เปลี่ยน พร้อม kernel event ของความพยายาม connect
4. เปลี่ยน 8080 เป็น ALLOW ในหน้า Server บันทึกและส่งซ้ำเพื่อแสดงการเปลี่ยนนโยบาย

Server เปิด listener ทุกพอร์ตใน config รวมถึง BLOCK จึงใช้แสดงว่าการปฏิเสธเกิดจาก firewall ฝั่ง Client ไม่ใช่การปิดบริการปลายทาง

`kernel_return=0` ไม่ได้แปลว่า HTTP สำเร็จ และ eBPF event ไม่ได้บอกว่าเป็นการโจมตี ค่า `ms` รวมงานควบคุมบางส่วนของ Docker/counter ไม่ใช่ network latency ล้วน

## 6. Run the integration check

ก่อนทดสอบ ให้ตั้ง 8000=ALLOW, 9000=ALERT, 8080=BLOCK; backend และ monitor ต้องเปิดอยู่ จากนั้นใน terminal ที่สาม:

```bash
cd ~/eBPF_network_observability
python3 verify_ui.py
```

สคริปต์ตรวจ HTTP/receipt, เปลี่ยนกฎของพอร์ต 8123, ลบและเพิ่ม listener, ปฏิเสธพอร์ตซ้ำ และตรวจรายการพอร์ตใน eBPF events ผลบันทึกที่ `data/verified-state.json`

**ข้อควรทราบ:** สคริปต์เปลี่ยนกฎจริงและคืนเป็นสามกฎ default ไม่ได้คืน custom config เดิมเสมอ ตรวจ eBPF จากรายการสะสม ไม่ได้จับคู่ event ใหม่กับ HTTP request ID จึงควรเปิด monitor ใหม่ก่อนทดสอบและงด traffic อื่น ผลผ่านไม่ใช่หลักฐานการตรวจจับ intrusion หรือ benchmark

## Optional PowerShell launchers

ไฟล์ `start.ps1` และ `monitor.ps1` เดิม hardcode ชื่อ distro เป็น `Ubuntu` ใช้ได้เมื่อ clone อยู่บน Windows และเปิด PowerShell ในโฟลเดอร์นั้น:

```powershell
.\start.ps1
# Separate PowerShell window:
.\monitor.ps1
```

หาก distro ชื่อ `Ubuntu-24.04` ให้แก้ `-d Ubuntu` เป็น `-d Ubuntu-24.04` ในทั้งสองไฟล์ หรือใช้ Ubuntu terminals ตามขั้นตอนหลัก อย่าเปิด app กับ monitor จากคนละสำเนาโฟลเดอร์

## Stop and restart

- Ctrl+C ใน monitor: หยุด bpftrace/ถอน probes แต่ firewall และ container ยังอยู่
- Ctrl+C ใน backend: ปิดเว็บ แต่ container ยังอยู่
- หยุด container ของ lab:

```bash
sudo docker stop codex-network-lab-client codex-network-lab-server
```

เมื่อเริ่มใหม่ กดเริ่มระบบผ่านเว็บ แล้วเปิด monitor ใหม่เสมอหลัง restart/recreate Client เพราะ cgroup อาจเปลี่ยน

หากย้ายโฟลเดอร์แล้วพบ server mount mismatch ให้ตรวจว่าทรัพยากรเป็นของ lab ก่อน:

```bash
sudo docker inspect --format '{{json .Config.Labels}}' codex-network-lab-server
sudo docker inspect --format '{{json .Mounts}}' codex-network-lab-server
```

เมื่อยืนยัน label `codex.network-lab=v1` แล้ว จึงลบเฉพาะ container ของ lab ที่ต้องสร้างใหม่ (คำสั่งนี้ลบ container; log/config ใน bind-mounted data ยังคงอยู่):

```bash
sudo docker rm -f codex-network-lab-client codex-network-lab-server
```

กดเริ่มระบบอีกครั้งและ restart monitor ไม่จำเป็นต้อง prune Docker ทั้งเครื่อง

## Troubleshooting

| Symptom | Check / action |
|---|---|
| Docker daemon unavailable | ตรวจ `sudo docker info` และเริ่ม local Engine |
| Sensor unavailable / `/proc/<pid>` missing | ตรวจว่า daemon อยู่ใน Ubuntu เดียวกับ monitor ไม่ใช่ Docker Desktop/remote |
| Missing BTF or kprobe | อัปเดต WSL/kernel และตรวจ prerequisites; อย่าใช้ log เก่าแทนผลจริง |
| Kernel headers error | placeholder/BTF ไม่พอกับ environment นี้ อาจต้องใช้ headers ที่ตรงกับ kernel; Ubuntu generic headers ไม่จำเป็นต้องตรง WSL kernel |
| `live` แต่ไม่มี event | ส่งคำขอใหม่ ตรวจ CLI errors และ restart monitor หลัง Client เปลี่ยน |
| `Monitor already running` | ใช้ terminal monitor เดิม หรือหยุดตัวเดิมก่อนเปิดใหม่ |
| Port 8765 already in use | หยุด backend เดิมก่อน ไม่เปิด app.py ซ้ำ |
| `ERROR` แทน BLOCK | อาจไม่มี listener/บริการยังไม่พร้อม/เชื่อมต่อผิดพลาด ไม่ใช่หลักฐาน firewall เสมอ |
| `Reload this page` | Reload หลัง restart backend เพราะ token เปลี่ยน |
| Rule update failed | ตรวจ Docker แล้วกดเริ่มระบบใหม่; rollback เดิมคืนเฉพาะ Python state ไม่ได้ทำ firewall transaction |

## Source map

| File | Responsibility |
|---|---|
| `app.py` | API, Docker lifecycle, firewall, HTTP result verification, bpftrace source/loader |
| `monitor.py` | CLI sensor lifecycle, policy annotations, file-based heartbeat |
| `service.py` | Dynamic HTTP listeners and request receipts inside Server |
| `index.html` | Thai UI; `/client` and `/server` are views, not authorization roles |
| `verify_ui.py` | Live integration test with policy mutations |
| `Dockerfile` | Python/iptables image |

Runtime artifacts live in `data/` (ignored by Git): `config.json`, `events.jsonl`, `received.jsonl`, `sensor-live.json`, `monitor.lock`, `verified-state.json`.

## Scope and limitations

- Observes IPv4 TCP attempts from one selected client cgroup; no IPv6, UDP, DNS parsing or Windows-wide tracing.
- No XDP filtering or automatic intrusion detection. BLOCK uses preconfigured iptables rules, independently of sensor events.
- BLOCK rules match destination port without restricting destination IP.
- Counter comparison is chain-wide; concurrent traffic can make attribution ambiguous.
- The monitor timestamps userspace receipt and annotates using current policy, not a kernel-time policy snapshot.
- Only the latest 100 kernel events are retained for display. No event-loss or high-load guarantee.
- Backend binds localhost and uses a per-process request token, not multi-user authentication. Intended as a local teaching lab.
- WSL2/kernel/bpftrace compatibility must be verified on the target machine. Syntax checks on macOS do not establish live eBPF functionality.

## Research context

D. Soldani et al., “eBPF: A New Approach to Cloud-Native Observability, Networking and Security for Current (5G) and Future Mobile Networks (6G and Beyond),” *IEEE Access*, vol. 11, pp. 57174–57202, 2023. [doi:10.1109/ACCESS.2023.3281480](https://doi.org/10.1109/ACCESS.2023.3281480).

ต้นแบบประยุกต์แนวคิด kernel observability และ runtime security ไม่ได้ทำซ้ำแพลตฟอร์ม Sauron ทั้งระบบหรือผล benchmark ของบทความ

เอกสารเดิมเพิ่มเติม: [README-TH.md](README-TH.md). ใช้ขั้นตอน README นี้เป็นหลักสำหรับการ clone ใหม่; path ของเครื่องเดิมในเอกสารเก่าเป็นเพียงตัวอย่าง
