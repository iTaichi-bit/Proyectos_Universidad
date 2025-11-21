import sys
import json
import struct
import psutil
import threading
import time
import logging

# --- ¡NUEVAS IMPORTACIONES! ---
try:
    from pynput import keyboard
except ImportError:
    logging.error("ERROR: La biblioteca 'pynput' no está instalada. Ejecuta: pip install pynput")
    sys.exit(1) # Salir si pynput no está

logging.basicConfig(filename='proctor_agent.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

APP_NAMES = {
    'discord': 'Discord.exe' if sys.platform == "win32" else "Discord",
    'zoom': 'Zoom.exe' if sys.platform == "win32" else "Zoom",
}

# --- Variables Globales ---
monitoring_thread = None
stop_monitoring_event = threading.Event()
key_listener = None
# Teclas que estamos vigilando
current_keys = set()
# Teclas/Combinaciones PROHIBIDAS
forbidden_keys = {
    keyboard.Key.print_screen, # Captura de pantalla
    keyboard.Key.cmd,          # Tecla Windows
    keyboard.Key.cmd_r,        # Tecla Windows Derecha
    keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
    keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8,
    keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12,
}
forbidden_combos = {
    frozenset([keyboard.Key.alt_l, keyboard.Key.tab]),    # Alt+Tab
    frozenset([keyboard.Key.alt_r, keyboard.Key.tab]),    # Alt+Tab (derecho)
    frozenset([keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.Key.delete]), # Ctrl+Alt+Del
    frozenset([keyboard.Key.ctrl_r, keyboard.Key.alt_r, keyboard.Key.delete]), # Ctrl+Alt+Del
    
    # --- ¡AÑADE ESTAS! ---
    frozenset([keyboard.Key.ctrl_l, keyboard.Key.esc]),   # Ctrl + Esc
    frozenset([keyboard.Key.ctrl_r, keyboard.Key.esc]),   # Ctrl + Esc (derecho)
    frozenset([keyboard.Key.alt_l, keyboard.Key.esc]),    # Alt + Esc
    frozenset([keyboard.Key.alt_r, keyboard.Key.esc]),    # Alt + Esc (derecho)
    # --- FIN DE LO AÑADIDO ---
    
    # Win+Shift+S (Herramienta de recortes)
    frozenset([keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('s')]),
    frozenset([keyboard.Key.cmd, keyboard.Key.shift, keyboard.KeyCode.from_char('S')]),
}

# --- Funciones de Comunicación Nativa (Sin cambios) ---
def get_message():
    try:
        raw_length = sys.stdin.buffer.read(4)
        if not raw_length:
            logging.warning("No se recibió longitud. Saliendo.")
            sys.exit(0)
        message_length = struct.unpack('@I', raw_length)[0]
        message = sys.stdin.buffer.read(message_length).decode('utf-8')
        logging.debug(f"Mensaje recibido: {message}")
        return json.loads(message)
    except Exception as e:
        logging.error(f"Error al leer mensaje: {e}")
        return None

def send_message(message_content):
    try:
        encoded_content = json.dumps(message_content).encode('utf-8')
        encoded_length = struct.pack('@I', len(encoded_content))
        sys.stdout.buffer.write(encoded_length)
        sys.stdout.buffer.write(encoded_content)
        sys.stdout.buffer.flush()
        logging.debug(f"Mensaje enviado: {message_content}")
    except Exception as e:
        logging.error(f"Error al enviar mensaje: {e}")

# --- Funciones del Agente (Procesos) (Sin cambios) ---
def check_apps_running():
    discord_open = False
    zoom_open = False
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == APP_NAMES['discord'].lower():
                discord_open = True
            if proc.info['name'].lower() == APP_NAMES['zoom'].lower():
                zoom_open = True
            if discord_open and zoom_open:
                break
    except Exception as e:
        logging.error(f"Error al chequear apps: {e}")
    return {"discordOpen": discord_open, "zoomOpen": zoom_open}

def close_apps():
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == APP_NAMES['discord'].lower() or \
               proc.info['name'].lower() == APP_NAMES['zoom'].lower():
                try:
                    proc.terminate()
                    logging.info(f"Terminando proceso: {proc.info['name']}")
                except psutil.AccessDenied:
                    logging.warning(f"Acceso denegado para terminar: {proc.info['name']}")
    except Exception as e:
        logging.error(f"Error al cerrar apps: {e}")

# --- ¡NUEVAS FUNCIONES DE TECLADO! ---
def on_key_press(key):
    global key_listener
    
    # 1. Revisa teclas individuales prohibidas
    if key in forbidden_keys:
        logging.warning(f"PLAGIO DETECTADO: Tecla prohibida presionada: {key}")
        send_message({"type": "PLAGIO_DETECTED", "app": f"Tecla prohibida ({str(key)})"})
        if key_listener:
            key_listener.stop()
        return False # ¡Bloquea la tecla Y detiene el listener!

    # 2. Revisa combinaciones prohibidas (como Alt+Tab)
    current_keys.add(key)
    for combo in forbidden_combos:
        if combo.issubset(current_keys):
            logging.warning(f"PLAGIO DETECTADO: Combinación de teclas prohibida: {combo}")
            send_message({"type": "PLAGIO_DETECTED", "app": "Combinación de teclas prohibida"})
            if key_listener:
                key_listener.stop()
            return False # ¡Bloquea la combinación Y detiene el listener!
            
    # Si la tecla es normal (ej. 'a', 'b', 'c'), la permite
    return True

def on_key_release(key):
    try:
        current_keys.remove(key)
    except KeyError:
        pass # La tecla ya fue removida

def start_key_listener():
    global key_listener
    # Inicia el listener en un hilo separado
    key_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release, suppress=True) # <-- suppress=True ¡BLOQUEA LAS TECLAS!
    key_listener.start()
    logging.info("Listener de teclado INICIADO y BLOQUEANDO.")

