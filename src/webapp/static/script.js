
const tg = window.Telegram.WebApp;

// Initialize
tg.expand();

// State
let userId = tg.initDataUnsafe?.user?.id;
// Fallback for dev if not passed (though Telegram always passes valid initData if opening via bot)
if (!userId) {
    console.warn("No user ID found, checking URL params or defaulting.");
    // Try to parse from URL query params (custom dev way)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('user_id')) {
        userId = urlParams.get('user_id');
    } else {
        // Fallback for dev - this lets the UI load even if empty
        // userId = 599142; // Example ID from logs
    }
}

const userInfo = document.getElementById('user-info');
if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    userInfo.textContent = `Hola, ${tg.initDataUnsafe.user.first_name}`;
} else {
    userInfo.textContent = "Modo Invitado (Usuario no detectado)";
}

// Routes
const API_URL = '/api';

// Logic
const apiRequest = async (endpoint, method = 'GET', body = null) => {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true',
        },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);

        let data = null;
        try {
            data = await response.json();
        } catch (jsonError) {
            // Ignore if no JSON body
        }

        if (!response.ok) {
            const errorMsg = (data && data.detail) ? data.detail : `API Error ${response.status}`;
            throw new Error(errorMsg);
        }

        return data;
    } catch (e) {
        // Use custom modal for errors instead of tg.showAlert
        await showModal('Error', e.message);
        return null;
    }
};

function formatDeadline(dateString) {
    if (!dateString) return null;
    const date = new Date(dateString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    // Normalize date to check calendar days
    const checkDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

    const diffTime = checkDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
        return `<span class="deadline-expired">Vencida el ${date.toLocaleDateString()}</span>`;
    } else if (diffDays === 0) {
        // Check if time is also passed if needed, but "Today" is usually fine.
        // If exact time matters:
        if (date < now) return `<span class="deadline-urgent">Vence hoy (ya pasó la hora)</span>`;
        return `<span class="deadline-today">Hoy</span>`;
    } else if (diffDays === 1) {
        return `<span class="deadline-soon">Mañana</span>`;
    } else if (diffDays < 7) {
        return `<span class="deadline-week">En ${diffDays} días (${date.toLocaleDateString(undefined, { weekday: 'long' })})</span>`;
    } else {
        return `<span class="deadline-future">${date.toLocaleDateString()}</span>`;
    }
}

async function loadTasks() {
    const container = document.getElementById('tasks-container');
    container.innerHTML = '<div class="empty-state">Cargando...</div>';

    if (!userId) {
        container.innerHTML = '<div class="empty-state">Error: No User ID found.<br>Use ?user_id=123 in URL.</div>';
        return;
    }

    try {
        const tasks = await apiRequest(`/tasks/${userId}`);
        container.innerHTML = '';

        if (!tasks || tasks.length === 0) {
            container.innerHTML = '<div class="empty-state">No hay tareas pendientes. ¡Buen trabajo! 🪝</div>';
            return;
        }

        tasks.forEach(task => {
            const deadlineHtml = task.deadline ? `<div class="task-deadline">${formatDeadline(task.deadline)}</div>` : '';
            const el = document.createElement('div');
            el.className = `task-item ${task.status === 'COMPLETED' ? 'completed' : ''}`;
            el.innerHTML = `
            <div class="task-checkbox ${task.status === 'COMPLETED' ? 'checked' : ''}" onclick="toggleTask(${task.id}, '${task.status}')"></div>
            <div class="task-content">
                <div class="task-title">${task.content}</div>
                ${deadlineHtml}
            </div>
            <button class="icon-btn edit-btn" data-content="${escapeAttr(task.content)}" onclick="editTask(${task.id}, this)">✏️</button>
            <button class="delete-btn" onclick="deleteTask(${task.id})">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        `;
            container.appendChild(el);
        });
    } catch (e) {
        container.innerHTML = `<div class="empty-state">API Error: ${e.message}</div>`;
    }
}

