# Instala Guion de Medios en esta PC: tareas programadas + acceso directo en el escritorio.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
# Se puede correr varias veces: reemplaza las tareas si ya existen.

$ErrorActionPreference = "Stop"

$Raiz    = Split-Path -Parent $PSScriptRoot
$Datos   = Join-Path $env:LOCALAPPDATA "GuionDeMedios"
$Pythonw = Join-Path $Datos "venv\Scripts\pythonw.exe"

if (-not (Test-Path $Pythonw)) {
    throw "No se encontró $Pythonw. Crea primero el entorno: python -m venv `"$Datos\venv`" y pip install -r requirements.txt"
}

$Usuario = "$env:USERDOMAIN\$env:USERNAME"
$Principal = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType Interactive -RunLevel Limited

# 1) Watcher: cada hora; si la PC estuvo apagada, corre apenas se pueda; nunca dos a la vez.
$AccionWatcher = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Raiz\watcher.py`"" -WorkingDirectory $Raiz
$DisparoWatcher = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
$AjustesWatcher = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

# 2) Portal: al iniciar sesión, sin límite de tiempo.
$AccionPortal = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Raiz\serve.py`"" -WorkingDirectory $Raiz
# Espera 2 min y reintenta: G: (Google Drive) se monta unos segundos después de iniciar sesión.
$DisparoPortal = New-ScheduledTaskTrigger -AtLogOn -User $Usuario
$DisparoPortal.Delay = "PT2M"
$AjustesPortal = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)

foreach ($Nombre in "GuionMedios-Watcher", "GuionMedios-Portal") {
    if (Get-ScheduledTask -TaskName $Nombre -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Nombre -Confirm:$false
    }
}

Register-ScheduledTask -TaskName "GuionMedios-Watcher" -Action $AccionWatcher -Trigger $DisparoWatcher `
    -Settings $AjustesWatcher -Principal $Principal -Description "Guion de Medios: recolecta noticias cada hora" | Out-Null
Register-ScheduledTask -TaskName "GuionMedios-Portal" -Action $AccionPortal -Trigger $DisparoPortal `
    -Settings $AjustesPortal -Principal $Principal -Description "Guion de Medios: portal en http://127.0.0.1:5050" | Out-Null

# 3) Acceso directo en el escritorio.
$Escritorio = [Environment]::GetFolderPath("Desktop")
$Acceso = Join-Path $Escritorio "Guion de Medios.url"
Set-Content -Path $Acceso -Encoding ASCII -Value "[InternetShortcut]`r`nURL=http://127.0.0.1:5050/"

Write-Host "Listo:"
Get-ScheduledTask -TaskName "GuionMedios-*" | Format-Table TaskName, State -AutoSize
Write-Host "Acceso directo: $Acceso"
