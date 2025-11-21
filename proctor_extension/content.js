console.log("--- ¡CONTENT.JS INYECTADO Y EJECUTANDO! ---");

let checks = { agent: false, browser: false, discord: false, zoom: false };

// Elementos del DOM
let progressBar = document.getElementById('proctor-progress-bar');
let statusMessage = document.getElementById('proctor-status-message');
let startButton = document.getElementById('start-exam-button');
let checkAgent = document.getElementById('check-agent');
let checkBrowser = document.getElementById('check-browser');
let checkDiscord = document.getElementById('check-discord');
let checkZoom = document.getElementById('check-zoom');

// Lógica para leer el ID del examen
let currentPage = null;
let currentExamenId = null;
const welcomeMatch = window.location.pathname.match(/exam\/(\d+)\/welcome\//);
const examMatch = window.location.pathname.match(/exam\/(\d+)\/start\//);

if (welcomeMatch) {
    currentPage = 'welcome';
    currentExamenId = welcomeMatch[1]; 
} else if (examMatch) {
    currentPage = 'exam';
    currentExamenId = examMatch[1]; 
}

// Informar al background script
chrome.runtime.sendMessage({ 
    type: 'PAGE_LOADED', 
    page: currentPage,
    examen_id: currentExamenId 
});

// --- LÓGICA PARA LA PÁGINA DE BIENVENIDA ---
if (currentPage === 'welcome') {
    setTimeout(() => {
         chrome.runtime.sendMessage({ type: 'CHECK_ENVIRONMENT' });
    }, 500); 
    setInterval(() => {
        if (startButton && !startButton.disabled) {
            chrome.runtime.sendMessage({ type: 'CHECK_ENVIRONMENT' });
        }
    }, 3000); 
    if (startButton) {
        startButton.addEventListener('click', onStartButtonClick);
    }
}

// --- LÓGICA DE PÁGINA DE EXAMEN ---
if (currentPage === 'exam') {
    
    // 1. El requestFullscreen lo maneja home.html, aquí solo atrapamos error por si acaso
    try {
        document.documentElement.requestFullscreen();
    } catch (err) {
        console.warn("No se pudo entrar en pantalla completa (puede que ya esté activa):", err);
    }

    // 2. Inicia el revisor de "buzón de mensajes" cada segundo
    const plagioCheckInterval = setInterval(checkPlagioFlag, 1000);

    // 3. Función genérica para bloquear eventos
    function blockEvent(e) {
        e.preventDefault();
        e.stopPropagation();
        return false;
    }

    // 4. Bloquear Clic Derecho, Copiar, Pegar, Cortar
    window.addEventListener('contextmenu', blockEvent);
    window.addEventListener('copy', blockEvent);
    window.addEventListener('paste', blockEvent);
    window.addEventListener('cut', blockEvent);

    // 5. Bloquear Teclas de Función (F1-F12)
    window.addEventListener('keydown', function(e) {
        if (e.key.startsWith('F') && !isNaN(e.key.substring(1))) {
            console.warn(`Tecla F bloqueada: ${e.key}`);
            blockEvent(e);
        }
    });

    // 6. Detectar si el usuario sale de pantalla completa
    window.addEventListener('fullscreenchange', async function() {
        
        // Revisa si la página sigue en pantalla completa
        if (document.fullscreenElement) {
            return; 
        }

        // Si salió, revisamos el "tablero de avisos" (Storage)
        try {
            const result = await chrome.storage.local.get('isFinishingExam');
            
            if (result.isFinishingExam === true) {
                // ¡Fue a propósito (finalizó el examen)!
                console.log("Saliendo de pantalla completa (final del examen). No es plagio.");
                // Limpiamos el tablero
                chrome.storage.local.remove('isFinishingExam');
                return; 
            }
        } catch (e) {
            console.error("Error al leer storage", e);
        }
        
        // Si NO fue a propósito, ¡ES PLAGIO!
        console.warn("¡ALERTA DE PLAGIO! Salió de pantalla completa (usuario forzó).");
        chrome.runtime.sendMessage({ 
            type: 'PLAGIO_DETECTED', 
            reason: 'salida de pantalla completa (usuario)' 
        });
    });
}

// --- LISTENERS DE MENSAJES ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("Mensaje recibido en content.js:", message);
    switch (message.type) {
        case 'AGENT_STATUS':
            checks.agent = message.connected;
            updateCheckUI(checkAgent, checks.agent, message.error);
            break;
        case 'BROWSER_STATUS':
            checks.browser = message.isClean;
            updateCheckUI(checkBrowser, checks.browser, message.message || "Navegador limpio.");
            break;
        case 'APPS_STATUS':
            checks.discord = !message.discordOpen;
            checks.zoom = !message.zoomOpen;
            updateCheckUI(checkDiscord, checks.discord, "Discord está abierto");
            updateCheckUI(checkZoom, checks.zoom, "Zoom está abierto");
            break;
        case 'PLAGIO_ALERT':
            handlePlagioInPage(message.reason);
            break;
    }
    if (window.location.pathname.includes('/welcome/')) {
        updateWelcomeUI();
    }
});