function escapeAttr(str) {
    if (!str) return '';
    return str.replace(/"/g, '&quot;');
}

async function loadLists() {
    const container = document.getElementById('lists-container');
    container.innerHTML = '<div class="empty-state">Cargando...</div>';

    if (!userId) {
        container.innerHTML = '<div class="empty-state">Please log in.</div>';
        return;
    }
    const lists = await apiRequest(`/lists/${userId}`);
    container.innerHTML = '';

    // Also load invites
    loadInvites();

    if (!lists || lists.length === 0) {
        container.innerHTML = '<div class="empty-state">No hay listas aún. ¡Crea una!</div>';
        return;
    }

    lists.forEach(list => {
        const isOwner = (list.owner_id == userId);

        let actionsHtml = '';
        if (isOwner) {
            actionsHtml = `
                <button class="icon-btn" data-name="${escapeAttr(list.name)}" onclick="editList(${list.id}, this)">✏️</button>
                <button class="icon-btn" onclick="shareList(${list.id})">🔗</button>
                <button class="icon-btn" onclick="deleteList(${list.id})" style="color: #ff3b30;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            `;
        } else {
            actionsHtml = `
                <button class="icon-btn" onclick="leaveList(${list.id})">🚪</button>
            `;
        }

        const el = document.createElement('div');
        el.className = 'list-item';
        el.innerHTML = `
            <div class="list-header" style="display:flex; justify-content:space-between; align-items:center;">
                <div><strong>${list.name}</strong> <small>(${list.task_count})</small></div>
                <div class="list-actions">${actionsHtml}</div>
            </div>
            <div class="list-tasks">
                ${list.tasks.map(t => {
            const deadlineHtml = t.deadline ? `<div class="task-deadline">${formatDeadline(t.deadline)}</div>` : '';
            return `
                    <div class="task-item small ${t.status === 'COMPLETED' ? 'completed' : ''}">
                       <div class="task-checkbox ${t.status === 'COMPLETED' ? 'checked' : ''}" onclick="toggleTask(${t.id}, '${t.status}')"></div>
                       <div class="task-content">
                            <div class="task-title">${t.content}</div>
                            ${deadlineHtml}
                       </div>
                       <button class="icon-btn edit-btn" data-content="${escapeAttr(t.content)}" onclick="editTask(${t.id}, this)">✏️</button>
                       <button class="delete-btn" onclick="deleteTask(${t.id}, true)">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                       </button>
                    </div>
                `}).join('')}
            </div>
            <div class="list-add-task">
                <input type="text" id="add-list-task-${list.id}" placeholder="Añadir a esta lista..." onkeypress="if(event.key === 'Enter') addTaskToList(${list.id})">
                <button onclick="addTaskToList(${list.id})">+</button>
            </div>
        `;
        container.appendChild(el);
    });
}

async function addTask() {
    const input = document.getElementById('new-task-input');
    const content = input.value.trim();
    if (!content) return;

    input.value = '';
    // Optimistic UI could be added here

    await apiRequest(`/tasks/${userId}/add`, 'POST', { content });
    loadTasks();
    tg.HapticFeedback.notificationOccurred('success');
}

async function toggleTask(taskId, currentStatus) {
    // Visual feedback
    tg.HapticFeedback.selectionChanged();
    const endpoint = currentStatus === 'COMPLETED' ? 'uncomplete' : 'complete';
    await apiRequest(`/tasks/${taskId}/${endpoint}`, 'POST', { user_id: userId });

    // Refresh context
    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab && activeTab.textContent.includes('Listas')) {
        loadLists();
    } else {
        loadTasks();
    }
}

async function addList() {
    const name = await showModal('Nueva Lista', 'Nombre de la lista:', true);
    if (!name) return;

    await apiRequest(`/lists/${userId}/add`, 'POST', { name });
    loadLists();
}

async function deleteList(listId) {
    const confirm = await showModal('Eliminar lista', '¿Seguro que quieres eliminar esta lista y sus tareas?');
    if (!confirm) return;
    await apiRequest(`/lists/${listId}/delete`, 'POST', { user_id: userId });
    loadLists();
}

async function shareList(listId) {
    const username = await showModal('Invitar Usuario', 'Introduce el @usuario, nombre o ID de Telegram:', true);
    if (!username) return;
    const res = await apiRequest(`/lists/${listId}/share`, 'POST', { username, user_id: userId });
    if (res) alert(res.message);  // Keep alert for result message or use another Modal? Let's assume alert works or replace.
    // Actually TG android supports alert usually. But let's be consistent.
}

async function leaveList(listId) {
    if (!confirm("¿Salir de esta lista compartida?")) return;
    const res = await apiRequest(`/lists/${listId}/leave`, 'POST', { user_id: userId });
    if (res) loadLists();
}

