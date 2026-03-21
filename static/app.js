/**
 * Kalyan College Management System - Frontend Logic
 * All API interactions, search, CRUD, fee management
 */

// ═══════════════════════════════════════════════════════
//  GLOBAL STATE
// ═══════════════════════════════════════════════════════

let currentPage = 1;
let searchDebounce = null;
let editingStudentId = null;
let coursesCache = [];

// ═══════════════════════════════════════════════════════
//  INITIALIZATION
// ═══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    loadCourses();
    loadDashboard();
    updateThemeIcon();
});

// ═══════════════════════════════════════════════════════
//  NAVIGATION
// ═══════════════════════════════════════════════════════

function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    // Show target
    const target = document.getElementById('sec-' + sectionId);
    if (target) target.classList.add('active');

    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-section="${sectionId}"]`);
    if (navItem) navItem.classList.add('active');

    // Load section specific data
    if (sectionId === 'dashboard') loadDashboard();
    if (sectionId === 'fee-structure') showFeeTab('ug');
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
    }
}

function toggleTheme() {
    const root = document.documentElement;
    const isDark = root.getAttribute('data-theme') === 'dark';
    const newTheme = isDark ? 'light' : 'dark';
    root.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon();
}

function updateThemeIcon() {
    const icon = document.getElementById('theme-icon');
    if (!icon) return;
    if (document.documentElement.getAttribute('data-theme') === 'light') {
        icon.className = 'ph-fill ph-moon';
        icon.style.color = 'inherit';
    } else {
        icon.className = 'ph-fill ph-sun';
        icon.style.color = '#FFBC11';
    }
}

// ═══════════════════════════════════════════════════════
//  API HELPERS
// ═══════════════════════════════════════════════════════

async function api(url, options = {}) {
    try {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'API Error');
        }
        return data;
    } catch (err) {
        showToast(err.message, 'error');
        throw err;
    }
}

// ═══════════════════════════════════════════════════════
//  TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '<i class="ph-fill ph-check-circle" style="color:var(--success)"></i>', error: '<i class="ph-fill ph-x-circle" style="color:var(--danger)"></i>', info: '<i class="ph-fill ph-info" style="color:var(--info)"></i>' };
    toast.innerHTML = `<span>${icons[type] || icons.info}</span> ${message}`;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ═══════════════════════════════════════════════════════
//  MODAL
// ═══════════════════════════════════════════════════════

function openModal(title, bodyHtml) {
    document.getElementById('modal-title').innerHTML = title;
    document.getElementById('modal-body').innerHTML = bodyHtml;
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

// Close modal on overlay click
document.getElementById('modal-overlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
});

// ═══════════════════════════════════════════════════════
//  LOAD COURSES
// ═══════════════════════════════════════════════════════

async function loadCourses() {
    try {
        const data = await api('/api/courses');
        coursesCache = data.courses;
        populateCourseDropdowns(data.courses);
    } catch (e) { }
}

function populateCourseDropdowns(courses) {
    const selects = ['course-select', 'search-course-filter'];
    selects.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const existing = el.querySelector('option');
        el.innerHTML = '';
        if (id === 'search-course-filter') {
            el.innerHTML = '<option value="">All Courses</option>';
        } else {
            el.innerHTML = '<option value="">Select Course</option>';
        }
        courses.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            el.appendChild(opt);
        });
    });
}

// ═══════════════════════════════════════════════════════
//  DASHBOARD
// ═══════════════════════════════════════════════════════

async function loadDashboard() {
    try {
        const data = await api('/api/dashboard');
        document.getElementById('stat-students').textContent = data.total_students.toLocaleString();
        document.getElementById('stat-courses').textContent = data.total_courses;
        document.getElementById('stat-fee-records').textContent = data.total_fee_records.toLocaleString();
        document.getElementById('stat-collected').textContent = '₹' + data.total_fees_collected.toLocaleString();

        // Render distributions
        renderDistribution('course-distribution', data.course_distribution);
        renderDistribution('gender-distribution', data.gender_distribution);
        renderDistribution('category-distribution', data.category_distribution);
    } catch (e) { }
}

function renderDistribution(containerId, data) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!data || Object.keys(data).length === 0) {
        el.innerHTML = '<div class="empty-state"><p>No data yet</p></div>';
        return;
    }
    const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
    el.innerHTML = sorted.map(([name, count]) =>
        `<div class="distribution-item">
            <span class="name">${name || 'Unknown'}</span>
            <span class="count">${count}</span>
        </div>`
    ).join('');
}

// ═══════════════════════════════════════════════════════
//  STUDENT FORM (ADD / EDIT)
// ═══════════════════════════════════════════════════════

async function submitStudent(e) {
    e.preventDefault();
    const form = document.getElementById('student-form');
    const formData = new FormData(form);
    const data = {};
    for (const [key, val] of formData.entries()) {
        data[key] = val.trim();
    }

    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Saving...';

    try {
        if (editingStudentId) {
            await api(`/api/students/${editingStudentId}`, {
                method: 'PUT',
                body: JSON.stringify(data),
            });
            showToast('Student updated successfully!', 'success');
            editingStudentId = null;
            btn.innerHTML = '<i class="ph ph-plus-circle"></i> Add Student';
        } else {
            await api('/api/students', {
                method: 'POST',
                body: JSON.stringify(data),
            });
            showToast('Student added successfully!', 'success');
        }
        form.reset();
    } catch (e) { }

    btn.disabled = false;
    if (!editingStudentId) btn.innerHTML = '<i class="ph ph-plus-circle"></i> Add Student';
}

// ═══════════════════════════════════════════════════════
//  SEARCH STUDENTS
// ═══════════════════════════════════════════════════════

function debounceSearch() {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(searchStudents, 400);
}

async function searchStudents(page = 1) {
    const q = document.getElementById('search-input').value.trim();
    const course = document.getElementById('search-course-filter').value;
    const category = document.getElementById('search-category-filter').value;

    currentPage = page;

    const params = new URLSearchParams({ q, course, category, page, per_page: 20 });

    try {
        const data = await api(`/api/students/search?${params}`);
        renderStudentTable(data);
    } catch (e) { }
}

async function loadAllStudents(page = 1) {
    currentPage = page;
    try {
        const data = await api(`/api/students?page=${page}&per_page=20`);
        renderStudentTable(data);
    } catch (e) { }
}

function renderStudentTable(data) {
    const container = document.getElementById('search-results');
    if (!data.students || data.students.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="icon"><i class="ph ph-mailbox"></i></div><p>No students found</p></div>';
        return;
    }

    let html = `
    <div class="table-wrapper">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Admission No</th>
                    <th>Student Name</th>
                    <th>Course</th>
                    <th>Mobile</th>
                    <th>Gender</th>
                    <th>Category</th>
                    <th>District</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>`;

    data.students.forEach(s => {
        html += `
            <tr>
                <td><strong>${s.admission_no}</strong></td>
                <td>${s.student_name}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">${s.course}</td>
                <td>${s.mobile_no}</td>
                <td>${s.gender}</td>
                <td><span class="badge badge-info">${s.category || '—'}</span></td>
                <td>${s.district}</td>
                <td>
                    <div class="action-btns">
                        <button class="action-btn" onclick="viewStudentDetails(${s.id})" title="View"><i class="ph ph-eye"></i></button>
                        <button class="action-btn edit" onclick="editStudent(${s.id})" title="Edit"><i class="ph ph-pencil-simple"></i></button>
                        <button class="action-btn delete" onclick="deleteStudent(${s.id}, '${s.student_name}')" title="Delete"><i class="ph ph-trash"></i></button>
                        <button class="action-btn fee" onclick="goToFeePayment(${s.id})" title="Fee"><i class="ph ph-currency-circle-dollar"></i></button>
                    </div>
                </td>
            </tr>`;
    });

    html += '</tbody></table></div>';

    // Pagination
    html += `<div class="pagination">
        <button ${data.page <= 1 ? 'disabled' : ''} onclick="searchStudents(${data.page - 1})">← Prev</button>
        <span class="pagination-info">Page ${data.page} of ${data.total_pages} (${data.total} students)</span>
        <button ${data.page >= data.total_pages ? 'disabled' : ''} onclick="searchStudents(${data.page + 1})">Next →</button>
    </div>`;

    container.innerHTML = html;
}

// ═══════════════════════════════════════════════════════
//  VIEW STUDENT DETAILS
// ═══════════════════════════════════════════════════════

async function viewStudentDetails(id) {
    try {
        const data = await api(`/api/students/${id}`);
        const s = data.student;

        const fields = [
            ['Admission No', s.admission_no], ['Student Name', s.student_name],
            ['Mobile No', s.mobile_no], ['Course', s.course],
            ['Subject', s.subject], ['Admission Date', s.admission_date],
            ['Father Name', s.father_name], ['Mother Name', s.mother_name],
            ['Father Occupation', s.father_occupation], ['Date of Birth', s.dob],
            ['Gender', s.gender], ['Category', s.category],
            ['Subcast', s.subcast], ['Permanent Address', s.permanent_address],
            ['Present Address', s.present_address], ['District', s.district],
            ['State', s.state], ['Domicile', s.domicile],
            ['Email', s.email], ['Aadhaar No', s.aadhaar_no],
            ['Subject 4', s.subject_4], ['Subject 5', s.subject_5],
            ['Subject 6', s.subject_6], ['Last Exam', s.last_exam],
            ['Last Exam Year', s.last_exam_year], ['Last Subject', s.last_subject],
            ['Last Roll No', s.last_roll_no], ['Last Enroll No', s.last_enroll_no],
            ['Board', s.board], ['Total Marks', s.total_marks],
            ['Obtained Marks', s.obtain_marks], ['Division', s.division],
            ['Percentage', s.percentage], ['Remark', s.remark],
        ];

        let html = '<div class="form-grid" style="gap:10px;">';
        fields.forEach(([label, val]) => {
            html += `<div class="form-group" style="gap:2px;">
                <span class="form-label">${label}</span>
                <div style="padding:6px 0;color:var(--text-primary);font-size:0.85rem;">${val || '—'}</div>
            </div>`;
        });
        html += '</div>';

        openModal(`<i class="ph ph-clipboard-text"></i> ${s.student_name}`, html);
    } catch (e) { }
}

// ═══════════════════════════════════════════════════════
//  EDIT STUDENT
// ═══════════════════════════════════════════════════════

async function editStudent(id) {
    try {
        const data = await api(`/api/students/${id}`);
        const s = data.student;

        editingStudentId = id;
        showSection('add-student');

        // Fill form
        const form = document.getElementById('student-form');
        const fields = [
            'admission_no', 'student_name', 'mobile_no', 'course', 'subject',
            'admission_date', 'father_name', 'mother_name', 'father_occupation',
            'dob', 'gender', 'category', 'subcast', 'permanent_address',
            'present_address', 'district', 'state', 'domicile', 'email',
            'aadhaar_no', 'subject_4', 'subject_5', 'subject_6', 'last_exam',
            'last_exam_year', 'last_subject', 'last_roll_no', 'last_enroll_no',
            'board', 'total_marks', 'obtain_marks', 'division', 'percentage', 'remark',
        ];

        fields.forEach(f => {
            const el = form.querySelector(`[name="${f}"]`);
            if (el) el.value = s[f] || '';
        });

        document.getElementById('submit-btn').innerHTML = '<i class="ph ph-floppy-disk"></i> Update Student';
        showToast('Editing student: ' + s.student_name, 'info');
    } catch (e) { }
}

// ═══════════════════════════════════════════════════════
//  DELETE STUDENT
// ═══════════════════════════════════════════════════════

async function deleteStudent(id, name) {
    const html = `
        <p style="margin-bottom:20px;">Are you sure you want to delete <strong>${name}</strong>? This action cannot be undone.</p>
        <div class="btn-group">
            <button class="btn btn-danger" onclick="confirmDelete(${id})"><i class="ph ph-trash"></i> Yes, Delete</button>
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        </div>`;
    openModal('<i class="ph ph-warning-circle" style="color:var(--warning)"></i> Confirm Delete', html);
}

async function confirmDelete(id) {
    try {
        await api(`/api/students/${id}`, { method: 'DELETE' });
        showToast('Student deleted successfully', 'success');
        closeModal();
        searchStudents(currentPage);
    } catch (e) { }
}

// ═══════════════════════════════════════════════════════
//  CSV IMPORT
// ═══════════════════════════════════════════════════════

async function handleCSVUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const resultDiv = document.getElementById('import-result');
    resultDiv.innerHTML = '<div class="loading-overlay"><span class="spinner"></span> Importing...</div>';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/students/import-csv', {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || 'Import failed');
        }

        resultDiv.innerHTML = `
            <div class="glass-card" style="margin-top:16px;">
                <h3 style="margin-bottom:12px;"><i class="ph-fill ph-check-circle" style="color:var(--success)"></i> Import Complete</h3>
                <div class="fee-summary">
                    <div class="fee-summary-item">
                        <div class="label">Imported</div>
                        <div class="value paid">${data.imported}</div>
                    </div>
                    <div class="fee-summary-item">
                        <div class="label">Skipped</div>
                        <div class="value balance">${data.skipped}</div>
                    </div>
                </div>
                ${data.errors && data.errors.length > 0 ?
                `<p style="color:var(--danger);font-size:0.8rem;margin-top:10px;">Errors: ${data.errors.join(', ')}</p>` : ''}
            </div>`;

        showToast(data.message, 'success');
    } catch (err) {
        resultDiv.innerHTML = `<p style="color:var(--danger);"><i class="ph-fill ph-x-circle"></i> ${err.message}</p>`;
        showToast(err.message, 'error');
    }

    e.target.value = '';
}

// ═══════════════════════════════════════════════════════
//  FEE STRUCTURE VIEW
// ═══════════════════════════════════════════════════════

let feeStructureCache = null;

async function loadFeeStructure() {
    if (feeStructureCache) return feeStructureCache;
    try {
        const data = await api('/api/fee-structure');
        feeStructureCache = data.structures;
        return data.structures;
    } catch (e) {
        return [];
    }
}

async function showFeeTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    const container = document.getElementById('fee-tab-content');
    const structures = await loadFeeStructure();

    if (tab === 'ug') {
        const ug = structures.filter(s => !s.course.startsWith('M.') && !s.course.startsWith('PGDCA'));
        renderFeeInstallmentTable(container, ug, 'UG Courses Fee Structure (2024)');
    } else if (tab === 'pg') {
        const pg = structures.filter(s => s.course.startsWith('M.') || s.course.startsWith('PGDCA'));
        renderFeeInstallmentTable(container, pg, 'PG Courses Fee Structure (2024)');
    } else if (tab === 'detail') {
        renderFeeDetailTable(container, structures);
    }
}

function renderFeeInstallmentTable(container, structures, title) {
    let html = `<h3 style="margin-bottom:16px;">${title}</h3>
    <div class="table-wrapper">
    <table class="fee-table">
        <thead>
            <tr>
                <th>Course</th>
                <th>Various (A)</th>
                <th>Tuition (A)</th>
                <th>Practical (A)</th>
                <th>1st Installment</th>
                <th>Various (B)</th>
                <th>Tuition (B)</th>
                <th>Practical (B)</th>
                <th>2nd Installment</th>
                <th>Year Total</th>
            </tr>
        </thead>
        <tbody>`;

    structures.forEach(s => {
        const f = s.installments.first;
        const sc = s.installments.second;
        html += `<tr>
            <td><strong>${s.course}</strong></td>
            <td>₹${f.various.toLocaleString()}</td>
            <td>₹${f.tuition.toLocaleString()}</td>
            <td>${f.practical ? '₹' + f.practical.toLocaleString() : '—'}</td>
            <td class="fee-highlight">₹${f.total.toLocaleString()}</td>
            <td>₹${sc.various.toLocaleString()}</td>
            <td>₹${sc.tuition.toLocaleString()}</td>
            <td>${sc.practical ? '₹' + sc.practical.toLocaleString() : '—'}</td>
            <td class="fee-highlight">₹${sc.total.toLocaleString()}</td>
            <td class="fee-highlight" style="font-size:0.9rem;">₹${s.installments.year_total.toLocaleString()}</td>
        </tr>`;
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

function renderFeeDetailTable(container, structures) {
    const heads = [
        'Admission Fees', 'Amalgamated Fund', 'Library Development',
        'Home Examination', 'Establishment Fund', 'Student Development',
        'College Development', 'Cycle Stand', 'Caution Money (Ref.)',
        'Seminar / Workshop', 'Computer Maint.', 'Physical Education',
        'Non Aided Staff Fund', 'Gym Development', 'TOTAL'
    ];

    let html = '<h3 style="margin-bottom:16px;">Detailed Fee Heads Breakdown</h3>';
    html += '<p style="color:var(--text-muted);font-size:0.8rem;margin-bottom:16px;">Annual various-heads breakdown per course. Click any course to view full details.</p>';

    // Build a simplified table
    html += '<div class="table-wrapper"><table class="fee-table"><thead><tr><th>Course</th>';
    heads.forEach(h => { html += `<th style="font-size:0.6rem;">${h}</th>`; });
    html += '</tr></thead><tbody>';

    // Unique courses by their head key
    const seen = new Set();
    structures.forEach(s => {
        if (!s.detailed_heads || Object.keys(s.detailed_heads).length === 0) return;
        const key = JSON.stringify(s.detailed_heads);
        if (seen.has(key)) return;
        seen.add(key);

        html += `<tr><td style="white-space:normal;max-width:200px;"><strong>${s.course}</strong></td>`;
        heads.forEach(h => {
            const val = s.detailed_heads[h] || 0;
            const isTotal = h === 'TOTAL';
            html += `<td ${isTotal ? 'class="fee-highlight"' : ''}>${val ? '₹' + val.toLocaleString() : '—'}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// ═══════════════════════════════════════════════════════
