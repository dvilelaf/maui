// Initialize Telegram WebApp carefully
let tg = null;
let userId = null;

try {
    if (window.Telegram && window.Telegram.WebApp) {
        tg = window.Telegram.WebApp;
        tg.expand();
        userId = tg.initDataUnsafe?.user?.id;
    }
} catch (e) {
    console.warn("Telegram WebApp not initialized:", e);
}

// State
let expandedLists = new Set(); // Track expanded state

if (!userId) {
    console.warn("No user ID found, checking URL params or defaulting.");
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('user_id')) {
        userId = urlParams.get('user_id');
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
            'X-Telegram-Init-Data': tg ? tg.initData : '',
        },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    // Cache busting
    const url = `${API_URL}${endpoint}${endpoint.includes('?') ? '&' : '?'}t=${new Date().getTime()}`;
    const response = await fetch(url, options);

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
};

function formatDeadline(dateString) {
    if (!dateString) return null;
    const date = new Date(dateString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    // Normalize date to check calendar days
    const checkDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diffTime = checkDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
        return `<span class="deadline-expired">vencida el ${date.toLocaleDateString()}</span>`;
    } else if (diffDays === 0) {
        if (date < now) return `<span class="deadline-expired">hoy (vencida)</span>`;
        return `<span class="deadline-today">hoy</span>`;
    } else if (diffDays === 1) {
        return `<span class="deadline-soon">mañana</span>`;
    } else if (diffDays < 7) {
        return `<span class="deadline-week">${date.toLocaleDateString(undefined, { weekday: 'long' })}</span>`;
    } else {
        return `<span class="deadline-future">${date.toLocaleDateString()}</span>`;
    }
}

// --- VIEWS ---

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

    // Update styling for active tab
    const buttons = document.querySelectorAll('.tab-btn');
    console.log(`Switching to tab: ${tab}, userId: ${userId}`);
    if (tab === 'dated') {
        buttons[0].classList.add('active');
        document.getElementById('dated-view').classList.add('active');
        loadDatedView();
    } else if (tab === 'all') {
        buttons[1].classList.add('active');
        document.getElementById('all-view').classList.add('active');
        document.getElementById('all-view').classList.add('active');
        loadAllView();
    }
    localStorage.setItem('activeTab', tab);
}

async function loadDatedView() {
    const container = document.getElementById('dated-container');

    // Silent Refresh: Only show loading if empty
    if (container.children.length === 0 || container.querySelector('.empty-state')) {
        container.innerHTML = '<div class="empty-state">Cargando...</div>';
    }

    if (!userId) {
        container.innerHTML = '<div class="empty-state">Error: No User ID.</div>';
        return;
    }

    try {
        const items = await apiRequest(`/dashboard/dated`);

        if (!items || items.length === 0) {
            container.innerHTML = '<div class="empty-state">No hay tareas con fecha</div>';
            return;
        }

        container.innerHTML = ''; // Clear "Waiting..." or static
        items.forEach(item => {
            const deadlineHtml = item.deadline ? `<div class="task-deadline">${formatDeadline(item.deadline)}</div>` : '';

            // If item belongs to list, show card style
            let itemHtml = '';

            if (item.list_id) {
                // Task inside list card
                const color = item.list_color || '#f2f2f2';
                // Note: using getTaskInnerHtml inside the task-item wrapper
                itemHtml = `
                    <div class="list-item" style="background-color: ${color}; padding: 8px;">
                         <div class="task-item small ${item.status === 'COMPLETED' ? 'completed' : ''}" style="background: rgba(255,255,255,0.6); width: 100%; border-radius: 8px; border: none; box-shadow: none;">
                            ${getTaskInnerHtml(item)}
                         </div>
                    </div>
                `;
            } else {
                // Regular task
                itemHtml = `
                    <div class="task-item ${item.status === 'COMPLETED' ? 'completed' : ''}">
                        ${getTaskInnerHtml(item)}
                    </div>
                 `;
            }
            const wrapper = document.createElement('div');
            wrapper.innerHTML = itemHtml;
            container.appendChild(wrapper.firstElementChild);
        });

    } catch (e) {
        container.innerHTML = `<div class="empty-state">API Error: ${e.message}</div>`;
    }
}

