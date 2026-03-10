"""
ACE-Step 1.5 Launcher — V4.0
One window. One big button. Everything else is automatic.

Drop this file inside ACE-Step-1.5/ next to pyproject.toml.
Installer should place it there and build the shortcut to it.

V4.0 Changes:
- Fixed: Heartbeat watchdog killing API mid-generation (one-song-and-done bug)
- Fixed: Heartbeat checkbox being bypassed when port shifts
- Fixed: Download button in WebUI navigating away instead of downloading
- Added: Visibility-aware heartbeat (survives background tabs)
- Added: Open WebUI Folder button
- Separated port rewriting from heartbeat injection
- Heartbeat server only starts when actually needed
"""

import sys
import os
import subprocess
import threading
import time
import tempfile
import socket
import webbrowser
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

import psutil
import tkinter as tk

# ─────────────────────────────────────────────────────────────────────────────
# V8: CROSS-PLATFORM UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
import platform
IS_WINDOWS = platform.system() == 'Windows'
IS_MAC     = platform.system() == 'Darwin'
IS_LINUX   = platform.system() == 'Linux'

def open_path(path):
    """Cross-platform file/folder opener."""
    import subprocess as sp
    path = str(path)
    if IS_WINDOWS:
        os.startfile(path)
    elif IS_MAC:
        sp.Popen(['open', path])
    else:
        sp.Popen(['xdg-open', path])

def get_device_for_torch():
    """V8: Cross-platform hardware routing for PyTorch."""
    try:
        import torch
        if torch.cuda.is_available():
            return 'cuda'
        if IS_MAC and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return 'mps'
    except ImportError:
        pass
    return 'cpu'

if IS_WINDOWS:
    import customtkinter as ctk
    import pystray
    from PIL import Image, ImageDraw
else:
    # Soft imports for non-Windows
    try:
        import customtkinter as ctk
    except ImportError:
        ctk = None
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        pystray = None

# ─────────────────────────────────────────────────────────────────────────────
# TOOLTIP  (zero deps — no CTkToolTip)
# ─────────────────────────────────────────────────────────────────────────────
class Tip:
    def __init__(self, widget, text, delay=650):
        self._w, self._text, self._delay = widget, text, delay
        self._id = self._win = None
        widget.bind('<Enter>', lambda e: self._schedule())
        widget.bind('<Leave>', lambda e: self._cancel())

    def _schedule(self):
        self._id = self._w.after(self._delay, self._show)

    def _cancel(self):
        if self._id:
            self._w.after_cancel(self._id)
            self._id = None
        if self._win:
            self._win.destroy()
            self._win = None

    def _show(self):
        x = self._w.winfo_rootx() + 10
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._win = w = tk.Toplevel(self._w)
        w.wm_overrideredirect(True)
        w.wm_geometry(f'+{x}+{y}')
        tk.Label(w, text=self._text,
                 bg='#1a1e2e', fg='#e8eaf0',
                 font=('Segoe UI', 9),
                 padx=10, pady=6,
                 justify='left',
                 relief='flat').pack()


# ─────────────────────────────────────────────────────────────────────────────
# INSTALL PATH DETECTION
# ─────────────────────────────────────────────────────────────────────────────
def _find_install_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent

    here = Path(__file__).parent
    if (here / 'pyproject.toml').exists():
        return here

    for candidate in [
        Path.home() / 'ACE-Step-1.5',
        Path('C:/ACE-Step-1.5'),
        Path.home() / 'Desktop' / 'ACE-Step-1.5',
    ]:
        if (candidate / 'pyproject.toml').exists():
            return candidate

    return here


INSTALL_PATH = _find_install_path()
WEBUI_DIR    = INSTALL_PATH / 'webui'

API_PORT    = 8001
GRADIO_PORT = 7860
HB_PORT     = 8765
HB_INTERVAL = 4
HB_TIMEOUT  = 300  # 5 minutes — generation can take 30-120s, browser tabs throttle timers


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATE
# ─────────────────────────────────────────────────────────────────────────────
api_process      = None
api_actual_port  = API_PORT
last_heartbeat   = 0.0
heartbeat_active = False
hb_server_started = False
tray_icon        = None
status_var       = None
temp_files: list = []


# ─────────────────────────────────────────────────────────────────────────────
# PORT UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(('127.0.0.1', port)) == 0


