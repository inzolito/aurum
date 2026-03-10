"""
AURUM ADMIN — Panel de Administración Central
Reemplaza las funciones de administración de aurum_cli.py con un menú
dedicado a operación diaria. No arranca el bot — solo lo monitorea y controla.

Uso: python aurum_admin.py
"""
import os
import sys
import time
import subprocess
import psutil
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich import box

sys.path.insert(0, str(Path(__file__).parent))
from config.db_connector import DBConnector

console = Console()

_PID_FILE     = Path(__file__).parent / "aurum_core.pid"
_VENV_PYTHON  = Path(__file__).parent / "venv" / "Scripts" / "python.exe"
_MAIN_PY      = Path(__file__).parent / "main.py"
_HUNTER_PY    = Path(__file__).parent / "news_hunter.py"
_HEARTBEAT_PY = Path(__file__).parent / "heartbeat.py"


# ── helpers ────────────────────────────────────────────────────────────────

def _fmt_voto(v, neutro_val=0.0) -> str:
    """Formatea un voto numérico con color rich."""
    if v is None:
        return "[dim]N/A[/dim]"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return "[dim]N/A[/dim]"
    if fv > neutro_val + 0.001:
        return f"[green]{fv:+.3f}[/green]"
    if fv < neutro_val - 0.001:
        return f"[red]{fv:+.3f}[/red]"
    return f"[dim]{fv:+.3f}[/dim]"


def _fmt_hurst(v) -> str:
    if v is None:
        return "[dim]N/A[/dim]"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return "[dim]N/A[/dim]"
    if fv > 0.55:
        return f"[green]{fv:.3f}[/green]"
    if fv < 0.45:
        return f"[yellow]{fv:.3f}[/yellow]"
    return f"[dim]{fv:.3f}[/dim]"


def _hace_cuanto(dt) -> str:
    if dt is None:
        return "?"
    try:
        ahora = datetime.now(timezone.utc)
        seg = int((ahora - dt).total_seconds())
        if seg < 60:
            return f"{seg}s"
        if seg < 3600:
            return f"{seg//60}m"
        return f"{seg//3600}h"
    except Exception:
        return "?"


