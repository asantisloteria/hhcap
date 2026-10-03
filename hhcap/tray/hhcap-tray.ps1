# Indicador de bandeja de sistema para hhcap en Windows (sin dependencias).
# Uso: hhcap menu   (o: powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File hhcap-tray.ps1)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$hhcap = if ($env:HHCAP_BIN) { $env:HHCAP_BIN } else { (Get-Command hhcap -ErrorAction SilentlyContinue).Source }
if (-not $hhcap) { [System.Windows.Forms.MessageBox]::Show("No encuentro 'hhcap' en el PATH."); exit 1 }

function Invoke-HHCap([string[]]$argv) {
    $out = & $hhcap @argv 2>&1 | Out-String
    return $out.Trim()
}

function New-Dot([System.Drawing.Color]$c) {
    $bmp = New-Object System.Drawing.Bitmap 16, 16
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.FillEllipse((New-Object System.Drawing.SolidBrush $c), 2, 2, 12, 12)
    $g.Dispose()
    return [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
}
$icons = @{
    en_horario       = New-Dot ([System.Drawing.Color]::FromArgb(46, 160, 67))
    extra_abierta    = New-Dot ([System.Drawing.Color]::FromArgb(212, 167, 44))
    extra_por_cerrar = New-Dot ([System.Drawing.Color]::FromArgb(219, 109, 40))
    fuera_sin_marca  = New-Dot ([System.Drawing.Color]::FromArgb(207, 34, 46))
    uso_personal     = New-Dot ([System.Drawing.Color]::FromArgb(51, 120, 217))
    error            = New-Dot ([System.Drawing.Color]::Gray)
}

$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Visible = $true
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$info = $menu.Items.Add("...")
$info.Enabled = $false
[void]$menu.Items.Add("-")
$menu.Items.Add("Ya marqué entrada").add_Click({ Show-Result (Invoke-HHCap @("marque-entrada")) })
$menu.Items.Add("Ya marqué salida").add_Click({ Show-Result (Invoke-HHCap @("marque-salida")) })
$menu.Items.Add("Ver mis horas extras").add_Click({
    $f = Join-Path $env:TEMP "hhcap-semana.txt"
    Invoke-HHCap @("reporte", "--semana") | Set-Content -Encoding UTF8 $f
    Start-Process notepad.exe $f
})
[void]$menu.Items.Add("-")
$menu.Items.Add("Salir").add_Click({ $tray.Visible = $false; [System.Windows.Forms.Application]::Exit() })
$tray.ContextMenuStrip = $menu

function Show-Result([string]$msg) {
    $tray.ShowBalloonTip(4000, "hhcap", $msg, 'Info')
    Update-Status
}

function Update-Status {
    try {
        $j = Invoke-HHCap @("status", "--json") | ConvertFrom-Json
        $m = [int]$j.minutos
        $reloj = "{0}:{1:D2}" -f [math]::Floor($m / 60), ($m % 60)
        $txt = switch ($j.estado) {
            "en_horario"       { "En horario" }
            "extra_abierta"    { "Hora extra $($j.tipo) abierta: $reloj" }
            "extra_por_cerrar" { "Inactivo: marca salida en GeoVictoria ($reloj)" }
            "uso_personal"     { "Uso personal: no cuenta como hora extra" }
            default            { "Fuera de horario ($($j.tipo)) sin marca" }
        }
        $tray.Icon = $icons[$j.estado]
    } catch {
        $txt = "hhcap no responde"
        $tray.Icon = $icons.error
    }
    $info.Text = $txt
    $tray.Text = ("hhcap: " + $txt).Substring(0, [math]::Min(63, ("hhcap: " + $txt).Length))
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 30000
$timer.add_Tick({ Update-Status })
$timer.Start()
Update-Status
[System.Windows.Forms.Application]::Run()