async function loadAllView() {
    const container = document.getElementById('all-container');

    // Silent Refresh: Only show loading if empty
    // Silent Refresh: Only show loading if empty or strictly the main empty state
    // We check if the FIRST child is the empty state div, to avoid finding nested empty-states in lists
    const firstChild = container.firstElementChild;
    const isMainEmpty = firstChild && firstChild.classList.contains('empty-state');

    if (container.children.length === 0 || isMainEmpty) {
        container.innerHTML = '<div class="empty-state">Cargando...</div>';
    }

    // Also load invites
    loadInvites();

    try {
        const items = await apiRequest(`/dashboard/all`); // [{type, id, title, position...}]

        if (!items || items.length === 0) {
            container.innerHTML = '<div class="empty-state">No hay nada por hacer.</div>';
            return;
        }

        // Optimization: if we have expanded lists, fetch full lists data ONCE
        let fullListsMap = new Map();
        const expandedIds = items.filter(i => i.type === 'list' && expandedLists.has(i.id)).map(i => i.id);

        if (expandedIds.length > 0) {
            const allLists = await apiRequest(`/lists`);
            if (allLists) {
                allLists.forEach(l => fullListsMap.set(l.id, l));
            }
        }

        // Build DocumentFragment off-screen
        const fragment = document.createDocumentFragment();

        // Render mixed items
        for (const item of items) {
            item.isExpanded = expandedLists.has(item.id);
            const el = await createDashboardElement(item);
            fragment.appendChild(el);

            // If expanded, hydrate immediately from cache if possible
            if (item.type === 'list' && item.isExpanded) {
                const listData = fullListsMap.get(item.id);
                // We need to find the list body inside the element we just created
                // Since 'el' is the list item wrapper, we can query inside it.
                // However, renderListTasks expects a listId and queries document.getElementById.
                // We should pass the ELEMENT to a modified renderListTasks or append manually.

                // Hack: Since 'el' is not in DOM yet, document.getElementById won't find it.
                // We must hydrate MANUALLY here or append fragment first?
                // Replacing children first is better, but then we have a split second unhydrated?
                // Actually, createDashboardElement returns the div. We can modify it directly.

                if (listData) {
                    const body = el.querySelector(`.list-body`);
                    if (body) {
                        body.style.display = 'block'; // Ensure visible logic matches CSS
                        // Manual renderListTasks logic reusing the HTML generator would be ideal,
                        // but let's stick to the existing pattern:
                        // We can't use renderListTasks because it queries by ID.
                        // Let's defer hydration until AFTER replaceChildren.
                        // Since data is already fetched, the user won't see a spinner.
                    }
                }
            }
        }

        // atomic swap
        container.replaceChildren(fragment);

        // Post-render hydration for lists (now they are in DOM)
        // This is fast enough to be imperceptible usually, but let's do it immediately.
        for (const item of items) {
            if (item.type === 'list' && item.isExpanded) {
                const listData = fullListsMap.get(item.id);
                if (listData) {
                    renderListTasks(item.id, listData.tasks);
                } else {
                    loadListTasksIntoBody(item.id);
                }
            }
        }

    } catch (e) {
        container.innerHTML = `<div class="empty-state">API Error: ${e.message}</div>`;
    }
}

