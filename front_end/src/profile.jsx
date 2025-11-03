import React, { useState, useEffect } from 'react';
import { User, Mail, Phone, Calendar, MapPin, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import axios from 'axios'; // 🟢 เพิ่มการนำเข้า axios

// ข้อมูลจำลองสำหรับใช้เป็นค่าเริ่มต้นในกรณีที่ดึงข้อมูลไม่สำเร็จ
const mockUserProfile = {
    name: 'กำลังโหลด...',
    email: 'N/A',
    phone: 'N/A',
    birthDate: 'N/A',
    address: 'N/A',
    joinDate: 'N/A',
    diabetesType: 'N/A',
};

// Component สำหรับแสดงแต่ละรายการข้อมูล
const ProfileItem = ({ icon: Icon, label, value }) => (
    <div className="flex items-center space-x-4 p-3 bg-white rounded-lg shadow-sm hover:shadow-md transition duration-200">
        <Icon className="w-6 h-6 text-indigo-500 flex-shrink-0" />
        <div className="flex flex-col">
            <span className="text-xs font-semibold uppercase text-gray-500">{label}</span>
            <span className="text-base text-gray-800 font-medium">{value}</span>
        </div>
    </div>
);

function ProfilePage() {
    // ใช้ mockUserProfile เป็นค่าเริ่มต้น
    const [profile, setProfile] = useState(mockUserProfile);
    const [loading, setLoading] = useState(true);
    const API_PROFILE_URL = 'http://localhost:5000/api/profile'; // 🟢 URL API ใหม่

    useEffect(() => {
        // 🟢 เปลี่ยนจาก setTimeout เป็นการเรียก API จริง
        axios.get(API_PROFILE_URL)
            .then(response => {
                // 💡 แมปข้อมูลจาก Express ให้เข้ากับรูปแบบของ Component
                setProfile({
                    name: response.data.fullName || 'ไม่พบชื่อ',
                    email: 'somying.s@example.com', // ใช้ค่าจำลองไปก่อน เพราะ Express ยังไม่มี field นี้
                    phone: response.data.phone || 'ไม่พบเบอร์',
                    birthDate: '15/05/2530',
                    address: `สถานะ: ${response.data.status}`, // แสดงสถานะที่ดึงจาก API
                    joinDate: '01/01/2565',
                    diabetesType: 'Type 2',
                });
                setLoading(false);
            })
            .catch(error => {
                console.error('Error fetching profile data:', error);
                setLoading(false); // หยุดโหลดแม้มีข้อผิดพลาด
                setProfile({
                    ...mockUserProfile,
                    name: 'เกิดข้อผิดพลาดในการโหลด',
                    address: 'โปรดตรวจสอบ Express Server',
                });
            });

        // ล้างฟังก์ชันในกรณี Component ถูกยกเลิกการโหลด (Cleanup)
        return () => { };
    }, []);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <p className="text-lg text-indigo-600">กำลังโหลดข้อมูล...</p>
            </div>
        );
    }

    // 💡 ข้อควรระวัง: ไม่ควรใช้ alert() ใน React แทนที่ด้วยการใช้ Modal หรือ Message Box
    const handleEditClick = () => {
        console.log('User clicked Edit button. Edit functionality is not yet implemented.');
        // ณ จุดนี้ เราจะใช้ console.log แทนการ alert()
    };

    return (
        <div className="min-h-screen bg-gray-100 p-4 sm:p-8">
            <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-2xl p-6 sm:p-10">

                {/* Header และ ปุ่มย้อนกลับ */}
                <div className="flex items-center justify-between border-b pb-4 mb-6">
                    <Link to="/" className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium transition duration-200">
                        <ArrowLeft className="w-5 h-5 mr-2" />
                        กลับหน้าหลัก
                    </Link>
                    <h1 className="text-3xl font-extrabold text-gray-900">
                        ข้อมูลส่วนตัว
                    </h1>
                    <button
                        className="px-4 py-2 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 transition duration-200 shadow-md"
                        onClick={handleEditClick}
                    >
                        แก้ไข
                    </button>
                </div>

                {/* ส่วนข้อมูลหลัก */}
                <div className="space-y-6">
                    <ProfileItem
                        icon={User}
                        label="ชื่อผู้ใช้งาน"
                        value={profile.name}
                    />
                    <ProfileItem
                        icon={Mail}
                        label="อีเมล"
                        value={profile.email}
                    />

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <ProfileItem
                            icon={Phone}
                            label="เบอร์โทรศัพท์"
                            value={profile.phone}
                        />
                        <ProfileItem
                            icon={Calendar}
                            label="วันเกิด"
                            value={profile.birthDate}
                        />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <ProfileItem
                            icon={MapPin}
                            label="ที่อยู่"
                            value={profile.address} // 💡 เปลี่ยนมาแสดงสถานะที่ดึงจาก API
                        />
                        <ProfileItem
                            icon={User}
                            label="ประเภทเบาหวาน"
                            value={profile.diabetesType}
                        />
                    </div>
                </div>

                {/* Footer Info */}
                <div className="mt-8 pt-4 border-t text-center text-sm text-gray-500">
                    <p>เป็นสมาชิกตั้งแต่: {profile.joinDate}</p>
                </div>

            </div>
        </div>
    );
}

export default ProfilePage;