def _get_proceso(script_name: str):
    """Retorna el proceso psutil que ejecuta el script, o None."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' not in proc.info.get('name', '').lower():
                continue
            cmd = ' '.join(proc.info.get('cmdline') or [])
            if script_name in cmd:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


# ── vistas ─────────────────────────────────────────────────────────────────

def tabla_votos(db: DBConnector):
    """
    Muestra la tabla de votos por obrero para todos los activos.
    Consulta registro_senales con el último registro de cada activo.
    Modo Live: se refresca cada 30 segundos hasta que el usuario presiona Ctrl+C.
    """

    def _generar():
        t = Table(
            title="📊 TABLA DE VOTOS POR OBRERO — Último ciclo registrado",
            box=box.ROUNDED, expand=True, show_lines=True
        )
        t.add_column("Activo",     style="bold yellow", width=8)
        t.add_column("Tendencia",  justify="center", width=10)
        t.add_column("NLP",        justify="center", width=8)
        t.add_column("Flow",       justify="center", width=8)
        t.add_column("Sniper",     justify="center", width=8)
        t.add_column("Hurst",      justify="center", width=8)
        t.add_column("Volumen",    justify="center", width=9)
        t.add_column("Cross",      justify="center", width=8)
        t.add_column("Veredicto",  justify="center", width=10)
        t.add_column("Decisión",   justify="center", width=18)
        t.add_column("Hace",       justify="right",  width=6)

        try:
            if not db.conn or db.conn.closed:
                db.conectar()
            db.cursor.execute("""
                SELECT a.simbolo,
                       rs.voto_tendencia, rs.voto_nlp, rs.voto_order_flow,
                       rs.voto_sniper,    rs.voto_hurst,
                       rs.voto_volume,    rs.voto_cross,
                       rs.voto_final_ponderado, rs.decision_gerente, rs.tiempo
                FROM registro_senales rs
                JOIN activos a ON rs.activo_id = a.id
                WHERE rs.tiempo = (
                    SELECT MAX(rs2.tiempo)
                    FROM registro_senales rs2
                    WHERE rs2.activo_id = rs.activo_id
                )
                ORDER BY a.simbolo;
            """)
            rows = db.cursor.fetchall()
        except Exception as e:
            t.add_row("[red]Error DB[/red]", *["—"]*10)
            return Panel(t, subtitle=f"[red]{e}[/red]")

        decision_colors = {
            "IGNORADO":         "dim",
            "CANCELADO_RIESGO": "red",
            "EJECUTADO":        "bold green",
            "COMPRA":           "green",
            "VENTA":            "red",
            "ERROR_BROKER":     "bold red",
            "VOLATILIDAD_EXTREMA": "bold yellow",
        }

        for r in rows:
            (simbolo, v_trend, v_nlp, v_flow, v_sniper, v_hurst,
             v_vol, v_cross, veredicto, decision, tiempo) = r

            d_color = decision_colors.get(str(decision), "white")
            d_str   = f"[{d_color}]{decision}[/{d_color}]"

            t.add_row(
                simbolo,
                _fmt_voto(v_trend),
                _fmt_voto(v_nlp),
                _fmt_voto(v_flow),
                _fmt_voto(v_sniper),
                _fmt_hurst(v_hurst),
                _fmt_voto(v_vol),
                _fmt_voto(v_cross),
                _fmt_voto(veredicto),
                d_str,
                _hace_cuanto(tiempo),
            )

        ts = datetime.now().strftime("%H:%M:%S")
        return Panel(t, subtitle=f"[dim]Actualizado: {ts} | Ctrl+C para volver[/dim]")

    console.print("[dim]Cargando... Ctrl+C para volver al menú[/dim]")
    with Live(_generar(), refresh_per_second=0.5, screen=False) as live:
        try:
            while True:
                time.sleep(30)
                live.update(_generar())
        except KeyboardInterrupt:
            pass


def estado_procesos():
    """Muestra el estado de los tres procesos Aurum."""
    t = Table(title="🚦 ESTADO DE PROCESOS AURUM", box=box.SIMPLE)
    t.add_column("Proceso",   style="bold cyan", width=18)
    t.add_column("Estado",    justify="center",  width=12)
    t.add_column("PID",       justify="right",   width=8)
    t.add_column("RAM (MB)",  justify="right",   width=10)
    t.add_column("CPU %",     justify="right",   width=8)

    scripts = [
        ("Core (main.py)",        "main.py"),
        ("News Hunter",           "news_hunter.py"),
        ("SHIELD (heartbeat.py)", "heartbeat.py"),
    ]

    for nombre, script in scripts:
        proc = _get_proceso(script)
        if proc:
            try:
                mem = proc.memory_info().rss / (1024 * 1024)
                cpu = proc.cpu_percent(interval=0.1)
                t.add_row(nombre, "[green]RUNNING[/green]", str(proc.pid),
                          f"{mem:.1f}", f"{cpu:.1f}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                t.add_row(nombre, "[red]CAIDO[/red]", "—", "—", "—")
        else:
            t.add_row(nombre, "[red]NO CORRE[/red]", "—", "—", "—")

    console.print(t)
    input("\nEnter para volver...")


def estado_activos(db: DBConnector):
    """Muestra y permite cambiar el estado_operativo de cada activo."""
    try:
        db.cursor.execute(
            "SELECT id, simbolo, nombre, estado_operativo FROM activos ORDER BY id;"
        )
        activos = db.cursor.fetchall()
    except Exception as e:
        console.print(f"[red]Error DB: {e}[/red]")
        input("Enter para volver...")
        return

    t = Table(title="🗄️  ESTADO DE ACTIVOS", box=box.ROUNDED)
    t.add_column("#",   width=4,  justify="right")
    t.add_column("Símbolo", style="bold yellow", width=10)
    t.add_column("Nombre",  width=22)
    t.add_column("Estado",  justify="center", width=16)

    colores = {
        "ACTIVO":       "green",
        "PAUSADO":      "yellow",
        "SOLO_CIERRAR": "red",
    }
    for row in activos:
        id_, simbolo, nombre, estado = row
        color = colores.get(str(estado), "white")
        t.add_row(str(id_), simbolo, nombre or "", f"[{color}]{estado}[/{color}]")
    console.print(t)

    console.print("\n[dim]Escribe el símbolo a modificar (o Enter para volver):[/dim]")
    simbolo_edit = Prompt.ask("Símbolo", default="").upper().strip()
    if not simbolo_edit:
        return

    ids_validos = {r[1]: r[0] for r in activos}
    if simbolo_edit not in ids_validos:
        console.print(f"[red]Símbolo '{simbolo_edit}' no encontrado.[/red]")
        input("Enter para volver...")
        return

    nuevo_estado = Prompt.ask(
        "Nuevo estado",
        choices=["ACTIVO", "PAUSADO", "SOLO_CIERRAR"],
        default="ACTIVO"
    )
    try:
        db.cursor.execute(
            "UPDATE activos SET estado_operativo = %s WHERE simbolo = %s;",
            (nuevo_estado, simbolo_edit)
        )
        db.conn.commit()
        console.print(f"[green]✅ {simbolo_edit} → {nuevo_estado}[/green]")
    except Exception as e:
        console.print(f"[red]Error actualizando: {e}[/red]")
    input("Enter para volver...")


def ver_parametros(db: DBConnector):
    """Muestra los parámetros del sistema desde parametros_sistema."""
    try:
        params = db.get_parametros()
    except Exception as e:
        console.print(f"[red]Error DB: {e}[/red]")
        input("Enter para volver...")
        return

    t = Table(title="⚙️  PARÁMETROS DEL SISTEMA (DB)", box=box.HORIZONTALS)
    t.add_column("Módulo",     style="bold cyan", width=16)
    t.add_column("Parámetro", width=30)
    t.add_column("Valor",     justify="right", style="bold yellow", width=12)

    for key in sorted(params.keys()):
        partes = key.split('.', 1)
        mod  = partes[0] if len(partes) > 1 else "GLOBAL"
        name = partes[1] if len(partes) > 1 else key
        try:
            t.add_row(mod, name, f"{float(params[key]):.4f}")
        except (TypeError, ValueError):
            t.add_row(mod, name, str(params[key]))

    console.print(t)
    input("\nEnter para volver...")


def ultimas_noticias(db: DBConnector):
    """Muestra las últimas 20 noticias de raw_news_feed."""
    try:
        db.cursor.execute("""
            SELECT timestamp, source, title, content_summary
            FROM raw_news_feed
            ORDER BY timestamp DESC
            LIMIT 20;
        """)
        rows = db.cursor.fetchall()
    except Exception as e:
        console.print(f"[red]Error DB: {e}[/red]")
        input("Enter para volver...")
        return

    t = Table(title="📰 ÚLTIMAS NOTICIAS (raw_news_feed)", box=box.ROUNDED, expand=True)
    t.add_column("Hora",    style="cyan",   width=6)
    t.add_column("Fuente",  style="dim",    width=12)
    t.add_column("Titular", style="white",  ratio=3)
    t.add_column("Impacto", justify="center", width=12)

    for row in rows:
        ts, source, title, summary = row
        hora    = ts.strftime("%H:%M") if ts else "??"
        fuente  = (source or "")[:12]
        titular = title or ""
        resumen = summary or ""

        if "Impacto:" in resumen:
            try:
                val = int(resumen.split("|")[0].replace("Impacto:", "").strip())
                if val >= 8:
                    imp = f"[bold red]🔴 {val}/10[/bold red]"
                elif val >= 5:
                    imp = f"[yellow]🟡 {val}/10[/yellow]"
                else:
                    imp = f"[green]🟢 {val}/10[/green]"
            except ValueError:
                imp = "[dim]?[/dim]"
        elif "Descargada" in resumen:
            imp = "[dim]IA: irrelevante[/dim]"
        elif "Filtro" in resumen:
            imp = "[dim]filtrada[/dim]"
        else:
            imp = "[dim]—[/dim]"

        t.add_row(hora, fuente, titular[:90], imp)

    console.print(t)
    input("\nEnter para volver...")


def reiniciar_bot():
    """Mata todas las instancias y lanza una nueva limpia."""
    if not Confirm.ask("¿Reiniciar el bot? Esto mata todas las instancias actuales"):
        return

    current_pid = os.getpid()
    killed = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid == current_pid:
                continue
            if 'python' not in proc.info.get('name', '').lower():
                continue
            cmd = ' '.join(proc.info.get('cmdline') or [])
            if any(s in cmd for s in ['main.py', 'news_hunter', 'heartbeat']):
                proc.kill()
                killed.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if _PID_FILE.exists():
        _PID_FILE.unlink()

    console.print(f"[yellow]Terminados {len(killed)} procesos. Esperando...[/yellow]")
    time.sleep(3)

    if _VENV_PYTHON.exists():
        flags = 0x08000000 if os.name == 'nt' else 0
        proc  = subprocess.Popen([str(_VENV_PYTHON), str(_MAIN_PY)],
                                 creationflags=flags,
                                 cwd=str(Path(__file__).parent))
        console.print(f"[green]✅ Bot lanzado — PID {proc.pid}[/green]")
    else:
        console.print("[red]No se encontró el entorno virtual. Lanza el bot manualmente.[/red]")

    input("\nEnter para volver...")


# ── menú principal ─────────────────────────────────────────────────────────

def _draw_header():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Estado rápido de procesos
    core_ok    = _get_proceso("main.py")    is not None
    hunter_ok  = _get_proceso("news_hunter") is not None
    shield_ok  = _get_proceso("heartbeat")   is not None

    status = (
        f"Core: {'[green]OK[/green]' if core_ok else '[red]CAIDO[/red]'}  "
        f"Hunter: {'[green]OK[/green]' if hunter_ok else '[red]CAIDO[/red]'}  "
        f"Shield: {'[green]OK[/green]' if shield_ok else '[red]CAIDO[/red]'}"
    )
    console.print(Panel(
        f"[bold yellow]AURUM ADMIN — Panel de Administración[/bold yellow]\n{status}",
        subtitle=f"[dim]{ts}[/dim]",
        box=box.DOUBLE, border_style="cyan"
    ))


def main():
    db = DBConnector()
    if not db.conectar():
        console.print("[red]No se pudo conectar a la base de datos.[/red]")
        sys.exit(1)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        _draw_header()

        t = Table(show_header=False, box=box.SIMPLE, expand=True)
        t.add_column("Opción", style="bold cyan", width=5)
        t.add_column("Descripción")
        t.add_row("[1]", "📊  Tabla de Votos por Obrero  (Live, refresco 30s)")
        t.add_row("[2]", "🚦  Estado de Procesos")
        t.add_row("[3]", "🗄️   Estado de Activos  (ver / cambiar ACTIVO · PAUSADO · SOLO_CIERRAR)")
        t.add_row("[4]", "⚙️   Parámetros del Sistema  (pesos, umbrales, drawdown)")
        t.add_row("[5]", "📰  Últimas Noticias  (raw_news_feed)")
        t.add_row("[6]", "🔄  Reiniciar Bot  (kill + relaunch limpio)")
        t.add_row("[0]", "❌  Salir")
        console.print(Panel(t, title="[bold white]MENÚ PRINCIPAL[/bold white]", border_style="yellow"))

        choice = Prompt.ask("Opción", choices=["0","1","2","3","4","5","6"], default="1")

        if   choice == "1": tabla_votos(db)
        elif choice == "2": estado_procesos()
        elif choice == "3": estado_activos(db)
        elif choice == "4": ver_parametros(db)
        elif choice == "5": ultimas_noticias(db)
        elif choice == "6": reiniciar_bot()
        elif choice == "0":
            db.desconectar()
            console.print("[bold yellow]Hasta luego.[/bold yellow]")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrumpido.[/bold red]")
        sys.exit(0)
