// --- rec_1.js : ตรรกะสำหรับหน้าผลตรวจสุขภาพ (DiaBalance) ---

let currentUser = {};
let currentPatientID = "";
let currentStep = 1;

const weightInput = document.getElementById('weight');
const heightInput = document.getElementById('height');
const bmiOutput = document.getElementById('bmi_result');

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/current_user');
        if (res.ok) {
            currentUser = await res.json();
            const fullName = (currentUser.firstname && currentUser.lastname)
                ? `${currentUser.firstname} ${currentUser.lastname}`
                : currentUser.username;
            document.getElementById('displayFullname').innerText = fullName;

            await fetchLastCheckup();
        }
    } catch (e) {
        console.error('Error fetching user:', e);
    }

    weightInput.addEventListener('input', calculateBMI);
    heightInput.addEventListener('input', calculateBMI);

    document.querySelectorAll('input[name="special"]:not(#chkNoOther)').forEach(el => {
        el.addEventListener('change', () => {
            if (el.checked) document.getElementById('chkNoOther').checked = false;
        });
    });
});

// ---------- OCR ----------
async function handleOCR(input) {
    if (!input.files || !input.files[0]) return;

    const placeholderDiv = document.getElementById('ocrPlaceholder');
    const statusDiv = document.getElementById('ocrStatus');
    const successDiv = document.getElementById('ocrSuccess');

    if (placeholderDiv) placeholderDiv.style.display = 'none';
    if (successDiv) successDiv.style.display = 'none';
    if (statusDiv) statusDiv.style.display = 'block';

    const formData = new FormData();
    formData.append('file', input.files[0]);

    try {
        const response = await fetch('http://127.0.0.1:5000/user/api/ocr', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Server Error');

        const result = await response.json();
        console.log("=== ผลลัพธ์ที่ส่งกลับมาจาก Python ===", result);

        if (result && result.success) {
            const data = result.data;

            document.querySelector('[name="hdl"]').value = data.hdl || "";
            document.querySelector('[name="ldl"]').value = data.ldl || "";
            document.querySelector('[name="cholesterol"]').value = data.cholesterol || "";
            document.querySelector('[name="fpg"]').value = data.fpg || "";

            if (data.weight) document.querySelector('[name="weight"]').value = data.weight;
            if (data.height) document.querySelector('[name="height"]').value = data.height;

            if (data.bmi && document.getElementById('bmi_result')) {
                document.getElementById('bmi_result').value = data.bmi;
            }

            if (data.bp && data.bp.includes('/')) {
                const bpParts = data.bp.split('/');
                if (document.querySelector('[name="bp_high"]')) document.querySelector('[name="bp_high"]').value = bpParts[0] || "";
                if (document.querySelector('[name="bp_low"]')) document.querySelector('[name="bp_low"]').value = bpParts[1] || "";
            }
            if (data.triglyceride) {
                document.querySelector('[name="triglyceride"]').value = data.triglyceride;
            }

            if (data.date && document.querySelector('[name="blood_test_date"]')) {
                const dateParts = data.date.split('/');
                if (dateParts.length === 3) {
                    let day = dateParts[0].padStart(2, '0');
                    let month = dateParts[1].padStart(2, '0');
                    let year = dateParts[2];

                    if (parseInt(year) > 2400) {
                        year = (parseInt(year) - 543).toString();
                    }

                    document.querySelector('[name="blood_test_date"]').value = `${year}-${month}-${day}`;
                }
            }

            if (statusDiv) statusDiv.style.display = 'none';
            if (successDiv) successDiv.style.display = 'block';

            if (typeof highlightFields === 'function') {
                highlightFields(['hdl', 'ldl', 'cholesterol', 'fpg', 'weight', 'height', 'bp_high', 'bp_low', 'blood_test_date', 'triglyceride']);
            }

        } else {
            if (statusDiv) statusDiv.style.display = 'none';
            if (placeholderDiv) placeholderDiv.style.display = 'block';
            alert("AI ไม่พบข้อมูลสุขภาพในภาพนี้ กรุณาอัปโหลดใหม่อีกครั้ง");
        }

    } catch (error) {
        console.error("OCR Error:", error);
        if (statusDiv) statusDiv.style.display = 'none';
        if (placeholderDiv) placeholderDiv.style.display = 'block';
        alert("ไม่สามารถเชื่อมต่อระบบ AI ได้");
    } finally {
        input.value = '';
    }
}

function highlightFields(fields) {
    fields.forEach(f => {
        const el = document.querySelector(`[name="${f}"]`);
        if (el) {
            el.style.transition = 'background-color 0.8s ease';
            el.style.backgroundColor = '#d1e7dd';
            setTimeout(() => {
                el.style.backgroundColor = '';
            }, 3000);
        }
    });
}

// ---------- โหลดข้อมูลตรวจครั้งล่าสุด ----------
async function fetchLastCheckup() {
    try {
        const res = await fetch('/user/get_latest_checkup');

        if (res.ok) {
            const data = await res.json();

            if (data && data.found) {
                console.log("📥 Loaded Data:", data);

                const setVal = (name, val) => {
                    if (!val) return;

                    const radios = document.querySelectorAll(`input[type="radio"][name="${name}"]`);
                    if (radios.length > 0) {
                        radios.forEach(r => {
                            if (r.value.toLowerCase() === val.toString().toLowerCase()) {
                                r.checked = true;
                            }
                        });
                        return;
                    }

                    const el = document.querySelector(`[name="${name}"]`);
                    if (el) {
                        el.value = val;
                        if (el.tagName === 'SELECT' && el.value !== val) {
                            Array.from(el.options).forEach(opt => {
                                if (opt.value.toLowerCase() === val.toString().toLowerCase()) {
                                    el.value = opt.value;
                                }
                            });
                        }
                    }
                };

                setVal('gender', data.gender);
                setVal('checkup_date', data.checkup_date);
                setVal('diabetes_type', data.diabetes_type);
                setVal('insulin_use', data.insulin_use);
                setVal('weight', data.weight);
                setVal('height', data.height);

                if (typeof calculateBMI === 'function') calculateBMI();

                setVal('bp_high', data.bp_high);
                setVal('bp_low', data.bp_low);
                setVal('blood_test_date', data.blood_test_date);
                setVal('hdl', data.hdl);
                setVal('ldl', data.ldl);
                setVal('cholesterol', data.cholesterol);
                setVal('triglyceride', data.triglyceride);
                setVal('microalbumin', data.microalbumin);
                setVal('ketone', data.ketone);
                setVal('fpg', data.fpg);
                setVal('frequency', data.frequency);

                const setCheckboxes = (inputName, savedList) => {
                    if (savedList && Array.isArray(savedList)) {
                        savedList.forEach(val => {
                            let chk = document.querySelector(`input[name="${inputName}"][value="${val}"]`);

                            if (!chk && val) {
                                chk = Array.from(document.querySelectorAll(`input[name="${inputName}"]`))
                                    .find(el => el.value.toLowerCase() === val.toLowerCase());
                            }

                            if (chk) {
                                chk.checked = true;
                                chk.dispatchEvent(new Event('change'));
                            }
                        });
                    }
                };

                const diseaseList = data.special || data.special_diseases;
                setCheckboxes('special', diseaseList);
                setCheckboxes('favorites', data.favorites);

                if (currentUser && currentUser.id) {
                    currentPatientID = currentUser.id;
                }

                const modalDateEl = document.getElementById('modalDate');
                if (modalDateEl && data.checkup_date) {
                    const d = new Date(data.checkup_date);
                    modalDateEl.innerText = d.toLocaleDateString('th-TH', {
                        year: 'numeric', month: 'long', day: 'numeric'
                    });
                }

                const modalEl = document.getElementById('existingDataModal');
                if (modalEl && data.found === true && data.checkup_date) {
                    const myModal = new bootstrap.Modal(modalEl);
                    myModal.show();
                }
            }
        }
    } catch (err) {
        console.error("Error fetching old health data:", err);
    }
}

function skipToPlan() {
    if (currentPatientID) {
        window.location.href = "/user/select_plan/Patient" + currentPatientID;
    } else {
        alert("ไม่พบรหัสผู้ป่วย กรุณาตรวจสอบข้อมูลอีกครั้ง");
        const modalEl = document.getElementById('existingDataModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal.hide();
    }
}

// ---------- BMI ----------
function calculateBMI() {
    const w = parseFloat(weightInput.value);
    const h = parseFloat(heightInput.value) / 100;
    if (w > 0 && h > 0) bmiOutput.value = (w / (h * h)).toFixed(2);
    else bmiOutput.value = "";
}

// ---------- Step navigation ----------
function updateUI() {
    for (let i = 1; i <= 4; i++) {
        const stepEl = document.getElementById('step' + i);
        if (stepEl) stepEl.style.display = 'none';
    }

    const currentStepEl = document.getElementById('step' + currentStep);
    if (currentStepEl) currentStepEl.style.display = 'block';

    const btnBack = document.getElementById('btnBack');
    const btnNext = document.getElementById('btnNext');
    const title = document.getElementById('pageTitle');

    if (currentStep === 1) {
        btnBack.innerText = 'ยกเลิก'; btnNext.innerText = 'ถัดไป';
        btnNext.onclick = handleNext; title.innerText = 'ผลตรวจสุขภาพ (1/3)';
    } else if (currentStep === 2) {
        btnBack.innerText = 'ย้อนกลับ'; btnNext.innerText = 'ถัดไป';
        btnNext.onclick = handleNext; title.innerText = 'โรคแทรกซ้อน (2/3)';
    } else if (currentStep === 3) {
        btnBack.innerText = 'ย้อนกลับ'; btnNext.innerText = 'สร้างตารางออกกำลังกาย';
        btnNext.onclick = analyzeData; title.innerText = 'กิจกรรมที่ชอบ (3/3)';
    } else if (currentStep === 4) {
        title.innerText = 'สรุปผลการวิเคราะห์';
        btnBack.innerText = 'แก้ไขข้อมูล';
        btnNext.innerText = 'ยืนยันและไปเลือกแผน';
        btnNext.onclick = function () {
            if (currentPatientID) {
                window.location.href = "/user/select_plan/Patient" + currentPatientID;
            } else {
                alert("ไม่พบ ID ผู้ป่วย กรุณากดประมวลผลใหม่อีกครั้ง");
            }
        };
    }

    const formScroll = document.querySelector('.form-scroll-area');
    if (formScroll) formScroll.scrollTop = 0;
}

function handleNext() {
    if (currentStep === 1) {
        const inputs = document.getElementById('step1').querySelectorAll('input[required], select[required]');
        let valid = true;
        inputs.forEach(input => {
            if (!input.value) { valid = false; input.style.borderColor = 'red'; }
            else { input.style.borderColor = '#dee2e6'; }
        });
        if (!valid) return alert('กรุณากรอกข้อมูลให้ครบถ้วน');
    }
    if (currentStep < 4) { currentStep++; updateUI(); }
}

function handleBack() {
    if (currentStep > 1) { currentStep--; updateUI(); }
    else { window.history.back(); }
}

function toggleNoOther(checkbox) {
    if (checkbox.checked) {
        document.querySelectorAll('input[name="special"]:not(#chkNoOther)').forEach(el => el.checked = false);
    }
}

// ---------- ส่งข้อมูลไปวิเคราะห์ ----------
async function analyzeData() {
    const getVal = (name) => {
        const el = document.querySelector(`[name="${name}"]`);
        return el ? el.value : '';
    };

    const selectedSpecials = Array.from(document.querySelectorAll('input[name="special"]:checked')).map(el => el.value);
    const selectedFavorites = Array.from(document.querySelectorAll('input[name="favorites"]:checked')).map(el => el.value);

    let generatedID = 'TEMP_GUEST';
    if (currentUser.id) generatedID = currentUser.id;

    currentPatientID = generatedID;

    const data = {
        id: generatedID,
        save_mode: false,
        firstname: currentUser.firstname,
        lastname: currentUser.lastname,
        gender: getVal('gender'),
        checkup_date: getVal('checkup_date'),
        blood_test_date: getVal('blood_test_date'),
        type: getVal('diabetes_type'),
        insulin_use: getVal('insulin_use'),
        frequency: getVal('frequency'),
        weight: getVal('weight'),
        height: getVal('height'),
        bmi: getVal('bmi'),
        sbp: getVal('bp_high'), dbp: getVal('bp_low'),
        chol: getVal('cholesterol'), ldl: getVal('ldl'), hdl: getVal('hdl'), tri: getVal('triglyceride'),
        fpg: getVal('fpg'), ketone: getVal('ketone'), micro: getVal('microalbumin'),
        special: selectedSpecials, favorites: selectedFavorites
    };

    const btn = document.getElementById('btnNext');
    const originalText = btn.innerText;
    btn.innerText = '⏳ กำลังประมวลผล...'; btn.disabled = true;

    try {
        const res = await fetch('/user/analyze', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const text = await res.text();
        try {
            const json = JSON.parse(text);
            if (json.status === 'ok') {
                currentStep = 4;
                updateUI();
                renderResults(json);
            } else {
                alert("❌ ระบบแจ้งเตือน: " + json.message);
            }
        } catch (err) {
            console.error("Server Error HTML:", text);
            alert("เกิดข้อผิดพลาดที่ Server");
        }
    } catch (e) {
        alert("เชื่อมต่อ Server ไม่ได้: " + e);
    } finally {
        btn.innerText = originalText; btn.disabled = false;
    }
}

// ---------- แสดงผลลัพธ์ ----------
function renderResults(json) {
    const updateList = (id, items) => {
        const el = document.getElementById(id);
        el.innerHTML = "";
        if (!items || items.length === 0) el.innerHTML = `<li class="text-muted">- ไม่พบข้อมูล -</li>`;
        else items.forEach(x => { el.innerHTML += `<li>${x}</li>`; });
    };

    updateList('warnList', json.warnings);
    updateList('compliList', json.complis);
    updateList('comorbList', json.comorbs);

    const exEl = document.getElementById('exList');
    exEl.innerHTML = "";

    if (!json.exercises || json.exercises.length === 0) {
        exEl.innerHTML = `<li class="text-muted">- เนื่องจากสภาวะร่างกายหรือความเสี่ยงร่วมของท่านในปัจจุบัน ไม่สอดคล้องกับเกณฑ์ความเข้มข้นของประเภทกิจกรรมที่เลือก <br>
                เพื่อป้องกันการบาดเจ็บหรืออันตรายต่อระบบหัวใจและหลอดเลือด ระบบจึงของดแนะนำกิจกรรมดังกล่าวชั่วคราว -</li>`;
        return;
    }

    console.log("ข้อมูลท่าออกกำลังกายที่ได้รับ:", json.exercises);

    const categories = {
        "🏃 การวิ่ง (Running)": [],
        "🚶 การเดิน (Walking)": [],
        "🚴 การปั่นจักรยาน (Bicycling)": [],
        "💃 การเต้น (Dancing)": [],
        "🏊 กิจกรรมทางน้ำ (Water Activity)": [],
        "🏅 กีฬาแอโรบิกลงน้ำหนัก": [],
        "🏅 กีฬาแอโรบิกไม่ลงน้ำหนัก": [],
        "💪 การฝึกแรงต้าน (Resistance)": [],
        "🧘 การยืดเหยียด (Stretching)": [],
        "✨ กิจกรรมอื่นๆ (Others)": []
    };

    json.exercises.forEach(item => {
        let exerciseName = (typeof item === 'object' && item.label) ? item.label : item.toString();
        let exerciseType = (typeof item === 'object' && item.type) ? item.type.toString() : "";

        if (exerciseType.includes('Running')) {
            categories["🏃 การวิ่ง (Running)"].push(exerciseName);
        }
        else if (exerciseType.includes('Walking')) {
            categories["🚶 การเดิน (Walking)"].push(exerciseName);
        }
        else if (exerciseType.includes('Bicycling')) {
            categories["🚴 การปั่นจักรยาน (Bicycling)"].push(exerciseName);
        }
        else if (exerciseType.includes('Dancing')) {
            categories["💃 การเต้น (Dancing)"].push(exerciseName);
        }
        else if (exerciseType.includes('WaterActivity')) {
            categories["🏊 กิจกรรมทางน้ำ (Water Activity)"].push(exerciseName);
        }
        else if (exerciseType.includes('WeightBearingAerobicSport') && !exerciseType.includes('NonWeightBearingAerobicSport')) {
            categories["🏅 กีฬาแอโรบิกลงน้ำหนัก"].push(exerciseName);
        }
        else if (exerciseType.includes('NonWeightBearingAerobicSport')) {
            categories["🏅 กีฬาแอโรบิกไม่ลงน้ำหนัก"].push(exerciseName);
        }
        else if (exerciseType.includes('Resistance')) {
            categories["💪 การฝึกแรงต้าน (Resistance)"].push(exerciseName);
        }
        else if (exerciseType.includes('Stretching')) {
            categories["🧘 การยืดเหยียด (Stretching)"].push(exerciseName);
        }
        else {
            categories["✨ กิจกรรมอื่นๆ (Others)"].push(exerciseName);
        }
    });

    for (const [catName, items] of Object.entries(categories)) {
        if (items.length > 0) {
            exEl.innerHTML += `<li class="category-header" style="font-weight:bold; color:#2c3e50; margin-top:10px; list-style:none;">${catName}</li>`;
            items.forEach(ex => {
                exEl.innerHTML += `<li class="ms-3 py-1 border-bottom" style="list-style:none; border-color: rgba(0,0,0,0.05) !important;">• ${ex}</li>`;
            });
        }
    }
}