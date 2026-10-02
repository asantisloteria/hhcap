# hhcap — captador de horas extras

Evita hacer horas extras "sin darse cuenta": fuera de tu jornada, Claude Code no acepta mensajes
hasta que confirmes que marcaste entrada en GeoVictoria. Registra cada bloque y genera el reporte
semanal (50% / 100%) para cargarlo en SAP.

La marca la haces siempre tú en la app de GeoVictoria; hhcap solo registra que la hiciste.

## Instalar

**macOS** (Homebrew):

```bash
brew tap asantisloteria/hhcap https://github.com/asantisloteria/hhcap.git
brew trust asantisloteria/hhcap      # Homebrew 7 exige confiar en taps de terceros
cd ~ && brew install hhcap           # desde ~: el sandbox de brew no puede leer ~/Documents
hhcap config --jornada lun=08:15-17:45 --jornada mar=08:15-17:45 --jornada mie=08:15-17:45 \
             --jornada jue=08:15-17:45 --jornada vie=08:15-13:35     # tu horario
hhcap hook install            # activa el bloqueo en Claude Code
brew services start hhcap     # indicador en la barra de menú (arranca con el Mac)
```

**Windows** (requiere Python 3.8+ y pipx):

```powershell
pipx install git+https://github.com/asantisloteria/hhcap.git
hhcap config --jornada lun=08:15-17:45 ...    # igual que en macOS
hhcap hook install
hhcap menu                                    # indicador en la bandeja del sistema
```

## Uso diario

| Situación | Qué hacer |
|---|---|
| Claude Code dice "Fuera de horario" | Marca entrada en GeoVictoria y ejecuta `! hhcap marque-entrada` (o `--a HH:MM` si marcaste antes) |
| Terminaste | Marca salida en GeoVictoria y ejecuta `hhcap marque-salida` |
| Ver tu semana | Menú 🚬 → «Ver mis horas extras» (tabla, navegar semanas, descargar semana o mes para Excel) |
| Reporte en terminal | `hhcap reporte` · `--mes` · `--desde/--hasta` · `-o archivo.csv` |
| Estado actual | `hhcap status` |

Indicador en la barra de menú (pastilla de color):
🟢 En horario · 🔴 Fuera de horario (late hasta que marques) · 🟡 Extra 50% · 1:25 ·
🟠 Cierra tu extra · ⚪️ hhcap no responde.

## Probar sin esperar a la tarde

```bash
hhcap simular 19:00            # el reloj de hhcap pasa a las 19:00 por 30 min (vence solo)
hhcap simular 2026-10-03T10:00 --minutos 10    # un sábado
hhcap simular --off
```

## Actualizar

```bash
hhcap update
```

## Festivos

Los feriados nacionales de Chile se calculan solos (`hhcap festivos`). Feriados electorales o
regionales: `hhcap config --festivo 2026-11-15`.

## Desinstalar

```bash
hhcap hook uninstall && brew services stop hhcap && brew uninstall hhcap
```

## Publicar una versión (mantenedor)

```bash
./scripts/release.sh 0.2.0     # tests, sube versión, tag y push
```

Datos locales en `~/.hhcap/` (`config.json`, `state.json`, `events.jsonl`).
