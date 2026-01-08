import { useState, useEffect } from 'react';
import './App.css'; // อย่าลืม import CSS

// ตั้งค่า URL ของ Backend (Flask)
const API_BASE = "http://localhost:5000";

function App() {
  // 1. State สำหรับ Form Data
  const [formData, setFormData] = useState({
    pid: '', dtype: 'T2DM', fname: '', lname: '',
    weight: '', height: '', bmi: '',
    fpg: '', sbp: '', dbp: '',
    chol: '', ldl: '', hdl: '', tri: '',
    ketone: 'Negative', micro: 'Negative',
    special: [], // Array เก็บค่า Checkbox
    favorites: [] // Array เก็บค่า Checkbox
  });

  // 2. State อื่นๆ
  const [searchId, setSearchId] = useState('');
  const [result, setResult] = useState(null); // เก็บผลลัพธ์จาก Backend

  // --- Logic 1: คำนวณ BMI อัตโนมัติเมื่อ weight/height เปลี่ยน ---
  useEffect(() => {
    const w = parseFloat(formData.weight);
    const h = parseFloat(formData.height);
    if (w > 0 && h > 0) {
      const bmiVal = (w / ((h / 100) ** 2)).toFixed(2);
      setFormData(prev => ({ ...prev, bmi: bmiVal }));
    } else if (formData.bmi !== '' && formData.bmi !== 'Auto') {
       // ถ้าลบค่าออก ก็ลบ BMI ด้วย (ยกเว้นตอนโหลดจาก DB ที่อาจมีค่ามา)
       // แต่ในที่นี้เอาแบบง่ายคือคำนวณใหม่ตลอด
       setFormData(prev => ({ ...prev, bmi: '' }));
    }
  }, [formData.weight, formData.height]);

  // --- Logic 2: Handle Input Change (Text/Number/Select) ---
  const handleChange = (e) => {
    const { id, value } = e.target;
    setFormData(prev => ({ ...prev, [id]: value }));
  };

  // --- Logic 3: Handle Checkbox (Special) - Logic "NoOther" ---
  const handleSpecialChange = (e) => {
    const { value, checked } = e.target;
    let newSpecials = [...formData.special];

    if (value === "NoOtherComplication") {
      if (checked) {
        newSpecials = ["NoOtherComplication"]; // เคลียร์ตัวอื่นหมด
      } else {
        newSpecials = newSpecials.filter(item => item !== value);
      }
    } else {
      // ถ้าเลือกโรคอื่น
      if (checked) {
        newSpecials.push(value);
        // เอา NoOther ออก
        newSpecials = newSpecials.filter(item => item !== "NoOtherComplication");
      } else {
        newSpecials = newSpecials.filter(item => item !== value);
      }
    }
    setFormData(prev => ({ ...prev, special: newSpecials }));
  };

  // --- Logic 4: Handle Checkbox (Favorites) ---
  const handleFavoriteChange = (e) => {
    const { value, checked } = e.target;
    let newFavs = [...formData.favorites];
    if (checked) newFavs.push(value);
    else newFavs = newFavs.filter(item => item !== value);
    
    setFormData(prev => ({ ...prev, favorites: newFavs }));
  };

  // --- API 1: Analyze Data ---
  const analyzeData = async () => {
    // แปลงชื่อ field ให้ตรงกับที่ Backend (Python) ต้องการ
    const payload = {
      id: formData.pid,
      type: formData.dtype,
      firstname: formData.fname,
      lastname: formData.lname,
      weight: formData.weight,
      height: formData.height,
      bmi: formData.bmi,
      sbp: formData.sbp,
      dbp: formData.dbp,
      chol: formData.chol,
      ldl: formData.ldl,
      hdl: formData.hdl,
      tri: formData.tri,
      fpg: formData.fpg,
      ketone: formData.ketone,
      micro: formData.micro,
      special: formData.special,
      favorites: formData.favorites
    };

    if (!payload.id) return alert("กรุณาใส่ ID ผู้ป่วย");

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const json = await res.json();
      
      if (json.status === 'ok') {
        setResult(json);
        alert("✅ บันทึกและประมวลผลสำเร็จ!");
        // Scroll to result (Optional in React, usually via ref)
        document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
      } else {
        alert("❌ Error: " + json.message);
      }
    } catch (e) {
      alert("Server Error: " + e);
    }
  };

  // --- API 2: Search Patient ---
  const searchPatient = async () => {
    if (!searchId) return;
    try {
      const res = await fetch(`${API_BASE}/api/patient/${searchId}`);
      const json = await res.json();
      
      if (json.status === 'error') {
        alert("ไม่พบข้อมูล");
        return;
      }

      const info = json.info;
      
      // Map ข้อมูลกลับเข้า State (Normalize Special/Favs ให้เป็น lowercase comparison หรือ logic ตามเดิม)
      // *หมายเหตุ* Logic การ Normalize (ตัด space/lowercase) ควรทำใน Backend หรือทำตรงนี้ก็ได้
      // ในที่นี้สมมติว่า Backend ส่งค่าตรงกับ value ใน checkbox
      
      // Logic การ Map Specials
      let loadedSpecials = [];
      if (json.specials && json.specials.length > 0) {
        // ทำ Clean data นิดหน่อยเผื่อ case/space ไม่ตรง
        const cleanSpecials = json.specials.map(s => s.toLowerCase().replace(/_/g,'').replace(/ /g,''));
        
        // เช็คกับ value ที่เรามีใน UI (Hardcode check หรือสร้าง list มาเทียบ)
        // เพื่อความง่าย รับค่ามาตรงๆ ก่อน (ถ้า Backend แก้ตามที่คุยกันแล้ว)
        loadedSpecials = json.specials; 
      } else {
        loadedSpecials = ["NoOtherComplication"];
      }

      setFormData({
        pid: searchId,
        dtype: info.type || 'T2DM',
        fname: info.firstname || '',
        lname: info.lastname || '',
        weight: info.weight || '',
        height: info.height || '',
        bmi: info.bmi || '',
        sbp: info.sbp || '',
        dbp: info.dbp || '',
        chol: info.chol || '',
        ldl: info.ldl || '',
        hdl: info.hdl || '',
        tri: info.tri || '',
        fpg: info.fpg || '',
        ketone: info.ketone || 'Negative',
        micro: info.micro || 'Negative',
        special: loadedSpecials,
        favorites: json.favorites || []
      });

      setResult(json); // แสดงผลลัพธ์ด้วย
    } catch (e) {
      console.error(e);
      alert("โหลดข้อมูลไม่สำเร็จ");
    }
  };

  // --- API 3: Reprocess ---
  const reprocessPatient = async () => {
    if (!searchId) return;
    const res = await fetch(`${API_BASE}/api/reprocess/${searchId}`, { method: 'POST' });
    const json = await res.json();
    if (json.status === 'ok') {
      alert("Run เสร็จสิ้น");
      searchPatient();
    }
  };

  // --- API 4: Delete ---
  const deletePatient = async () => {
    if (!searchId) return;
    if (window.confirm("ยืนยันลบ ID " + searchId + " ?")) {
      await fetch(`${API_BASE}/api/delete/${searchId}`, { method: 'DELETE' });
      alert("ลบข้อมูลแล้ว");
      window.location.reload(); // หรือเคลียร์ state
    }
  };

  // Helper สำหรับ Render List Result
  const ResultList = ({ items, emptyMsg = "- ไม่พบข้อมูล -" }) => {
    if (!items || items.length === 0) return <li style={{ color: '#bbb' }}>{emptyMsg}</li>;
    return items.map((x, i) => <li key={i}>{x}</li>);
  };

  return (
    <div className="container">
      <h2>🏥 ระบบผู้เชี่ยวชาญวินิจฉัยโรคเบาหวาน</h2>

      <div className="card">
        <h3>📝 ข้อมูลผู้ป่วย (Patient Info)</h3>
        <div className="form-grid">
          <div className="form-group">
            <label>ID (รหัส)</label>
            <input type="number" id="pid" placeholder="เช่น 101" 
                   value={formData.pid} onChange={handleChange} />
          </div>
          <div className="form-group">
            <label>Type (ชนิดเบาหวาน)</label>
            <select id="dtype" value={formData.dtype} onChange={handleChange}>
              <option value="T1DM">T1DM (ชนิดที่ 1)</option>
              <option value="T2DM">T2DM (ชนิดที่ 2)</option>
              <option value="GDM">GDM (ขณะตั้งครรภ์)</option>
            </select>
          </div>
          <div className="form-group">
            <label>ชื่อ</label>
            <input type="text" id="fname" value={formData.fname} onChange={handleChange} />
          </div>
          <div className="form-group">
            <label>นามสกุล</label>
            <input type="text" id="lname" value={formData.lname} onChange={handleChange} />
          </div>
        </div>

        <hr style={{ border: 0, borderTop: '1px solid #eee', margin: '20px 0' }} />

        <h3>🩺 ผลตรวจร่างกาย (Physical & Lab)</h3>
        <div className="form-grid">
          <div><label>น้ำหนัก (kg)</label><input type="number" id="weight" step="0.1" value={formData.weight} onChange={handleChange} /></div>
          <div><label>ส่วนสูง (cm)</label><input type="number" id="height" step="0.1" value={formData.height} onChange={handleChange} /></div>
          <div><label>BMI</label><input type="number" id="bmi" readOnly placeholder="Auto" className="input-bmi" value={formData.bmi} /></div>

          <div><label>FPG (น้ำตาล)</label><input type="number" id="fpg" value={formData.fpg} onChange={handleChange} /></div>
          <div><label>SBP (ความดันบน)</label><input type="number" id="sbp" value={formData.sbp} onChange={handleChange} /></div>
          <div><label>DBP (ความดันล่าง)</label><input type="number" id="dbp" value={formData.dbp} onChange={handleChange} /></div>

          <div><label>Cholesterol</label><input type="number" id="chol" value={formData.chol} onChange={handleChange} /></div>
          <div><label>LDL</label><input type="number" id="ldl" value={formData.ldl} onChange={handleChange} /></div>
          <div><label>HDL</label><input type="number" id="hdl" value={formData.hdl} onChange={handleChange} /></div>
          <div><label>Triglyceride</label><input type="number" id="tri" value={formData.tri} onChange={handleChange} /></div>

          <div>
            <label>Ketone</label>
            <select id="ketone" value={formData.ketone} onChange={handleChange}>
              <option value="Negative">Negative</option>
              <option value="Positive">Positive</option>
            </select>
          </div>
          <div>
            <label>Microalbuminuria</label>
            <select id="micro" value={formData.micro} onChange={handleChange}>
              <option value="Negative">Negative</option>
              <option value="Positive">Positive</option>
            </select>
          </div>

          <div style={{ gridColumn: 'span 2' }}>
            <label>⚠️ ภาวะแทรกซ้อนพิเศษ</label>
            <div className="checkbox-group">
               {['HeartDisease', 'PeripheralNeuropathy', 'AutonomicNeuropathy', 'Retinopathy'].map(val => (
                 <label key={val} className="checkbox-item">
                   <input type="checkbox" value={val} 
                          checked={formData.special.includes(val)} 
                          onChange={handleSpecialChange} /> 
                   {val}
                 </label>
               ))}
               <label className="checkbox-item" style={{ color: 'green' }}>
                 <input type="checkbox" value="NoOtherComplication" 
                        checked={formData.special.includes("NoOtherComplication")}
                        onChange={handleSpecialChange} /> 
                 ✅ ไม่มีภาวะแทรกซ้อนอื่น
               </label>
            </div>
          </div>

          <div style={{ gridColumn: 'span 2' }}>
            <label>⭐ ท่าออกกำลังกายที่ชอบ (Favorites)</label>
            <div className="checkbox-group">
              {['Walking', 'Running', 'Swimming', 'Bicycling', 'Yoga', 'Aerobic', 'Dancing'].map(val => (
                <label key={val} className="checkbox-item">
                  <input type="checkbox" value={val}
                         checked={formData.favorites.includes(val)}
                         onChange={handleFavoriteChange} />
                  {val}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="action-bar">
          <button className="btn-main" onClick={analyzeData}>🚀 บันทึก & ประมวลผล (Analyze)</button>
        </div>
      </div>

      {result && (
        <div id="result" className="card result-section">
          <h3 style={{ color: '#2e7d32' }}>📊 ผลการวินิจฉัย (Diagnosis Result)</h3>
          <div className="result-grid">
            <div className="result-box box-warn">
              <p style={{ color: '#f57f17', margin: 0 }}><strong>⚠️ คำเตือน (Warnings)</strong></p>
              <ul><ResultList items={result.warnings} /></ul>
            </div>
            <div className="result-box box-danger">
              <p style={{ color: '#c62828', margin: 0 }}><strong>💉 ภาวะแทรกซ้อน (Complications)</strong></p>
              <ul style={{ color: '#d32f2f' }}><ResultList items={result.complis} /></ul>
            </div>
          </div>
          <div className="result-grid" style={{ marginTop: '15px' }}>
            <div className="result-box box-success">
              <p style={{ color: '#2e7d32', margin: 0 }}><strong>🏃 แนะนำออกกำลังกาย (Exercise)</strong></p>
              <ul><ResultList items={result.exercises} /></ul>
            </div>
            <div className="result-box">
              <p style={{ color: '#1565c0', margin: 0 }}><strong>➕ โรคร่วม (Comorbidities)</strong></p>
              <ul><ResultList items={result.comorbs} /></ul>
            </div>
          </div>
        </div>
      )}

      <div className="search-area">
        <strong>🔍 จัดการข้อมูล:</strong>
        <input type="text" value={searchId} onChange={(e) => setSearchId(e.target.value)} placeholder="ID ผู้ป่วย" />
        <button className="btn-blue" onClick={searchPatient}>ค้นหา</button>
        <button className="btn-orange" onClick={reprocessPatient}>⚡ รันใหม่ (Re-Run)</button>
        <button className="btn-red" onClick={deletePatient}>ลบ (Delete)</button>
      </div>
    </div>
  );
}

export default App;