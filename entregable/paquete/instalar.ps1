# Instalador de Veridy y Kerna para Windows (lo abre Instalar.bat). Ventana con los pasos y botones al terminar.
# Los pasos corren en segundo plano; la ventana solo muestra el estado, así nunca se congela.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$ErrorActionPreference = "Continue"
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Aqui

# Estado compartido entre los pasos (segundo plano) y la ventana.
$E = [hashtable]::Synchronized(@{
  Aqui = $Aqui; Pasos = @("", "", "", "", ""); Mensaje = "No cierres esta ventana."; Base = ""; Desde = $null
  Final = ""; Botones = @(); Barra = "mover"; Puertos = @{ inicio = 8400; veridy = 8401; panel = 8402 }
})

# ---------------------------------------------------------------- pasos (segundo plano)
$trabajo = {
  param($E)
  $ErrorActionPreference = "Continue"
  $Aqui = $E.Aqui
  $Config = Join-Path $Aqui "configuracion.env"
  $Version = ((Get-Content $Config | Where-Object { $_ -like "VERSION=*" }) -replace "VERSION=", "").Trim()
  $registro = Join-Path $env:TEMP "instalar-veridy-kerna.log"
  function Anotar($t) { Add-Content -Path $registro -Value ("{0:HH:mm:ss} {1}" -f (Get-Date), $t) }
  function Paso($i, $estado) { $p = $E.Pasos; $p[$i] = $estado; $E.Pasos = $p; Anotar "paso $i $estado" }
  function Avance($t) { $E.Base = $t; $E.Desde = Get-Date; Anotar $t }
  function Fallo($i, $t) { Paso $i "mal"; $E.Base = $t; $E.Desde = $null; $E.Final = "mal"; $E.Barra = "parar"; Anotar "FALLO $t" }
  function Ejecutar($argumentos, $limite = 0) {
    # Devuelve el código de salida de docker; -1 si pasa del límite (en segundos).
    # (Start-Process -PassThru a veces no entrega el código de salida; por eso se usa Process directo.)
    $exe = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"
    if (-not (Test-Path $exe)) { $exe = "docker" }
    $si = New-Object System.Diagnostics.ProcessStartInfo
    $si.FileName = $exe; $si.Arguments = $argumentos
    $si.UseShellExecute = $false; $si.CreateNoWindow = $true
    $si.RedirectStandardOutput = $true; $si.RedirectStandardError = $true; $si.RedirectStandardInput = $true
    try { $p = [System.Diagnostics.Process]::Start($si) } catch { Anotar "docker no se pudo ejecutar: $_"; Set-Content "$env:TEMP\vk-error.txt" "$_"; return -2 }
    $p.StandardInput.Close()  # si docker preguntara algo, no queda esperando una respuesta
    $out = $p.StandardOutput.ReadToEndAsync(); $err = $p.StandardError.ReadToEndAsync()
    if ($limite -gt 0) { if (-not $p.WaitForExit($limite * 1000)) { try { $p.Kill() } catch {}; Anotar "docker ${argumentos}: sin respuesta en $limite s"; Set-Content "$env:TEMP\vk-error.txt" ("No terminó en $limite s. Lo último que dijo Docker: " + $err.Result + $out.Result); return -1 } } else { $p.WaitForExit() }
    $p.WaitForExit()
    Set-Content "$env:TEMP\vk-salida.txt" $out.Result; Set-Content "$env:TEMP\vk-error.txt" $err.Result
    if ($p.ExitCode -ne 0) { Anotar ("docker $argumentos -> " + $p.ExitCode + ": " + $err.Result) }
    return $p.ExitCode
  }
  function DockerResponde { return ((Ejecutar "info" 10) -eq 0) }
  function Responde($url) {
    try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4; return ($r.StatusCode -lt 400) } catch { return $false }
  }
  function SeguirTrasReiniciar {
    # Al volver a entrar a Windows, «Instalar» se abre solo y sigue donde quedó.
    $bat = Join-Path (Split-Path -Parent $Aqui) "Instalar.bat"
    New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce" -Name "InstalarVeridyKerna" -Value "`"$bat`"" -PropertyType String -Force | Out-Null
    $E.Botones = @("reiniciar")
  }

  try {
    # 1. Docker instalado (si falta, se descarga e instala)
    Paso 0 "curso"
    $binDocker = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
    if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path "$binDocker\docker.exe")) { $env:PATH = "$binDocker;$env:PATH" }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
      Avance "Descargando Docker Desktop (unos 600 MB; puede tardar varios minutos)."
      $destino = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
      try { (New-Object System.Net.WebClient).DownloadFile("https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe", $destino) }
      catch { Fallo 0 "No se pudo descargar Docker Desktop. Revisa la conexión a internet y vuelve a abrir «Instalar»."; $E.Botones = @("docker"); return }
      Avance "Instalando Docker Desktop. Windows pedirá permiso: presiona «Sí». Tarda unos minutos."
      try { $p = Start-Process -FilePath $destino -ArgumentList "install","--quiet","--accept-license","--backend=wsl-2","--always-run-service" -Verb RunAs -PassThru }
      catch { Fallo 0 "Se necesita presionar «Sí» para instalar Docker Desktop. Vuelve a abrir «Instalar»."; return }
      $p.WaitForExit()
      if (-not (Test-Path "$binDocker\docker.exe")) { Fallo 0 "La instalación de Docker Desktop no terminó. Reinicia el computador y vuelve a abrir «Instalar»."; return }
      # Recién instalado, Docker Desktop solo arranca bien después de reiniciar Windows.
      Paso 0 "ok"; $E.Barra = "parar"; $E.Desde = $null
      $E.Base = "Docker Desktop quedó instalado. Falta reiniciar Windows una vez: presiona «Reiniciar ahora». Al volver a entrar, la instalación sigue sola."
      SeguirTrasReiniciar; $E.Final = "pausa"; return
    }
    Paso 0 "ok"

    # 2. Docker encendido
    Paso 1 "curso"
    Avance "Revisando si Docker Desktop está encendido."
    if (-not (DockerResponde)) {
      $exe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
      if (Test-Path $exe) { Start-Process $exe }
      Avance "Encendiendo Docker Desktop. Si Docker muestra una ventana pidiendo aceptar condiciones, acéptalas."
      $ini = Get-Date; $listo = $false
      while (-not $listo -and ((Get-Date) - $ini).TotalSeconds -lt 120) { Start-Sleep -Seconds 3; $listo = DockerResponde }
      if (-not $listo) { Fallo 1 "Docker Desktop no terminó de encender. Presiona «Reiniciar ahora»: al volver a entrar, la instalación sigue sola."; SeguirTrasReiniciar; return }
    }
    Paso 1 "ok"

    # 3. Imágenes
    Paso 2 "curso"
    Avance "Revisando los programas."
    if ((Ejecutar "image inspect veridy-local:$Version kerna-conector-local:$Version kerna-panel-local:$Version" 60) -ne 0) {
      Avance "Copiando los programas a Docker. Puede tardar entre 2 y 6 minutos."
      if ((Ejecutar "load -i `"$Aqui\imagenes.tar.gz`"") -ne 0) { Fallo 2 ("No se pudieron copiar los programas: " + (Get-Content "$env:TEMP\vk-error.txt" -Raw)); return }
    }
    Paso 2 "ok"

    # 4. Encender (en puertos libres: Windows a veces se reserva 8400-8402)
    Paso 3 "curso"; Avance "Poniendo en marcha Veridy y Kerna."
    [void](Ejecutar "compose --env-file `"$Config`" -f `"$Aqui\docker-compose.yml`" stop" 120)  # suelta los puertos de una vez anterior
    function Libre($n) { try { $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $n); $l.Start(); $l.Stop(); return $true } catch { return $false } }
    $usados = @()
    foreach ($k in @("INICIO", "VERIDY", "PANEL")) {
      $base = @{ INICIO = 8400; VERIDY = 8401; PANEL = 8402 }[$k]
      $n = $base
      foreach ($c in @($base, ($base + 10000), ($base + 20000), ($base + 30000), ($base + 40000), ($base + 50000))) { if (($usados -notcontains $c) -and (Libre $c)) { $n = $c; break } }
      $usados += $n; Set-Item "env:PUERTO_$k" $n
    }
    $E.Puertos = @{ inicio = $env:PUERTO_INICIO; veridy = $env:PUERTO_VERIDY; panel = $env:PUERTO_PANEL }
    Anotar ("puertos: inicio $env:PUERTO_INICIO, veridy $env:PUERTO_VERIDY, panel $env:PUERTO_PANEL")
    if ((Ejecutar "compose --progress plain --env-file `"$Config`" -f `"$Aqui\docker-compose.yml`" up -d --pull never" 300) -ne 0) {
      $e = Get-Content "$env:TEMP\vk-error.txt" -Raw
      if ($e -match "port is already allocated|address already in use") { $e = "Otro programa está usando los puertos que necesita Veridy. Vuelve a abrir «Instalar»: buscará otros." }
      Fallo 3 $e; return
    }
    Paso 3 "ok"

    # 5. Esperar
    Paso 4 "curso"; Avance "Esperando a que Veridy y el panel respondan (hasta 3 minutos)."
    $ini = Get-Date; $ok = $false
    while (-not $ok -and ((Get-Date) - $ini).TotalMinutes -lt 3) { Start-Sleep -Seconds 3; $ok = (Responde "http://localhost:$env:PUERTO_VERIDY/api/health") -and (Responde "http://localhost:$env:PUERTO_PANEL/salud") }
    if (-not $ok) { Fallo 4 "Todavía no responde. Abre la página de inicio: allí se ve qué falta, y se actualiza sola."; $E.Botones = @("inicio"); return }
    Paso 4 "ok"
    $E.Desde = $null
    $E.Base = "Elige por dónde empezar. Las cuentas de prueba están en la página de inicio. Para apagar todo, usa «Detener» en la carpeta «archivos»."
    $E.Botones = @("inicio", "denuncia", "panel"); $E.Final = "ok"
  } catch {
    $E.Base = "Algo falló: " + $_.Exception.Message + "  (detalle en $registro)"; $E.Desde = $null; $E.Final = "mal"; $E.Barra = "parar"; Anotar $_
  }
}

