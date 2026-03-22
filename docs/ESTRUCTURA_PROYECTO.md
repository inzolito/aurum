# Aurum — Estructura de Archivos del Proyecto
> Generado: 2026-03-22 | Basado en actividad git (últimas 2 semanas)

---

## ARCHIVOS ACTIVOS (tocados en las últimas 2 semanas)

### Entrypoints
| Archivo | Rol |
|---------|-----|
| `main.py` | Motor principal AurumEngine — ciclo cada 60s |
| `heartbeat.py` | SHIELD — vigila los 3 procesos y los relanza |
| `news_hunter.py` | Daemon RSS scraping + análisis Gemini |
| `telegram_daemon.py` | Daemon Telegram V2.0 — recibe comandos, envía alertas |

### Administración
| Archivo | Rol |
|---------|-----|
| `aurum_cli.py` | CLI — control manual del bot desde consola |
| `aurum_admin.py` | Panel administrativo — operaciones DB manuales |
| `start_dashboard.py` | Lanzador del servidor web del dashboard |
| `kill_aurum.py` | Detiene todos los procesos Aurum limpiamente |
| `backfill_autopsias.py` | Recalcula autopsias históricas de operaciones |

### Core
| Archivo | Rol |
|---------|-----|
| `core/manager.py` | Meta-algoritmo: votación ponderada, filtros de riesgo, decisión final |
| `core/risk_module.py` | Kill-switch, gestión de capital, filtros de sesión |
| `core/scheduler.py` | AurumScheduler — tareas periódicas |
| `core/lab_evaluator.py` | Motor de laboratorio V18 — evalúa configs alternativas |

### Config
| Archivo | Rol |
|---------|-----|
| `config/db_connector.py` | PostgreSQL GCP + Survival Mode con RAM buffer |
| `config/mt5_connector.py` | Conexión MetaTrader 5 / MetaAPI Cloud |
| `config/notifier.py` | Envío de notificaciones Telegram |
| `config/logging_config.py` | Configuración centralizada de logs |
| `config/telegram_bot.py` | DEPRECADO — mantenido por compatibilidad, no usar |

### Workers (9 activos)
| Archivo | Rol |
|---------|-----|
| `workers/worker_trend.py` | Análisis de tendencia técnica |
| `workers/worker_nlp.py` | Contexto macro con Gemini AI (NLP) |
| `workers/worker_flow.py` | Flujo de órdenes / order flow |
| `workers/worker_structure.py` | Estructura de mercado (soportes/resistencias) |
| `workers/worker_hurst.py` | Exponente de Hurst — detección de tendencia vs ruido |
| `workers/worker_vix.py` | Volatilidad implícita (VIX proxy) |
| `workers/worker_volume.py` | Análisis de volumen |
| `workers/worker_cross.py` | Correlaciones cruzadas entre activos |
| `workers/worker_spread.py` | Monitor de spread bid/ask |
| `workers/worker_macro.py` | MacroWorker V18.1 — lee regimenes_macro, vota por ciclo |

### MetaTrader5 Shim (Linux)
| Archivo | Rol |
|---------|-----|
| `MetaTrader5/__init__.py` | Shim Linux — implementa MT5 API vía MetaAPI Cloud |

