import os
import sys
import time
import threading
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich import box

# Import Aurum components
from main import AurumEngine
from config.db_connector import DBConnector
import MetaTrader5 as mt5

console = Console()

class AurumCLI:
    def __init__(self):
        # Auto-cleanup other instances on startup to avoid Conflict errors
        self._auto_cleanup()
        
        self.engine = AurumEngine()
        self.bot_thread = None
        self.running = True
        self.db = DBConnector()
        self.db.conectar()

    def _auto_cleanup(self):
        """Silently kills other instances on startup, except critical background workers."""
        import psutil
        current_pid = os.getpid()
        project_dir = os.path.dirname(os.path.abspath(__file__))
        for proc in psutil.process_iter(['pid', 'name', 'cwd', 'cmdline']):
            try:
                # We only want to kill other "main" CLI or Engine instances
                # to avoid conflicting with the Telegram bot or MT5.
                if "python" in proc.info['name'].lower() and proc.info['pid'] != current_pid:
                    if proc.info.get('cwd') == project_dir:
                        cmdline = " ".join(proc.info.get('cmdline', [])).lower()
                        # CRITICAL: Do NOT kill the watchdog (heartbeat) or the hunter
                        if "heartbeat.py" in cmdline or "news_hunter.py" in cmdline:
                            continue
                        proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def draw_header(self):
        header_text = Text("AURUM OMNI - PROFESSIONAL CLOUD INTERFACE", style="bold yellow")
        status = "🟢 ONLINE" if self.engine.running else "🔴 OFFLINE"
        header_panel = Panel(
            Align.center(header_text),
            subtitle=f"Status: {status} | Time: {datetime.now().strftime('%H:%M:%S')}",
            box=box.DOUBLE,
            border_style="cyan"
        )
        console.print(header_panel)

    def draw_menu(self):
        table = Table(show_header=False, box=box.SIMPLE, expand=True)
        table.add_column("Option", style="bold cyan", width=5)
        table.add_column("Description", style="white")

        table.add_row("[1]", "🚀 START BOT / RESUME")
        table.add_row("[2]", "📊 GLOBAL DASHBOARD (Live Voting)")
        table.add_row("[3]", "🩺 SYSTEM HEALTH CHECK")
        table.add_row("[4]", "📰 NEWS RADAR (NLP Analysis)")
        table.add_row("[5]", "⚙️  WEIGHTS & RISK CONFIG")
        table.add_row("[6]", "📜 RECENT ACTIVITY LOGS")
        table.add_row("[9]", "🛑 KILL ALL RUNNING BOTS (Fix Conflict)")
        table.add_row("[0]", "❌ EXIT SYSTEM")

        menu_panel = Panel(table, title="[bold white]MAIN MENU (Escribe el número)[/bold white]", border_style="yellow")
        console.print(menu_panel)

    def cleanup_processes(self):
        """Termina solo instancias duplicadas del proyecto Aurum (no procesos del sistema)."""
        import psutil
        current_pid = os.getpid()
        project_dir = os.path.dirname(os.path.abspath(__file__))
        console.print("[yellow]Buscando procesos duplicados de Aurum...[/yellow]")
        count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cwd', 'cmdline']):
            try:
                if "python" not in proc.info['name'].lower(): continue
                if proc.info['pid'] == current_pid: continue
                if proc.info.get('cwd') != project_dir: continue
                cmdline = " ".join(proc.info.get('cmdline', [])).lower()
                if "main.py" in cmdline or "aurum_cli.py" in cmdline:
                    proc.terminate()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        console.print(f"[green]Completado. Se cerraron {count} procesos Aurum duplicados.[/green]")
        time.sleep(2)

    def start_bot(self):
        if self.engine.running:
            console.print("[yellow]Bot is already running![/yellow]")
            time.sleep(2)
            return

        console.print("[bold green]Initializing Aurum Engine...[/bold green]")
        if self.engine.inicializar():
            def run_with_handling():
                try:
                    self.engine.run()
                except Exception as e:
                    if "Conflict" in str(e):
                        console.print("\n[bold red]⚠️ ERROR DE CONFLICTO TELEGRAM:[/bold red]")
                        console.print("Ya hay otro bot funcionando. Usa la opción [9] para limpiar el sistema.")
                    else:
                        console.print(f"\n[bold red]BOT ERROR:[/bold red] {e}")

            self.bot_thread = threading.Thread(target=run_with_handling, daemon=True)
            self.bot_thread.start()
            console.print("[bold green]Success! Bot is now running in the background.[/bold green]")
        else:
            console.print("[bold red]Failed to initialize engine. Check connections.[/bold red]")
        time.sleep(2)

    def show_dashboard(self):
        self.clear_screen()
        with Live(self._generate_dashboard_table(), refresh_per_second=1) as live:
            console.print("[dim]Press Ctrl+C to return to menu[/dim]")
            try:
                while True:
                    live.update(self._generate_dashboard_table())
                    time.sleep(2)
            except KeyboardInterrupt:
                pass

    def _generate_dashboard_table(self):
        data = self.db.get_dashboard_data()
        table = Table(title="📊 GLOBAL VOTING DASHBOARD (ONTOLOGY V1.0)", box=box.ROUNDED, expand=True)
        table.add_column("Symbol", style="bold yellow")
        table.add_column("Trend", justify="center")
        table.add_column("NLP", justify="center")
        table.add_column("Flow", justify="center")
        table.add_column("Sniper", justify="center")
        table.add_column("Hurst", justify="center")
        table.add_column("VIX", justify="center")
        table.add_column("Spread", justify="center")
        table.add_column("States", justify="center")
        table.add_column("Veredict", justify="center")
        table.add_column("Last Analysis", style="dim italic")

        for d in data:
            veredicto_val = d['veredicto'] if d['veredicto'] is not None else 0.0
            v_color = "green" if veredicto_val > 0.4 else "red" if veredicto_val < -0.4 else "white"
            v_text = f"{veredicto_val:+.3f}" if d['veredicto'] is not None else "N/A"
            
            def fmt_v(v, is_hurst=False):
                if v is None: return "[dim]Faltante[/dim]"
                if is_hurst:
                    # Hurst is 0.5 neutral, 0-1 range
                    return f"{v:+.3f}"
                color = "green" if v > 0 else "red" if v < 0 else "white"
                return f"[{color}]{v:+.2f}[/color]"

            table.add_row(
                d['simbolo'],
                fmt_v(d['trend']),
                fmt_v(d['nlp']),
                fmt_v(d['flow']),
                fmt_v(d['sniper']),
                fmt_v(d['hurst'], is_hurst=True),
                "[dim]Faltante[/dim]", # VIX
                "[dim]Faltante[/dim]", # Spread
                "[dim]Faltante[/dim]", # States
                f"[{v_color}]{v_text}[/{v_color}]",
                (d['ia_analysis'][:50] + "...") if d['ia_analysis'] else "N/A"
            )
        return table

    def show_health(self):
        self.clear_screen()
        console.print(Panel("[bold cyan]🩺 SYSTEM HEALTH CHECK[/bold cyan]", border_style="cyan"))
        
        # Check DB
        db_status = "✅ CONNECTED" if self.db.test_conexion() else "❌ DISCONNECTED"
        
        # Check MT5
        mt5_status = "✅ CONNECTED" if mt5.terminal_info() else "❌ DISCONNECTED"
        acc_info = mt5.account_info()
        equity = f"${acc_info.equity:,.2f}" if acc_info else "N/A"
        
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_row("PostgreSQL (GCP)", db_status)
        table.add_row("MetaTrader 5", mt5_status)
        table.add_row("Account Equity", equity)
        table.add_row("Environment", "Cloud Production")
        
        console.print(table)
        input("\nPress Enter to return...")

    def show_news(self):
        self.clear_screen()
        news = self.db.get_top_news(limit=10)
        table = Table(title="📰 NEWS RADAR - NLP ANALYTICS", box=box.ROUNDED)
        table.add_column("Time", style="cyan")
        table.add_column("Source", style="dim")
        table.add_column("Title", style="white")

        for n in news:
            table.add_row(
                n['fecha'].strftime("%H:%M") if n['fecha'] else "N/A",
                "GCP-Feed",
                n['title']
            )
        console.print(table)
        input("\nPress Enter to return...")

    def show_config(self):
        self.clear_screen()
        params = self.db.get_parametros()
        table = Table(title="⚙️ SYSTEM CONFIGURATION (LIVE)", box=box.HORIZONTALS)
        table.add_column("Module", style="bold cyan")
        table.add_column("Parameter", style="white")
        table.add_column("Value", justify="right", style="bold yellow")

        # Sort by module
        sorted_keys = sorted(params.keys())
        for key in sorted_keys:
            parts = key.split('.', 1)
            mod = parts[0] if len(parts) > 1 else "GLOBAL"
            name = parts[1] if len(parts) > 1 else key
            table.add_row(mod, name, f"{params[key]:.4f}")

        console.print(table)
        input("\nPress Enter to return...")

    def run_logs(self):
        self.clear_screen()
        console.print(Panel("[bold white]📜 SYSTEM ACTIVITY LOGS[/bold white]", border_style="white"))
        # Simulating tail from bot_live.log or system_logs table
        try:
            with open("bot_live.log", "r") as f:
                lines = f.readlines()
                for line in lines[-20:]:
                    console.print(line.strip(), style="dim")
        except:
            console.print("[red]Could not read bot_live.log[/red]")
        
        input("\nPress Enter to return...")

    def main_loop(self):
        while self.running:
            self.clear_screen()
            self.draw_header()
            self.draw_menu()
            
            choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "9", "0"], default="1")
            
            if choice == "1":
                self.start_bot()
            elif choice == "2":
                self.show_dashboard()
            elif choice == "3":
                self.show_health()
            elif choice == "4":
                self.show_news()
            elif choice == "5":
                self.show_config()
            elif choice == "6":
                self.run_logs()
            elif choice == "9":
                self.cleanup_processes()
            elif choice == "0":
                if self.engine.running:
                    self.engine.stop()
                self.running = False
                console.print("[bold yellow]Shutting down CLI. Goodbye![/bold yellow]")

if __name__ == "__main__":
    try:
        cli = AurumCLI()
        cli.main_loop()
    except Exception as e:
        console.print(Panel(f"[bold red]FATAL ERROR DURING STARTUP:[/bold red]\n{str(e)}", border_style="red"))
        import traceback
        console.print(traceback.format_exc(), style="dim")
        input("\nPress Enter to exit...")
    except KeyboardInterrupt:
        try:
            if 'cli' in locals() and cli.engine.running:
                cli.engine.stop()
        except Exception:
            pass
        console.print("\n[bold red]Interrupted by user.[/bold red]")
        sys.exit(0)