# ---------------------------------------------------------------- ventana
$f = New-Object System.Windows.Forms.Form
$f.Text = "Instalar Veridy y Kerna"
$f.Size = New-Object System.Drawing.Size(640, 520)
$f.StartPosition = "CenterScreen"
$f.FormBorderStyle = "FixedDialog"; $f.MaximizeBox = $false
$f.BackColor = [System.Drawing.Color]::White
$f.Font = New-Object System.Drawing.Font("Segoe UI", 11)

$titulo = New-Object System.Windows.Forms.Label
$titulo.Text = "Instalando Veridy y Kerna en este computador"
$titulo.Font = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Bold)
$titulo.Location = New-Object System.Drawing.Point(24, 18); $titulo.AutoSize = $true
$f.Controls.Add($titulo)

$nombres = @("Revisar o instalar Docker Desktop", "Encender Docker Desktop", "Copiar los programas (la primera vez tarda unos minutos)", "Poner en marcha Veridy y Kerna", "Esperar a que todo responda")
$pasos = @()
for ($i = 0; $i -lt $nombres.Count; $i++) {
  $l = New-Object System.Windows.Forms.Label
  $l.Location = New-Object System.Drawing.Point(24, (70 + 34 * $i)); $l.Size = New-Object System.Drawing.Size(590, 28)
  $f.Controls.Add($l); $pasos += $l
}

