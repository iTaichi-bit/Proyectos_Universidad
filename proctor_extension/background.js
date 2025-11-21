// 6TA VERSIÓN - MANEJO DE MÚLTIPLES EXÁMENES

console.log("--- ¡SERVICE WORKER BACKGROUND.JS CARGADO! ---");

const NATIVE_HOST_NAME = "com.examen.proctoring";
let nativePort = null;
let examTabId = null;
let isExamActive = false;
let isConnecting = false;
let examWindowId = null; 
let activeExamenId = null; // <-- ¡NUEVO! Guardará el ID del examen activo

// --- (connectNative, onNativeMessage, onNativeDisconnect, sendNativeMessage no cambian) ---
function connectNative() {
  if (isConnecting || nativePort) { return; }
  isConnecting = true; 
  console.log(`Intentando conectar a ${NATIVE_HOST_NAME}`);
  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);
    nativePort.onMessage.addListener(onNativeMessage);
    nativePort.onDisconnect.addListener(onNativeDisconnect);
    console.log("Conectado al agente nativo.");
    isConnecting = false; 
    sendMessageToContent({ type: "AGENT_STATUS", connected: true });
  } catch (error) {
    console.error("Error al conectar con agente nativo:", error);
    isConnecting = false; 
    sendMessageToContent({ type: "AGENT_STATUS", connected: false, error: error.message });
    if (!isExamActive) { setTimeout(connectNative, 5000); }
  }
}
function onNativeMessage(message) {
  console.log("Mensaje recibido del agente:", message);
  sendMessageToContent(message); 
  if (message.type === 'PLAGIO_DETECTED') {
    handlePlagio(`apertura de ${message.app}`);
  }
}
function onNativeDisconnect() {
  console.error("Agente Nativo Desconectado.", chrome.runtime.lastError?.message || "Error desconocido");
  nativePort = null;
  isConnecting = false; 
  sendMessageToContent({ type: "AGENT_STATUS", connected: false, error: "Agente desconectado" });
  if (isExamActive) {
    handlePlagio("desconexión del agente de seguridad");
  } else {
    console.log("Reintentando conexión en 5 segundos...");
    if (!isConnecting) { setTimeout(connectNative, 5000); }
  }
}
function sendNativeMessage(msg) {
  if (nativePort) {
    try { nativePort.postMessage(msg); } 
    catch(e) { console.error("Error al enviar mensaje nativo:", e); }
  } else {
    console.error("No se puede enviar mensaje, puerto nativo no conectado.");
  }
}

// --- ¡LÓGICA DEL EXAMEN MODIFICADA! ---
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'PAGE_LOADED') {
    examTabId = sender.tab.id;
    examWindowId = sender.tab.windowId; 
    activeExamenId = message.examen_id; // <-- ¡NUEVO! Guarda el ID del examen

    console.log(`Página cargada: ${message.page}, ID de Examen: ${activeExamenId}`);

    
    
    
    
    
    // Lógica de reconexión de agente (para F5)
    if (nativePort) {
        sendMessageToContent({ type: "AGENT_STATUS", connected: true });
    } else {
        connectNative();
    }

    if (message.page === 'welcome') {
      isExamActive = false;
    } else if (message.page === 'exam') {
      isExamActive = true;
      sendNativeMessage({ command: 'START_MONITORING' });
    }
    sendResponse({ status: "ok" });
  }
  
  // --- ¡AÑADE ESTE BLOQUE! ---
  else if (message.type === 'PLAGIO_DETECTED') {
      handlePlagio(message.reason);
      sendResponse({status: 'plagio reportado'});
  }
  // --- FIN DEL BLOQUE ---


// --- ¡BLOQUE MODIFICADO! ---
  // --- ¡BLOQUE MODIFICADO! ---
  else if (message.type === 'EXAM_FINISHED') {
    console.log("Examen finalizado por el usuario.");
    isExamActive = false; // Desactiva la guardia
    activeExamenId = null;
    examWindowId = null;
    sendNativeMessage({ command: 'STOP_MONITORING' }); // ¡Apaga el agente!
    
    // Limpia el tablero de avisos
    chrome.storage.local.remove('isFinishingExam'); 
    chrome.storage.local.remove('plagioFlag'); // Limpia también el de plagio
    
    sendResponse({status: 'exam finished ack'});
  }
  // --- FIN DEL BLOQUE ---


  else if (message.type === 'CHECK_ENVIRONMENT') {
    checkBrowserState(); 
    sendNativeMessage({ command: 'CHECK_APPS' });
  }


  // --- ¡AÑADE ESTE BLOQUE! ---
  else if (message.type === 'PING') {
    console.log("BACKGROUND: Recibido PING, enviando PONG.");
    sendResponse({ status: 'PONG' });
  }
  // --- FIN DEL BLOQUE ---


  else if (message.type === 'CLOSE_ALL') {
    cleanBrowserState(); 
    sendNativeMessage({ command: 'CLOSE_APPS' }); 
  }
  return true; 
});






// --- (tabs.onCreated y windows.onFocusChanged no cambian) ---
chrome.tabs.onCreated.addListener(function(tab) {
    if (isExamActive) {
        console.warn("¡ALERTA DE PLAGIO! Nueva pestaña abierta.");
        handlePlagio("intento de abrir una nueva pestaña");
    }
});
chrome.windows.onFocusChanged.addListener(function(windowId) {
    if (!isExamActive || !examWindowId) { return; }
    if (windowId === chrome.windows.WINDOW_ID_NONE) {
        handlePlagio("pérdida de foco del examen (cambio a otra app o escritorio)");
    } else if (windowId !== examWindowId) {
        handlePlagio("cambio a otra ventana de Chrome (modo incógnito o perfil)");
    }
});

