const APPS = [
    { id: "discussion", label: "Discussion", icon: "fa-comments", color: "#ff9f43" },
    { id: "calendar", label: "Calendrier", icon: "fa-calendar-alt", color: "#54a0ff" },
    { id: "appointments", label: "Rendez-vous", icon: "fa-clock", color: "#5f27cd" },
    { id: "todo", label: "To-do", icon: "fa-check-square", color: "#1dd1a1" },
    { id: "knowledge", label: "Connaissances", icon: "fa-book", color: "#feca57" },
    { id: "contacts", label: "Contacts", icon: "fa-address-book", color: "#00d2d3" },
    { id: "crm", label: "CRM", icon: "fa-users", color: "#ff6b6b" },
    { id: "sales", label: "Ventes", icon: "fa-chart-line", color: "#48dbfb" },
    { id: "accounting", label: "Comptabilité", icon: "fa-file-invoice-dollar", color: "#10ac84" },
    { id: "documents", label: "Documents", icon: "fa-file-alt", color: "#54a0ff" },
    { id: "timesheets", label: "Feuilles de temps", icon: "fa-stopwatch", color: "#2e86de" },
    { id: "employees", label: "Employés", icon: "fa-user-tie", color: "#ee5253" },
    { id: "inventory", label: "Inventaire", icon: "fa-boxes", color: "#f39c12" },
    { id: "leave", label: "Congés", icon: "fa-plane", color: "#1abc9c" },
    { id: "settings", label: "Paramètres", icon: "fa-cog", color: "#7f8c8d" }
];

let currentModule = null;

// --- Initialisation ---
document.addEventListener('DOMContentLoaded', () => {
    checkConnection();
    renderApps();
});

// --- Gestion Connexion ---
document.getElementById('login-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const credentials = {
        url: document.getElementById('odoo_url').value,
        db: document.getElementById('odoo_db').value,
        user: document.getElementById('odoo_username').value,
        pass: document.getElementById('odoo_password').value
    };
    localStorage.setItem('odoo_creds', JSON.stringify(credentials));
    showDashboard();
});

function checkConnection() {
    if (localStorage.getItem('odoo_creds')) {
        showDashboard();
    }
}

function showDashboard() {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('dashboard-view').classList.remove('hidden');
    const creds = JSON.parse(localStorage.getItem('odoo_creds'));
    document.getElementById('display-user').innerText = creds.user;
}

document.getElementById('logout-btn').addEventListener('click', () => {
    localStorage.removeItem('odoo_creds');
    location.reload();
});

// --- Rendu des Apps ---
function renderApps() {
    const grid = document.getElementById('apps-grid');
    grid.innerHTML = '';
    APPS.forEach(app => {
        const card = document.createElement('div');
        card.className = 'app-card';
        card.innerHTML = `
            <div class="app-icon" style="background: ${app.color}">
                <i class="fas ${app.icon}"></i>
            </div>
            <span>${app.label}</span>
        `;
        card.onclick = () => openModule(app);
        grid.appendChild(card);
    });
}

// --- Navigation Module ---
async function openModule(app) {
    currentModule = app;
    document.getElementById('apps-grid').classList.add('hidden');
    document.getElementById('module-detail').classList.remove('hidden');
    document.getElementById('back-to-apps').classList.remove('hidden');
    document.getElementById('current-module-title').innerText = app.label;

    fetchData(app.id);
}

document.getElementById('back-to-apps').onclick = () => {
    document.getElementById('apps-grid').classList.remove('hidden');
    document.getElementById('module-detail').classList.add('hidden');
    document.getElementById('back-to-apps').classList.add('hidden');
};

// --- API Calls ---
async function fetchData(moduleId) {
    const tableHead = document.getElementById('table-head');
    const tableBody = document.getElementById('table-body');
    tableBody.innerHTML = '<tr><td colspan="4">Chargement...</td></tr>';

    try {
        const response = await fetch(`/${moduleId}/?limit=15`);
        const result = await response.json();

        if (!response.ok) throw new Error(result.detail || "Erreur API");

        if (result.length > 0) {
            // Création entête dynamique basique
            const firstItem = result[0].data;
            const keys = Object.keys(firstItem).slice(0, 5); // Max 5 colonnes
            tableHead.innerHTML = keys.map(k => `<th>${k}</th>`).join('') + '<th>Actions</th>';

            // Remplissage table
            tableBody.innerHTML = result.map(item => `
                <tr>
                    ${keys.map(k => `<td>${item.data[k] || '-'}</td>`).join('')}
                    <td><button onclick="editItem(${item.id})" class="btn-edit"><i class="fas fa-edit"></i></button></td>
                </tr>
            `).join('');
        } else {
            tableBody.innerHTML = '<tr><td colspan="5">Aucune donnée trouvée.</td></tr>';
        }
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="5" style="color: #ff6b6b">Erreur : ${err.message}</td></tr>`;
    }
}

// --- CRUD Modals (Simulé pour la démo) ---
function closeModal() { document.getElementById('modal').classList.add('hidden'); }
document.getElementById('add-item-btn').onclick = () => {
    document.getElementById('modal').classList.remove('hidden');
    document.getElementById('modal-title').innerText = `Nouveau dans ${currentModule.label}`;
    document.getElementById('modal-form-fields').innerHTML = `
        <div class="input-group">
            <label>Données (JSON)</label>
            <textarea id="json-data" style="width:100%; height:150px; background:rgba(255,255,255,0.1); color:white; border:none; padding:10px; border-radius:10px;">{ "name": "Nouveau" }</textarea>
        </div>
    `;
};

document.getElementById('save-btn').onclick = async () => {
    const data = JSON.parse(document.getElementById('json-data').value);
    try {
        const resp = await fetch(`/${currentModule.id}/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data })
        });
        if (resp.ok) {
            closeModal();
            fetchData(currentModule.id);
        }
    } catch (e) { alert("Erreur d'enregistrement"); }
};