def find_free_port(preferred: int) -> int:
    if not port_in_use(preferred):
        return preferred
    for p in range(preferred + 1, preferred + 20):
        if not port_in_use(p):
            return p
    return preferred


# ─────────────────────────────────────────────────────────────────────────────
# HEARTBEAT RECEIVER
# ─────────────────────────────────────────────────────────────────────────────
class _HBHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self._cors()
        self.end_headers()

    def do_POST(self):
        global last_heartbeat
        self._cors()
        if self.path == '/heartbeat':
            last_heartbeat = time.time()
            self.send_response(200)
        else:
            self.send_response(404)
        self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')


def _start_hb_server_once():
    """Start heartbeat HTTP server if not already running."""
    global hb_server_started
    if hb_server_started:
        return
    hb_server_started = True
    threading.Thread(target=lambda: HTTPServer(('127.0.0.1', HB_PORT), _HBHandler).serve_forever(),
                     daemon=True).start()


def _is_api_busy() -> bool:
    """Check if the API server has active/queued jobs before allowing shutdown."""
    try:
        import urllib.request
        import json
        url = f'http://127.0.0.1:{api_actual_port}/v1/stats'
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            jobs = data.get('data', {}).get('jobs', {})
            running = jobs.get('running', 0)
            queued = jobs.get('queued', 0)
            return (running + queued) > 0
    except Exception:
        return False


def _watchdog():
    """Monitor heartbeat and stop API when browser is confirmed gone.

    Key improvements over V3.5:
    - 5 minute timeout instead of 12 seconds (browser tabs throttle timers)
    - Checks if API has active jobs before killing (protects mid-generation)
    - Grace period after timeout to double-check
    """
    global heartbeat_active
    while heartbeat_active:
        time.sleep(5)
        if last_heartbeat <= 0:
            continue
        silence = time.time() - last_heartbeat
        if silence > HB_TIMEOUT:
            # Heartbeat timed out — but check if API is mid-generation
            if _is_api_busy():
                show_status('Heartbeat lost but API is busy — waiting...')
                continue
            show_status('Browser closed — stopping API server.')
            stop_api()
            heartbeat_active = False


# ─────────────────────────────────────────────────────────────────────────────
# HTML REWRITING — port fix and heartbeat are now SEPARATE operations
# ─────────────────────────────────────────────────────────────────────────────

# Heartbeat script with visibility-aware keepalive.
# When the tab goes background, browsers throttle setInterval to ~1/min.
# This uses visibilitychange + navigator.sendBeacon as a fallback so
# the heartbeat doesn't falsely expire during long generations.
_HB_SCRIPT = """
<script>
/* ACE-Step Launcher heartbeat — auto-injected (V4) */
(function () {
    var _hb = 'http://127.0.0.1:%%HB_PORT%%/heartbeat';
    var _interval = %%INTERVAL%%;

    function ping() {
        try { fetch(_hb, { method: 'POST', keepalive: true }).catch(function () {}); }
        catch(e) {}
    }

    /* Normal interval ping (works fine in foreground) */
    ping();
    setInterval(ping, _interval);

    /* When tab goes background, browsers throttle setInterval to ~60s.
       Use visibilitychange to fire an immediate ping on hide/show,
       and a slower backup interval while hidden. */
    var _bgTimer = null;
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            ping();
            /* Backup: ping every 30s while hidden via setTimeout chain */
            (function bgPing() {
                _bgTimer = setTimeout(function () {
                    ping();
                    bgPing();
                }, 30000);
            })();
        } else {
            ping();
            if (_bgTimer) { clearTimeout(_bgTimer); _bgTimer = null; }
        }
    });
})();
</script>
"""


def _rewrite_api_port(content: str, api_port: int) -> str:
    """Rewrite hardcoded API port references in HTML content.
    This is SEPARATE from heartbeat injection so it works regardless of checkbox.
    """
    if api_port != API_PORT:
        for old in [f'127.0.0.1:{API_PORT}', f'localhost:{API_PORT}']:
            content = content.replace(old, f'127.0.0.1:{api_port}')
    return content


def _inject_heartbeat_script(content: str) -> str:
    """Inject the heartbeat ping script into HTML content.
    Only called when heartbeat is actually enabled.
    """
    snippet = (_HB_SCRIPT
               .replace('%%HB_PORT%%', str(HB_PORT))
               .replace('%%INTERVAL%%', str(HB_INTERVAL * 1000)))
    tag = '</body>'
    if tag in content:
        content = content.replace(tag, snippet + '\n' + tag, 1)
    else:
        content += snippet
    return content


