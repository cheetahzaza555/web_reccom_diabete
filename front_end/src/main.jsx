import React from 'react'; // ต้อง import React ถ้าใช้ JSX
import ReactDOM from 'react-dom/client'; 
import App from './App.jsx';
import './index.css';

// 1. นำเข้า BrowserRouter
import { BrowserRouter } from 'react-router-dom';

// 2. ใช้ createRoot และ render เพียงครั้งเดียว
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