async function loadInvites() {
    const container = document.getElementById('invites-container');
    if (!container) return; // Fail safe

    // Only load if section exists in HTML
    const invites = await apiRequest(`/invites/${userId}`);
    if (!invites || invites.length === 0) {
        container.style.display = 'none';
        container.innerHTML = '';
        return;
    }

    container.style.display = 'block';
    container.innerHTML = '<h3>Invitaciones Pendientes 📩</h3>';

    invites.forEach(inv => {
        const el = document.createElement('div');
        el.className = 'invite-item';
        el.innerHTML = `
            <div><strong>${inv.list_name}</strong> de @${inv.owner_name}</div>
            <div class="invite-actions">
                <button onclick="respondInvite(${inv.list_id}, true)">✅</button>
                <button onclick="respondInvite(${inv.list_id}, false)">❌</button>
            </div>
        `;
        container.appendChild(el);
    });
}

async function respondInvite(listId, accept) {
    await apiRequest(`/invites/${listId}/respond`, 'POST', { user_id: userId, accept });
    loadInvites();
    loadLists();
}

// Deprecated or alias
async function completeTask(taskId) {
    toggleTask(taskId, 'PENDING');
}

async function addTaskToList(listId) {
    const input = document.getElementById(`add-list-task-${listId}`);
    const content = input.value.trim();
    if (!content) return;

    input.value = '';
    await apiRequest(`/tasks/${userId}/add`, 'POST', { content, list_id: listId });
    loadLists(); // Refresh lists view specifically
    tg.HapticFeedback.notificationOccurred('success');
}

async function editList(listId, btnElement) {
    const currentName = btnElement.getAttribute('data-name');
    const newName = await showModal('Renombrar Lista', 'Nuevo nombre:', true, currentName);

    if (newName === null || newName.trim() === "") return;
    if (newName.trim() === currentName) return;

    await apiRequest(`/lists/${listId}/update`, 'POST', { name: newName, user_id: userId });
    loadLists();
}

async function editTask(taskId, btnElement) {
    const currentContent = btnElement.getAttribute('data-content');
    const newContent = await showModal('Editar Tarea', 'Contenido:', true, currentContent);

    if (newContent === null || newContent.trim() === "") return;
    if (newContent.trim() === currentContent) return; // No change

    await apiRequest(`/tasks/${taskId}/update`, 'POST', { content: newContent, user_id: userId });

    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab && activeTab.textContent.includes('Tareas')) {
        loadTasks();
    } else {
        loadLists();
    }
}

async function deleteTask(taskId, isFromList = false) {
    const confirm = await showModal('Eliminar Tarea', '¿Eliminar esta tarea?');
    if (!confirm) return;
    tg.HapticFeedback.notificationOccurred('warning');
    await apiRequest(`/tasks/${taskId}/delete`, 'POST', { user_id: userId });

    if (isFromList) {
        loadLists();
    } else {
        const activeTab = document.querySelector('.tab-btn.active');
        if (activeTab && activeTab.textContent.includes('Listas')) {
            loadLists();
        } else {
            loadTasks();
        }
    }
}

// Modal Logic
let modalResolver = null;

function showModal(title, message, hasInput = false, initialValue = '') {
    return new Promise((resolve) => {
        document.getElementById('modal-title').innerText = title;
        document.getElementById('modal-message').innerText = message;

        const input = document.getElementById('modal-input');
        if (hasInput) {
            input.style.display = 'block';
            input.value = initialValue;
            setTimeout(() => input.focus(), 100);
        } else {
            input.style.display = 'none';
        }

        document.getElementById('custom-modal').style.display = 'flex';
        modalResolver = resolve;
    });
}

function closeModal(result) {
    const modal = document.getElementById('custom-modal');
    const input = document.getElementById('modal-input');

    modal.style.display = 'none';

    if (modalResolver) {
        if (result && input.style.display !== 'none') {
            modalResolver(input.value);
        } else {
            modalResolver(result);
        }
        modalResolver = null;
    }
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

    // Find button with matching onclick handler is hardish, just index?
    // Let's use simple logic
    // Use data attributes or simple indexing if classes were clean
    // Fixing selector to be robust against quoting style
    if (tab === 'tasks') {
        const btn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.textContent.includes('Tareas'));
        if (btn) btn.classList.add('active');
        document.getElementById('tasks-view').classList.add('active');
        loadTasks();
    } else {
        const btn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.textContent.includes('Listas'));
        if (btn) btn.classList.add('active');
        document.getElementById('lists-view').classList.add('active');
        loadLists();
    }
}

// Initial Load
if (userId) {
    loadTasks();
} else {
    document.getElementById('tasks-container').innerHTML = '<div class="empty-state">Please open via Telegram Bot.</div>';
}

// Main Button for adding task?
// tg.MainButton.setText("Update").show().onClick(() => loadTasks());