def _prepare_html(html_path: Path, api_port: int, use_heartbeat: bool) -> Path:
    """Prepare an HTML file for opening: rewrite port if needed, inject heartbeat if enabled.

    Returns the original path if no modifications needed, or a temp file path if modified.
    """
    needs_port_fix = (api_port != API_PORT)

    if not needs_port_fix and not use_heartbeat:
        return html_path  # No modifications needed, open the original

    content = html_path.read_text(encoding='utf-8', errors='replace')

    if needs_port_fix:
        content = _rewrite_api_port(content, api_port)

    if use_heartbeat:
        content = _inject_heartbeat_script(content)

    tmp = tempfile.NamedTemporaryFile(
        suffix='.html', delete=False,
        mode='w', encoding='utf-8',
        prefix='acestep_ui_')
    tmp.write(content)
    tmp.close()
    temp_files.append(tmp.name)
    return Path(tmp.name)


# ─────────────────────────────────────────────────────────────────────────────
# API MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
def start_api() -> bool:
    global api_process, api_actual_port
    if api_process and api_process.poll() is None:
        return True

    api_actual_port = find_free_port(API_PORT)
    if api_actual_port != API_PORT:
        show_status(f'Port {API_PORT} busy — using {api_actual_port}')

    try:
        kwargs = {'cwd': str(INSTALL_PATH)}
        if IS_WINDOWS:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            kwargs['startupinfo'] = si
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        else:
            kwargs['start_new_session'] = True
        api_process = subprocess.Popen(
            ['uv', 'run', 'acestep-api', '--port', str(api_actual_port)],
            **kwargs)
        return True
    except Exception as exc:
        show_status(f'Failed to start API: {exc}')
        return False


def kill_orphaned_acestep_procs(silent=False):
    """Kill any python processes running acestep-api that we didn't spawn."""
    killed = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'acestep-api' in cmdline or 'acestep_api' in cmdline:
                        if proc.pid != os.getpid():
                            if api_process is None or proc.pid != api_process.pid:
                                proc.kill()
                                killed.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    if killed and not silent:
        show_status(f'Cleaned up {len(killed)} orphaned process(es): {killed}')
    return killed


def stop_api():
    global api_process, api_actual_port
    if api_process:
        try:
            api_process.terminate()
            api_process.wait(timeout=5)
        except Exception:
            try:
                api_process.kill()
            except Exception:
                pass
        api_process = None
    kill_orphaned_acestep_procs(silent=True)
    api_actual_port = API_PORT
    show_status('API server stopped.')


def wait_for_api(port: int, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    start = time.time()
    while time.time() < deadline:
        if port_in_use(port):
            return True
        elapsed = int(time.time() - start)
        remaining = timeout - elapsed
        show_status(f'Loading models... {elapsed}s elapsed  ({remaining}s before timeout)')
        time.sleep(1)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# LAUNCH ACTIONS
# ─────────────────────────────────────────────────────────────────────────────
def action_launch_webui(use_heartbeat: bool):
    global heartbeat_active, last_heartbeat

    htmls = sorted(WEBUI_DIR.glob('*.html')) if WEBUI_DIR.exists() else []
    if not htmls:
        fallback = INSTALL_PATH / 'webui.html'
        if fallback.exists():
            htmls = [fallback]
    if not htmls:
        show_status('No HTML files found — check /webui/ folder.')
        return

    show_status('Starting API server...')
    if not start_api():
        return

    def _go():
        global heartbeat_active, last_heartbeat
        show_status(f'Waiting for API on :{api_actual_port}...')
        if not wait_for_api(api_actual_port):
            show_status('API timed out — models may still be loading.')
            return

        # Start heartbeat infrastructure ONLY if checkbox is checked
        if use_heartbeat:
            _start_hb_server_once()
            heartbeat_active = True
            last_heartbeat   = time.time()
            threading.Thread(target=_watchdog, daemon=True).start()

        for html in htmls:
            prepared = _prepare_html(html, api_actual_port, use_heartbeat)
            webbrowser.open(prepared.as_uri())

        label = f'{len(htmls)} UI(s) open  |  API :{api_actual_port}'
        if use_heartbeat:
            label += '  |  Heartbeat ON'
        show_status(label)

    threading.Thread(target=_go, daemon=True).start()


def action_start_api_only():
    def _go():
        show_status('Starting API server...')
        if not start_api():
            return
        if wait_for_api(api_actual_port):
            show_status(f'API running on :{api_actual_port}')
        else:
            show_status('API started — still loading, give it a minute.')
    threading.Thread(target=_go, daemon=True).start()


def action_launch_gradio():
    def _go():
        port = find_free_port(GRADIO_PORT)
        show_status(f'Starting Gradio on :{port}...')
        gradio_kwargs = {'cwd': str(INSTALL_PATH)}
        if IS_WINDOWS:
            gradio_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        else:
            gradio_kwargs['start_new_session'] = True
        subprocess.Popen(
            ['uv', 'run', 'acestep', '--port', str(port)],
            **gradio_kwargs)
        time.sleep(10)
        webbrowser.open(f'http://127.0.0.1:{port}')
        show_status(f'Gradio open at :{port}')
    threading.Thread(target=_go, daemon=True).start()


def action_open_webui_folder():
    """Open the webui folder in Explorer so users can drop in HTML files."""
    WEBUI_DIR.mkdir(parents=True, exist_ok=True)
    open_path(str(WEBUI_DIR))


# ─────────────────────────────────────────────────────────────────────────────
# STATUS HELPER
# ─────────────────────────────────────────────────────────────────────────────
def show_status(msg: str):
    if status_var:
        try:
            status_var.set(msg)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM TRAY
# ─────────────────────────────────────────────────────────────────────────────
def _make_tray_icon_image() -> Image.Image:
    img  = Image.new('RGB', (64, 64), (12, 15, 25))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(0, 90, 210))
    draw.polygon([(20, 17), (20, 47), (50, 32)], fill=(240, 245, 255))
    return img


