# Instalador de Veridy y Kerna para Windows (lo abre Instalar.bat). Ventana con los pasos y botones al terminar.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$ErrorActionPreference = "Continue"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Aqui
$Config = Join-Path $Aqui "configuracion.env"
$Version = ((Get-Content $Config | Where-Object { $_ -like "VERSION=*" }) -replace "VERSION=", "").Trim()
$Inicio = "http://localhost:8400"

# ---------------------------------------------------------------- ventana
$f = New-Object System.Windows.Forms.Form
$f.Text = "Instalar Veridy y Kerna"
$f.Size = New-Object System.Drawing.Size(640, 520)
$f.StartPosition = "CenterScreen"
$f.FormBorderStyle = "FixedDialog"; $f.MaximizeBox = $false
$f.BackColor = [System.Drawing.Color]::White
$fuente = New-Object System.Drawing.Font("Segoe UI", 11)
$f.Font = $fuente

$titulo = New-Object System.Windows.Forms.Label
$titulo.Text = "Instalando Veridy y Kerna en este computador"
$titulo.Font = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Bold)
$titulo.Location = New-Object System.Drawing.Point(24, 18); $titulo.AutoSize = $true
$f.Controls.Add($titulo)

$nombres = @("Revisar o instalar Docker Desktop", "Encender Docker Desktop", "Copiar los programas (la primera vez tarda unos minutos)", "Poner en marcha Veridy y Kerna", "Esperar a que todo responda")
$pasos = @()
for ($i = 0; $i -lt $nombres.Count; $i++) {
  $l = New-Object System.Windows.Forms.Label
  $l.Text = "  ○  " + $nombres[$i]
  $l.Location = New-Object System.Drawing.Point(24, (70 + 34 * $i)); $l.Size = New-Object System.Drawing.Size(590, 28)
  $l.ForeColor = [System.Drawing.Color]::FromArgb(93, 102, 132)
  $f.Controls.Add($l); $pasos += $l
}

$barra = New-Object System.Windows.Forms.ProgressBar
$barra.Location = New-Object System.Drawing.Point(24, 250); $barra.Size = New-Object System.Drawing.Size(575, 18)
$barra.Style = "Marquee"; $barra.MarqueeAnimationSpeed = 30
$f.Controls.Add($barra)

$mensaje = New-Object System.Windows.Forms.Label
$mensaje.Location = New-Object System.Drawing.Point(24, 280); $mensaje.Size = New-Object System.Drawing.Size(580, 90)
$mensaje.Text = "No cierres esta ventana."
$f.Controls.Add($mensaje)

function Boton($texto, $x, $ancho, $color) {
  $b = New-Object System.Windows.Forms.Button
  $b.Text = $texto; $b.Location = New-Object System.Drawing.Point($x, 390); $b.Size = New-Object System.Drawing.Size($ancho, 46)
  $b.FlatStyle = "Flat"; $b.BackColor = $color; $b.ForeColor = [System.Drawing.Color]::White
  $b.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
  $b.Visible = $false; $f.Controls.Add($b); return $b
}
$bInicio   = Boton "Abrir la página de inicio" 24 190 ([System.Drawing.Color]::FromArgb(11, 16, 32))
$bDenuncia = Boton "Hacer una denuncia en Veridy" 222 190 ([System.Drawing.Color]::FromArgb(47, 95, 208))
$bPanel    = Boton "Panel de Kerna" 420 180 ([System.Drawing.Color]::FromArgb(14, 124, 134))
$bDocker   = Boton "Ir a descargar Docker Desktop" 24 260 ([System.Drawing.Color]::FromArgb(47, 95, 208))
$bDocker.Add_Click({ Start-Process "https://docs.docker.com/desktop/setup/install/windows-install/" })
$bInicio.Add_Click({ Start-Process $Inicio })
$bDenuncia.Add_Click({ Start-Process "http://localhost:8401/#/submission" })
$bPanel.Add_Click({ Start-Process "http://localhost:8402/acceso" })

function Paso($i, $estado) {
  $marca = @{ "curso" = "  ►  "; "ok" = "  ✓  "; "mal" = "  ✗  " }[$estado]
  $pasos[$i].Text = $marca + $nombres[$i]
  $pasos[$i].ForeColor = @{ "curso" = [System.Drawing.Color]::FromArgb(20, 26, 46); "ok" = [System.Drawing.Color]::FromArgb(31, 138, 76); "mal" = [System.Drawing.Color]::FromArgb(179, 71, 63) }[$estado]
  [System.Windows.Forms.Application]::DoEvents()
}
function Esperar($segundos) {
  $fin = (Get-Date).AddSeconds($segundos)
  while ((Get-Date) -lt $fin) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 100 }
}
function Ejecutar($argumentos) {
  # Corre docker sin bloquear la ventana. Devuelve el código de salida.
  $p = Start-Process -FilePath "docker" -ArgumentList $argumentos -NoNewWindow -PassThru -RedirectStandardOutput "$env:TEMP\vk-salida.txt" -RedirectStandardError "$env:TEMP\vk-error.txt"
  while (-not $p.HasExited) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 150 }
  return $p.ExitCode
}
function DockerResponde { return ((Ejecutar "info") -eq 0) }
function Fallo($i, $texto) {
  Paso $i "mal"; $barra.Style = "Blocks"; $barra.Value = 0
  $mensaje.ForeColor = [System.Drawing.Color]::FromArgb(179, 71, 63); $mensaje.Text = $texto
}
function Responde($url) {
  try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5; return ($r.StatusCode -lt 400) } catch { return $false }
}

