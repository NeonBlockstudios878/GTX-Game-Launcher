"""
GTX Game Launcher - Nexus Edition
Enterprise Monolithic Single-File Core Architecture
Designed for scalability, persistence, hardware telemetry, and multi-platform library management.
"""

# ==============================================================================
# 00. SYSTEM IMPORTS & ENVIRONMENT SETUP
# ==============================================================================
import os
import sys
import time
import json
import sqlite3
import datetime
import threading
import subprocess
from typing import List, Dict, Any, Optional, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import psutil

# Windows-specific imports for process & registry scanning
if sys.platform == "win32":
    import winreg

# Global CustomTkinter Application Defaults
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ==============================================================================
# 01. CONSTANTS, COLOR PALETTES & THEME DEFINITIONS
# ==============================================================================
APP_NAME = "GTX Game Launcher"
APP_VERSION = "2.4.0-NEXUS"
DB_FILE = "gtx_nexus_data.db"

# Master Theme Dictionaries
THEMES = {
    "Cyberpunk Cyan": {
        "bg": "#0B0E14",
        "panel_bg": "#121721",
        "card_bg": "#1A202C",
        "card_hover": "#222C3D",
        "accent_primary": "#00F0FF",
        "accent_secondary": "#A855F7",
        "accent_warning": "#FFB800",
        "accent_danger": "#FF0033",
        "text_white": "#FFFFFF",
        "text_muted": "#64748B",
        "border": "#1E293B"
    },
    "Crimson Red Alert": {
        "bg": "#0A0203",
        "panel_bg": "#140507",
        "card_bg": "#1F080A",
        "card_hover": "#2E0C0F",
        "accent_primary": "#FF0033",
        "accent_secondary": "#FF5500",
        "accent_warning": "#FFCC00",
        "accent_danger": "#990000",
        "text_white": "#FFFFFF",
        "text_muted": "#993344",
        "border": "#4A0D15"
    },
    "Emerald Matrix": {
        "bg": "#020B05",
        "panel_bg": "#05160B",
        "card_bg": "#0A2412",
        "card_hover": "#0F351B",
        "accent_primary": "#00FF66",
        "accent_secondary": "#00E5FF",
        "accent_warning": "#FFD700",
        "accent_danger": "#FF3333",
        "text_white": "#FFFFFF",
        "text_muted": "#2E7D4E",
        "border": "#0D401F"
    }
}

ACTIVE_THEME = "Cyberpunk Cyan"
THEME = THEMES[ACTIVE_THEME]

FONT_HEADER = "Orbitron"
FONT_BODY = "Segoe UI" if sys.platform == "win32" else "Helvetica"


