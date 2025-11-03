import React from 'react';
// 1. นำเข้า Routes และ Route จาก react-router-dom
import { Routes, Route } from 'react-router-dom'; 
import HomePage from './test.jsx'; 
import ProfilePage from './profile.jsx';


function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} /> 
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/admin" element={<h1>Admin Control Panel</h1>} />
    </Routes>
  );
}

export default App;