$f.Add_Shown({
  # 1. Docker instalado
  Paso 0 "curso"
  $binDocker = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
  if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path "$binDocker\docker.exe")) { $env:PATH = "$binDocker;$env:PATH" }
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $mensaje.Text = "Descargando Docker Desktop (unos 600 MB; puede tardar varios minutos)."
    $destino = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
    $wc = New-Object System.Net.WebClient
    $tarea = $wc.DownloadFileTaskAsync("https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe", $destino)
    while (-not $tarea.IsCompleted) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 200 }
    if ($tarea.IsFaulted) { Fallo 0 "No se pudo descargar Docker Desktop. Revisa la conexión a internet o usa el botón para descargarlo a mano."; $bDocker.Visible = $true; return }
    $mensaje.Text = "Instalando Docker Desktop. Windows pedirá permiso: presiona «Sí». Tarda unos minutos."
    try { $p = Start-Process -FilePath $destino -ArgumentList "install","--quiet","--accept-license","--backend=wsl-2","--always-run-service" -Verb RunAs -PassThru }
    catch { Fallo 0 "Se necesita presionar «Sí» para instalar Docker Desktop. Vuelve a abrir «Instalar»."; return }
    while (-not $p.HasExited) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 300 }
    if (-not (Test-Path "$binDocker\docker.exe")) { Fallo 0 "La instalación de Docker Desktop no terminó. Reinicia el computador y vuelve a abrir «Instalar»."; return }
    $env:PATH = "$binDocker;$env:PATH"
    if ($p.ExitCode -eq 3010) { Fallo 0 "Docker Desktop quedó instalado. Windows necesita reiniciarse: reinicia el computador y vuelve a abrir «Instalar»."; return }
  }
  Paso 0 "ok"

  # 2. Docker encendido
  Paso 1 "curso"
  if (-not (DockerResponde)) {
    $exe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $exe) { Start-Process $exe }
    $mensaje.Text = "Encendiendo Docker Desktop. Si aparece una ventana de Docker pidiendo aceptar condiciones, acéptalas."
    $listo = $false
    for ($s = 0; $s -lt 60 -and -not $listo; $s++) { Esperar 5; $listo = DockerResponde }
    if (-not $listo) { Fallo 1 "Docker Desktop no terminó de encender. Ábrelo desde el menú Inicio, espera a que diga «Engine running» y vuelve a abrir «Instalar»."; return }
  }
  Paso 1 "ok"

  # 3. Imágenes
  Paso 2 "curso"
  if ((Ejecutar "image inspect veridy-local:$Version kerna-conector-local:$Version kerna-panel-local:$Version") -ne 0) {
    $mensaje.Text = "Copiando los programas a Docker. Puede tardar entre 2 y 6 minutos."
    if ((Ejecutar "load -i `"$Aqui\imagenes.tar.gz`"") -ne 0) { Fallo 2 ("No se pudieron copiar los programas: " + (Get-Content "$env:TEMP\vk-error.txt" -Raw)); return }
  }
  Paso 2 "ok"

  # 4. Encender
  Paso 3 "curso"; $mensaje.Text = "Poniendo en marcha Veridy y Kerna."
  if ((Ejecutar "compose --env-file `"$Config`" -f `"$Aqui\docker-compose.yml`" up -d") -ne 0) {
    $e = Get-Content "$env:TEMP\vk-error.txt" -Raw
    if ($e -match "port is already allocated|address already in use") { $e = "Otro programa está usando los puertos 8400, 8401 o 8402. Ciérralo y vuelve a abrir «Instalar»." }
    Fallo 3 $e; return
  }
  Paso 3 "ok"

  # 5. Esperar
  Paso 4 "curso"; $mensaje.Text = "Esperando a que Veridy y el panel respondan (hasta 3 minutos)."
  $ok = $false
  for ($s = 0; $s -lt 60 -and -not $ok; $s++) { Esperar 3; $ok = (Responde "http://localhost:8401/api/health") -and (Responde "http://localhost:8402/salud") }
  if (-not $ok) { Fallo 4 "Todavía no responde. Abre la página de inicio: allí se ve qué falta, y se actualiza sola."; $bInicio.Visible = $true; return }
  Paso 4 "ok"

  $barra.Style = "Blocks"; $barra.Value = 100
  $titulo.Text = "Listo. Veridy y Kerna están funcionando"
  $mensaje.ForeColor = [System.Drawing.Color]::FromArgb(31, 138, 76)
  $mensaje.Text = "Elige por dónde empezar. Las cuentas de prueba están en la página de inicio. Para apagar todo, usa «Detener» en la carpeta «archivos»."
  $bInicio.Visible = $true; $bDenuncia.Visible = $true; $bPanel.Visible = $true
})

[void]$f.ShowDialog()
