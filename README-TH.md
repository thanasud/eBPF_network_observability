# Network Lab — UI เดโมจริง

เปิด http://localhost:8765 ในเบราว์เซอร์ หน้านี้รันบนเครื่องผู้ใช้ ไม่ได้ deploy ขึ้นอินเทอร์เน็ต

## เริ่มครั้งต่อไป

เปิด PowerShell ในโฟลเดอร์นี้แล้วรัน `./start.ps1` หรือใน Ubuntu WSL:

```bash
cd /mnt/c/Users/fam17/Downloads/eBPF
sudo python3 app.py
```

เปิดเว็บแล้วกด **เริ่มระบบ Docker** รอพร้อมทดสอบ ต้องมี Docker daemon และ bpftrace ใน Ubuntu หากใช้ Docker Desktop ตัว HTTP/firewall ยังใช้ได้ แต่ sensor อาจไม่สามารถอ่าน cgroup/PID ของ Docker host ได้ หน้าเว็บจะแสดง unavailable ตามจริง

## ลำดับนำเสนอ

1. ฝั่ง Server เพิ่ม/ลบพอร์ตได้ 1–12 พอร์ต ช่วง 1024–65535 ห้ามซ้ำ แล้วเลือก ALLOW, ALERT หรือ BLOCK
2. กด **ใช้การตั้งค่า** รอให้เสร็จก่อนส่ง การเปลี่ยนนี้เปิด/ปิด HTTP listener และเปลี่ยน iptables จริง
3. ฝั่ง Client เลือกพอร์ต แล้วกด **ส่ง request**
4. ดูผล Client และตาราง Server activity: ALLOW และ ALERT ต้องได้ HTTP 200 และ receipt จาก server; BLOCK ต้องล้มเหลวและ counter ของกฎเพิ่ม
5. ดู Kernel events ซึ่งมาจาก bpftrace จริง แยกจากผล HTTP

ค่าเริ่มต้น: 8000 ALLOW / 9000 ALERT / 8080 BLOCK

BLOCK คือปฏิเสธที่ client namespace ก่อนถึง server ดังนั้น server จะไม่ได้รับ request; แถว BLOCK ในตารางเป็นข้อมูลของ controller ไม่ใช่ server access log ส่วน ALERT ส่งผ่านและแจ้งเตือนใน UI ไม่ได้ส่งข้อความออกภายนอก

## การทำงาน

- index.html: หน้าจอภาษาไทย สองฝั่ง พร้อมประวัติและ kernel events
- app.py: API บน 127.0.0.1:8765, สั่ง Docker, เปลี่ยนกฎ และอ่าน bpftrace
- service.py: HTTP server หลายพอร์ตใน server container ติดตาม config.json และบันทึก receipt จริง
- Dockerfile: Python + iptables ใช้กับ client/server และ helper ชั่วคราว
- trace.bt: สร้างใหม่ตอนเริ่ม sensor กรอง cgroup ของ client เท่านั้น อ่าน port ที่ entry ของ tcp_v4_connect และ return value ตอนออก
- data/events.jsonl: ประวัติการทดลอง; received.jsonl: หลักฐาน server ได้รับ request; verified-state.json: ผลตรวจครั้งล่าสุด
- verify_ui.py: ทดสอบ API จริงครบสามสถานะ เพิ่มพอร์ต เปลี่ยนกฎ ลบและเพิ่มพอร์ตเดิม และตรวจ kernel events

## ขอบเขตและข้อจำกัด

เดโม IPv4 TCP เท่านั้น ใช้ network internal แยก ชื่อ codex-network-lab และ containers codex-network-lab-client/server ไม่มี published service ports พอร์ต UI เปิดเฉพาะ loopback การแก้กฎใช้ helper ที่มี NET_ADMIN เฉพาะ client network namespace ไม่มีการเปลี่ยน Windows Firewall

eBPF ใช้ตรวจจับ ส่วน enforcement ใช้ iptables; Python กำหนด ALLOW/ALERT จาก policy ผล HTTP และ receipt กรณี BLOCK ใช้หลักฐาน counter เปลี่ยนประกอบ ไม่อ้างว่า Python เป็น eBPF หรือใช้ eBPF บล็อก