### Dashboard — Backend
| Archivo | Rol |
|---------|-----|
| `dashboard/backend/main.py` | FastAPI — todos los endpoints /api/* |
| `dashboard/backend/auth.py` | Autenticación JWT |
| `dashboard/backend/__init__.py` | Paquete Python |
| `dashboard/__init__.py` | Paquete Python |

### Dashboard — Frontend (React/Vite)
| Archivo | Rol |
|---------|-----|
| `dashboard/frontend/src/App.jsx` | Router principal |
| `dashboard/frontend/src/main.jsx` | Entry point React |
| `dashboard/frontend/src/pages/Dashboard.jsx` | Página principal — precios y estado general |
| `dashboard/frontend/src/pages/Monitor.jsx` | Salud del bot — latido, ciclos, workers |
| `dashboard/frontend/src/pages/Historial.jsx` | Historial de operaciones |
| `dashboard/frontend/src/pages/Lab.jsx` | Laboratorio de activos V18 |
| `dashboard/frontend/src/pages/Config.jsx` | Configuración — activos, parámetros, macros |
| `dashboard/frontend/src/pages/Control.jsx` | Control manual — iniciar/detener/actualizar |
| `dashboard/frontend/src/pages/Noticias.jsx` | Feed de noticias procesadas |
| `dashboard/frontend/src/pages/Login.jsx` | Login JWT |
| `dashboard/frontend/src/components/MacroBar.jsx` | Barra global de regímenes macro |
| `dashboard/frontend/src/components/MarketPulse.jsx` | Indicador de pulso de mercado |
| `dashboard/frontend/src/components/SideNav.jsx` | Navegación lateral |

### Scripts de Deploy/Servidor
| Archivo | Rol |
|---------|-----|
| `scripts/deploy.sh` | Deploy al servidor GCP (rsync + restart) |
| `scripts/setup_vm.sh` | Setup inicial del VM aurum-server |
| `scripts/update.sh` | Actualización en el servidor (git pull + restart) |
| `scripts/migrate_v18.sql` | Migración V18 — tablas lab_*, regimenes_macro |
| `scripts/migrate_lab_versioning.sql` | Migración versionado de labs |
| `scripts/add_xptusd_lab.sql` | Migración XPTUSD al Lab Metales |
| `scripts/services/` | Systemd units (aurum-core, aurum-hunter, aurum-telegram, aurum-dashboard, aurum-shield) |
| `scripts/sync_operaciones.py` | Sincroniza operaciones MT5 → DB |
| `scripts/crear_servicios.py` | Genera archivos .service de systemd |

### DB Migrations (activas)
| Archivo | Rol |
|---------|-----|
| `db/apply_migration.py` | Runner de migraciones |
| `db/migration_v14_security.sql` | Migración V14 seguridad |
| `db/migration_v15_broker_map.sql` | Migración V15 mapa de broker symbols |
| `db/migration_v15_fixes.sql` | Fixes V15 |

### Dashboard — Utilidades internas
| Archivo | Rol |
|---------|-----|
| `dashboard/backend/test_db_prism.py` | Test de conexión DB desde backend |
| `dashboard/docs/apply_migration_level0.py` | Migración de nivel 0 del dashboard |
| `dashboard/docs/create_master_user.py` | Crea usuario master en auth |

### Tests integrados
| Archivo | Rol |
|---------|-----|
| `tests/__init__.py` | Paquete tests |
| `tests/test_workers.py` | Tests de workers (pytest) |

---

## ARCHIVOS NO TOCADOS EN MÁS DE 2 SEMANAS — CANDIDATOS A ELIMINAR

> Ninguno de estos archivos ha sido modificado en el repositorio en las últimas 2 semanas.
> Verificar antes de borrar que no sean necesarios para el proyecto.

### Scripts temporales (prefijo tmp_ / temp_) — ELIMINAR
Creados durante sesiones de debug, sin valor permanente.
```
tmp_check_tg.py
tmp_cycle_test.py
tmp_debug_nlp_raw.py
tmp_final_table.py
tmp_force_nlp.py
tmp_run_core.py
temp_analyze_closed.py
temp_analyze_ops.py
temp_analyze_remote.py
temp_check_10016.py
temp_check_schema_tmp2.py
temp_parse_logs.py
```

### Migraciones ya ejecutadas — ELIMINAR
Scripts de migración de versiones anteriores (V10-V15) ya aplicados en producción.
```
apply_v11_patches.py
migrate_estado_bot.py
migrate_nuevos_activos.py
migrate_precision.py
migrate_version_v15.py
patch.py
patch_drawdown.py
patch_history.py
patch_manager.py
run_all_migrations.py
run_v15fixes.py
reactivar_oro_plata.py      ← "ejecutar una sola vez", ya ejecutado
recoup_xti.py
database/migrate_v10_senales.py
database/run_migrations.py
database/migrations/         ← historial V10-V13, ya aplicadas (mantener solo como referencia)
```

### Scripts de diagnóstico/auditoría — ELIMINAR
Usados para diagnosticar problemas puntuales, ya resueltos.
```
audit_final_temp.py
audit_forensic_temp.py
audit_signals_temp.py
audit_v6.py
audit_v7.py
check_db_diag.py
check_ndx.py
check_params_temp.py
check_real_db_ip.py
check_schema_tmp.py
diagnostics_connection.py
find_news_table.py
inspect_senales_temp.py
inspect_bot.py
troubleshoot_ndx.py
reproduce_error.py
research_indices.py
```

### Scripts fix_* — ELIMINAR
Correcciones puntuales ya aplicadas.
```
fix_db.py
fix_db2.py
fix_db3.py
fix_db_real.py
fix_prism_db.py
fix_risk.py
fix_symbols.py
```

### Tests no integrados — ELIMINAR o mover a tests/
Tests sueltos en raíz, reemplazados por tests/test_workers.py.
```
test_cross.py
test_fase2.py
test_latencia.py
test_manager.py
test_mt5.py
test_news_report.py
test_nlp_priority.py
test_risk.py
test_telegram.py
test_volume.py
```

### Scripts de otro proyecto — ELIMINAR
No pertenecen a Aurum.
```
cloud_sentinel.py    ← monitor externo con requests+psycopg2, no es el SHIELD
dashboard.py         ← dashboard CLI con pandas, reemplazado 100% por React
```

### Scripts utilitarios sin uso claro — REVISAR
```
force_analysis.py        ← revisar si tiene lógica útil
get_table_counts.py      ← utilitario DB, podría servir para debug
manual_test_news.py      ← test manual del hunter
send_ws_open_report.py   ← reporte de apertura semanal, verificar si se usa
recalibrate_v2.py        ← recalibración de pesos, verificar si aplica
backfill_autopsias.py    ← recalcula autopsias (fue tocado en las últimas 2 semanas, mantener)
```

### Setup antiguo — REVISAR
```
setup_pg.sh              ← setup de PostgreSQL local, obsoleto si todo está en GCP
```

### Archivos de output/logs en raíz — ELIMINAR
```
backend_debug.log, bot_err.log, bot_live.log, bot_startup.log, bot_v11.log
core_live_output.txt, core_run_test.txt, core_startup_test.txt
cycle_test_output.txt, out.txt, out_closed.txt, out_live_now.txt
test_cycle_result.txt, test_gbpjpy_result.txt, test_us30_result.txt
test_ustec_result.txt, test_xbrusd_result.txt
aurum_ops.txt, tmp_data.json
```

### Directorio inválido — ELIMINAR
```
C:wwwAurumdb/    ← directorio vacío creado por bug de ruta Windows/Unix
```

---

## RESUMEN

| Categoría | Archivos activos | Candidatos a eliminar |
|-----------|:---:|:---:|
| Entrypoints + Core | 18 | 0 |
| Workers | 10 | 0 |
| Dashboard frontend | 13 | 0 |
| Dashboard backend | 5 | 0 |
| Config | 5 | 0 |
| Scripts servidor | 9 | 0 |
| tmp_ / temp_ | 0 | 12 |
| fix_* | 0 | 7 |
| Migraciones antiguas | 0 | 14 |
| Diagnóstico/auditoría | 0 | 17 |
| Tests no integrados | 2 | 10 |
| Otro proyecto | 0 | 2 |
| Logs/outputs raíz | 0 | 20 |
| **TOTAL** | **~62** | **~82** |
