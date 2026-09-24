# Deploy DiaBalance ทีละขั้น

ชุดนี้ยังไม่ได้ขึ้นออนไลน์ ต้องติดตั้ง Docker Desktop (Linux containers/WSL 2) ก่อน
คำสั่งทั้งหมดเริ่มจากโฟลเดอร์ back_end

## 1. ตั้งค่า

**สถานะล่าสุด:** เตรียม `.env.deploy` แล้ว พร้อม secret keys ใหม่และค่าบริการจาก `.env`
ตรวจ GraphDB ต้นทางได้เวอร์ชัน `11.4.2` และกำหนด `GRAPHDB_IMAGE=ontotext/graphdb:11.4.2`
ยังเว้น `SITE_DOMAIN` ไว้จนกว่าจะมีโดเมน ขั้นตอน Copy-Item ด้านล่างใช้เฉพาะตอนยังไม่มีไฟล์
อ่านขั้นตอนต่อที่ [เตรียม GraphDB](graphdb-preparation.md)

```powershell
Copy-Item .env.deploy.example .env.deploy
python -c "import secrets; print(secrets.token_hex(32))"
```

นำค่าที่สร้างใส่ SECRET_KEY และสร้างอีกครั้งสำหรับ JWT_SECRET_KEY
อย่าสั่ง Copy-Item ซ้ำทับไฟล์ที่กรอกแล้ว ไม่ต้องแก้ .env เดิม

- GRAPHDB_IMAGE: image/tag ทางการที่ตรงรุ่นและ edition ฐานข้อมูลเดิม ตรวจ tag ที่มีจริงก่อน
  `ontotext/graphdb:11.0.1` เป็นเพียงตัวอย่างรูปแบบ ห้ามลดฐานข้อมูลรุ่น 12 ไป 11
  ตรวจสิทธิ์ licence ด้วย ถ้าใช้เครื่อง ARM ต้องตรวจว่า image รองรับก่อน
- GRAPHDB_REPO: ชื่อ repository เดิม เช่น Project
- GEMINI_API_KEY: สำหรับ OCR ตรวจ quota แยกจากค่าเซิร์ฟเวอร์
- LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET: ไม่กรอกก็เปิดเว็บได้ แต่ webhook จะไม่ถูกเปิด
- sender_email / app_password: สำหรับส่ง OTP ต้องตั้งค่านี้จึงสมัครสมาชิกได้
- SITE_DOMAIN: ชื่อเว็บจริงสำหรับ production ไม่ใส่ https:// หรือ path

ห้าม commit .env.deploy หรือ backup ข้อมูลผู้ป่วย

## 2. ย้ายฐานข้อมูล

GraphDB ใน Docker เป็นฐานข้อมูลใหม่ ไม่ได้ย้ายข้อมูลจากเครื่อง 26.x ให้อัตโนมัติ

1. บันทึก version/edition, repository ID, ruleset ของ GraphDB เดิม
2. Export repository configuration และข้อมูล explicit **ทุก graph** เป็น TriG ผ่าน Workbench
   ไม่ใช่ export เฉพาะกฎหรือผล query หากใช้ระบบ backup ให้ทำตาม restore ของรุ่นเดียวกัน
3. เก็บใน backups/ และสำเนานอกเครื่อง หยุดการแก้ข้อมูลต้นทางก่อน export รอบสุดท้าย
4. เปิด GraphDB ใหม่:

```powershell
docker compose --env-file .env.deploy up -d graphdb
```

เปิด http://localhost:7200 สร้าง repository ด้วย configuration/ruleset เดิม และ import TriG
ถ้าพอร์ตชน GraphDB เดิม ให้หยุดตัวเดิมก่อน หรือเปลี่ยนพอร์ตด้านซ้ายเป็น
`127.0.0.1:7201:7200` แล้วเปิด localhost:7201 ไม่ต้องแก้ URL ภายใน web
เทียบจำนวนกฎ ผู้ใช้ และแผนกับต้นทาง ยังไม่เปิด scheduler

## 3. ทดลองเว็บบนคอม

ตอนนี้ localhost:8000 เข้า Caddy ก่อนส่งต่อไป web:8000 ภายใน Docker
เพื่อให้ connection ที่เบราว์เซอร์เปิดรอไม่ขวาง Gunicorn sync worker
web ไม่เปิด host port โดยตรง และ TRUST_PROXY=1 รับ forwarded headers จาก Caddy
production override เปลี่ยนพอร์ต proxy เป็น 80/443 ด้วย !override (ต้องใช้ Docker Compose 2.24.4 ขึ้นไป)
การประมวลผลกฎที่ใช้เวลานานยังใช้ worker เดียว จึงยังอาจทำให้คำขออื่นรอได้

```powershell
docker compose --env-file .env.deploy up -d --build web proxy
docker compose --env-file .env.deploy ps
docker compose --env-file .env.deploy logs --tail 100 web
```

เปิด http://localhost:8000 และ /readyz
ready หมายถึงอ่าน repository ที่มีข้อมูลได้ ไม่ใช่การรับรองว่าทุกฟังก์ชันถูกต้อง
ทดสอบล็อกอิน OTP OCR ประมวลผลกฎด้วย Java/Pellet เลือกหลายท่า แก้แผน ทำเสร็จและ streak
ใช้ sync worker เดียวเพื่อไม่ให้ shared SPARQL client ชนกัน เหมาะเริ่มเดโมคนจำนวนน้อย
ต้องวัดเวลาและ RAM ก่อนเพิ่ม worker; Pellet อาจใช้เวลาประมวลผลนาน

