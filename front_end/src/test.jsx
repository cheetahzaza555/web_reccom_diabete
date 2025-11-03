import React, { useState, useEffect } from 'react';
import axios from 'axios'; // ถ้าใช้ Axios
import { Link } from 'react-router-dom'; // 🟢 เพิ่มการนำเข้า Link

function HomePage() {
    const [data, setData] = useState('');
    const API_URL = 'http://localhost:5000/api/data';

    useEffect(() => {
        // เรียกข้อมูลจาก Express Server
        axios.get(API_URL)
            .then(response => {
                setData(response.data.message);
            })
            .catch(error => {
                console.error('Error fetching data:', error);
                setData('Failed to fetch data. Check if Express server is running on port 5000.'); // ข้อความแจ้งเตือนที่ชัดเจนขึ้น
            });
    }, []);

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
            <div className="bg-white p-8 rounded-xl shadow-2xl text-center max-w-md w-full">
                <h1 className="text-4xl font-extrabold text-indigo-700 mb-4">React Front-end Home</h1>
                <p className="text-lg text-gray-600 mb-6 border p-4 rounded-lg bg-indigo-50">
                    Data from Backend: <strong className="text-gray-800">{data}</strong>
                </p>

                {/* 🟢 ปุ่มนำทางไปหน้า Profile */}
                <Link
                    to="/profile"
                    className="inline-block px-6 py-3 mt-4 text-white font-semibold rounded-lg bg-teal-500 hover:bg-teal-600 transition duration-300 shadow-lg transform hover:scale-105"
                >
                    👤 ไปที่หน้าโปรไฟล์
                </Link>

            </div>
        </div>
    );
}

export default HomePage;
