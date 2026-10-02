# Guardia de horas extras — plan

Herramienta local (macOS) para no hacer horas extras "sin darse cuenta": detecta trabajo fuera de
horario, obliga a confirmar la marca en GeoVictoria (hecha por el usuario en la app móvil) antes de
usar Claude Code, avisa al terminar por inactividad y genera un reporte semanal exacto.

## Fuera de alcance (decidido)

- **No** se analiza ni replica la app/APK de GeoVictoria ni se marca automáticamente. La marca la
  hace siempre la persona en la app oficial. La confirmación es declarativa ("Ya marqué").
- Si TI/RR.HH. habilitan la **API oficial** de GeoVictoria o el marcaje web, se reemplaza solo el
  paso de confirmación por una verificación de lectura (ver Fase 6). El resto no cambia.
- No bloquear el PC completo: solo Claude Code.

## Jornada (de la skill `horas-extras`)

- Lun–jue 8h40, vie 5h20 (40 h). Corte 17:45 lun–jue. Confirmar horario exacto de entrada y del
  viernes con el usuario y dejarlo en `config.json` (configurable por persona).
- Fines de semana y festivos chilenos = fuera de horario (100%); día hábil fuera de jornada = 50%.

## Estado (fuente única)

`~/.guardia-he/state.json` + log append-only `~/.guardia-he/events.jsonl`:

| estado | significado |
|---|---|
| `en_horario` | dentro de la jornada |
| `fuera_sin_marca` | fuera de horario, sin hora extra abierta → gate cerrado |
| `extra_abierta` | usuario confirmó "ya marqué entrada"; guarda `inicio`, `confirmado_en` |
| `extra_por_cerrar` | inactividad ≥ umbral; espera "ya marqué salida" (hora real = último uso) |

Eventos: `confirma_entrada`, `confirma_salida`, `idle_start`, `idle_end`, `pantalla_bloqueada`,
`pantalla_desbloqueada`, `aviso_enviado`.

## Fases

1. **Núcleo (CLI `guardia`)** — Python o Swift, sin dependencias raras.
   `guardia status | marque-entrada | marque-salida | config | reporte --semana`.
   Calcula estado a partir de hora + config + festivos + state.json.
2. **Gate en Claude Code** — hook `UserPromptSubmit` (y aviso en `SessionStart`) en
   `~/.claude/settings.json` que llama `guardia status --hook`. Si `fuera_sin_marca` → bloquea con
   mensaje "Fuera de horario: marca en GeoVictoria y luego ejecuta `! guardia marque-entrada`".
   Debe fallar abierto (si el script falla, no bloquear) y responder en <100 ms.
3. **Indicador en barra de menú** — SwiftBar (plugin script) o app Swift mínima:
   🟢 / 🟡 / 🔴 + contador; menú con "Ya marqué entrada", "Ya marqué salida", "Ver semana".
4. **Daemon de actividad** — LaunchAgent cada 60 s: lee `HIDIdleTime` (`ioreg -c IOHIDSystem`),
   bloqueo de pantalla, app activa. Notificaciones (`osascript`/`terminal-notifier`):
   - Uso detectado fuera de horario sin marca → "Marca entrada en GeoVictoria".
   - `extra_abierta` + idle ≥ 15 min → "¿Terminaste? Marca salida" (registra último uso real).
   - Recordatorio a las 17:45 si sigue activo.
5. **Reporte semanal** — por bloque: inicio/fin confirmados, inicio/fin reales de actividad,
   duración, tipo 50%/100%, y qué se hizo: transcripts de `~/.claude/projects` en ese rango
   (resumen de prompts), commits `git log --since/--until` en repos de `~/Documents/Developement`,
   apps activas. Salida CSV + HTML; formato compatible con la skill `horas-extras` para cargar en SAP.
6. **(Opcional) Verificación oficial** — si TI entrega acceso a la API de GeoVictoria o marcaje
   web: reemplazar "Ya marqué" por consulta de lectura de marcas. Redactar correo de solicitud.

## Primer entregable

Fases 1 + 2 + 3 funcionando y probadas (simular horas con `GUARDIA_NOW=...`). Luego 4 y 5.
