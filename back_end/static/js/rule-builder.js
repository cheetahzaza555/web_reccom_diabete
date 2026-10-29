"use strict";
const catalog = JSON.parse(
  document.getElementById("builder-catalog").textContent,
);

const categories = catalog.categories;
const fields = catalog.fields;
Object.values(fields).forEach((meta) => {
  if (meta.options) meta.values = meta.options.map((item) => item.value);
});
const operators = {
  gte: "ตั้งแต่",
  gt: "มากกว่า",
  lte: "ไม่เกิน",
  lt: "น้อยกว่า",
  eq: "เท่ากับ",
};

const results = catalog.results;
let conditions = [];
let outcomes = [];
const actionLabels = {
  warning: "คำเตือน",
  exercise: "แนะนำหมวดออกกำลังกาย",
  avoid: "ข้อควรหลีกเลี่ยง",
  frequency: "ความถี่ในการออกกำลังกาย",
};

let nextId = 0;
let customName = false;
const $ = (id) => document.getElementById(id);

/**
 * แปลงค่าที่เป็นรหัสของตัวเลือกให้เป็นข้อความที่อ่านง่าย
 */
function displayValue(value) {
  for (const meta of Object.values(fields)) {
    const item = meta.options?.find((item) => item.value === value);
    if (item) return item.label;
  }
  return value;
}