$barra = New-Object System.Windows.Forms.ProgressBar
$barra.Location = New-Object System.Drawing.Point(24, 250); $barra.Size = New-Object System.Drawing.Size(575, 18)
$barra.Style = "Marquee"; $barra.MarqueeAnimationSpeed = 30
$f.Controls.Add($barra)

$mensaje = New-Object System.Windows.Forms.Label
$mensaje.Location = New-Object System.Drawing.Point(24, 280); $mensaje.Size = New-Object System.Drawing.Size(580, 100)
$f.Controls.Add($mensaje)

function Boton($texto, $x, $ancho, $color) {
  $b = New-Object System.Windows.Forms.Button
  $b.Text = $texto; $b.Location = New-Object System.Drawing.Point($x, 390); $b.Size = New-Object System.Drawing.Size($ancho, 46)
  $b.FlatStyle = "Flat"; $b.BackColor = $color; $b.ForeColor = [System.Drawing.Color]::White
  $b.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
  $b.Visible = $false; $f.Controls.Add($b); return $b
}
$azul = [System.Drawing.Color]::FromArgb(47, 95, 208)
$botones = @{
  inicio    = Boton "Abrir la página de inicio" 24 190 ([System.Drawing.Color]::FromArgb(11, 16, 32))
  denuncia  = Boton "Hacer una denuncia en Veridy" 222 190 $azul
  panel     = Boton "Panel de Kerna" 420 180 ([System.Drawing.Color]::FromArgb(14, 124, 134))
  docker    = Boton "Ir a descargar Docker Desktop" 24 260 $azul
  reiniciar = Boton "Reiniciar ahora" 24 200 $azul
}
$botones.inicio.Add_Click({ Start-Process ("http://localhost:" + $E.Puertos.inicio) })
$botones.denuncia.Add_Click({ Start-Process ("http://localhost:" + $E.Puertos.veridy + "/#/submission") })
$botones.panel.Add_Click({ Start-Process ("http://localhost:" + $E.Puertos.panel + "/acceso") })
$botones.docker.Add_Click({ Start-Process "https://docs.docker.com/desktop/setup/install/windows-install/" })
$botones.reiniciar.Add_Click({ Restart-Computer -Force })