// --- (sendMessageToContent, checkBrowserState, cleanBrowserState no cambian) ---
function sendMessageToContent(message) {
  if (examTabId) {
    chrome.tabs.sendMessage(examTabId, message, (response) => {
      if (chrome.runtime.lastError) { /* Silenciar errores */ }
    });
  }
}
async function checkBrowserState() {
    if (!examWindowId) return; 
    let isClean = true;
    let failReason = "";
    const currentWindow = await chrome.windows.get(examWindowId, { populate: true });
    if (currentWindow.incognito) {
        isClean = false;
        failReason = "El examen no puede iniciarse en modo incógnito.";
    }
    const otherTabs = currentWindow.tabs.filter(tab => tab.id !== examTabId && !tab.url.startsWith("chrome://"));
    if (otherTabs.length > 0) {
        isClean = false;
        failReason = `Hay ${otherTabs.length} pestañas abiertas.`;
    }
    const allWindows = await chrome.windows.getAll();
    const otherWindows = allWindows.filter(w => w.id !== examWindowId && w.type === 'normal');
    if (otherWindows.length > 0) {
        isClean = false;
        failReason = `Hay ${otherWindows.length} ventanas (normales) abiertas.`;
    }
    sendMessageToContent({ 
        type: 'BROWSER_STATUS', 
        isClean: isClean,
        message: failReason
    });
}
async function cleanBrowserState() {
    if (!examWindowId) return;
    const currentWindow = await chrome.windows.get(examWindowId);
    if (currentWindow.incognito) {
        checkBrowserState(); 
        return; 
    }
    const currentTabs = await chrome.tabs.query({ windowId: examWindowId });
    const tabsToClose = [];
    for (const tab of currentTabs) {
        if (tab.id !== examTabId && !tab.url.startsWith("chrome://")) {
            tabsToClose.push(tab.id);
        }
    }
    if (tabsToClose.length > 0) {
        await chrome.tabs.remove(tabsToClose);
    }
    const allWindows = await chrome.windows.getAll();
    const windowsToClose = [];
    for (const w of allWindows) {
        if (w.id !== examWindowId && w.type === 'normal') {
            windowsToClose.push(w.id);
        }
    }
    if (windowsToClose.length > 0) {
        for (const windowId of windowsToClose) {
            await chrome.windows.remove(windowId);
        }
    }
    checkBrowserState(); 
}











// ... (todo el código anterior de background.js se queda igual) ...







// --- ¡FUNCIÓN handlePlagio MODIFICADA! (Arregla Bug Tecla Windows) ---
// --- ¡FUNCIÓN handlePlagio MODIFICADA! (Arregla Bug Tecla Windows) ---
async function handlePlagio(reason) {
  if (!isExamActive) return; // Evita que se llame varias veces
  isExamActive = false;
  
  // 1. Iniciar la cancelación en la BD (esto ya funciona)
  getCsrfTokenAndFetch(activeExamenId); 
  
  // 2. Parar el monitoreo del agente
  sendNativeMessage({ command: 'STOP_MONITORING' }); 
  console.error(`ALERTA DE PLAGIO: ${reason}`);

  // --- ¡SOLUCIÓN BUG 2! ---
  // 3. Dejamos una "nota" en el "tablero de avisos" de plagio
  if (activeExamenId) {
      chrome.storage.local.set({
          plagioFlag: {
              examenId: activeExamenId,
              reason: reason
          }
      });
  }

  // 4. Intentamos forzar el foco de vuelta
  try {
    if (examWindowId) {
        await chrome.windows.update(examWindowId, { focused: true });
    }
    if (examTabId) {
        await chrome.tabs.update(examTabId, { active: true });
        
        // 5. Enviamos el mensaje (puede fallar, pero la "nota" es el respaldo)
        chrome.tabs.sendMessage(examTabId, {
          type: "PLAGIO_ALERT",
          reason: reason
        });
    }
  } catch (error) {
    console.error("Error al forzar el foco:", error);
  }
  // --- FIN DE LA SOLUCIÓN ---

  // 6. Limpiar las variables
  examWindowId = null; 
  activeExamenId = null; 
}
// --- (La función getCsrfTokenAndFetch se queda igual) ---
// ...








// --- ¡FUNCIÓN getCsrfTokenAndFetch MODIFICADA! ---
// Ahora acepta el ID del examen como argumento
// --- ¡FUNCIÓN getCsrfTokenAndFetch MODIFICADA! ---
async function getCsrfTokenAndFetch(examen_id) {
    console.log(`Obteniendo token CSRF para cancelar examen ID: ${examen_id}...`);
    
    if (!examen_id) {
        console.error("Error: Se intentó cancelar un examen sin ID.");
        return;
    }

    try {
        // 1. CAMBIO: Dominio real HTTPS
        const cookie = await chrome.cookies.get({
            url: 'https://examen.asantosb.dev', 
            name: 'csrftoken'
        });

        if (!cookie) {
            console.error("Error: No se encontró la cookie CSRF.");
            return;
        }

        const csrfToken = cookie.value;
        console.log("Token CSRF encontrado:", csrfToken);

        // 2. CAMBIO: Endpoint real HTTPS
        const response = await fetch('https://examen.asantosb.dev/exam/cancel/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            },
            credentials: 'include', 
            body: JSON.stringify({
                'examen_id': examen_id 
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('Respuesta del servidor (cancelación exitosa):', data);
        } else {
            console.error('Error del servidor al cancelar:', data);
        }

    } catch (error) {
        console.error('Error crítico al obtener CSRF o enviar fetch:', error);
    }
}