function updateCheckUI(element, success, failMessage) {
    if (!element) return;
    if (success) {
        element.textContent = 'OK';
        element.className = 'badge bg-success rounded-pill';
    } else {
        element.textContent = 'PENDIENTE';
        element.className = 'badge bg-danger rounded-pill';
    }
    if (!success && statusMessage) {
        statusMessage.textContent = failMessage;
    }
}

function updateWelcomeUI() {
    if (!progressBar || !startButton) return;
    let progress = 0;
    if (checks.agent) progress += 25;
    if (checks.browser) progress += 25;
    if (checks.discord) progress += 25;
    if (checks.zoom) progress += 25;
    progressBar.style.width = `${progress}%`;
    progressBar.setAttribute('aria-valuenow', progress);
    progressBar.textContent = `${progress}%`;
    const allClear = checks.agent && checks.browser && checks.discord && checks.zoom;
    if (allClear) {
        progressBar.classList.remove('bg-warning');
        progressBar.classList.add('bg-success');
        statusMessage.textContent = '¡Todo listo! Puedes comenzar el examen.';
        startButton.disabled = false;
        startButton.textContent = 'Comenzar Examen';
        startButton.classList.remove('btn-primary');
        startButton.classList.add('btn-success');
    } else {
        progressBar.classList.add('bg-warning');
        progressBar.classList.remove('bg-success');
        startButton.disabled = false; 
        startButton.textContent = 'Cerrar Todo y Comenzar';
        startButton.classList.add('btn-primary');
        startButton.classList.remove('btn-success');
        
        if (checks.agent && checks.discord && checks.zoom && !checks.browser) {
            // msg ya seteado
        } else if (!checks.agent) {
             statusMessage.textContent = "Error: El agente de seguridad no está conectado.";
        }
    }
}

function onStartButtonClick() {
    if (!startButton) return;

    const allClear = checks.agent && checks.browser && checks.discord && checks.zoom;

    if (allClear) {
        startButton.disabled = true;
        startButton.textContent = 'Iniciando...';
        const examUrl = startButton.getAttribute('data-url');

        if (examUrl) {
            // SOLO redirigimos, el fullscreen lo pide home.html
            window.location.href = examUrl;
        } else {
            console.error("No se pudo encontrar la URL del examen en el botón.");
        }
    } else {
        statusMessage.textContent = 'Forzando cierre de pestañas y aplicaciones...';
        startButton.disabled = true;
        chrome.runtime.sendMessage({ type: 'CLOSE_ALL' });
        setTimeout(() => {
            if (startButton.disabled) {
                startButton.disabled = false;
                statusMessage.textContent = "Error al cerrar. Por favor, intente de nuevo o cierre manualmente.";
            }
        }, 5000); 
    }
}

function handlePlagioInPage(reason) {
    if (document.fullscreenElement) {
        document.exitFullscreen();
    }
    document.body.innerHTML = `
        <div style="display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; background-color: #f8d7da; color: #721c24; text-align: center; font-family: sans-serif;">
            <h1 style="font-size: 3em; margin: 0;">Examen Cancelado</h1>
            <p style="font-size: 1.5em; margin-top: 20px;">Motivo: Intento de plagio detectado.</p>
            <p style="font-size: 1.2em; color: #721c24;">(${reason})</p>
            <p style="margin-top: 40px;">Serás redirigido al panel de exámenes.</p>
        </div>
    `;
    setTimeout(() => {
        // --- ¡AQUÍ ESTÁ EL CAMBIO DE DOMINIO! ---
        window.location.href = 'https://examen.asantosb.dev/exam/dashboard/';
    }, 5000);
}

function checkPlagioFlag() {
    if (!currentExamenId) return; 

    chrome.storage.local.get('plagioFlag', function(result) {
        if (result.plagioFlag) {
            // Revisa si la bandera es PARA este examen
            if (result.plagioFlag.examenId == currentExamenId) {
                console.log("¡Bandera de plagio detectada por el revisor!");
                handlePlagioInPage(result.plagioFlag.reason);
                chrome.storage.local.remove('plagioFlag');
            }
        }
    });
}

// Listener para la comunicación segura con home.html al finalizar
window.addEventListener("message", async (event) => {
    if (event.source === window && event.data && event.data.type === 'FROM_PAGE_EXAM_FINISHED') {
        
        console.log("Content.js recibió solicitud de finalización.");

        // 1. Pone el "aviso" en el tablero (Storage)
        await chrome.storage.local.set({ isFinishingExam: true });

        // 2. Avisa al background para apagar el agente python
        chrome.runtime.sendMessage({ type: 'EXAM_FINISHED' });

        // 3. Envía confirmación DE VUELTA a home.html
        window.postMessage({ type: 'EXTENSION_ACK_FINISHED' }, '*');
    }
});