$verde = [System.Drawing.Color]::FromArgb(31, 138, 76); $rojo = [System.Drawing.Color]::FromArgb(179, 71, 63)
$oscuro = [System.Drawing.Color]::FromArgb(20, 26, 46); $gris = [System.Drawing.Color]::FromArgb(93, 102, 132)
$reloj = New-Object System.Windows.Forms.Timer
$reloj.Interval = 400
$reloj.Add_Tick({
  for ($i = 0; $i -lt $nombres.Count; $i++) {
    $st = $E.Pasos[$i]
    $marca = @{ "" = "  ○  "; "curso" = "  ►  "; "ok" = "  ✓  "; "mal" = "  ✗  " }[$st]
    $pasos[$i].Text = $marca + $nombres[$i]
    $pasos[$i].ForeColor = @{ "" = $gris; "curso" = $oscuro; "ok" = $verde; "mal" = $rojo }[$st]
  }
  $t = $E.Base; if (-not $t) { $t = "No cierres esta ventana." }
  if ($E.Desde) { $s = [int]((Get-Date) - $E.Desde).TotalSeconds; if ($s -ge 5) { $t = "$t  (lleva $s s)" } }
  $mensaje.Text = $t
  if ($E.Barra -eq "parar" -and $barra.Style -ne "Blocks") { $barra.Style = "Blocks"; $barra.Value = 0 }
  foreach ($k in $E.Botones) { $botones[$k].Visible = $true }
  if ($E.Final -eq "mal") { $mensaje.ForeColor = $rojo }
  if ($E.Final -eq "ok") {
    $reloj.Stop(); $barra.Style = "Blocks"; $barra.Value = 100; $mensaje.ForeColor = $verde
    $titulo.Text = "Listo. Veridy y Kerna están funcionando"
  }
})

$ps = [PowerShell]::Create()
[void]$ps.AddScript($trabajo).AddArgument($E)
$f.Add_Shown({ $reloj.Start(); [void]$ps.BeginInvoke() })
[void]$f.ShowDialog()