//  FEE PAYMENT
// ═══════════════════════════════════════════════════════

let feePaymentDebounce = null;

function debounceStudentFeeSearch() {
    clearTimeout(feePaymentDebounce);
    feePaymentDebounce = setTimeout(searchStudentsForFee, 400);
}

async function searchStudentsForFee() {
    const q = document.getElementById('fee-student-search').value.trim();
    if (!q) {
        document.getElementById('fee-student-select-list').innerHTML = '';
        return;
    }

    try {
        const data = await api(`/api/students/search?q=${encodeURIComponent(q)}&per_page=10`);
        const container = document.getElementById('fee-student-select-list');

        if (data.students.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);padding:10px;">No students found</p>';
            return;
        }

        container.innerHTML = data.students.map(s =>
            `<div class="distribution-item" style="cursor:pointer;padding:10px;" onclick="selectStudentForFee(${s.id}, '${s.student_name}', '${s.admission_no}', '${s.course}')">
                <span><strong>${s.student_name}</strong> — ${s.admission_no} (${s.course})</span>
                <span class="badge badge-info">Select</span>
            </div>`
        ).join('');
    } catch (e) { }
}

async function selectStudentForFee(id, name, admNo, course) {
    document.getElementById('fee-student-select-list').innerHTML = `
        <div style="padding:10px;background:var(--info-bg);border-radius:var(--radius-sm);border:1px solid rgba(59,130,246,0.2);margin-bottom:16px;">
            <strong>${name}</strong> — ${admNo} (${course})
            <button class="btn btn-sm btn-secondary" style="margin-left:10px;" onclick="clearFeeSelection()">Change</button>
        </div>`;

    // Get fee structure for course
    const structure = await api(`/api/fee-structure/${encodeURIComponent(course)}`).catch(() => null);

    const container = document.getElementById('fee-payment-form-container');
    container.style.display = 'block';

    let firstTotal = 0, secondTotal = 0;
    if (structure && structure.installments) {
        firstTotal = structure.installments.first.total;
        secondTotal = structure.installments.second.total;
    }

    const safeName = name ? name.replace(/'/g, "\\'") : '';
    const safeAdmNo = admNo ? admNo.replace(/'/g, "\\'") : '';
    const onAmountChange = `updateUPIQRCode(this.value, '${safeName}', '${safeAdmNo}')`;
    const onPaymentModeChange = `toggleUPIQR('${safeName}', '${safeAdmNo}')`;

    container.innerHTML = `
    <form onsubmit="submitFeePayment(event, ${id})">
        <div class="form-grid">
            
            <div id="upi-qr-container" class="form-group full-width" style="text-align:center; padding: 15px; background: var(--glass-bg); border-radius: 12px; border: 1px solid var(--glass-border); display: none;">
                <h4 style="margin-bottom:12px; color:var(--text-primary);"><i class="ph ph-qr-code"></i> Scan & Pay via UPI</h4>
                <p style="font-size:0.9rem;color:var(--text-primary);margin-bottom:12px;">Scan this QR code to pay <strong style="color:var(--success);">₹<span id="qr-amount-display">${firstTotal}</span></strong></p>
                <img id="upi-qr-image" src="" alt="UPI QR Code" style="margin:0 auto; border-radius:10px; border:4px solid white; display:block; max-width:200px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <p style="font-size:0.75rem;color:var(--text-muted);margin-top:10px;">Fast & Free • Zero Transaction Fees</p>
            </div>

            <div class="form-section-title"><i class="ph ph-currency-circle-dollar"></i> Payment Details</div>

            <div class="form-group">
                <label class="form-label">Academic Year</label>
                <select class="form-select" name="academic_year">
                    <option value="2024-25">2024-25</option>
                    <option value="2025-26">2025-26</option>
                    <option value="2023-24">2023-24</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Installment</label>
                <select class="form-select" name="installment" onchange="updateFeeAmount(this.value, ${firstTotal}, ${secondTotal}, '${safeName}', '${safeAdmNo}')">
                    <option value="FIRST">First Installment (₹${firstTotal.toLocaleString()})</option>
                    <option value="SECOND">Second Installment (₹${secondTotal.toLocaleString()})</option>
                    <option value="CUSTOM">Custom Amount</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Payment Date</label>
                <input type="text" class="form-input" name="date" value="${new Date().toLocaleDateString('en-GB').replace(/\//g, '-')}" placeholder="DD-MM-YYYY">
            </div>
            <div class="form-group">
                <label class="form-label">Fee Period From</label>
                <input type="date" class="form-input" name="fee_period_from" id="fee-period-from">
            </div>
            <div class="form-group">
                <label class="form-label">Fee Period To</label>
                <input type="date" class="form-input" name="fee_period_to" id="fee-period-to">
            </div>
            <div class="form-group">
                <label class="form-label">Payment Mode</label>
                <select class="form-select" name="payment_mode" id="payment-mode-select" onchange="${onPaymentModeChange}">
                    <option value="UPI" selected>UPI</option>
                    <option value="CASH">Cash</option>
                    <option value="ONLINE">Online</option>
                    <option value="CHEQUE">Cheque</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Total Amount (₹)</label>
                <input type="number" class="form-input" name="total_amount" id="fee-total-amount" value="${firstTotal}" required step="0.01" oninput="${onAmountChange}">
            </div>

            <div class="form-section-title"><i class="ph ph-chart-pie-slice"></i> Fee Breakdown (Optional)</div>

            <div class="form-group">
                <label class="form-label">Various Heads</label>
                <input type="number" class="form-input" name="various_heads" value="${structure ? structure.installments.first.various : 0}" step="0.01">
            </div>
            <div class="form-group">
                <label class="form-label">Tuition</label>
                <input type="number" class="form-input" name="tuition" value="${structure ? structure.installments.first.tuition : 0}" step="0.01">
            </div>
            <div class="form-group">
                <label class="form-label">Practical</label>
                <input type="number" class="form-input" name="practical" value="${structure ? structure.installments.first.practical : 0}" step="0.01">
            </div>
        </div>
        <div class="btn-group">
            <button type="submit" class="btn btn-primary"><i class="ph ph-currency-circle-dollar"></i> Record Payment</button>
            <button type="reset" class="btn btn-secondary">Reset</button>
        </div>
    </form>`;

    // Initialize QR code
    setTimeout(() => {
        updateUPIQRCode(firstTotal, safeName, safeAdmNo);
    }, 100);
}

function updateFeeAmount(installment, firstTotal, secondTotal, studentName, admNo) {
    const input = document.getElementById('fee-total-amount');
    if (installment === 'FIRST') input.value = firstTotal;
    else if (installment === 'SECOND') input.value = secondTotal;
    else input.value = 0;

    updateUPIQRCode(input.value, studentName, admNo);
}

function toggleUPIQR(studentName, admissionNo) {
    const amount = document.getElementById('fee-total-amount').value;
    updateUPIQRCode(amount, studentName, admissionNo);
}

function updateUPIQRCode(amount, studentName, admissionNo) {
    const qrContainer = document.getElementById('upi-qr-container');
    const qrImg = document.getElementById('upi-qr-image');
    const displayAmt = document.getElementById('qr-amount-display');
    const paymentMode = document.getElementById('payment-mode-select');

    if (!qrContainer || !qrImg || !displayAmt) return;

    const amtNum = parseFloat(amount) || 0;
    displayAmt.textContent = amtNum;

    // Only display QR if amount > 0 and mode is UPI
    if (amtNum > 0 && paymentMode && paymentMode.value === 'UPI') {
        const upiId = 'sameerbanchhor@upi';
        const name = encodeURIComponent('Kalyan College');
        const msg = encodeURIComponent(`Fee-${admissionNo}-${studentName}`);

        // Construct standard UPI URI
        const upiString = `upi://pay?pa=${upiId}&pn=${name}&am=${amtNum}&cu=INR&tn=${msg}`;

        // Generate QR via reliable free API
        const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(upiString)}&margin=10`;

        qrImg.src = qrUrl;
        qrContainer.style.display = 'block';
    } else {
        qrContainer.style.display = 'none';
        qrImg.src = '';
    }
}

function clearFeeSelection() {
    document.getElementById('fee-student-select-list').innerHTML = '';
    document.getElementById('fee-payment-form-container').style.display = 'none';
    document.getElementById('fee-student-search').value = '';
}

async function submitFeePayment(e, studentId) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = { student_id: studentId };
    for (const [key, val] of formData.entries()) {
        data[key] = val;
    }

    // Combine fee period from/to into a single string
    const from = data.fee_period_from || '';
    const to = data.fee_period_to || '';
    data.fee_period = (from && to) ? `${from} TO ${to}` : from || to || '';
    delete data.fee_period_from;
    delete data.fee_period_to;

    try {
        const result = await api('/api/fees/pay', {
            method: 'POST',
            body: JSON.stringify(data),
        });
        showToast(`Payment recorded! Receipt No: ${result.receipt_no}`, 'success');
        clearFeeSelection();
    } catch (e) { }
}

function goToFeePayment(studentId) {
    showSection('fee-payment');
    // Pre-fill search
    api(`/api/students/${studentId}`).then(data => {
        const s = data.student;
        document.getElementById('fee-student-search').value = s.student_name;
        selectStudentForFee(s.id, s.student_name, s.admission_no, s.course);
    });
}

// ═══════════════════════════════════════════════════════
//  FEE STATUS
// ═══════════════════════════════════════════════════════

let feeStatusDebounce = null;

function debounceStudentFeeStatusSearch() {
    clearTimeout(feeStatusDebounce);
    feeStatusDebounce = setTimeout(searchStudentsForFeeStatus, 400);
}

async function searchStudentsForFeeStatus() {
    const q = document.getElementById('fee-status-search').value.trim();
    if (!q) {
        document.getElementById('fee-status-student-list').innerHTML = '';
        return;
    }

    try {
        const data = await api(`/api/students/search?q=${encodeURIComponent(q)}&per_page=10`);
        const container = document.getElementById('fee-status-student-list');

        if (data.students.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);padding:10px;">No students found</p>';
            return;
        }

        container.innerHTML = data.students.map(s =>
            `<div class="distribution-item" style="cursor:pointer;padding:10px;" onclick="loadFeeStatus(${s.id})">
                <span><strong>${s.student_name}</strong> — ${s.admission_no} (${s.course})</span>
                <span class="badge badge-success">View Status</span>
            </div>`
        ).join('');
    } catch (e) { }
}

async function loadFeeStatus(studentId) {
    try {
        const data = await api(`/api/fees/student/${studentId}`);
        const container = document.getElementById('fee-status-details');
        container.style.display = 'block';
        document.getElementById('fee-status-student-list').innerHTML = '';

        let html = `
        <div style="margin-bottom:16px;">
            <h3>${data.student_name} — ${data.admission_no}</h3>
            <p style="color:var(--text-muted);">${data.course}</p>
        </div>

        <div class="fee-summary">
            <div class="fee-summary-item total-card">
                <i class="ph-fill ph-wallet fee-icon"></i>
                <div class="label">Total Fee</div>
                <div class="value total">₹${data.total_fee.toLocaleString()}</div>
            </div>
            <div class="fee-summary-item paid-card">
                <i class="ph-fill ph-check-circle fee-icon"></i>
                <div class="label">Total Paid</div>
                <div class="value paid">₹${data.total_paid.toLocaleString()}</div>
            </div>
            <div class="fee-summary-item balance-card">
                <i class="ph-fill ph-scales fee-icon"></i>
                <div class="label">Balance Due</div>
                <div class="value balance">₹${data.balance.toLocaleString()}</div>
            </div>
        </div>`;

        if (data.records.length > 0) {
            html += `
            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Receipt No</th>
                            <th>Date</th>
                            <th>Year</th>
                            <th>Installment</th>
                            <th>Amount</th>
                            <th>Mode</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>`;

            data.records.forEach(r => {
                html += `<tr>
                    <td><strong>${r.receipt_no}</strong></td>
                    <td>${r.date}</td>
                    <td>${r.academic_year}</td>
                    <td>${r.installment}</td>
                    <td class="fee-highlight">₹${r.total_amount.toLocaleString()}</td>
                    <td>${r.payment_mode}</td>
                    <td><span class="badge badge-success">${r.payment_status}</span></td>
                </tr>`;
            });

            html += '</tbody></table></div>';
        } else {
            html += '<div class="empty-state"><div class="icon"><i class="ph ph-mailbox"></i></div><p>No fee payments recorded yet</p></div>';
        }

        html += `<div class="btn-group">
            <button class="btn btn-primary btn-sm" onclick="goToFeePayment(${studentId})"><i class="ph ph-currency-circle-dollar"></i> Record Payment</button>
            <button class="btn btn-secondary btn-sm" onclick="document.getElementById('fee-status-details').style.display='none'; document.getElementById('fee-status-search').value='';">← Back</button>
        </div>`;

        container.innerHTML = html;
    } catch (e) { }
}