# ==============================================================================
# SECTION I: SQLITE DATABASE MANAGER & PERSISTENCE ENGINE
# ==============================================================================
class DatabaseManager:
    """Handles thread-safe persistence for games, system apps, playtime records, and settings."""

    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Games Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL UNIQUE,
                        platform TEXT NOT NULL,
                        executable_path TEXT NOT NULL,
                        launch_arguments TEXT DEFAULT '',
                        is_favorite INTEGER DEFAULT 0,
                        total_playtime_minutes INTEGER DEFAULT 0,
                        last_played_timestamp DATETIME,
                        date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
                        custom_cover_path TEXT DEFAULT ''
                    )
                """)

                # System Utilities & Integrated Apps
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS apps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        executable_path TEXT NOT NULL,
                        category TEXT DEFAULT 'Utility',
                        launch_arguments TEXT DEFAULT ''
                    )
                """)

                # Key-Value System Configuration
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
                
                conn.commit()
                self._seed_default_data(cursor, conn)

    def _seed_default_data(self, cursor: sqlite3.Cursor, conn: sqlite3.Connection):
        # Default Games
        defaults = [
            ("Cyberpunk 2077", "STEAM", "steam://rungameid/1091500", 1),
            ("Elden Ring", "STEAM", "steam://rungameid/1245620", 1),
            ("GTA V", "ROCKSTAR", "C:\\Program Files\\Rockstar Games\\Grand Theft Auto V\\PlayGTAV.exe", 0),
            ("Red Dead Redemption II", "ROCKSTAR", "C:\\Program Files\\Rockstar Games\\Launcher\\Launcher.exe", 0)
        ]
        for title, plat, cmd, fav in defaults:
            cursor.execute("""
                INSERT OR IGNORE INTO games (title, platform, executable_path, is_favorite)
                VALUES (?, ?, ?, ?)
            """, (title, plat, cmd, fav))

        # Default Apps
        default_apps = [
            ("Steam Client", "steam://open/main", "Launcher"),
            ("Discord", "cmd.exe /c start discord", "Communication"),
            ("Task Manager", "taskmgr.exe", "Diagnostic"),
            ("Command Console", "cmd.exe", "System")
        ]
        for name, path, cat in default_apps:
            cursor.execute("""
                INSERT OR IGNORE INTO apps (name, executable_path, category)
                VALUES (?, ?, ?)
            """, (name, path, cat))

        conn.commit()

    def get_all_games(self) -> List[Dict[str, Any]]:
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM games ORDER BY title ASC")
                return [dict(row) for row in cursor.fetchall()]

    def add_game(self, title: str, platform: str, exec_path: str, is_fav: bool = False) -> bool:
        with self._lock:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO games (title, platform, executable_path, is_favorite)
                        VALUES (?, ?, ?, ?)
                    """, (title, platform, exec_path, 1 if is_fav else 0))
                    conn.commit()
                    return True
            except sqlite3.IntegrityError:
                return False

    def toggle_favorite(self, game_id: int) -> bool:
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE games SET is_favorite = NOT is_favorite WHERE id = ?", (game_id,))
                conn.commit()
                return True

    def update_playtime(self, game_id: int, minutes_elapsed: int):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE games 
                    SET total_playtime_minutes = total_playtime_minutes + ?,
                        last_played_timestamp = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (minutes_elapsed, game_id))
                conn.commit()


# ==============================================================================
# SECTION II: HARDWARE DIAGNOSTICS & STEAM SCANNER ENGINE
# ==============================================================================
class HardwareDiagnosticsEngine:
    """Gathers real-time performance metrics for CPU, RAM, Disk, and Network."""

    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        try:
            cpu_usage = psutil.cpu_percent(interval=None)
            cpu_freq = psutil.cpu_freq()
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()

            return {
                "cpu_percent": cpu_usage,
                "cpu_frequency_mhz": round(cpu_freq.current, 1) if cpu_freq else 0.0,
                "cpu_core_count": psutil.cpu_count(logical=True),
                "ram_percent": ram.percent,
                "ram_used_gb": round(ram.used / (1024 ** 3), 2),
                "ram_total_gb": round(ram.total / (1024 ** 3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024 ** 3), 2),
                "net_bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 2),
                "net_bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 2)
            }
        except Exception:
            return {
                "cpu_percent": 0.0,
                "cpu_frequency_mhz": 0.0,
                "cpu_core_count": 4,
                "ram_percent": 0.0,
                "ram_used_gb": 0.0,
                "ram_total_gb": 0.0,
                "disk_percent": 0.0,
                "disk_free_gb": 0.0,
                "net_bytes_sent_mb": 0.0,
                "net_bytes_recv_mb": 0.0
            }


class GameScanner:
    """Scans the local filesystem and Windows Registry for installed game libraries."""

    @staticmethod
    def scan_steam_vdf() -> List[Tuple[str, str]]:
        found_games = []
        if sys.platform != "win32":
            return found_games

        try:
            # Query Registry for Steam Path
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(reg_key, "SteamPath")
            winreg.CloseKey(reg_key)

            apps_dir = os.path.join(steam_path, "steamapps")
            if os.path.exists(apps_dir):
                for file_name in os.listdir(apps_dir):
                    if file_name.startswith("appmanifest_") and file_name.endswith(".vdf"):
                        manifest_path = os.path.join(apps_dir, file_name)
                        with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            # Basic manifest token parsing
                            app_id, name = None, None
                            for line in content.splitlines():
                                if '"appid"' in line.lower():
                                    parts = line.split('"')
                                    if len(parts) >= 4:
                                        app_id = parts[3]
                                elif '"name"' in line.lower():
                                    parts = line.split('"')
                                    if len(parts) >= 4:
                                        name = parts[3]
                            if app_id and name:
                                found_games.append((name, f"steam://rungameid/{app_id}"))
        except Exception:
            pass
        return found_games


# ==============================================================================
# SECTION III: PROCESS EXECUTION & ACTIVE SESSION TRACKER
# ==============================================================================
class ProcessMonitor:
    """Manages asynchronous game launching and tracks session durations."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def launch_payload(self, game_id: Optional[int], command_or_path: str):
        threading.Thread(
            target=self._launch_and_track,
            args=(game_id, command_or_path),
            daemon=True
        ).start()

    def _launch_and_track(self, game_id: Optional[int], target: str):
        start_time = time.time()
        try:
            if target.startswith("steam://") or target.startswith("com.epicgames"):
                os.startfile(target)
            else:
                proc = subprocess.Popen(target, shell=True)
                proc.wait()  # Block background thread until application exits
        except Exception as err:
            print(f"[Execution Error] Failed to launch payload {target}: {err}")
            return

        elapsed_seconds = int(time.time() - start_time)
        elapsed_minutes = max(1, elapsed_seconds // 60)

        if game_id is not None:
            self.db.update_playtime(game_id, elapsed_minutes)


# ==============================================================================
# SECTION IV: REUSABLE UI WIDGET COMPONENTS
# ==============================================================================
class TacticalStatCard(ctk.CTkFrame):
    """Reusable diagnostic meter with dynamic progress bars."""

    def __init__(self, master, label: str, unit: str = "%", accent_color: str = THEME["accent_primary"], **kwargs):
        super().__init__(master, fg_color=THEME["card_bg"], corner_radius=10, border_width=1, border_color=THEME["border"], **kwargs)
        self.unit = unit

        self.title_lbl = ctk.CTkLabel(
            self, text=label.upper(),
            font=ctk.CTkFont(family=FONT_HEADER, size=11, weight="bold"),
            text_color=THEME["text_muted"]
        )
        self.title_lbl.pack(anchor="w", padx=16, pady=(12, 2))

        self.val_lbl = ctk.CTkLabel(
            self, text=f"0.0 {self.unit}",
            font=ctk.CTkFont(family=FONT_HEADER, size=20, weight="bold"),
            text_color=THEME["text_white"]
        )
        self.val_lbl.pack(anchor="w", padx=16, pady=(0, 8))

        self.progress = ctk.CTkProgressBar(self, progress_color=accent_color, fg_color=THEME["panel_bg"], height=6)
        self.progress.pack(fill="x", padx=16, pady=(0, 16))
        self.progress.set(0)

    def update_val(self, percentage: float, display_str: Optional[str] = None):
        self.progress.set(max(0.0, min(1.0, percentage / 100.0)))
        if display_str:
            self.val_lbl.configure(text=display_str)
        else:
            self.val_lbl.configure(text=f"{percentage:.1f} {self.unit}")


# ==============================================================================
# SECTION V: ANIMATED BOOT SPLASH SCREEN
# ==============================================================================
class BootSplashScreen(ctk.CTkFrame):
    """Animated boot screen executed during application initialization."""

    def __init__(self, master, on_complete_callback):
        super().__init__(master, fg_color=THEME["bg"], corner_radius=0)
        self.on_complete = on_complete_callback

        self.logo_label = ctk.CTkLabel(
            self, text="GTX",
            font=ctk.CTkFont(family=FONT_HEADER, size=72, weight="bold"),
            text_color=THEME["accent_primary"]
        )
        self.logo_label.place(relx=0.5, rely=0.38, anchor="center")

        self.sub_label = ctk.CTkLabel(
            self, text="N E X U S   E D I T I O N",
            font=ctk.CTkFont(family=FONT_HEADER, size=14, weight="bold"),
            text_color=THEME["accent_secondary"]
        )
        self.sub_label.place(relx=0.5, rely=0.48, anchor="center")

        self.progress_bar = ctk.CTkProgressBar(
            self, width=360, height=8, corner_radius=4,
            progress_color=THEME["accent_primary"], fg_color=THEME["panel_bg"]
        )
        self.progress_bar.place(relx=0.5, rely=0.62, anchor="center")
        self.progress_bar.set(0)

        self.status_lbl = ctk.CTkLabel(
            self, text="INITIALIZING SYSTEM CORE...",
            font=ctk.CTkFont(family=FONT_HEADER, size=10),
            text_color=THEME["text_muted"]
        )
        self.status_lbl.place(relx=0.5, rely=0.68, anchor="center")

        self.step = 0
        self.sequence = [
            (0.20, "INITIALIZING SYSTEM CORE & DATABASE..."),
            (0.45, "VERIFYING DRIVER HOOKS & REGISTRY ENTRIES..."),
            (0.70, "SCANNING LOCAL STEAM & EPIC MANIFESTS..."),
            (0.90, "LOADING TELEMETRY MONITORING SUBSYSTEM..."),
            (1.00, "INITIALIZATION COMPLETE // LAUNCHING NEXUS")
        ]
        self._animate()

    def _animate(self):
        if self.step < len(self.sequence):
            val, msg = self.sequence[self.step]
            self.progress_bar.set(val)
            self.status_lbl.configure(text=msg)
            self.step += 1
            self.after(350, self._animate)
        else:
            self.after(200, self.on_complete)


# ==============================================================================
# SECTION VI & VII: MAIN APPLICATION CONTROLLER & VIEWS
# ==============================================================================
class GTXGameLauncherApp(ctk.CTk):
    """Main Application Controller orchestrating database persistence and custom views."""

    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} // v{APP_VERSION}")
        self.geometry("1180x740")
        self.minsize(980, 620)
        self.configure(fg_color=THEME["bg"])

        # Core Subsystems
        self.db = DatabaseManager()
        self.monitor = ProcessMonitor(self.db)

        self.nav_buttons = {}
        self.pages = {}

        # Show Splash Screen
        self.splash = BootSplashScreen(self, self._initialize_main_ui)
        self.splash.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _initialize_main_ui(self):
        self.splash.destroy()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_sidebar()
        self.build_views_container()
        self.show_page("Home")

    # --- SIDEBAR COMPONENT ---
    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=230, fg_color=THEME["panel_bg"], corner_radius=12,
            border_width=1, border_color=THEME["border"]
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(15, 8), pady=15)
        self.sidebar.grid_propagate(False)

        # Brand Title
        self.logo_lbl = ctk.CTkLabel(
            self.sidebar, text="GTX",
            font=ctk.CTkFont(family=FONT_HEADER, size=28, weight="bold"),
            text_color=THEME["accent_primary"]
        )
        self.logo_lbl.pack(anchor="w", padx=20, pady=(20, 0))

        self.sub_logo = ctk.CTkLabel(
            self.sidebar, text="NEXUS EDITION",
            font=ctk.CTkFont(family=FONT_HEADER, size=8, weight="bold"),
            text_color=THEME["accent_secondary"]
        )
        self.sub_logo.pack(anchor="w", padx=20, pady=(0, 20))

        # Navigation Links
        nav_items = [
            ("Home", "🏠  Home"),
            ("Library", "🎮  Game Library"),
            ("Favorites", "⭐  Favorites"),
            ("Apps", "🎛  Apps & Tools"),
            ("Diagnostics", "📊  Diagnostics"),
            ("Settings", "⚙  Settings")
        ]

        for key, text in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=text, anchor="w", height=40,
                fg_color="transparent", text_color=THEME["text_white"],
                border_width=0, hover_color=THEME["card_bg"], corner_radius=8,
                font=ctk.CTkFont(family=FONT_BODY, size=13),
                command=lambda p=key: self.show_page(p)
            )
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[key] = btn

        # Exit Button
        self.exit_btn = ctk.CTkButton(
            self.sidebar, text="⏻ EXIT", height=38,
            fg_color=THEME["card_bg"], text_color=THEME["text_white"],
            hover_color=THEME["card_hover"], corner_radius=8,
            border_width=1, border_color=THEME["border"],
            font=ctk.CTkFont(family=FONT_HEADER, size=11, weight="bold"),
            command=self.destroy
        )
        self.exit_btn.pack(side="bottom", fill="x", padx=12, pady=(0, 15))

    # --- VIEWS CONTAINER ---
    def build_views_container(self):
        self.container = ctk.CTkFrame(
            self, fg_color=THEME["panel_bg"], corner_radius=12,
            border_width=1, border_color=THEME["border"]
        )
        self.container.grid(row=0, column=1, sticky="nsew", padx=(8, 15), pady=15)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # Mount Pages
        self.pages["Home"] = self.view_home()
        self.pages["Library"] = self.view_library()
        self.pages["Favorites"] = self.view_favorites()
        self.pages["Apps"] = self.view_apps()
        self.pages["Diagnostics"] = self.view_diagnostics()
        self.pages["Settings"] = self.view_settings()

    # 1. VIEW: HOME (Quick Launch Dashboard)
    def view_home(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="transparent")

        # Top System Announcement Banner
        banner = ctk.CTkFrame(frame, height=45, fg_color=THEME["card_bg"], corner_radius=8, border_width=1, border_color=THEME["accent_primary"])
        banner.pack(fill="x", padx=25, pady=(20, 15))
        banner.pack_propagate(False)

        b_txt = ctk.CTkLabel(banner, text="SYSTEM STATUS: ALL GAME ENGINES OPERATIONAL", font=ctk.CTkFont(family=FONT_HEADER, size=10, weight="bold"), text_color=THEME["accent_primary"])
        b_txt.place(relx=0.5, rely=0.5, anchor="center")

        title = ctk.CTkLabel(frame, text="FEATURED REPERTOIRE", font=ctk.CTkFont(family=FONT_HEADER, size=24, weight="bold"), text_color=THEME["text_white"])
        title.pack(anchor="w", padx=25, pady=(5, 0))

        sub = ctk.CTkLabel(frame, text="Your top pinned and recently launched titles.", font=ctk.CTkFont(family=FONT_BODY, size=12), text_color=THEME["text_muted"])
        sub.pack(anchor="w", padx=25, pady=(0, 15))

        self.home_cards_scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent", orientation="horizontal", height=300)
        self.home_cards_scroll.pack(fill="x", expand=True, padx=25)

        self.refresh_home_cards()
        return frame

    def refresh_home_cards(self):
        for widget in self.home_cards_scroll.winfo_children():
            widget.destroy()

        games = self.db.get_all_games()
        col = 0
        for g in games:
            card = ctk.CTkFrame(self.home_cards_scroll, width=210, height=275, fg_color=THEME["card_bg"], corner_radius=10, border_width=1, border_color=THEME["border"])
            card.grid(row=0, column=col, padx=(0, 15), pady=5)
            card.grid_propagate(False)

            thumb = ctk.CTkFrame(card, fg_color=THEME["bg"], corner_radius=8, border_width=1, border_color=THEME["border"])
            thumb.pack(fill="x", padx=10, pady=10)
            thumb.configure(height=130)
            thumb.pack_propagate(False)

            icon_lbl = ctk.CTkLabel(thumb, text="🎮\n" + g["title"][:10], font=ctk.CTkFont(family=FONT_HEADER, size=14, weight="bold"), text_color=THEME["accent_primary"])
            icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

            title_lbl = ctk.CTkLabel(card, text=g["title"][:18], font=ctk.CTkFont(family=FONT_BODY, size=12, weight="bold"), text_color=THEME["text_white"])
            title_lbl.pack(anchor="w", padx=12, pady=(2, 0))

            plat_lbl = ctk.CTkLabel(card, text=g["platform"], font=ctk.CTkFont(family=FONT_HEADER, size=8, weight="bold"), text_color=THEME["accent_secondary"])
            plat_lbl.pack(anchor="w", padx=12, pady=(0, 8))

            play_btn = ctk.CTkButton(
                card, text="▶  PLAY", height=32,
                fg_color=THEME["accent_primary"], text_color=THEME["bg"],
                hover_color="#00C4D4", corner_radius=6,
                font=ctk.CTkFont(family=FONT_HEADER, size=11, weight="bold"),
                command=lambda g_id=g["id"], c=g["executable_path"]: self.monitor.launch_payload(g_id, c)
            )
            play_btn.pack(fill="x", padx=10, side="bottom", pady=10)
            col += 1

    # 2. VIEW: GAME LIBRARY
    def view_library(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        
        title = ctk.CTkLabel(frame, text="MASTER GAME REPOSITORY", font=ctk.CTkFont(family=FONT_HEADER, size=24, weight="bold"), text_color=THEME["text_white"])
        title.pack(anchor="w", padx=25, pady=(25, 5))

        # Action Toolbar
        tb = ctk.CTkFrame(frame, fg_color="transparent")
        tb.pack(fill="x", padx=25, pady=(0, 15))

        self.lib_search = ctk.CTkEntry(tb, placeholder_text="Filter library...", height=38, fg_color=THEME["card_bg"], border_color=THEME["border"], text_color=THEME["text_white"])
        self.lib_search.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.lib_search.bind("<KeyRelease>", lambda e: self.refresh_library_list())

        add_btn = ctk.CTkButton(tb, text="+ ADD GAME", height=38, fg_color=THEME["accent_primary"], text_color=THEME["bg"], font=ctk.CTkFont(family=FONT_HEADER, size=11, weight="bold"), command=self.modal_add_game)
        add_btn.pack(side="right")

        scan_btn = ctk.CTkButton(tb, text="AUTO-SCAN", height=38, fg_color=THEME["card_bg"], text_color=THEME["text_white"], border_width=1, border_color=THEME["border"], font=ctk.CTkFont(family=FONT_HEADER, size=11, weight="bold"), command=self.run_auto_scan)
        scan_btn.pack(side="right", padx=(0, 10))

        self.lib_scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.lib_scroll.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        self.refresh_library_list()
        return frame

    def refresh_library_list(self):
        for widget in self.lib_scroll.winfo_children():
            widget.destroy()

        filter_text = self.lib_search.get().lower() if hasattr(self, 'lib_search') else ""
        games = self.db.get_all_games()

        for g in games:
            if filter_text and filter_text not in g["title"].lower():
                continue

            row = ctk.CTkFrame(self.lib_scroll, height=55, fg_color=THEME["card_bg"], corner_radius=8, border_width=1, border_color=THEME["border"])
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)

            t_lbl = ctk.CTkLabel(row, text=f"🎮  {g['title']}", font=ctk.CTkFont(family=FONT_BODY, size=14, weight="bold"), text_color=THEME["text_white"])
            t_lbl.pack(side="left", padx=15)

            p_lbl = ctk.CTkLabel(row, text=g["platform"], font=ctk.CTkFont(family=FONT_HEADER, size=9, weight="bold"), text_color=THEME["accent_secondary"])
            p_lbl.pack(side="left", padx=15)

            time_str = f"{g['total_playtime_minutes']} mins played"
            time_lbl = ctk.CTkLabel(row, text=time_str, font=ctk.CTkFont(family=FONT_BODY, size=11), text_color=THEME["text_muted"])
            time_lbl.pack(side="left", padx=15)

            play_btn = ctk.CTkButton(row, text="LAUNCH", width=90, height=32, fg_color=THEME["accent_primary"], text_color=THEME["bg"], font=ctk.CTkFont(family=FONT_HEADER, size=10, weight="bold"), command=lambda g_id=g["id"], c=g["executable_path"]: self.monitor.launch_payload(g_id, c))
            play_btn.pack(side="right", padx=15)

            fav_icon = "⭐" if g["is_favorite"] else "☆"
            fav_btn = ctk.CTkButton(row, text=fav_icon, width=35, height=32, fg_color="transparent", hover_color=THEME["card_hover"], text_color=THEME["accent_primary"], command=lambda g_id=g["id"]: self.toggle_fav(g_id))
            fav_btn.pack(side="right", padx=5)

    def toggle_fav(self, game_id: int):
        self.db.toggle_favorite(game_id)
        self.refresh_library_list()
        self.refresh_home_cards()
        self.refresh_favorites_list()

    def modal_add_game(self):
        f = filedialog.askopenfilename(title="Select Game Payload", filetypes=[("Executables & Links", "*.exe;*.lnk"), ("All Files", "*.*")])
        if f:
            name = os.path.basename(f).rsplit('.', 1)[0].upper()
            self.db.add_game(name, "MANUAL", f)
            self.refresh_library_list()
            self.refresh_home_cards()

    def run_auto_scan(self):
        steam_games = GameScanner.scan_steam_vdf()
        added_count = 0
        for title, uri in steam_games:
            if self.db.add_game(title, "STEAM", uri):
                added_count += 1
        messagebox.showinfo("Library Scanner", f"Scan complete. Imported {added_count} new Steam titles into repository.")
        self.refresh_library_list()
        self.refresh_home_cards()

    # 3. VIEW: FAVORITES
    def view_favorites(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        title = ctk.CTkLabel(frame, text="STARRED FAVORITES", font=ctk.CTkFont(family=FONT_HEADER, size=24, weight="bold"), text_color=THEME["text_white"])
        title.pack(anchor="w", padx=25, pady=(25, 5))

        self.fav_scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.fav_scroll.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        self.refresh_favorites_list()
        return frame

    def refresh_favorites_list(self):
        for widget in self.fav_scroll.winfo_children():
            widget.destroy()

        games = [g for g in self.db.get_all_games() if g["is_favorite"]]
        for g in games:
            row = ctk.CTkFrame(self.fav_scroll, height=55, fg_color=THEME["card_bg"], corner_radius=8, border_width=1, border_color=THEME["border"])
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)

            t_lbl = ctk.CTkLabel(row, text=f"⭐  {g['title']}", font=ctk.CTkFont(family=FONT_BODY, size=14, weight="bold"), text_color=THEME["text_white"])
            t_lbl.pack(side="left", padx=15)

            play_btn = ctk.CTkButton(row, text="LAUNCH", width=100, height=32, fg_color=THEME["accent_primary"], text_color=THEME["bg"], font=ctk.CTkFont(family=FONT_HEADER, size=10, weight="bold"), command=lambda g_id=g["id"], c=g["executable_path"]: self.monitor.launch_payload(g_id, c))
            play_btn.pack(side="right", padx=15)

    # 4. VIEW: APPS & UTILITIES
    def view_apps(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        title = ctk.CTkLabel(frame, text="INTEGRATED APPS & TOOLS", font=ctk.CTkFont(family=FONT_HEADER, size=24, weight="bold"), text_color=THEME["text_white"])
        title.pack(anchor="w", padx=25, pady=(25, 5))

        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM apps")
            apps = [dict(row) for row in cursor.fetchall()]

        for a in apps:
            btn = ctk.CTkButton(
                scroll, text=f"⚡  {a['name']} ({a['category']})", height=50, anchor="w",
                fg_color=THEME["card_bg"], text_color=THEME["text_white"],
                hover_color=THEME["card_hover"], corner_radius=8, border_width=1, border_color=THEME["border"],
                font=ctk.CTkFont(family=FONT_BODY, size=13, weight="bold"),
                command=lambda c=a["executable_path"]: self.monitor.launch_payload(None, c)
            )
            btn.pack(fill="x", pady=5)
        return frame

    # 5. VIEW: DIAGNOSTICS & TELEMETRY
    def view_diagnostics(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        title = ctk.CTkLabel(frame, text="SYSTEM DIAGNOSTICS", font=ctk.CTkFont(family=FONT_HEADER, size=24, weight="bold"), text_color=THEME["text_white"])
        title.pack(anchor="w", padx=25, pady=(25, 5))

        grid_frame = ctk.CTkFrame(frame, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=25, pady=(10, 15))
        grid_frame.grid_columnconfigure((0, 1), weight=1)

        self.card_cpu = TacticalStatCard(grid_frame, "CPU Total Load", accent_color=THEME["accent_primary"])
        self.card_cpu.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.card_ram = TacticalStatCard(grid_frame, "RAM Allocation", accent_color=THEME["accent_secondary"])
        self.card_ram.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

        self.card_disk = TacticalStatCard(grid_frame, "Primary Disk Utilization", accent_color=THEME["accent_warning"])
        self.card_disk.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self.card_net = TacticalStatCard(grid_frame, "Network Stream", unit="MB", accent_color=THEME["accent_primary"])
        self.card_net.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)

        self._poll_diagnostics()
        return frame

    def _poll_diagnostics(self):
        m = HardwareDiagnosticsEngine.get_metrics()
        if hasattr(self, 'card_cpu'):
            self.card_cpu.update_val(m["cpu_percent"])
            self.card_ram.update_val(m["ram_percent"], f"{m['ram_used_gb']} / {m['ram_total_gb']} GB")
            self.card_disk.update_val(m["disk_percent"], f"{m['disk_percent']}% ({m['disk_free_gb']} GB Free)")
            self.card_net.update_val(min(100.0, m["net_bytes_recv_mb"] / 10.0), f"↓ {m['net_bytes_recv_mb']} MB")
        self.after(2500, self._poll_diagnostics)

    # 6. VIEW: SETTINGS
    def view_settings(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        title = ctk.CTkLabel(frame, text="SETTINGS & PREFERENCES", font=ctk.CTkFont(family=FONT_HEADER, size=24, weight="bold"), text_color=THEME["text_white"])
        title.pack(anchor="w", padx=25, pady=(25, 5))

        box = ctk.CTkFrame(frame, fg_color=THEME["card_bg"], corner_radius=10, border_width=1, border_color=THEME["border"])
        box.pack(fill="x", padx=25, pady=15)

        s1_lbl = ctk.CTkLabel(box, text="UI Appearance Mode", font=ctk.CTkFont(family=FONT_BODY, size=13, weight="bold"), text_color=THEME["text_white"])
        s1_lbl.pack(anchor="w", padx=20, pady=(15, 5))

        mode_menu = ctk.CTkOptionMenu(box, values=["Dark", "Light", "System"], command=lambda m: ctk.set_appearance_mode(m))
        mode_menu.pack(anchor="w", padx=20, pady=(0, 15))

        sw1 = ctk.CTkSwitch(box, text="Minimize launcher on game boot", font=ctk.CTkFont(family=FONT_BODY, size=12), text_color=THEME["text_white"], progress_color=THEME["accent_primary"])
        sw1.pack(anchor="w", padx=20, pady=10)

        sw2 = ctk.CTkSwitch(box, text="Hardware overlay diagnostics telemetry", font=ctk.CTkFont(family=FONT_BODY, size=12), text_color=THEME["text_white"], progress_color=THEME["accent_primary"])
        sw2.pack(anchor="w", padx=20, pady=(0, 20))
        return frame

    # --- NAVIGATION ROUTER ---
    def show_page(self, page_name: str):
        for name, p_frame in self.pages.items():
            p_frame.grid_forget()

        for name, btn in self.nav_buttons.items():
            if name == page_name:
                btn.configure(fg_color=THEME["card_bg"], text_color=THEME["accent_primary"], border_width=1, border_color=THEME["accent_primary"])
            else:
                btn.configure(fg_color="transparent", text_color=THEME["text_white"], border_width=0, border_color=THEME["panel_bg"])

        self.pages[page_name].grid(row=0, column=0, sticky="nsew")


# ==============================================================================
# SECTION VIII: ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    app = GTXGameLauncherApp()
    app.mainloop()