# --- Hilo de Monitoreo (MODIFICADO) ---
def monitor_apps_thread():
    global key_listener
    logging.info("MONITOREO DE PLAGIO INICIADO")
    
    # ¡Inicia el listener de teclado!
    start_key_listener()
    
    while not stop_monitoring_event.is_set():
        try:
            # 1. Revisa si el listener de teclado sigue vivo
            if key_listener is None or not key_listener.is_alive():
                logging.warning("El listener de teclado se detuvo (probablemente por plagio). Deteniendo monitoreo.")
                break # Sale del bucle

            # 2. Revisa las apps (Discord/Zoom)
            status = check_apps_running()
            if status["discordOpen"]:
                logging.warning("PLAGIO DETECTADO: Discord")
                send_message({"type": "PLAGIO_DETECTED", "app": "Discord"})
                break
            if status["zoomOpen"]:
                logging.warning("PLAGIO DETECTADO: Zoom")
                send_message({"type": "PLAGIO_DETECTED", "app": "Zoom"})
                break
                
            time.sleep(3) # Chequear apps cada 3 segundos
        except Exception as e:
            logging.error(f"Error en hilo de monitoreo: {e}")
            break
            
    # Detiene el listener de teclado si el bucle se rompe
    if key_listener and key_listener.is_alive():
        key_listener.stop()
        key_listener = None
    
    logging.info("MONITOREO DE PLAGIO DETENIDO")

# --- Bucle Principal (MODIFICADO) ---
def main_loop():
    global monitoring_thread, key_listener
    
    while True:
        message = get_message()
        if message is None:
            continue

        command = message.get('command')

        if command == 'CHECK_APPS':
            status = check_apps_running()
            send_message({"type": "APPS_STATUS", **status})
            
        elif command == 'CLOSE_APPS':
            close_apps()
            time.sleep(1)
            status = check_apps_running()
            send_message({"type": "APPS_STATUS", **status})
            
        elif command == 'START_MONITORING':
            if monitoring_thread is None or not monitoring_thread.is_alive():
                stop_monitoring_event.clear()
                monitoring_thread = threading.Thread(target=monitor_apps_thread, daemon=True)
                monitoring_thread.start()
                
        elif command == 'STOP_MONITORING':
            stop_monitoring_event.set()
            if monitoring_thread and monitoring_thread.is_alive():
                monitoring_thread.join(timeout=1)
            if key_listener and key_listener.is_alive():
                key_listener.stop()
                key_listener = None
                
if __name__ == "__main__":
    logging.info("Agente de Proctoring Iniciado.")
    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("Agente detenido manualmente.")
    except Exception as e:
        logging.error(f"Error fatal en main_loop: {e}")
    finally:
        stop_monitoring_event.set()
        if key_listener and key_listener.is_alive():
            key_listener.stop()
        logging.info("Agente de Proctoring Finalizado.")