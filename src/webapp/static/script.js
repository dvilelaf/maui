
const tg = window.Telegram.WebApp;

// Initialize
tg.expand();

// State
let userId = tg.initDataUnsafe?.user?.id;
let expandedLists = new Set(); // Track expanded state
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
            <button class="icon-btn edit-btn" data-content="${escapeAttr(task.content)}" onclick="editTask(${task.id}, this)"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg></button>
            <button class="delete-btn" onclick="deleteTask(${task.id})">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
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
        const isExpanded = expandedLists.has(list.id);

        let actionsHtml = '';
        if (isOwner) {
            actionsHtml = `
                <button class="icon-btn edit-btn" data-name="${escapeAttr(list.name)}" onclick="editList(${list.id}, this); event.stopPropagation();"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg></button>
                <button class="icon-btn" onclick="shareList(${list.id}); event.stopPropagation();"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg></button>
                <div class="icon-btn" style="position:relative; color: #2481cc;" onclick="event.stopPropagation();">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/><path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2.5 2.24 0 .46.62.8.8.8h3.48c1.67 0 3.04-1.36 3.04-3.02 0-1.34-2.5-1.52-2.5-2.24 0-.46.61-.8.8-.8z"/></svg>
                    <input type="color" value="${list.color || '#f2f2f2'}"
                        style="position:absolute; top:0; left:0; width:100%; height:100%; opacity:0; cursor:pointer; padding:0; border:none; margin:0;"
                        onchange="changeListColor(${list.id}, this.value)">
                </div>
                <button class="icon-btn" onclick="deleteList(${list.id}); event.stopPropagation();" style="color: #ff3b30;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            `;
        } else {
            actionsHtml = `
                <button class="icon-btn" onclick="leaveList(${list.id}); event.stopPropagation();"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg></button>
            `;
        }

        const el = document.createElement('div');
        el.className = `list-item ${isExpanded ? 'expanded' : ''}`;
        el.id = `list-item-${list.id}`;
        // Apply background color
        el.style.backgroundColor = list.color || '#f2f2f2';

        el.innerHTML = `
            <div class="list-header" onclick="toggleList(${list.id})">
                <div class="list-header-content">
                    <svg class="list-toggle-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <div><strong>${list.name}</strong> <small>(${list.task_count})</small></div>
                </div>
                <div class="list-actions" style="display:flex; align-items:center; gap:4px;">${actionsHtml}</div>
            </div>

            <div class="list-body">
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
                        <button class="icon-btn edit-btn" data-content="${escapeAttr(t.content)}" onclick="editTask(${t.id}, this)"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg></button>
                        <button class="delete-btn" onclick="deleteTask(${t.id}, true)">
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                        </div>
                    `}).join('')}
                </div>
                <div class="list-add-task">
                    <input type="text" id="add-list-task-${list.id}" placeholder="Añadir a esta lista..." onkeypress="if(event.key === 'Enter') addTaskToList(${list.id})">
                    <button onclick="addTaskToList(${list.id})">+</button>
                </div>
            </div>
        `;
        container.appendChild(el);
    });
}

function toggleList(listId) {
    const el = document.getElementById(`list-item-${listId}`);
    if (!el) return;

    if (expandedLists.has(listId)) {
        expandedLists.delete(listId);
        el.classList.remove('expanded');
    } else {
        expandedLists.add(listId);
        el.classList.add('expanded');
    }
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
    container.innerHTML = '<h3>Invitaciones Pendientes <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg></h3>';

    invites.forEach(inv => {
        const el = document.createElement('div');
        el.className = 'invite-item';
        el.innerHTML = `
            <div><strong>${inv.list_name}</strong> de @${inv.owner_name}</div>
            <div class="invite-actions">
                <button onclick="respondInvite(${inv.list_id}, true)"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></button>
                <button onclick="respondInvite(${inv.list_id}, false)"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
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

async function changeListColor(listId, color) {
    if (!color) return;
    await apiRequest(`/lists/${listId}/color`, 'POST', { color: color, user_id: userId });
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