การแก้กฎถูก serialize กับ request ใน UI แต่ไม่ได้เป็น atomic firewall update สำหรับ traffic ที่สร้างจากภายนอก UI ห้ามใช้เป็น firewall production ผู้ใช้ต้องกดเริ่มระบบใหม่หลัง restart client เพื่อใส่กฎและจับ cgroup ใหม่

Kernel events มี timestamp ตอน userspace รับข้อมูล ไม่ใช่ kernel timestamp และไม่มี request ID จึงเทียบตามเวลา/พอร์ตได้เท่านั้น ไม่รับประกันการจับคู่หนึ่งต่อหนึ่งในระบบที่มี traffic พร้อมกัน ค่า return 0 ไม่ยืนยัน TCP handshake หรือ HTTP สำเร็จ

ประวัติบนหน้าเว็บและ draft configuration เป็น session ของ backend; รีสตาร์ท backend แล้วกดเริ่มระบบจะใช้ค่าเริ่มต้น ไฟล์ log เดิมยังเก็บไว้ ไม่มี rotation; UI แสดงล่าสุด 100 requests/15 kernel events

หยุด UI ด้วย Ctrl+C ในหน้าต่างที่รัน app.py Containers ยังอยู่; หากต้องล้างชุดนี้ให้หยุด UI และตรวจชื่อ/label ก่อนใช้ `docker rm -f codex-network-lab-client codex-network-lab-server` แล้ว `docker network rm codex-network-lab` กฎหายไปพร้อม namespace ของ client

## รูปแบบนำเสนอใหม่: CLI + Server UI + Client UI
1. เปิด backend ด้วย sudo python3 app.py
2. เปิด http://localhost:8765/server แล้วกดเริ่มระบบ ตั้งพอร์ตและกฎ
3. เปิด Ubuntu WSL อีกหน้าต่าง cd มาที่โฟลเดอร์เดียวกัน แล้วรัน sudo python3 -u monitor.py ทิ้งไว้ รอ SENSOR: live
4. เปิด http://localhost:8765/client กรอกหมายเลขพอร์ตเอง ก่อนกดส่งจะไม่แสดงนโยบายหรือผลลัพธ์
5. หลังส่ง: ALLOW = ผ่าน, ALERT = ผ่านพร้อมเตือน, BLOCK = ไม่ถึง server เพราะ firewall, ERROR = ติดต่อบริการไม่สำเร็จโดยยังยืนยันว่าโดนบล็อกไม่ได้ รวมถึงพอร์ตที่ไม่ได้เปิดรับ

monitor.py เป็น process แยกจากเว็บ รับ event จาก eBPF จริงและแสดง CLI; frontend อ่าน sensor-live.json เพื่อบอกสถานะเท่านั้น ตัวตรวจจับไม่จำเป็นต่อการบังคับกฎ iptables หยุด monitor ด้วย Ctrl+C เพื่อถอด probes กฎ firewall ยังอยู่ ห้ามเปิด monitor ซ้ำ ถ้า recreate/restart client ให้หยุดแล้วเปิด monitor ใหม่ cgroup ID จะถูกอ่านใหม่

หน้า Client ซ่อนกฎเพื่อการสาธิต ไม่ใช่ระบบแยกสิทธิ์ ผู้ใช้เครื่องเดียวกันยังเปิดหน้า Server/API ได้ Backend เก็บ configuration เดิมข้ามการ restart แล้ว การตั้งค่าจากไฟล์เดิมต้องกดเริ่มระบบเพื่อใช้จริง

## ย้ายโฟลเดอร์เดโม

ไฟล์ชุดนี้เป็นสำเนา โค้ดต้นฉบับยังอยู่ที่เดิม หาก server container เดิมยังผูกโฟลเดอร์เดิมอยู่ อย่าเพิ่งลบ container ที่มีอยู่: สำเนานี้จะเตือนเมื่อกดเริ่มระบบ ให้หยุดแอปเดิม แล้วตรวจข้อมูล/label ก่อนลบเฉพาะ container เดโมสองตัวตามคำสั่งในคู่มือ จากนั้นเริ่มแอปในโฟลเดอร์นี้และกดเริ่มระบบเพื่อสร้าง container ใหม่ โดย config และ log เก่าถูกคัดลอกไว้ใน data; trace.bt ถูกสร้างใหม่เมื่อ monitor เริ่ม จึงไม่ควรใช้ cgroup ID เก่าโดยตรง