async function createDashboardElement(item) {
    const el = document.createElement('div');
    // Common ID format for drag
    el.id = `item-${item.type}-${item.id}`;

    // Drag handlers
    el.ontouchstart = (e) => handleTouchStart(e, item.type, item.id);

    if (item.type === 'task') {
        const task = item;

        // Note: Global tasks in "All" view are often styled differently (row style), but the inner content is same
        // Wait, lines 280-282 set 'list-item' style.
        // We need to keep the wrapper setup, but use helper for inner content.

        el.className = `list-item ${task.status === 'COMPLETED' ? 'completed' : ''}`;
        el.style.backgroundColor = 'var(--tg-theme-secondary-bg-color)';
        el.style.flexDirection = 'row';
        el.style.alignItems = 'center';

        // NOTE: getTaskInnerHtml returns the Checkbox, Content, Edit, Delete structure.
        el.innerHTML = getTaskInnerHtml(task);

    } else if (item.type === 'list') {
        const list = item;
        el.className = `list-item ${list.isExpanded ? 'expanded' : ''}`;
        el.style.backgroundColor = list.color || '#f2f2f2';

        el.innerHTML = `
            <div class="list-header" onclick="toggleListMixed(${list.id}, this)">
                <div class="list-header-content">
                    <svg class="list-toggle-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <div><strong>${list.title}</strong> <small>(${list.task_count})</small></div>
                </div>
                <div class="list-actions" style="display:flex; align-items:center; gap:4px;">
                     <button class="icon-btn edit-btn" data-name="${escapeAttr(list.title)}" onclick="editList(${list.id}, this); event.stopPropagation();"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg></button>
                      <!-- Color Picker -->
                    <div class="icon-btn" style="position:relative; color: #2481cc;" onclick="event.stopPropagation();">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08"/><path d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2.5 2.24 0 .46.62.8.8.8h3.48c1.67 0 3.04-1.36 3.04-3.02 0-1.34-2.5-1.52-2.5-2.24 0-.46.61-.8.8-.8z"/></svg>
                        <input type="color" value="${list.color || '#f2f2f2'}"
                            style="position:absolute; top:0; left:0; width:100%; height:100%; opacity:0; cursor:pointer;"
                            oninput="previewListColorMixed('item-list-${list.id}', this.value)"
                            onchange="saveListColor(${list.id}, this.value)">
                    </div>
                     <button class="icon-btn" onclick="deleteList(${list.id}); event.stopPropagation();" style="color: #ff3b30;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                    </button>
                </div>
            </div>
            <div class="list-body" id="list-body-${list.id}">
                <div class="empty-state" style="font-size:12px; margin:0;">Loading...</div>
            </div>
        `;

        // Removed eager loading call here to avoid DOM issue
    }

    return el;
}

// Helper to load tasks inside a list (client side fetch)
async function loadListTasksIntoBody(listId) {
    const lists = await apiRequest(`/lists`);
    const mylist = lists.find(l => l.id == listId);

    if (mylist) {
        renderListTasks(listId, mylist.tasks);
    }
}

function renderListTasks(listId, tasks) {
    const body = document.getElementById(`list-body-${listId}`);
    if (!body) return;

    // Split tasks
    const pendingTasks = tasks.filter(t => t.status !== 'COMPLETED');
    const completedTasks = tasks.filter(t => t.status === 'COMPLETED');

    // Button HTML
    const addButtonHtml = `
        <div class="list-add-area" style="margin: 8px 0; padding: 0 4px; text-align: center;">
             <button class="list-add-btn" onclick="openAddTaskModal(${listId})">
                 <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                 Añadir tarea
             </button>
        </div>
    `;

    // Render logic
    const renderTask = (t) => `
        <div class="task-item small ${t.status === 'COMPLETED' ? 'completed' : ''}" style="width: 100%; margin: 0; border: none; background: rgba(255,255,255,0.6); box-shadow: none; border-radius: 8px;">
            ${getTaskInnerHtml(t)}
        </div>
    `;

    body.innerHTML = `
        <div class="list-tasks" style="display: flex; flex-direction: column; gap: 8px; width: 100%; padding: 0;">
            ${pendingTasks.map(renderTask).join('')}
            ${addButtonHtml}
            ${completedTasks.map(renderTask).join('')}
        </div>
    `;
}

async function toggleListMixed(listId, headerElement) {
    if (wasDragging) {
        console.log("Toggle blocked by wasDragging");
        return;
    }

    // Robust element finding: use passed element's parent, or fallback to ID
    let el = null;
    if (headerElement) {
        el = headerElement.parentElement;
    } else {
        el = document.getElementById(`item-list-${listId}`);
    }

    console.log(`Toggling list ${listId}, el found: ${!!el}`);
    if (!el) return;

    if (expandedLists.has(listId)) {
        expandedLists.delete(listId);
        el.classList.remove('expanded');
        const body = el.querySelector('.list-body');
        if (body) body.style.display = '';
    } else {
        expandedLists.add(listId);
        el.classList.add('expanded');
        try {
            await loadListTasksIntoBody(listId);
        } catch (e) {
            console.error(`Failed to load list ${listId}:`, e);
            // Optionally remove expanded state if load fails?
            // expandedLists.delete(listId);
            // el.classList.remove('expanded');
            // For now, just alert user so they know why it's empty
            // alert("No se pudieron cargar las tareas. Revisa tu conexión.");
            const body = document.getElementById(`list-body-${listId}`);
            if (body) body.innerHTML = '<div class="empty-state" style="color:red">Error loading details.</div>';
        }
    }
}


// --- ACTIONS ---

// --- Add Task Modal Logic ---

// --- Add/Edit Task Modal Logic ---

