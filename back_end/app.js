var express = require('express');
var logger = require('morgan');
const cors = require('cors'); // สำหรับอนุญาตให้ Front-end เข้าถึงได้
const port = 5000;

var app = express();
app.use(cors());

// ตั้งค่า Middleware ที่จำเป็นสำหรับ API Server
app.use(logger('dev'));
app.use(express.json()); // สำหรับการอ่าน JSON ใน body ของ request (เช่น POST)
app.use(express.urlencoded({ extended: false })); // สำหรับการอ่าน form data

// --- API Endpoints ---

// 1. Route สำหรับหน้าหลัก (HomePage)
app.get('/api/data', (req, res) => {
    res.json({ message: 'Hello from Express API! (Backend is working)' });
});

// 2. Route สำหรับหน้าโปรไฟล์ (ProfilePage)
app.get('/api/profile', (req, res) => {
    // ข้อมูลโปรไฟล์ที่ถูกดึงจากฐานข้อมูล (ตอนนี้เป็นข้อมูลจำลอง)
    const userProfile = {
        id: 1,
        fullName: 'สมหญิง สุขสบาย',
        phone: '081-123-4567',
        status: 'Active', // ใช้สำหรับแสดงในช่อง "ที่อยู่" ใน ProfilePage
    };
    // ส่งข้อมูลในรูปแบบ JSON
    res.json(userProfile);
});


// --- Server Listener ---

app.listen(port, () => {
    console.log(`Express API server running at http://localhost:${port}`);
});

module.exports = app;