## 4. เซิร์ฟเวอร์และ HTTPS

ติดตั้ง Docker Engine/Compose บน Linux นำโค้ดกับ .env.deploy ขึ้นเครื่อง
ตั้ง DNS ของ SITE_DOMAIN ชี้ IP เซิร์ฟเวอร์ เปิดพอร์ต 80/443
7200/8000 ถูกผูกกับ localhost ไม่เปิดสู่ภายนอก
เข้า GraphDB ปลายทางผ่าน SSH tunnel จากคอม:

```text
ssh -L 7200:127.0.0.1:7200 your-user@your-server
```

สร้าง/import ฐานข้อมูลบนเซิร์ฟเวอร์ตามข้อ 2 แล้วรัน:

```text
docker compose --env-file .env.deploy -f compose.yaml -f compose.production.yaml up -d --build
```

Caddy จัดการ HTTPS เมื่อ DNS/พอร์ตพร้อม production ใช้ Secure cookie ต้องเข้าผ่าน HTTPS
ตั้ง LINE webhook เป็น https://ชื่อเว็บ/line/callback แล้วกด Verify

## 5. เปิด scheduler หลังทดสอบพร้อมแล้ว

ปิด scheduler ต้นทางก่อนเพื่อไม่เลื่อนแผน/ส่ง LINE ซ้ำ ใช้เพียงหนึ่ง instance ห้าม scale

```text
docker compose --env-file .env.deploy -f compose.yaml -f compose.production.yaml --profile jobs up -d scheduler
```

เลื่อนแผนเวลาไทย 00:05 และส่ง LINE 08:00 เมื่อมี token
profile นี้ส่งแจ้งเตือนจริงตามเวลา จึงไม่เปิดระหว่างเตรียม
ถ้าเครื่องปิดขณะถึงเวลา งานระหว่างปิดจะไม่ replay อัตโนมัติ ต้องตรวจแผนหลังระบบล่ม
การรัน python app.py ตอนพัฒนาไม่เปิด scheduler อีกแล้ว ใช้ python scheduler.py แยกถ้าต้องการ

## อัปเดตและสำรอง

- สำรอง GraphDB และจด commit/image tag ก่อนอัปเดต
- git pull แล้วใช้คำสั่ง up -d --build เดิม เติม --profile jobs ถ้าต้องการอัปเดต scheduler ด้วย
- แก้ .env.deploy ต้อง recreate ด้วย up -d ไม่ใช่รีเฟรชหน้าอย่างเดียว
- docker compose down เก็บ volume ไว้; **ห้าม down -v** เพราะจะลบฐานข้อมูล
- volume ไม่ใช่ backup ต้องสำรองนอกเซิร์ฟเวอร์เป็นระยะ
- คง SECRET_KEY เดิมระหว่าง restart เพื่อไม่ให้ session ใช้ไม่ได้
- ชุดนี้เป็นการเตรียม deploy ไม่ใช่การรับรอง security audit ทั้งระบบ

## สถานะการตรวจ

ตรวจเมื่อ 23 กันยายน 2026: build image บน Linux ผ่านแล้ว และทดสอบ container แบบปิดเครือข่ายผ่าน
ทั้งการโหลดแอป health/readiness endpoint การล็อกอินด้วยบัญชีจำลอง JWT และ Secure cookie
dependencies ผ่าน pip check และ Java/Pellet ประมวลผลกฎด้วยข้อมูลจำลองสำเร็จ
ตรวจ syntax ของ Python, JavaScript และ Jinja templates รวมถึงโครงสร้าง Compose ผ่านแล้ว

ทดสอบซ้ำโดยไม่เชื่อมบริการจริง:

```powershell
docker build -t diabalance-web:deploy-check .
docker run --rm --network none diabalance-web:deploy-check python -m deploy.check
```

ยังไม่พร้อมเปิดใช้งานจริงจนกว่าจะทำรายการต่อไปนี้:

- ตรวจค่าบริการใน `.env.deploy` ที่เตรียมแล้ว และกรอก SITE_DOMAIN เมื่อมีโดเมน
- เลือก GraphDB image ให้ตรงเวอร์ชัน/สิทธิ์ใช้งาน แล้วทดสอบ import และ restore ฐานข้อมูล
- เตรียมเซิร์ฟเวอร์และชื่อโดเมน ทดสอบ HTTPS และการล็อกอินผ่าน URL จริง
- ทดสอบ OTP, OCR, LINE webhook และการเพิ่มกฎ/แนะนำ/ทำแผนเสร็จ/streak กับฐานข้อมูลทดสอบ
- ตรวจการจำกัดสิทธิ์และการแสดงข้อมูลที่ผู้ใช้กรอกก่อนเปิดสู่สาธารณะ

ผลทดสอบนี้ยังไม่ครอบคลุมการทำงานร่วมกับฐานข้อมูลจริงหรือการทดสอบทุกฟังก์ชันของระบบ
ไม่มีการย้ายข้อมูลจริง เปิด scheduler หรือสร้างเซิร์ฟเวอร์ในขั้นเตรียมนี้

อ้างอิง: [GraphDB](https://github.com/Ontotext-AD/graphdb-docker),
[Gunicorn](https://docs.gunicorn.org/en/stable/settings.html),
[Caddy](https://caddyserver.com/docs/automatic-https)