function describeCondition(c) {
  const value = c.value === "" ? "[ยังไม่ได้ใส่ตัวเลข]" : displayValue(c.value);
  // ใช้กับโรคแทรกซ้อนอื่นๆ
  if (c.field === "special")
    return "มี " + (c.value ? value : "[ยังไม่ได้เลือกรายการ]");
  // ใช้กับประเภทของผู้ป่วย
  if (c.field === "type")
    return "เป็น " + (c.value ? value : "[ยังไม่ได้เลือกรายการ]");
  if (fields[c.field].values) return fields[c.field].label + "เป็น " + value;
  return [
    fields[c.field].label,
    operators[c.op],
    value,
    fields[c.field].unit || "",
    c.op === "gte" ? "ขึ้นไป" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

// แปลงความหนักของการออกกำลังกายเป็นข้อความช่วง MET
function intensityMetLabel(intensity) {
  if (typeof intensity?.met_label === "string" && intensity.met_label.trim()) {
    return intensity.met_label;
  }
  const ranges = {
    "http://example.org/diabetes#Light": "MET < 3",
    "http://example.org/diabetes#Moderate": "3 ≤ MET ≤ 6",
    "http://example.org/diabetes#Vigorous": "MET > 6",
  };
  return ranges[intensity?.value] || "ยังไม่มีข้อมูลช่วง MET กรุณาโหลดหน้าใหม่";
}

// แปลงผลลัพธ์ที่แอดมินเลือกทั้งหมดเป็นข้อความสำหรับแสดงในสรุปกฎ
function resultText() {
  return outcomes
    .map((outcome) => {
      const item = results[outcome.action]?.find(
        (item) => item.value === outcome.result,
      );
      let text =
        actionLabels[outcome.action] +
        ": " +
        (item?.label || "[ยังไม่ได้เลือกรายการ]");
      if (outcome.action === "exercise") {  // ถ้าเป็นผลลัพธ์ประเภทแนะนำหมวดออกกำลังกาย
        const intensity = results.intensity.find(
          (item) => item.value === outcome.intensity,
        );
        text +=
          " · ความหนัก " +
          (intensity?.label || "[ยังไม่ได้เลือก]") +
          (intensity ? " · " + intensityMetLabel(intensity) : "");
        if (outcome.use_favorites) text += " · เฉพาะหมวดที่ผู้ป่วยชอบ";
      }
      return text;
    })
    .join("\nและ");
}

function resultId(item) {
  return item.value.split(/[#/]/).pop();
}

// ตรวจสอบว่ากฎที่สร้างขึ้นมีข้อมูลครบถ้วนและถูกต้องหรือไม่
function validateRule() {
  const controls = [
    $("name"),
    ...conditions.map((c) => $("value-" + c.id)),
    ...$("outputs").querySelectorAll("select,input"),
  ];
  return controls.every((input) => input.reportValidity());
}

// สร้าง element <option> สำหรับ select
function option(value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  return o;
}

// สร้างกล่องควบคุมที่มี label และ element input/select
function control(labelText, element) {
  const box = document.createElement("div");
  const label = document.createElement("label");
  label.htmlFor = element.id;
  label.textContent = labelText;
  box.append(label, element);
  return box;
}

// สร้าง element ว่าเป็นช่องกรอกหรือตัวเลือก
function valueInput(field, value, id) {
  const meta = fields[field];
  const input = document.createElement(meta.values ? "select" : "input");
  input.id = id;
  if (meta.values) {
    input.append(
      option("", meta.values.length ? "เลือกรายการ" : "ไม่มีรายการในฐานข้อมูล"),
    );
    meta.values.forEach((v) => input.append(option(v, displayValue(v))));
    input.required = true;
  } else {
    input.type = "number";
    input.step = "any";
    input.min = "0";
    input.max = "1000000";
    input.required = true;
  }
  input.value = value;
  return input;
}

function defaultValue(field) {
  return "";
}

function clearStatus() {
  $("save-status").textContent = "";
}

function render() {
  $("conditions").replaceChildren(); // ลบเงื่อนไขเดิมทั้งหมด
  $("condition-count").textContent = // อัปเดตข้อความนับจำนวนเงื่อนไข
    conditions.length + " เงื่อนไข · ต้องตรงทุกข้อ";
  conditions.forEach((c, index) => {  // c = เงื่อนไขแต่ละข้อ, index = ลำดับของเงื่อนไข
    if (index) {
      const join = document.createElement("div");
      join.className = "join";
      join.textContent = "และ";
      $("conditions").append(join); // เพิ่มข้อความ "และ" ระหว่างเงื่อนไข หาก index = 0 ไม่แสดงข้อความ "และ"
    }
    const row = document.createElement("div");
    row.className = "condition builder-row categorized-row"; // สร้างกล่องสำหรับเงื่อนไขแต่ละข้อ
    const category = document.createElement("select");
    category.id = "category-" + c.id; // สร้าง select สำหรับเลือกหมวดข้อมูล
    Object.entries(categories).forEach(([key, label]) => 
      category.append(option(key, label)),
    );  // Object.entries() แยกข้อมูลออกเป็นคู่ [ชื่อคีย์, ค่า] เช่น: ["physical", "ผลตรวจสุขภาพ"]
    category.value = fields[c.field].category; // กำหนดค่าเริ่มต้นของ select เป็นหมวดข้อมูลของ field ที่เลือกในเงื่อนไข
    category.onchange = () => {
      c.field = Object.keys(fields).find(
        (key) => fields[key].category === category.value,
      );
      c.op = fields[c.field].values ? "eq" : "gte";
      c.value = defaultValue(c.field);
      render();
      $("field-" + c.id).focus();
    };

    const categoryBox = control("หมวดข้อมูล", category);
    categoryBox.className = "category-group";
    row.append(categoryBox); // เพิ่มกล่อง select สำหรับเลือกหมวดข้อมูลลงใน row ของเงื่อนไข

    const field = document.createElement("select"); 
    field.id = "field-" + c.id;
    Object.entries(fields)
      .filter(([, meta]) => meta.category === fields[c.field].category)
      .forEach(([key, m]) => field.append(option(key, m.label))); // ถ้าเลือกหมวดผลตรวจสุขภาพ ก็แสดง BMI น้ำหนัก ส่วนสูง และความดันตามที่กำหนดไว้ใน fields
    field.value = c.field;
    field.onchange = () => {
      c.field = field.value;
      c.op = fields[c.field].values ? "eq" : "gte";
      c.value = defaultValue(c.field);
      render(); 
    }; // จะอัปเดตข้อมูล ล้างค่าที่กรอกเดิม และสร้างช่องใหม่ เพราะหน่วยหรือชนิดช่องอาจเปลี่ยนไป

    const fieldBox = control("ข้อมูลที่ใช้เป็นเงื่อนไข", field);
    fieldBox.className = "field-group";
    row.append(fieldBox); // เพิ่มกล่อง select สำหรับเลือก field ลงใน row ของเงื่อนไข
    const op = document.createElement("select");
    op.id = "op-" + c.id;
    Object.entries(operators)
      .filter(([key]) => !fields[c.field].values || key === "eq")
      .forEach(([key, label]) =>
        op.append(option(key, fields[c.field].values ? "เป็น" : label)),
      ); // ถ้า field เป็นตัวเลือก จะมี operator แค่ "เป็น" (eq) เท่านั้น
    op.value = c.op; // กำหนดค่าเริ่มต้นของ select เป็น operator ของเงื่อนไข
    op.onchange = () => {
      c.op = op.value;
      row.querySelector(".value-suffix").textContent =
        c.op === "gte" ? "ขึ้นไป" : "";
      preview(); // อัปเดตข้อความสรุปกฎด้านล่าง
    };
    row.append(control("เงื่อนไข", op));
    const input = valueInput(c.field, c.value, "value-" + c.id);
    input.oninput = () => {
      c.value = input.value;
      preview();
    }; // อัปเดตค่าของเงื่อนไขและข้อความสรุปกฎด้านล่างเมื่อผู้ใช้กรอกข้อมูล
    row.append(
      control(
        (c.field === "special"
          ? "มีภาวะแทรกซ้อน"
          : fields[c.field].values
            ? "เลือกรายการ"
            : "ตัวเลข") +
          (fields[c.field].unit ? " (" + fields[c.field].unit + ")" : ""),
        input,
      ),
    ); // เพิ่มกล่อง input สำหรับกรอกค่าของเงื่อนไขลงใน row ของเงื่อนไข
    const suffix = document.createElement("span");
    suffix.className = "value-suffix";
    input.parentElement.append(suffix); // เพิ่มข้อความ "ขึ้นไป" หรือ "" หลังกล่อง input ของเงื่อนไข
    if (fields[c.field].values) {
      op.parentElement.hidden = true;
      input.parentElement.classList.add("categorical-value");
    } // ถ้า field เป็นตัวเลือก จะซ่อน select ของ มากกว่าน้อยกว่า และเพิ่ม class "categorical-value" ให้กับกล่อง input ของเงื่อนไข
    if (c.field === "special") {
      suffix.textContent =
        "เพิ่มเงื่อนไขอีกข้อเพื่อระบุว่าต้องมีหลายภาวะร่วมกัน";
    } // ถ้า field เป็นภาวะแทรกซ้อน จะเพิ่มข้อความแนะนำให้ผู้ใช้เพิ่มเงื่อนไขอีกข้อเพื่อระบุว่าต้องมีหลายภาวะร่วมกัน

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "ลบเงื่อนไขที่ " + (index + 1));
    remove.disabled = conditions.length === 1;
    remove.onclick = () => {
      conditions = conditions.filter((item) => item.id !== c.id);
      render();
    }; // ลบเงื่อนไขออกจาก array และเรียก render() เพื่ออัปเดตหน้าจอ
    row.append(remove);
    $("conditions").append(row);
  }); // เพิ่ม row ของเงื่อนไขทั้งหมดลงใน div id="conditions"
  preview(); // อัปเดตข้อความสรุปกฎด้านล่าง
}

function preview() {
  clearStatus();
  for (const outcome of outcomes) { // outcome = ผลลัพธ์แต่ละข้อ
    const hint = $("met-hint-" + outcome.id); // hint = ข้อความแนะนำช่วง MET ของผลลัพธ์แต่ละข้อ
    if (hint) {
      const intensity = results.intensity.find(
        (item) => item.value === outcome.intensity,
      );
      hint.textContent = intensity
        ? "ช่วงที่ระบบใช้: " + intensityMetLabel(intensity)
        : "เลือกความหนักเพื่อกำหนดช่วง MET อัตโนมัติ";
    } // อัปเดตข้อความแนะนำช่วง MET ของผลลัพธ์แต่ละข้อ
    const item = results[outcome.action]?.find(
      (item) => item.value === outcome.result,
    ); // item = ผลลัพธ์ที่เลือกใน select ของผลลัพธ์แต่ละข้อ
    const description = $("output-description-" + outcome.id); // description = ข้อความสรุปของผลลัพธ์แต่ละข้อ
    if (description) {
      description.textContent = item ? resultId(item) + " — " + item.label : "";
      description.hidden = !item;
    }
  }
  const sentence =
    "ถ้าผู้ป่วย" +
    conditions.map(describeCondition).join("\nและ") +
    "\nให้" +
    resultText(); 
  $("preview-sentence").textContent = sentence; // แสดงข้อความสรุปของกฎทั้งหมดด้านล่าง
}

function outputSelect(items, value, id, showId = false, hierarchy = false) {
  if (showId) {
    const picker = document.createElement("details");
    picker.className = "result-picker";
    const summary = document.createElement("summary");
    summary.id = id;
    summary.textContent = "เลือกรายการ";
    summary.setAttribute("aria-label", "เลือกรายการผลลัพธ์");
    const list = document.createElement("div");
    list.className = "result-picker-list";
    picker.value = value || "";
    [...items].sort((a, b) => resultId(a).localeCompare(resultId(b), undefined, { numeric: true })).forEach((item) => {
      const label = document.createElement("label");
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = id;
      radio.value = item.value;
      radio.required = true;
      radio.checked = item.value === value;
      const text = (item.label === resultId(item) ? "ยังไม่มีคำอธิบาย" : item.label) + " (" + resultId(item) + ")";
      if (radio.checked) summary.textContent = text;
      radio.addEventListener("invalid", () => { picker.open = true; });
      radio.addEventListener("change", () => {
        picker.value = radio.value;
        summary.textContent = text;
        picker.open = false;
        summary.focus();
      });
      label.append(radio, document.createTextNode(text));
      list.append(label);
    });
    if (!items.length) {
      // Keep native required validation when the catalog has no selectable items.
      return outputSelect(items, value, id);
    }
    picker.append(summary, list);
    return picker;
  }
  const input = document.createElement("select");
  input.id = id;
  input.required = true;
  input.append(
    option("", items.length ? "เลือกรายการ" : "ไม่มีรายการในฐานข้อมูล"),
  );
  const byId = new Map(items.map((item) => [item.value, item]));
  const depth = (item) => {
    const seen = new Set([item.value]);
    let n = 0;
    while (byId.has(item.parent) && !seen.has(item.parent) && n < 6) {
      seen.add(item.parent);
      item = byId.get(item.parent);
      n++;
    }
    return n;
  };
  const ordered = [...items].sort((a, b) =>
    resultId(a).localeCompare(resultId(b), undefined, { numeric: true }),
  );
  if (hierarchy) ordered.sort((a, b) => depth(a) - depth(b));
  ordered.forEach((item) => {
    const label =
      hierarchy && resultId(item) === "Exercise"
        ? "ExerciseCategory (ทุกหมวด)"
        : showId
          ? (item.label === resultId(item)
              ? "ยังไม่มีคำอธิบาย"
              : item.label) + " (" + resultId(item) + ")"
          : item.label.length > 55
            ? item.label.slice(0, 52) + "…"
            : item.label;
    input.append(
      option(item.value, (hierarchy ? "· ".repeat(depth(item)) : "") + label),
    );
  });
  input.value = value || "";
  return input;
} // สร้าง select โดยแสดงคำอธิบายพร้อมรหัส หรือแสดงลำดับชั้นของหมวดหมู่

function newOutcome() {
  return {
    id: nextId++,
    action: "warning",
    result: "",
    intensity: "",
    use_favorites: true,
  };
} // สร้างผลลัพธ์ใหม่ โดยกำหนดค่าเริ่มต้นเป็นคำเตือน และให้ใช้หมวดที่ผู้ป่วยชอบ

function renderOutputs() {
  $("outputs").replaceChildren(); // ลบผลลัพธ์เดิมทั้งหมด
  outcomes.forEach((outcome, index) => {
    const box = document.createElement("div");
    box.className = "output-card";
    const top = document.createElement("div");
    top.className = "output-heading";
    const title = document.createElement("strong");
    title.textContent = "ผลลัพธ์ที่ " + (index + 1);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove";
    remove.textContent = "×";
    remove.disabled = outcomes.length === 1;
    remove.setAttribute("aria-label", "ลบผลลัพธ์ที่ " + (index + 1));
    remove.onclick = () => {
      outcomes = outcomes.filter((item) => item.id !== outcome.id);
      renderOutputs(); // ลบผลลัพธ์ออกจาก array และเรียก renderOutputs() เพื่ออัปเดตหน้าจอ
    };
    top.append(title, remove);
    box.append(top);
    const grid = document.createElement("div");
    grid.className = "action-grid";
    const action = document.createElement("select");
    action.id = "output-action-" + outcome.id;
    Object.entries(actionLabels).forEach(([key, label]) =>
      action.append(option(key, label)),
    ); // สร้าง select สำหรับเลือกประเภทผลลัพธ์ โดยมีตัวเลือกเป็นคำเตือน แนะนำหมวดออกกำลังกาย ข้อควรหลีกเลี่ยง และความถี่ในการออกกำลังกาย
    action.value = outcome.action;
    action.onchange = () => {
      outcome.action = action.value;
      outcome.result = "";
      renderOutputs();
    }; // อัปเดตประเภทผลลัพธ์และล้างค่าที่เลือกเดิม จากนั้นเรียก renderOutputs() เพื่ออัปเดตหน้าจอ
    grid.append(control("ประเภทผลลัพธ์", action));
    const select = outputSelect(
      results[outcome.action] || [],
      outcome.result,
      "output-result-" + outcome.id,
      ["warning", "avoid", "frequency"].includes(outcome.action),
      outcome.action === "exercise", // ถ้าเป็นผลลัพธ์ประเภทแนะนำหมวดออกกำลังกาย ให้แสดงลำดับชั้นของผลลัพธ์
    );
    select.onchange = () => {
      outcome.result = select.value;
      preview(); // อัปเดตข้อความสรุปกฎด้านล่างเมื่อผู้ใช้เลือกผลลัพธ์
    };
    grid.append(
      control(
        outcome.action === "exercise" ? "เลือกหมวดออกกำลังกาย" : "เลือกรายการ",
        select,
      ),
    );
    box.append(grid);
    if (outcome.action === "exercise") {
      const details = document.createElement("div");
      details.className = "exercise-settings";
      const intensity = outputSelect(
        results.intensity || [],
        outcome.intensity,
        "intensity-" + outcome.id,
      );
      intensity.onchange = () => {
        outcome.intensity = intensity.value;
        preview();
      };
      details.append(control("ความหนักในการออกกำลังกาย", intensity));
      box.append(details);
      const range = document.createElement("div");
      range.id = "met-hint-" + outcome.id;
      range.className = "hint";
      range.setAttribute("aria-live", "polite");
      box.append(range);
      const favorite = document.createElement("input");
      favorite.type = "checkbox";
      favorite.id = "favorites-" + outcome.id;
      favorite.checked = outcome.use_favorites;
      favorite.onchange = () => {
        outcome.use_favorites = favorite.checked;
        preview();
      };
      const label = document.createElement("label");
      label.className = "favorite-choice";
      label.htmlFor = favorite.id;
      label.append(
        favorite,
        document.createTextNode("เลือกเฉพาะกิจกรรมในหมวดที่ผู้ป่วยชอบ"),
      );
      box.append(label);
      const note = document.createElement("div");
      note.className = "hint";
      note.textContent =
        "ระบบกำหนดช่วง MET จากความหนักที่เลือก แล้วคัดกิจกรรมจากค่า MET ในคลังข้อมูล หากไม่มีกิจกรรมตรงเงื่อนไข กฎทั้งข้อจะไม่ทำงาน";
      box.append(note);
    }
    const description = document.createElement("div");
    description.id = "output-description-" + outcome.id;
    description.hidden = true;
    $("outputs").append(box); 
  });
  preview();
}

function reset() {
  conditions = [{ id: nextId++, field: "bmi", op: "gte", value: "" }];
  customName = false;
  outcomes = [newOutcome()];
  renderOutputs();
  render();
} // รีเซ็ตกฎทั้งหมดกลับไปเป็นค่าเริ่มต้น โดยมีเงื่อนไขเดียวคือ BMI และผลลัพธ์เดียวคือคำเตือน

$("add").onclick = () => {
  if (conditions.length >= 30) {
    $("save-status").textContent = "เพิ่มได้สูงสุด 30 เงื่อนไขต่อกฎ";
    return;
  }
  const id = nextId++; // เพิ่ม id ใหม่สำหรับเงื่อนไขใหม่
  conditions.push({ id, field: "sbp", op: "gte", value: "" });
  render();
  $("category-" + id).focus();
}; // เพิ่มเงื่อนไขใหม่ โดยกำหนดค่าเริ่มต้นเป็นความดันตัวบน (sbp) และเรียก render() เพื่ออัปเดตหน้าจอ

$("name").oninput = () => {
  customName = true;
  clearStatus();
}; // เมื่อผู้ใช้กรอกชื่อกฎเอง ให้ตั้งตัวแปร customName เป็น true เพื่อไม่ให้ระบบเปลี่ยนชื่อกฎอัตโนมัติ และล้างข้อความสถานะการบันทึก

$("add-output").onclick = () => {
  if (outcomes.length >= 30) {
    $("save-status").textContent = "เพิ่มผลลัพธ์ได้สูงสุด 30 รายการ";
    return;
  }
  outcomes.push(newOutcome());
  renderOutputs();
  $("output-action-" + outcomes.at(-1).id).focus();
}; // เพิ่มผลลัพธ์ใหม่ โดยเรียก newOutcome() เพื่อสร้างผลลัพธ์ใหม่ และเรียก renderOutputs() เพื่ออัปเดตหน้าจอ

$("reset").onclick = reset;
let saving = false;
async function showSaveMessage(success, message) {
  const title = success ? "เพิ่มกฎสำเร็จ" : "เพิ่มกฎไม่สำเร็จ";
  if (window.Swal) {
    try {
      await window.Swal.fire({
        icon: success ? "success" : "error",
        title,
        text: message,
        confirmButtonText: success ? "กลับหน้ารวมกฎ" : "กลับไปแก้ไข",
        confirmButtonColor: "#3366cc",
        allowOutsideClick: false,
        allowEscapeKey: false,
      });
      return;
    } catch (_) {
    }
  }
  window.alert(title + "\n" + message);
} // แสดงข้อความแจ้งเตือนการบันทึกกฎ โดยใช้ SweetAlert2 ถ้าไม่สามารถใช้ได้ ให้ใช้ alert ธรรมดาแทน 

// กดบันทึกกฎ → ตรวจข้อมูล → ส่งไป Backend → แจ้งผล → กลับหน้ารวมกฎ
$("builder").onsubmit = async (event) => {
  event.preventDefault(); // ป้องกันการ submit form แบบปกติ
  if (saving || !validateRule()) return; // ถ้ากำลังบันทึกอยู่หรือข้อมูลไม่ถูกต้อง ให้หยุดการทำงาน
  if (!$("name").value.trim()) {
    $("save-status").textContent = "กรุณาระบุชื่อกฎ";
    $("name").focus();
    return;
  } // ถ้าชื่อกฎว่าง ให้แสดงข้อความแจ้งเตือนและ focus ไปที่ช่องกรอกชื่อกฎ
  const payload = {
    name: $("name").value.trim(),
    conditions: conditions.map(({ field, op, value }) => ({
      field,
      op,
      value,
    })),
    outputs: outcomes.map(({ id, ...outcome }) => outcome),
  }; // สร้าง payload สำหรับส่งไป Backend โดยเอาเฉพาะ field, op, value ของเงื่อนไข และเอาเฉพาะ action, result, intensity, use_favorites ของผลลัพธ์
  saving = true;
  const controls = Array.from(
    $("builder").querySelectorAll("input,select,button"),
  ); // เก็บ element ทั้งหมดใน form เพื่อปิดการใช้งานชั่วคราว

  const disabled = controls.map((input) => input.disabled);
  controls.forEach((input) => (input.disabled = true)); 
  // ปิดการใช้งาน element ทั้งหมดใน form เพื่อป้องกันผู้ใช้แก้ไขข้อมูลระหว่างบันทึก

  $("save-status").dataset.state = "loading"; // แสดงข้อความกำลังบันทึก
  $("save-status").textContent = "กำลังตรวจสอบรายการล่าสุดและบันทึกกฎ…"; // แสดงข้อความกำลังตรวจสอบรายการล่าสุดและบันทึกกฎ
  try {
    const response = await fetch("/admin/api/swrl/rules/builder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.redirected)
      throw new Error(
        "เซสชันหมดอายุหรือไม่มีสิทธิ์ กรุณาเข้าสู่ระบบแอดมินอีกครั้ง",
      );
    const result = await response.json();
    if (!response.ok || !result.success)
      throw new Error(result.message || "ไม่สามารถบันทึกกฎได้");
  } catch (error) {
    const message =
      error instanceof TypeError || error instanceof SyntaxError
        ? "ไม่สามารถยืนยันผลการบันทึกได้ กรุณาตรวจหน้ารวมกฎก่อนลองบันทึกอีกครั้ง"
        : error.message;
    $("save-status").dataset.state = "error";
    $("save-status").textContent = message;
    await showSaveMessage(false, message);
    controls.forEach((input, i) => (input.disabled = disabled[i]));
    saving = false;
    return;
  } // ถ้าเกิดข้อผิดพลาดในการบันทึกกฎ ให้แสดงข้อความแจ้งเตือนและเปิดใช้งาน element ทั้งหมดใน form อีกครั้ง
  const message =
    "บันทึกกฎ “" +
    payload.name +
    "” เรียบร้อยแล้ว กฎจะใช้ในการประมวลผลคำแนะนำครั้งถัดไป";
  $("save-status").dataset.state = "success";
  $("save-status").textContent = message;
  await showSaveMessage(true, message);
  window.location.href = "/admin/swrl";
};

document.addEventListener("DOMContentLoaded", () => {
  const link = document.querySelector('.sidebar a[href="/admin/swrl"]');
  if (link) {
    link.classList.add("active");
    link.closest(".collapse")?.classList.add("show");
    document
      .querySelector('[href="#masterDataMenu"]')
      ?.setAttribute("aria-expanded", "true");
  }
}); // เมื่อโหลดหน้าเว็บเสร็จ ให้เพิ่ม class "active" ให้กับเมนูด้านข้างที่ตรงกับหน้ารวมกฎ และเปิดเมนูย่อย masterDataMenu ถ้ามี
reset();

// Voice input only prepares a draft; the existing save flow remains explicit.
(() => {
  const panel = $("voice-panel");
  const text = $("voice-text");
  const status = $("voice-status");
  const record = $("voice-record");
  const convert = $("voice-convert");
  let recognition, listening = false, draft = null, pending = false;
  const invalidate = () => { draft = null; $("voice-review").hidden = true; };
  text.addEventListener("input", invalidate);
  $("voice-open").onclick = () => {
    panel.hidden = !panel.hidden;
    $("voice-open").setAttribute("aria-expanded", String(!panel.hidden));
    if (panel.hidden) recognition?.stop();
    else text.focus();
  };
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Speech) {
    record.disabled = true;
    status.textContent = "เบราว์เซอร์นี้ไม่รองรับการรับเสียง สามารถพิมพ์ข้อความเพื่อสร้างร่างได้";
  } else {
    recognition = new Speech();
    recognition.lang = "th-TH";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onstart = () => {
      listening = true; convert.disabled = true;
      record.textContent = "หยุดพูด";
      status.textContent = "กำลังฟัง…";
    };
    recognition.onresult = (event) => {
      invalidate();
      const transcript = Array.from(event.results).map(r => r[0].transcript).join(" ");
      text.value = (text.value + " " + transcript).trim().slice(0, 4000);
      status.textContent = "รับข้อความแล้ว ตรวจตัวเลขและคำเปรียบเทียบก่อนแปลงเป็นร่าง";
    };
    recognition.onerror = () => { status.textContent = "รับเสียงไม่สำเร็จ ตรวจสิทธิ์ไมโครโฟนและอินเทอร์เน็ต หรือพิมพ์ข้อความแทน"; };
    recognition.onend = () => { listening = false; record.textContent = "เริ่มพูด"; convert.disabled = pending; };
    record.onclick = () => {
      if (listening) recognition.stop();
      else { try { recognition.start(); } catch { status.textContent = "เปิดไมโครโฟนไม่ได้ กรุณาลองใหม่"; } }
    };
  }
  convert.onclick = async () => {
    if (pending || listening || saving) return;
    const instruction = text.value.trim();
    if (!instruction) { status.textContent = "กรุณาพูดหรือพิมพ์ข้อความก่อน"; return; }
    invalidate(); pending = true; convert.disabled = true; record.disabled = true; text.disabled = true;
    status.textContent = "กำลังแปลงข้อความเป็นร่างกฎ…";
    try {
      const response = await fetch("/admin/api/swrl/rules/voice-draft", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({text: instruction}),
        signal: AbortSignal.timeout(60000),
      });
      if (response.redirected) throw new Error("กรุณาเข้าสู่ระบบแอดมินใหม่");
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.message || "สร้างร่างไม่สำเร็จ");
      draft = result.draft;
      // Resolve using the page catalog too, in case it changed while this page was open.
      if (!draft.conditions.every(c => fields[c.field] && operators[c.op]) ||
          !draft.outputs.every(o => results[o.action]?.some(i => i.value === o.result) &&
            (o.action !== "exercise" || results.intensity.some(i => i.value === o.intensity)))) {
        throw new Error("รายการในหน้าจอไม่ตรงกับฐานข้อมูล กรุณาโหลดหน้าใหม่");
      }
      const outputLines = draft.outputs.map(o => {
        let line = actionLabels[o.action] + ": " + results[o.action].find(i => i.value === o.result).label;
        if (o.action === "exercise") line += " · " + results.intensity.find(i => i.value === o.intensity).label + (o.use_favorites ? " · เฉพาะหมวดที่ชอบ" : " · ไม่จำกัดหมวดที่ชอบ");
        return line;
      });
      $("voice-draft-text").textContent = draft.name + "\n\nเงื่อนไข (ต้องตรงทุกข้อ)\n• " + draft.conditions.map(describeCondition).join("\n• ") + "\n\nผลลัพธ์\n• " + outputLines.join("\n• ");
      $("voice-review").hidden = false;
      status.textContent = "ตรวจร่าง โดยเฉพาะตัวเลขและผลลัพธ์ก่อนนำไปใช้";
    } catch (error) {
      invalidate(); status.textContent = error.name === "TimeoutError" ? "หมดเวลารอ กรุณาลองใหม่ ยังไม่มีการบันทึกกฎ" : error.message;
    } finally { pending = false; convert.disabled = false; record.disabled = !Speech; text.disabled = false; }
  };
  $("voice-apply").onclick = () => {
    if (!draft || saving) return;
    conditions = draft.conditions.map(c => ({...c, id: nextId++}));
    outcomes = draft.outputs.map(o => ({...o, id: nextId++}));
    customName = true; $("name").value = draft.name;
    render(); renderOutputs();
    invalidate(); status.textContent = "เติมฟอร์มแล้ว ตรวจสอบอีกครั้งและกดบันทึกเมื่อพร้อม";
    $("name").focus();
  };
})();
