# DiaBalance - Diabetes Exercise Recommendation System

DiaBalance เป็นระบบแนะนำและจัดตารางการออกกำลังกายสำหรับผู้ป่วยเบาหวาน โดยใช้เทคโนโลยี Semantic Web (Ontology & SWRL Rules) ร่วมกับ Machine Learning และ Generative AI

## 🌐 Production URLs
- **Main Website**: [https://diabalance.tech](https://diabalance.tech) (หรือ [https://www.diabalance.tech](https://www.diabalance.tech))
- **GraphDB Workbench**: [http://graphdb.diabalance.tech](http://graphdb.diabalance.tech)
- **Healthcheck**: [https://diabalance.tech/healthz](https://diabalance.tech/healthz)
- **Readiness**: [https://diabalance.tech/readyz](https://diabalance.tech/readyz)

## 🏗️ Architecture & Technology Stack
- **Backend**: Python 3.13 (Flask) + Gunicorn + Jinja2 Templates
- **Knowledge Base & Reasoner**: Ontotext GraphDB 11, RDF/OWL, Owlready2 + Pellet Reasoner (Java JRE)
- **Background Scheduler**: APScheduler (Midnight reschedule & morning LINE reminders)
- **Web Server & Reverse Proxy**: Caddy 2 (Automatic Let's Encrypt HTTPS/SSL)
- **Integrations**: LINE Bot Messaging API, Google Gemini AI (OCR & Lab analysis)
- **DevOps**: Docker, Docker Compose, GitHub Actions CI/CD Pipeline

## 🚀 CI/CD Pipeline
ระบบติดตั้ง GitHub Actions Pipeline อัตโนมัติ:
1. **CI**: สร้าง Docker Image และรันการทดสอบ Deploy Check (Pellet reasoner, Flask endpoints, JWT, security headers)
2. **CD**: เชื่อมต่อ SSH ไปยัง VPS เพื่อดึงโค้ดล่าสุด และทำการ Rebuild/Restart คอนเทนเนอร์อัตโนมัติเมื่อ push เข้าสู่ branch `main`