async function openTaskModal(taskId = null, listId = null, initialData = {}) {
    const modal = document.getElementById('add-task-modal');
    const titleEl = document.getElementById('task-modal-title');
    const taskIdInput = document.getElementById('new-task-id');
    const listSelect = document.getElementById('new-task-list-select');

    // Reset fields
    document.getElementById('new-task-title').value = '';
    document.getElementById('new-task-recurrence').value = '';
    const dateInput = document.getElementById('new-task-date');
    dateInput.value = '';
    dateInput.type = 'text';

    taskIdInput.value = taskId || '';

    // Populate Lists Dropdown
    listSelect.innerHTML = '<option value="">Ninguna</option>';
    try {
        const lists = await apiRequest('/lists'); // Assume this endpoint exists and returns {id, title...}
        if (lists && lists.length > 0) {
            lists.forEach(l => {
                const opt = document.createElement('option');
                opt.value = l.id;
                opt.textContent = l.name; // Use 'name' from ListResponse
                listSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn("Failed to load lists for dropdown", e);
    }

    // Set Initial List Selection
    // Priority: initialData.list_id (Edit) > listId (Add from List) > "" (Add Global)
    let selectedListId = "";
    if (taskId && initialData.list_id !== undefined) {
        selectedListId = initialData.list_id || "";
    } else if (listId) {
        selectedListId = listId;
    }
    listSelect.value = selectedListId;

    if (taskId) {
        // Edit Mode
        titleEl.innerText = "Editar Tarea";
        document.getElementById('new-task-title').value = initialData.content || '';
        document.getElementById('new-task-recurrence').value = initialData.recurrence || '';
        if (initialData.deadline) {
            dateInput.value = initialData.deadline.split('T')[0];
            dateInput.type = 'date';
        }
    } else {
        // Create Mode
        titleEl.innerText = "Nueva Tarea";
    }

    modal.style.display = 'flex';
    document.getElementById('new-task-title').focus();
}

// Alias for old calls (add button) - defaults to create mode
function openAddTaskModal(listId = null) {
    openTaskModal(null, listId);
}

function closeAddTaskModal() {
    document.getElementById('add-task-modal').style.display = 'none';
}

async function submitNewTask() {
    const title = document.getElementById('new-task-title').value.trim();
    if (!title) {
        alert("Por favor escribe un título para la tarea.");
        return;
    }

    const taskId = document.getElementById('new-task-id').value;
    const recurrence = document.getElementById('new-task-recurrence').value;
    let deadline = document.getElementById('new-task-date').value;
    const listSelect = document.getElementById('new-task-list-select');
    const selectedListId = listSelect.value;

    // Convert "" to null for API
    const listIdToSave = selectedListId ? parseInt(selectedListId) : null;

    const payload = {
        content: title,
        recurrence: recurrence || "",
        deadline: deadline || "",
        list_id: listIdToSave
    };

    closeAddTaskModal();

    try {
        if (taskId) {
            // Update Existing
            await apiRequest(`/tasks/${taskId}/update`, 'POST', {
                content: payload.content,
                deadline: payload.deadline,
                recurrence: payload.recurrence,
                list_id: payload.list_id
            });
        } else {
            // Create New
            await apiRequest('/tasks/add', 'POST', payload);
        }

        tg.HapticFeedback.notificationOccurred('success');

        // Full Refresh needed to show task in new list or remove from old
        // refreshCurrentView might be checking active tab.
        // If we moved a task, it's safer to reload the view completely.
        refreshCurrentView();

    } catch (e) {
        alert("Error al guardar tarea: " + e.message);
    }
}


// Old method for reference (replaced by separate modal functions above)
/*
async function openAddTaskModal() {
    // ...
}
*/

function refreshCurrentView() {
    if (document.getElementById('dated-view').classList.contains('active')) loadDatedView();
    else loadAllView();
}

async function toggleTask(taskId, currentStatus) {
    try {
        tg.HapticFeedback.selectionChanged();
        const endpoint = currentStatus === 'COMPLETED' ? 'uncomplete' : 'complete';
        await apiRequest(`/tasks/${taskId}/${endpoint}`, 'POST'); // Auth header handles user identification
        refreshCurrentView();
    } catch (e) {
        console.error(e);
        alert("Error al actualizar tarea: " + e.message);
    }
}

async function startReorderList(listId) {
    alert("Mantén presionado para reordenar.");
}

async function addList() {
    const name = await showModal('Nueva Lista', 'Nombre de la lista:', true);
    if (!name) return;
    await apiRequest(`/lists/add`, 'POST', { name });
    await loadAllView(); // Wait for view to update
    if (!document.getElementById('all-view').classList.contains('active')) {
        switchTab('all');
    }
}

// ... Reuse edit/delete/share helpers from before with minor updates

async function editTask(taskId, btnElement) {
    const currentContent = btnElement.getAttribute('data-content');
    const currentDeadline = btnElement.getAttribute('data-deadline') || '';
    const currentRecurrence = btnElement.getAttribute('data-recurrence') || '';
    const currentListId = btnElement.getAttribute('data-list-id');

    openTaskModal(taskId, null, {
        content: currentContent,
        deadline: currentDeadline,
        recurrence: currentRecurrence,
        list_id: currentListId ? parseInt(currentListId) : null
    });
}

// async function deleteTask(taskId, isFromList = false) {
// if (!await showModal('Borrar', '¿Eliminar tarea?')) return;
// try { ... }

async function deleteTask(taskId, isFromList = false) {
    if (!confirm('¿Eliminar tarea?')) return;
    try {
        await apiRequest(`/tasks/${taskId}/delete`, 'POST'); // Auth header handles user identification
        refreshCurrentView();
    } catch (e) {
        console.error(e);
        alert("Error al eliminar tarea: " + e.message);
    }
}


async function addTaskToList(listId) {
    const input = document.getElementById(`add-list-task-${listId}`);
    const dateInput = document.getElementById(`add-list-date-${listId}`);
    const content = input.value.trim();
    if (!content) return;

    input.value = '';
    const deadline = dateInput ? dateInput.value : null;
    if (dateInput) dateInput.value = ''; // Reset date

    await apiRequest(`/tasks/add`, 'POST', { content, list_id: listId, deadline: deadline });
    // Refresh list body?
    loadListTasksIntoBody(listId);
}

// Reuse other list helpers
// async function deleteList(listId) {
// if (!await showModal('Borrar Lista', ...)) return;

async function deleteList(listId) {
    if (!confirm('¿Seguro que quieres eliminar esta lista?')) return;
    try {
        await apiRequest(`/lists/${listId}/delete`, 'POST');
        refreshCurrentView();
    } catch (e) {
        console.error(e);
        alert("Error al eliminar lista: " + e.message);
    }
}

async function editList(listId, btn) {
    const name = btn.getAttribute('data-name');
    const newName = await showModal('Renombrar', 'Nuevo nombre:', true, name);
    if (newName) {
        await apiRequest(`/lists/${listId}/update`, 'POST', { name: newName, user_id: userId });
        refreshCurrentView();
    }
}

async function inviteUser(listId) { /* ... same ... */ } // reusing old shareList logic
async function shareList(listId) {
    const username = await showModal('Invitar', 'Introduce @usuario o ID:', true);
    if (username) {
        const res = await apiRequest(`/lists/${listId}/share`, 'POST', { username, user_id: userId });
        if (res) alert(res.message);
    }
}
async function saveListColor(listId, color) {
    await apiRequest(`/lists/${listId}/color`, 'POST', { color, user_id: userId });
}
function previewListColorMixed(elemId, color) {
    const el = document.getElementById(elemId);
    if (el) el.style.backgroundColor = color;
}


// --- DRAG AND DROP (MIXED) ---
let dragTimer = null;
let isDragging = false;
let wasDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let dragElement = null;
let lastSwapTime = 0; // Debounce for reordering

function handleTouchStart(e, type, id) {
    if (e.target.closest('button') || e.target.closest('input')) return;

    // Always reset wasDragging on new touch to prevent stuck state
    wasDragging = false;

    // Store start coordinates
    const touch = e.touches[0];
    dragStartX = touch.clientX;
    dragStartY = touch.clientY;

    // Double check cleanup
    isDragging = false;
    if (dragTimer) clearTimeout(dragTimer);

    const el = document.getElementById(`item-${type}-${id}`);
    if (!el) return;

    dragTimer = setTimeout(() => {
        isDragging = true;
        wasDragging = true;
        dragElement = el;
        el.classList.add('dragging');
        tg.HapticFeedback.impactOccurred('medium');
        document.body.style.overflow = 'hidden';
    }, 400);
}

document.addEventListener('touchmove', function (e) {
    const touch = e.touches[0];

    // Check if we are waiting for long press or already dragging
    if (!isDragging) {
        if (!dragTimer) return; // No timer active

        // Calculate movement distance
        const moveX = Math.abs(touch.clientX - dragStartX);
        const moveY = Math.abs(touch.clientY - dragStartY);

        // If moved significantly, cancel timer
        if (moveX > 10 || moveY > 10) {
            clearTimeout(dragTimer);
            dragTimer = null;
        }
        // If small movement, do nothing (keep timer running)
        return;
    }

    // Is Dragging Logic
    if (e.cancelable) e.preventDefault();
    if (!dragElement) return;

    const target = document.elementFromPoint(touch.clientX, touch.clientY);
    if (!target) return;

    // Find closest list-item
    const targetItem = target.closest('.list-item');
    if (targetItem && targetItem !== dragElement && targetItem.parentElement === dragElement.parentElement) {
        // Debounce swaps to prevent flickering
        const now = Date.now();
        if (now - lastSwapTime < 250) return;

        const container = dragElement.parentElement;
        const children = [...container.children];
        const dragIndex = children.indexOf(dragElement);
        const targetIndex = children.indexOf(targetItem);

        if (dragIndex < targetIndex) {
            container.insertBefore(dragElement, targetItem.nextSibling);
        } else {
            container.insertBefore(dragElement, targetItem);
        }
        lastSwapTime = now;
        lastSwapTime = now;
        tg.HapticFeedback.selectionChanged();
    }
}, { passive: false });

// Helper to reset drag state completely
function forceResetDrag() {
    isDragging = false;
    wasDragging = false;
    if (dragElement) {
        dragElement.classList.remove('dragging');
        dragElement = null;
    }
    if (dragTimer) {
        clearTimeout(dragTimer);
        dragTimer = null;
    }
    document.body.style.overflow = '';
}

// Helper to cleanup drag state
function cleanupDragState() {
    if (dragTimer) {
        clearTimeout(dragTimer);
        dragTimer = null;
    }
    if (isDragging) {
        isDragging = false;
        if (dragElement) {
            dragElement.classList.remove('dragging');
            dragElement = null;
        }
        document.body.style.overflow = '';
    }
    // Note: wasDragging logic blocking clicks is handled specifically in touchend
    // For cancel/cleanup, we typically just want to reset everything.
}

document.addEventListener('touchcancel', function (e) {
    console.log('[TouchCancel] Drag cancelled.');
    cleanupDragState();
    wasDragging = false;
});

document.addEventListener('touchend', function (e) {
    // Always clear timer on lift
    if (dragTimer) {
        clearTimeout(dragTimer);
        dragTimer = null;
    }

    if (isDragging) {
        console.log('[TouchEnd] Drag finished.');

        // Calculate total movement to detect "Stationary Long Press"
        const touch = e.changedTouches[0];
        const endX = touch.clientX;
        const endY = touch.clientY;
        const dist = Math.sqrt(Math.pow(endX - dragStartX, 2) + Math.pow(endY - dragStartY, 2));

        const wasStationary = dist < 10;
        console.log(`[TouchEnd] Distance: ${dist.toFixed(1)}px. Stationary: ${wasStationary}`);

        isDragging = false;
        if (dragElement) {
            dragElement.classList.remove('dragging');
            dragElement = null;
        }
        document.body.style.overflow = '';

        if (wasStationary) {
            // If we didn't move, treat it as a click (allow toggle)
            // We reset wasDragging immediately so the click event (which comes next) works
            console.log('[TouchEnd] Stationary lift -> Allowing click.');
            wasDragging = false;
        } else {
            // We moved, so this was a real drag. Block the click.
            // Save new order
            const items = [];
            document.querySelectorAll('#all-container > div').forEach(el => {
                const idParts = el.id.split('-');
                if (idParts.length >= 3) {
                    items.push({ type: idParts[1], id: parseInt(idParts[2]) });
                }
            });
            saveDashboardOrder(items);

            // Delay clearing wasDragging to block the click
            setTimeout(() => {
                console.log('[TouchEnd] Clearing wasDragging (block click expired).');
                wasDragging = false;
            }, 100);
        }
    } else {
        wasDragging = false;
    }
});

async function saveDashboardOrder(items) {
    await apiRequest('/dashboard/reorder', 'POST', { user_id: userId, items: items });
}


// Modal Helpers
let modalResolver = null;
// Updated signature to support Date and Initial Date
function showModal(title, message, hasInput = false, initialValue = '', hasDate = false, initialDate = '') {
    return new Promise((resolve) => {
        document.getElementById('modal-title').innerText = title;
        document.getElementById('modal-message').innerText = message;

        const input = document.getElementById('modal-input');
        input.value = initialValue;
        input.style.display = hasInput ? 'block' : 'none';

        // Date Input handling
        // We create a wrapper with label if it doesn't exist
        let dateWrapper = document.getElementById('modal-date-wrapper');
        if (!dateWrapper) {
            dateWrapper = document.createElement('div');
            dateWrapper.id = 'modal-date-wrapper';
            dateWrapper.style.marginTop = '16px';
            dateWrapper.style.width = '100%';
            dateWrapper.style.boxSizing = 'border-box';

            const label = document.createElement('label');
            label.innerText = 'Fecha de vencimiento (Opcional)';
            label.style.display = 'block';
            label.style.marginBottom = '8px';
            label.style.fontSize = '14px';
            label.style.fontWeight = '500';
            label.style.color = 'var(--tg-theme-hint-color)';

            const dateInput = document.createElement('input');
            dateInput.type = 'text'; // Start as text for placeholder support
            dateInput.placeholder = 'Seleccionar fecha...';
            dateInput.onfocus = function () {
                this.type = 'date';
                this.click(); // Try to open picker immediately
            };
            dateInput.onblur = function () {
                if (!this.value) this.type = 'text';
            };
            dateInput.id = 'modal-date';

            // Mobile-friendly styling: Prevent overflow and enforce appearance
            dateInput.style.display = 'block';
            dateInput.style.width = '100%';
            dateInput.style.maxWidth = '100%';
            dateInput.style.margin = '0';
            dateInput.style.padding = '12px';
            dateInput.style.borderRadius = '10px';
            dateInput.style.border = '1px solid var(--tg-theme-secondary-bg-color)';
            dateInput.style.backgroundColor = 'var(--tg-theme-secondary-bg-color)';
            dateInput.style.color = 'var(--tg-theme-text-color)';
            dateInput.style.minHeight = '50px';
            dateInput.style.boxSizing = 'border-box';
            dateInput.style.fontSize = '16px';
            dateInput.style.fontFamily = 'inherit';
            dateInput.style.appearance = 'none';
            dateInput.style.webkitAppearance = 'none'; // Critical for iOS width issues

            dateWrapper.appendChild(label);
            dateWrapper.appendChild(dateInput);

            // Insert after text input
            input.parentNode.insertBefore(dateWrapper, input.nextSibling);
        }

        // Reset and Toggle
        const dateInput = document.getElementById('modal-date');
        // Handle YYYY-MM-DDT00:00:00 or similar. Input type=date expects YYYY-MM-DD
        let formattedDate = '';
        if (initialDate) {
            // backend passes str(datetime) which can be "YYYY-MM-DD HH:MM:SS" OR "YYYY-MM-DDT..."
            formattedDate = initialDate.split(/[T ]/)[0]; // Regex split on T or space
        }
        dateInput.value = formattedDate;
        dateWrapper.style.display = hasDate ? 'block' : 'none';

        document.getElementById('custom-modal').style.display = 'flex';
        document.getElementById('custom-modal').dataset.hasDate = hasDate;

        modalResolver = resolve;
        if (hasInput) setTimeout(() => input.focus(), 100);
    });
}

function closeModal(result) {
    const modal = document.getElementById('custom-modal');
    const input = document.getElementById('modal-input');
    const dateInput = document.getElementById('modal-date');
    const hasDate = modal.dataset.hasDate === 'true'; // string comparison because dataset is string

    modal.style.display = 'none';
    if (modalResolver) {
        if (result && hasDate) {
            modalResolver({
                content: input.value,
                deadline: dateInput.value || null
            });
        } else {
            modalResolver(result ? input.value : null);
        }
    }
    modalResolver = null;
}

// --- HELPER: Centralized Task Rendering ---
function getTaskInnerHtml(task) {
    const deadlineHtml = task.deadline ? `<div class="task-deadline">${formatDeadline(task.deadline)}</div>` : '';
    // Determine completed class based on task status
    const isCompleted = task.status === 'COMPLETED';
    const escapedContent = escapeAttr(task.content);
    const deadline = task.deadline || "";
    const recurrence = task.recurrence || "";


    // Recurrence Icon Indicator if set
    let recurrenceIcon = "";
    if (recurrence && recurrence !== "None") {
        recurrenceIcon = `<span style="font-size:12px; margin-left:4px; color:var(--tg-theme-link-color);" title="Repite: ${recurrence}">↻</span>`;
    }

    return `
        <div class="task-checkbox ${isCompleted ? 'checked' : ''}" onclick="toggleTask(${task.id}, '${task.status}'); event.stopPropagation();"></div>
        <div class="task-content">
            <span class="${isCompleted ? 'completed-text' : ''}">${task.content} ${recurrenceIcon}</span>
            ${task.deadline ? `<span class="deadline-text">${formatDeadline(task.deadline)}</span>` : ''}
        </div>
        <button class="icon-btn edit-btn"
            data-content="${escapedContent}"
            data-deadline="${deadline}"
            data-recurrence="${recurrence}"
            data-list-id="${task.list_id || ''}"
            onclick="editTask(${task.id}, this); event.stopPropagation();">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
            </svg>
        </button>
        <button class="icon-btn delete-btn" onclick="deleteTask(${task.id}); event.stopPropagation();">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2-2v2"></path>
            </svg>
        </button>
    `;
}
// Expose global
window.closeModal = closeModal;
window.switchTab = switchTab;
window.openAddTaskModal = openAddTaskModal;
window.addList = addList;
window.toggleTask = toggleTask;
window.addTaskToList = addTaskToList;
window.toggleListMixed = toggleListMixed;
window.editList = editList;
window.deleteList = deleteList;
window.shareList = shareList;
window.startReorderList = startReorderList;
window.saveListColor = saveListColor;
window.previewListColorMixed = previewListColorMixed;
window.editTask = editTask;
window.deleteTask = deleteTask;
window.respondInvite = respondInvite;

function escapeAttr(str) { return str ? str.replace(/"/g, '&quot;') : ''; }
async function loadInvites() {
    const container = document.getElementById('invites-container');
    const invites = await apiRequest(`/invites`);
    if (!invites || invites.length === 0) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'block';
    container.innerHTML = '<h3>Invitaciones</h3>';
    invites.forEach(inv => {
        const el = document.createElement('div');
        el.className = 'invite-item';
        el.innerHTML = `<div>${inv.list_name} (@${inv.owner_name})</div>
        <div class="invite-actions">
           <button onclick="respondInvite(${inv.list_id}, true)">✅</button>
           <button onclick="respondInvite(${inv.list_id}, false)">❌</button>
        </div>`;
        container.appendChild(el);
    });
}



// Helper for invite response
async function respondInvite(listId, accept) {
    try {
        await apiRequest(`/invites/${listId}/respond`, 'POST', { accept: accept });
        loadInvites(); // Refresh invites
        if (accept) loadAllView();
    } catch (e) {
        console.error("Error al responder invitación: " + e.message);
    }
}

// Ensure everything is loaded
// Ensure everything is loaded
// Safe Init
function initApp(retries = 0) {
    // Try to get userId if missing
    if (!userId) {
        userId = tg.initDataUnsafe?.user?.id;
        if (!userId) {
            const urlParams = new URLSearchParams(window.location.search);
            userId = urlParams.get('user_id');
        }
    }

    if (userId) {
        // Initialize TG but don't wait for it to render data
        if (tg) {
            try { tg.ready(); tg.expand(); } catch (e) { console.error(e); }
        }

        console.log("InitApp: Triggering dated view immediately");

        // Load saved tab or default
        const savedTab = localStorage.getItem('activeTab') || 'dated';
        switchTab(savedTab);

    } else {
        if (retries < 10) {
            setTimeout(() => initApp(retries + 1), 200);
        } else {
            // Try one last time to get from URL
            const urlParams = new URLSearchParams(window.location.search);
            const fallbackId = urlParams.get('user_id');
            if (fallbackId) {
                userId = fallbackId;
                const savedTab = localStorage.getItem('activeTab') || 'dated';
                switchTab(savedTab);
            } else {
                console.error("No userId found after retries");
                document.getElementById('dated-container').innerHTML = '<div class="empty-state">Error: Usuario no identificado.</div>';
            }
        }
    }
}

// Safe Init Trigger
function triggerInit() {
    initApp();
}

// Robust initialization trigger
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    triggerInit();
} else {
    window.addEventListener('load', triggerInit);
    document.addEventListener('DOMContentLoaded', triggerInit);
}
