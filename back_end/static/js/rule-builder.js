
      "use strict";
      const catalog = JSON.parse(document.getElementById('builder-catalog').textContent);
      const categories = catalog.categories;
      const fields = catalog.fields;
      Object.values(fields).forEach(meta => {
        if (meta.options) meta.values = meta.options.map(item => item.value);
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
      const actionLabels = {warning:'คำเตือน',exercise:'แนะนำหมวดออกกำลังกาย',avoid:'ข้อควรหลีกเลี่ยง',frequency:'ความถี่ในการออกกำลังกาย'};
      let nextId = 0;
      let customName = false;
      const $ = (id) => document.getElementById(id);
      function displayValue(value) {
        for (const meta of Object.values(fields)) {
          const item = meta.options?.find(item => item.value === value);
          if (item) return item.label;
        }
        return value;
      }
      function allConditions() {
        return conditions;
      }
      function describeCondition(c) {
        const value = c.value === '' ? '[ยังไม่ได้ใส่ตัวเลข]' : displayValue(c.value);
        if (c.field === 'special') return 'มี ' + (c.value ? value : '[ยังไม่ได้เลือกรายการ]');
        if (c.field === 'type') return 'เป็น ' + (c.value ? value : '[ยังไม่ได้เลือกรายการ]');
        if (fields[c.field].values) return fields[c.field].label + 'เป็น ' + value;
        return [fields[c.field].label, operators[c.op], value, fields[c.field].unit || '', c.op === 'gte' ? 'ขึ้นไป' : ''].filter(Boolean).join(' ');
      }
      function intensityMetLabel(intensity) {
        if (typeof intensity?.met_label === 'string' && intensity.met_label.trim()) {
          return intensity.met_label;
        }
        // Older open pages may have a catalog without the new met_label field.
        const ranges = {
          'http://example.org/diabetes#Light': 'MET < 3',
          'http://example.org/diabetes#Moderate': '3 ≤ MET ≤ 6',
          'http://example.org/diabetes#Vigorous': 'MET > 6',
        };
        return ranges[intensity?.value] || 'ยังไม่มีข้อมูลช่วง MET กรุณาโหลดหน้าใหม่';
      }
      function resultText() {
        return outcomes.map(outcome => {
          const item = results[outcome.action]?.find(item => item.value === outcome.result);
          let text = actionLabels[outcome.action] + ': ' + (item?.label || '[ยังไม่ได้เลือกรายการ]');
          if (outcome.action === 'exercise') {
            const intensity = results.intensity.find(item => item.value === outcome.intensity);
            text += ' · ความหนัก ' + (intensity?.label || '[ยังไม่ได้เลือก]') + (intensity ? ' · ' + intensityMetLabel(intensity) : '');
            if (outcome.use_favorites) text += ' · เฉพาะหมวดที่ผู้ป่วยชอบ';
          }
          return text;
        }).join('\nและ');
      }
      function resultId(item) {
        return item.value.split(/[#/]/).pop();
      }
      function validateRule() {
        const controls = [$('name'), ...conditions.map(c => $('value-' + c.id)), ...$('outputs').querySelectorAll('select,input')];
        return controls.every(input => input.reportValidity());
      }
      function option(value, label) {
        const o = document.createElement("option");
        o.value = value;
        o.textContent = label;
        return o;
      }
      function control(labelText, element) {
        const box = document.createElement("div");
        const label = document.createElement("label");
        label.htmlFor = element.id;
        label.textContent = labelText;
        box.append(label, element);
        return box;
      }
      function valueInput(field, value, id) {
        const meta = fields[field];
        const input = document.createElement(meta.values ? "select" : "input");
        input.id = id;
        if (meta.values) {
          input.append(option('', meta.values.length ? 'เลือกรายการ' : 'ไม่มีรายการในฐานข้อมูล'));
          meta.values.forEach((v) => input.append(option(v, displayValue(v))));
          input.required = true;
        } else {
          input.type = "number";
          input.step = "any";
          input.min = "0";
          input.max = '1000000';
          input.required = true;
        }
        input.value = value;
        return input;
      }
      function defaultValue(field) {
        return "";
      }
      function clearStatus() {
        $("test-status").textContent = "";
        $("save-status").textContent = "";
      }
      function render() {
        $("conditions").replaceChildren();
        $('condition-count').textContent = conditions.length + ' เงื่อนไข · ต้องตรงทุกข้อ';
        conditions.forEach((c, index) => {
          if (index) {
            const join = document.createElement("div");
            join.className = "join";
            join.textContent = "และ";
            $("conditions").append(join);
          }
          const row = document.createElement("div");
          row.className = "condition builder-row categorized-row";
          const category = document.createElement('select');
          category.id = 'category-' + c.id;
          Object.entries(categories).forEach(([key,label]) => category.append(option(key,label)));
          category.value = fields[c.field].category;
          category.onchange = () => {
            c.field = Object.keys(fields).find(key => fields[key].category === category.value);
            c.op = fields[c.field].values ? 'eq' : 'gte';
            c.value = defaultValue(c.field);
            render();
            $('field-' + c.id).focus();
          };
          const categoryBox = control('หมวดข้อมูล', category);
          categoryBox.className = 'category-group';
          row.append(categoryBox);
          const field = document.createElement("select");
          field.id = "field-" + c.id;
          Object.entries(fields).filter(([,meta]) => meta.category === fields[c.field].category).forEach(([key, m]) =>
            field.append(option(key, m.label)),
          );
          field.value = c.field;
          field.onchange = () => {
            c.field = field.value;
            c.op = fields[c.field].values ? "eq" : "gte";
            c.value = defaultValue(c.field);
            render();
          };
          const fieldBox = control('ข้อมูลที่ใช้เป็นเงื่อนไข', field);
          fieldBox.className = "field-group";
          row.append(fieldBox);
          const op = document.createElement("select");
          op.id = "op-" + c.id;
          Object.entries(operators)
            .filter(([key]) => !fields[c.field].values || key === "eq")
            .forEach(([key, label]) => op.append(option(key, fields[c.field].values ? 'เป็น' : label)));
          op.value = c.op;
          op.onchange = () => {
            c.op = op.value;
            row.querySelector('.value-suffix').textContent = c.op === 'gte' ? 'ขึ้นไป' : '';
            preview();
          };
          row.append(control("เงื่อนไข", op));
          const input = valueInput(c.field, c.value, "value-" + c.id);
          input.oninput = () => {
            c.value = input.value;
            preview();
          };
          row.append(
            control(
              (c.field === 'special' ? "มีภาวะแทรกซ้อน" : fields[c.field].values ? "เลือกรายการ" : "ตัวเลข") +
                (fields[c.field].unit ? " (" + fields[c.field].unit + ")" : ""),
              input,
            ),
          );
          const suffix = document.createElement('span');
          suffix.className = 'value-suffix';
          suffix.textContent = c.op === 'gte' ? 'ขึ้นไป' : '';
          input.parentElement.append(suffix);
          if (fields[c.field].values) {
            op.parentElement.hidden = true;
            input.parentElement.classList.add('categorical-value');
          }
          if (c.field === 'special') {
            suffix.textContent = 'เพิ่มเงื่อนไขอีกข้อเพื่อระบุว่าต้องมีหลายภาวะร่วมกัน';
          }
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "remove";
          remove.textContent = "×";
          remove.setAttribute("aria-label", "ลบเงื่อนไขที่ " + (index + 1));
          remove.disabled = conditions.length === 1;
          remove.onclick = () => {
            conditions = conditions.filter((item) => item.id !== c.id);
            render();
          };
          row.append(remove);
          $("conditions").append(row);
        });
        renderTest();
        preview();
      }
      function renderTest() {
        const old = {};
        $("test-fields")
          .querySelectorAll("input,select")
          .forEach((el) => (old[el.dataset.field] = el.multiple ? Array.from(el.selectedOptions, item => item.value) : el.value));
        $("test-fields").replaceChildren();
        [...new Set(allConditions().map((c) => c.field))].forEach((field) => {
          const input = valueInput(
            field,
            fields[field].multiple ? '' : old[field] ?? defaultValue(field),
            "test-" + field,
          );
          input.required = false;
          if (fields[field].values) {
            input.prepend(option('', 'ยังไม่มีข้อมูล'));
            input.value = fields[field].multiple ? '' : old[field] ?? '';
          }
          if (fields[field].multiple) {
            input.multiple = true;
            input.size = Math.min(5, input.options.length);
            Array.from(input.options).forEach(item => item.selected = (old[field] || []).includes(item.value));
          }
          input.dataset.field = field;
          input.oninput = () => {
            input.setCustomValidity('');
            $("test-status").textContent = "";
          };
          const testControl = control(
              fields[field].label +
                (fields[field].unit ? " (" + fields[field].unit + ")" : ""),
              input,
            );
          if (fields[field].multiple) {
            const hint=document.createElement('div');hint.className='hint';hint.textContent='เลือกได้หลายรายการ กด Ctrl หรือ Command ค้างไว้ขณะเลือก';testControl.append(hint);
          }
          $("test-fields").append(testControl);
        });
      }
      function preview() {
        clearStatus();
        for (const outcome of outcomes) {
          const hint = $('met-hint-' + outcome.id);
          if (hint) {
            const intensity = results.intensity.find(item => item.value === outcome.intensity);
            hint.textContent = intensity ? 'ช่วงที่ระบบใช้: ' + intensityMetLabel(intensity) : 'เลือกความหนักเพื่อกำหนดช่วง MET อัตโนมัติ';
          }
          const item = results[outcome.action]?.find(item => item.value === outcome.result);
          const description = $('output-description-' + outcome.id);
          if (description) { description.textContent = item ? resultId(item) + ' — ' + item.label : ''; description.hidden = !item; }
        }
        const sentence = 'ถ้าผู้ป่วย' + conditions.map(describeCondition).join('\nและ') + '\nให้' + resultText();
        $('preview-sentence').textContent = sentence;
        if (!customName) $('name').value = sentence.slice(0, 250);
      }
      function outputSelect(items, value, id, short = false, hierarchy = false) {
        const input = document.createElement('select'); input.id = id; input.required = true;
        input.append(option('', items.length ? 'เลือกรายการ' : 'ไม่มีรายการในฐานข้อมูล'));
        const byId = new Map(items.map(item => [item.value,item]));
        const depth = item => { const seen = new Set([item.value]); let n=0; while(byId.has(item.parent) && !seen.has(item.parent) && n<6){seen.add(item.parent);item=byId.get(item.parent);n++;} return n; };
        const ordered = [...items].sort((a,b) => resultId(a).localeCompare(resultId(b), undefined, {numeric:true}));
        if(hierarchy) ordered.sort((a,b) => depth(a)-depth(b));
        ordered.forEach(item => {
          const label = hierarchy && resultId(item)==='Exercise' ? 'ExerciseCategory (ทุกหมวด)' : short ? resultId(item) : item.label.length>55 ? item.label.slice(0,52)+'…' : item.label;
          input.append(option(item.value, (hierarchy ? '· '.repeat(depth(item)) : '') + label));
        });
        input.value = value || ''; return input;
      }
      function newOutcome() {return {id:nextId++,action:'warning',result:'',intensity:'',use_favorites:true};}
      function renderOutputs() {
        $('outputs').replaceChildren();
        outcomes.forEach((outcome,index) => {
          const box=document.createElement('div');box.className='output-card';
          const top=document.createElement('div');top.className='output-heading';
          const title=document.createElement('strong');title.textContent='ผลลัพธ์ที่ '+(index+1);
          const remove=document.createElement('button');remove.type='button';remove.className='remove';remove.textContent='×';remove.disabled=outcomes.length===1;
          remove.setAttribute('aria-label','ลบผลลัพธ์ที่ '+(index+1));remove.onclick=()=>{outcomes=outcomes.filter(item=>item.id!==outcome.id);renderOutputs();};
          top.append(title,remove);box.append(top);
          const grid=document.createElement('div');grid.className='action-grid';
          const action=document.createElement('select');action.id='output-action-'+outcome.id;
          Object.entries(actionLabels).forEach(([key,label])=>action.append(option(key,label)));action.value=outcome.action;
          action.onchange=()=>{outcome.action=action.value;outcome.result='';renderOutputs();};
          grid.append(control('ประเภทผลลัพธ์',action));
          const select=outputSelect(results[outcome.action]||[],outcome.result,'output-result-'+outcome.id,['warning','avoid','frequency'].includes(outcome.action),outcome.action==='exercise');
          select.onchange=()=>{outcome.result=select.value;preview();};
          grid.append(control(outcome.action==='exercise'?'เลือกหมวดออกกำลังกาย':'เลือกรายการ',select));box.append(grid);
          if(outcome.action==='exercise') {
            const details=document.createElement('div');details.className='exercise-settings';
            const intensity=outputSelect(results.intensity||[],outcome.intensity,'intensity-'+outcome.id);
            intensity.onchange=()=>{outcome.intensity=intensity.value;preview();};details.append(control('ความหนักในการออกกำลังกาย',intensity));box.append(details);
            const range=document.createElement('div');range.id='met-hint-'+outcome.id;range.className='hint';range.setAttribute('aria-live','polite');box.append(range);
            const favorite=document.createElement('input');favorite.type='checkbox';favorite.id='favorites-'+outcome.id;favorite.checked=outcome.use_favorites;favorite.onchange=()=>{outcome.use_favorites=favorite.checked;preview();};
            const label=document.createElement('label');label.className='favorite-choice';label.htmlFor=favorite.id;label.append(favorite,document.createTextNode('เลือกเฉพาะกิจกรรมในหมวดที่ผู้ป่วยชอบ'));box.append(label);
            const note=document.createElement('div');note.className='hint';note.textContent='ระบบกำหนดช่วง MET จากความหนักที่เลือก แล้วคัดกิจกรรมจากค่า MET ในคลังข้อมูล หากไม่มีกิจกรรมตรงเงื่อนไข กฎทั้งข้อจะไม่ทำงาน';box.append(note);
          }
          const description=document.createElement('div');description.id='output-description-'+outcome.id;description.className='result-description';description.hidden=true;box.append(description);
          $('outputs').append(box);
        });preview();
      }
      function reset() {
        conditions = [{ id: nextId++, field: 'bmi', op: 'gte', value: '' }];
        customName = false;
        $('test-panel').open = false;
        outcomes = [newOutcome()];
        $("test-fields").replaceChildren();
        renderOutputs();
        render();
      }
      $("add").onclick = () => {
        if (conditions.length >= 30) {
          $('save-status').textContent = 'เพิ่มได้สูงสุด 30 เงื่อนไขต่อกฎ';
          return;
        }
        const id = nextId++;
        conditions.push({ id, field: "sbp", op: "gte", value: "" });
        render();
        $("category-" + id).focus();
      };
      $("name").oninput = () => { customName = true; clearStatus(); };
      $('add-output').onclick=()=>{if(outcomes.length>=30){$('save-status').textContent='เพิ่มผลลัพธ์ได้สูงสุด 30 รายการ';return;}outcomes.push(newOutcome());renderOutputs();$('output-action-'+outcomes.at(-1).id).focus();};
      $("reset").onclick = reset;
      $("test").onclick = () => {
        if (!validateRule()) return;
        for (const field of new Set(allConditions().map((c) => c.field))) {
          const input = $("test-" + field);
          if (input.value === "" || !input.checkValidity()) {
            $("test-status").textContent =
              input.value === '' ? 'ยังประเมินไม่ได้: ไม่มีข้อมูล' + fields[field].label + ' จึงยังยืนยันไม่ได้ว่าตรงทุกเงื่อนไข' : 'กรุณาใส่ตัวเลขตั้งแต่ 0 ขึ้นไป';
            input.focus();
            return;
          }
        }
        const matched = allConditions().every((c) => {
          const actual = $("test-" + c.field).value;
          if (fields[c.field].multiple) return Array.from($('test-'+c.field).selectedOptions).some(item => item.value === c.value);
          if (fields[c.field].values) return actual === c.value;
          const a = Number(actual),
            b = Number(c.value);
          return {
            gte: a >= b,
            gt: a > b,
            lte: a <= b,
            lt: a < b,
            eq: a === b,
          }[c.op];
        });
        $("test-status").textContent = matched
          ? (outcomes.some(item=>item.action==='exercise') ? 'ตรงเงื่อนไขผู้ป่วยแล้ว แต่ต้องตรวจว่ามีกิจกรรมตรงหมวด MET และความชอบในการประมวลผลจริงก่อน กฎจึงจะทำงาน' : "กฎนี้จะแสดงผล: " + resultText())
          : "กฎนี้จะไม่แสดงผล เพราะข้อมูลตัวอย่างไม่ตรงกับกลุ่มผู้ป่วยหรือเงื่อนไขบางข้อ";
      };
      let saving = false;
      async function showSaveMessage(success, message) {
        const title = success ? 'เพิ่มกฎสำเร็จ' : 'เพิ่มกฎไม่สำเร็จ';
        if (window.Swal) {
          try {
            await window.Swal.fire({
              icon: success ? 'success' : 'error', title, text: message,
              confirmButtonText: success ? 'กลับหน้ารวมกฎ' : 'กลับไปแก้ไข',
              confirmButtonColor: '#3366cc', allowOutsideClick: false,
              allowEscapeKey: false,
            });
            return;
          } catch (_) { /* Keep feedback available if the dialog library fails. */ }
        }
        window.alert(title + '\n' + message);
      }
      $('builder').onsubmit = async event => {
        event.preventDefault();
        if (saving || !validateRule()) return;
        if (!$('name').value.trim()) {
          $('save-status').textContent = 'กรุณาระบุชื่อกฎ';
          $('name').focus();
          return;
        }
        const payload = {name: $('name').value.trim(), conditions: conditions.map(({field,op,value}) => ({field,op,value})), outputs: outcomes.map(({id,...outcome})=>outcome)};
        saving = true;
        const controls = Array.from($('builder').querySelectorAll('input,select,button'));
        const disabled = controls.map(input => input.disabled);
        controls.forEach(input => input.disabled = true);
        $('save-status').dataset.state = 'loading';
        $('save-status').textContent = 'กำลังตรวจสอบรายการล่าสุดและบันทึกกฎ…';
        try {
          const response = await fetch('/admin/api/swrl/rules/builder', {
            method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
          });
          if (response.redirected) throw new Error('เซสชันหมดอายุหรือไม่มีสิทธิ์ กรุณาเข้าสู่ระบบแอดมินอีกครั้ง');
          const result = await response.json();
          if (!response.ok || !result.success) throw new Error(result.message || 'ไม่สามารถบันทึกกฎได้');
        } catch (error) {
          const message = error instanceof TypeError || error instanceof SyntaxError ? 'ไม่สามารถยืนยันผลการบันทึกได้ กรุณาตรวจหน้ารวมกฎก่อนลองบันทึกอีกครั้ง' : error.message;
          $('save-status').dataset.state = 'error';
          $('save-status').textContent = message;
          await showSaveMessage(false, message);
          controls.forEach((input,i) => input.disabled = disabled[i]);
          saving = false;
          return;
        }
        const message = 'บันทึกกฎ “' + payload.name + '” เรียบร้อยแล้ว กฎจะใช้ในการประมวลผลคำแนะนำครั้งถัดไป';
        $('save-status').dataset.state = 'success';
        $('save-status').textContent = message;
        await showSaveMessage(true, message);
        window.location.href = '/admin/swrl';
      };
      document.addEventListener('DOMContentLoaded', () => {
        const link = document.querySelector('.sidebar a[href="/admin/swrl"]');
        if (link) {
          link.classList.add('active');
          link.closest('.collapse')?.classList.add('show');
          document.querySelector('[href="#masterDataMenu"]')?.setAttribute('aria-expanded','true');
        }
      });
      reset();
