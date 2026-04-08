# Incidencia: Regresión del Dashboard por `git checkout -- .`

## Descripción del Problema
Al subir cambios al servidor, el Dashboard volvió a un estado anterior poco después de un despliegue exitoso. 

## Causa Raíz
El uso del comando `git checkout -- .` para "limpiar" permisos o archivos no seguidos en el servidor. 
- Este comando resetea TODOS los archivos modificados que pertenecen al repositorio.
- Como el frontend del Dashboard (`dist/`) está commiteado en Git, cualquier cambio local o build que no se haya sincronizado con el repositorio central se pierde al ejecutar este comando.
- En este caso, el build del Dashboard en el servidor tenía cambios específicos que fueron sobrescritos por el estado del commit actual al forzar el checkout.

## Protocolo de Recuperación (Solución Actual)

1. **Rebuild del Frontend**:
   Ejecutar en Cloud Shell para regenerar los archivos del Dashboard:
   ```bash
   gcloud compute ssh aurum-server --project=aurum-489120 --zone=us-central1-a --command="cd /opt/aurum/dashboard/frontend && sudo npm run build && echo BUILD_OK"
   ```

2. **Reinicio de Servicios**:
   Reiniciar el core y los obreros:
   ```bash
   gcloud compute ssh aurum-server --project=aurum-489120 --zone=us-central1-a --command="sudo systemctl restart aurum-core aurum-hunter aurum-telegram && echo RESTART_OK"
   ```

---

## Lecciones Aprendidas y Reglas para el Futuro (IMPORTANT/WARNING)

> [!WARNING]
> **NUNCA** usar `git checkout -- .` en el servidor de producción. Borra cambios locales del Dashboard que podrían no estar en el flujo de Git yet.

### Flujo de Deploy Recomendado:
1. Después de un `git push` desde local, usar el **botón "Deploy"** en la página de Configuración del Dashboard (esto ejecuta `update.sh` de forma segura vía FastAPI).
2. Si se hace manualmente: Usar solo `git pull` + `restart`. 
3. Si hay conflictos de archivos untracked (como `tests/test_mtf.py`), borrarlos manualmente o moverlos, pero NO usar checkout masivo.

---
*Documentado: 2026-04-07 | Referencia: Incidente de despliegue MTF V19.1*
