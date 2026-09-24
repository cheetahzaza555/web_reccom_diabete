# เตรียม GraphDB และ .env.deploy

## ทำให้แล้ว

- สร้าง `.env.deploy` โดยไม่แก้ `.env` เดิม สร้าง SECRET_KEY และ JWT_SECRET_KEY ใหม่แยกกัน
- คัดลอกค่า Gemini, LINE และอีเมลจาก `.env` เดิม การมีค่าไม่ได้ยืนยันว่า token ยังใช้ได้
- ตรวจเวอร์ชันต้นทางผ่าน API ได้ `11.4.2` ตั้ง image เป็น `ontotext/graphdb:11.4.2`
- สำรอง explicit statements ทุก graph เป็น `backups/graphdb-20260923T163304723280Z/data.trig`
- อ่านไฟล์ TriG กลับด้วย RDFLib ผ่าน: 10,136 quads ขนาด 1,091,163 bytes
- เก็บเวอร์ชัน เวลา และ SHA-256 ใน `manifest.json` ข้างไฟล์สำรอง
- ตรวจว่า `.env.deploy` และ `backups/` ถูก ignore โดย Git และไม่เข้า Docker build context

ยังไม่ได้เปิด GraphDB container หรือ import ข้อมูล สำเนานี้ยังไม่ใช่การยืนยันว่า restore สำเร็จ
SITE_DOMAIN ยังว่างเพราะยังไม่มีโดเมน ไม่จำเป็นสำหรับการทดลองบนคอม

## สิ่งที่ต้องทำต่อ

1. เปิด Workbench ของ GraphDB เดิม ไปที่ Setup → Repositories แล้ว export/download configuration ของ repository ที่ใช้งาน
   เก็บเป็น `repository-config.ttl` ในโฟลเดอร์สำรองข้าง `data.trig`
   ชื่อเมนูอาจต่างตามรุ่น; จด repository ID, ruleset และตัวเลือกเพิ่มเติมไว้ด้วย
   การอ่าน configuration อัตโนมัติครั้งนี้ตอบ HTTP 406 จึงยังไม่มีไฟล์ configuration
2. ตรวจ edition และ licence ใน Workbench ว่าอนุญาตให้ใช้งานบนเครื่องใหม่
   ไฟล์ TriG ไม่รวม licence, บัญชีผู้ดูแล GraphDB หรือ server settings
3. สำเนาโฟลเดอร์ backup ไปไว้นอกเครื่องอีกแห่ง เพราะไฟล์มีข้อมูลผู้ป่วยและข้อมูลบัญชีของแอป
4. ตรวจว่าพอร์ต 7200 ไม่ชน GraphDB เดิม หากชนให้เปลี่ยนเฉพาะ host port ใน compose.yaml
   จาก `127.0.0.1:7200:7200` เป็น `127.0.0.1:7201:7200` แล้วใช้ localhost:7201
5. จากโฟลเดอร์ back_end รันเมื่อพร้อมทดลอง:

```powershell
docker compose --env-file .env.deploy config --quiet
docker compose --env-file .env.deploy pull graphdb
docker compose --env-file .env.deploy up -d graphdb
docker compose --env-file .env.deploy logs --tail 80 graphdb
```

การ pull จะตรวจด้วยว่าเข้าถึง image tag ได้จริง เครื่องปลายทางต้องรองรับสถาปัตยกรรมของ image

6. เปิด http://localhost:7200 ไป Setup → Repositories → สร้าง repository จาก configuration ที่ export
   ตรวจ ID ให้ตรง GRAPHDB_REPO ใน `.env.deploy` หากใช้ licence ให้ติดตั้งตามข้อกำหนดของรุ่นนั้นก่อน
7. เลือก repository ใหม่ที่ว่าง ไป Import → Upload RDF files แล้วเลือก `data.trig`
   รักษา named graphs จากไฟล์ ไม่กำหนดให้ทุกข้อมูลไปรวมใน graph เดียว รอ import สำเร็จ
   อย่า import ซ้ำลงฐานข้อมูลที่มีข้อมูลแล้ว โดยเฉพาะข้อมูล blank nodes
8. เปิดเว็บและเช็กความพร้อม:

```powershell
docker compose --env-file .env.deploy up -d --build web proxy
docker compose --env-file .env.deploy ps
```

เปิด http://localhost:8000/readyz แล้วทดสอบล็อกอิน จำนวนผู้ป่วย กฎ แผน และผลแนะนำเทียบต้นทาง
จำนวน inferred statements อาจมากกว่าข้อมูล explicit ในไฟล์ จึงต้องเปรียบเทียบชนิดเดียวกัน
ทดสอบ restart container แล้วตรวจว่าข้อมูลยังอยู่ใน volume ด้วย
ยังไม่เปิด profile jobs ระหว่างทดลอง เพื่อไม่ส่ง LINE หรือเลื่อนแผนซ้ำกับระบบเดิม

## สำรองใหม่ก่อนย้ายจริง

หยุดการแก้ข้อมูลและงาน scheduler ต้นทางในช่วงสำรองรอบสุดท้าย แล้วรัน:

```powershell
python deploy/export_graphdb.py
```

สคริปต์อ่านต้นทางจาก `.env` และสร้างโฟลเดอร์ใหม่ตามเวลา ไม่ลบหรือเขียนฐานข้อมูลต้นทาง
สำรอง configuration ใหม่ด้วยถ้ามีการเปลี่ยนค่า สคริปต์ยังไม่รองรับ GraphDB ที่ต้องล็อกอิน
หากสคริปต์รายงานไม่สำเร็จ ห้ามใช้ไฟล์ `.partial` สำหรับ import
ห้ามใช้ `docker compose down -v` กับข้อมูลที่ต้องการเก็บ เพราะจะลบ volume

อ้างอิง: [GraphDB export/restore](https://graphdb.ontotext.com/documentation/10.0/backing-up-and-recovering-repo.html)
และ [official Docker images](https://hub.docker.com/r/ontotext/graphdb/tags)