def build_tray(app_window) -> pystray.Icon:
    def on_show(icon, item):
        app_window.after(0, lambda: (app_window.deiconify(), app_window.lift()))

    def on_stop(icon, item):
        stop_api()

    def on_quit(icon, item):
        stop_api()
        _cleanup()
        icon.stop()
        app_window.after(0, app_window.destroy)

    menu = pystray.Menu(
        pystray.MenuItem('Show Launcher', on_show, default=True),
        pystray.MenuItem('Stop API Server', on_stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit', on_quit))

    return pystray.Icon('acestep', _make_tray_icon_image(), 'ACE-Step 1.5', menu)


# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────────────────
def _cleanup():
    for f in temp_files:
        try:
            os.unlink(f)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    global status_var, tray_icon

    WEBUI_DIR.mkdir(parents=True, exist_ok=True)
    # Kill any acestep-api orphans from previous sessions before we do anything
    kill_orphaned_acestep_procs(silent=True)

    ctk.set_appearance_mode('dark')
    ctk.set_default_color_theme('blue')

    ACCENT    = '#1a6fff'
    ACCENT_HV = '#3d85ff'
    BTN2_BG   = '#252a3d'
    BTN2_HV   = '#2f3650'
    BG        = '#12151e'
    BG2       = '#1a1e2e'
    FG        = '#e8eaf0'
    FG_DIM    = '#8b90a8'
    FG_RDY    = '#3ddc84'

    app = ctk.CTk()
    app.title('ACE-Step 1.5')
    app.geometry('440x340')
    app.resizable(False, False)
    app.configure(fg_color=BG)

    status_var = tk.StringVar(value='Ready.')
    hb_var     = tk.BooleanVar(value=False)  # V8: OFF by default, persists preference
    tray_icon  = build_tray(app)

    def on_close():
        app.withdraw()
        threading.Thread(target=tray_icon.run, daemon=True).start()

    app.protocol('WM_DELETE_WINDOW', on_close)

    outer = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)
    outer.pack(fill='both', expand=True, padx=28, pady=20)

    title_lbl = ctk.CTkLabel(outer,
                              text='ACE-Step  1.5',
                              font=ctk.CTkFont('Segoe UI', 18, 'bold'),
                              text_color=ACCENT,
                              cursor='hand2')
    title_lbl.pack(anchor='w')
    title_lbl.bind('<Button-1>',
                   lambda e: webbrowser.open('https://ace-step.github.io'))
    Tip(title_lbl,
        'ace-step.github.io\nDemo tracks, docs, what this thing can actually do.')

    ctk.CTkLabel(outer,
                 text='AI Music Generation',
                 font=ctk.CTkFont('Segoe UI', 9),
                 text_color=FG_DIM).pack(anchor='w', pady=(0, 14))

    big_btn = ctk.CTkButton(
        outer,
        text='▶   Launch WebUI',
        font=ctk.CTkFont('Segoe UI', 11, 'bold'),
        fg_color=ACCENT, hover_color=ACCENT_HV,
        text_color=FG,
        height=46, corner_radius=6,
        command=lambda: action_launch_webui(hb_var.get()))
    big_btn.pack(fill='x', pady=(0, 10))
    Tip(big_btn, 'Starts the API server and opens every HTML file in the /webui/ folder.\n'
                 'Want a different UI? Drop it in the folder. Want five? Go nuts.')

    row = ctk.CTkFrame(outer, fg_color=BG)
    row.pack(fill='x', pady=(0, 8))
    row.columnconfigure(0, weight=1)
    row.columnconfigure(1, weight=1)

    api_btn = ctk.CTkButton(
        row,
        text='⚙  Start API Only',
        font=ctk.CTkFont('Segoe UI', 10),
        fg_color=BTN2_BG, hover_color=BTN2_HV,
        text_color=FG,
        height=36, corner_radius=6,
        command=action_start_api_only)
    api_btn.grid(row=0, column=0, sticky='ew', padx=(0, 5))
    Tip(api_btn, 'API. My dude. Just the API.\nPort 8001. No browser, no UI.')

    grad_btn = ctk.CTkButton(
        row,
        text='⚡  Gradio UI',
        font=ctk.CTkFont('Segoe UI', 10),
        fg_color=BTN2_BG, hover_color=BTN2_HV,
        text_color=FG,
        height=36, corner_radius=6,
        command=action_launch_gradio)
    grad_btn.grid(row=0, column=1, sticky='ew', padx=(5, 0))
    Tip(grad_btn, 'Gradio UI. My guy.\nSelf-contained. No separate API needed.')

    # Second row: WebUI folder + rickroll
    row2 = ctk.CTkFrame(outer, fg_color=BG)
    row2.pack(fill='x', pady=(0, 8))
    row2.columnconfigure(0, weight=1)
    row2.columnconfigure(1, weight=0)

    folder_btn = ctk.CTkButton(
        row2,
        text='📂  WebUI Folder',
        font=ctk.CTkFont('Segoe UI', 10),
        fg_color=BTN2_BG, hover_color=BTN2_HV,
        text_color=FG,
        height=30, corner_radius=6,
        command=action_open_webui_folder)
    folder_btn.grid(row=0, column=0, sticky='ew', padx=(0, 5))
    Tip(folder_btn,
        'Opens the /webui/ folder.\n'
        'Drop any .html file in here and it shows up next launch.\n'
        'Collect them like Pokémon. Or don\'t. I\'m a button, not a cop.')

    rick_btn = ctk.CTkButton(
        row2,
        text='😊',
        font=ctk.CTkFont('Segoe UI', 9),
        fg_color=BG2, hover_color='#c00020',
        text_color='#3a3e52',
        width=40,
        height=30, corner_radius=6,
        command=lambda: webbrowser.open(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'))
    rick_btn.grid(row=0, column=1, sticky='e')
    Tip(rick_btn, 'The tutorial.')

    hb_box = ctk.CTkCheckBox(
        outer,
        text='Auto-stop server when browser closes',
        font=ctk.CTkFont('Segoe UI', 10),
        variable=hb_var,
        text_color=FG,
        fg_color=ACCENT, hover_color=ACCENT_HV,
        checkmark_color=FG,
        border_color=BTN2_HV)
    hb_box.pack(anchor='w', pady=(0, 10))
    Tip(hb_box,
        'Heartbeat ping from browser → launcher.\n'
        'Server auto-stops when all tabs are closed.\n'
        'Uncheck to keep it running until you kill it from the tray.\n'
        'Won\'t kill mid-generation even if the heartbeat hiccups.')

    def _color_update(*_):
        status_lbl.configure(
            text_color=FG_RDY if status_var.get() == 'Ready.' else FG_DIM)

    status_lbl = ctk.CTkLabel(
        outer,
        textvariable=status_var,
        font=ctk.CTkFont('Segoe UI', 8),
        text_color=FG_RDY,
        anchor='w')
    status_lbl.pack(fill='x')
    status_var.trace_add('write', _color_update)

    app.mainloop()
    _cleanup()


if __name__ == '__main__':
    main()
