# Reconstruye static/CSS/app.css (tailwind v3 + fuentes self-hosted).
# Uso: powershell -ExecutionPolicy Bypass -File tools\build_css.ps1
# Requiere: node/npx con red (solo al construir, no en prod).
# Tras correrlo, commitear static/CSS/app.css + static/fonts + plantillas (?v=).
$ErrorActionPreference = 'Stop'
$v2 = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path ([IO.Path]::GetTempPath()) 'muse_tw_build'
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

# 1. Fuentes woff2 (latin) -> static/fonts + @font-face
$cssUrl = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap'
$css = (Invoke-WebRequest -Uri $cssUrl -UseBasicParsing -Headers @{'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0' }).Content
$fontsDir = Join-Path $v2 'static\fonts'
New-Item -ItemType Directory -Path $fontsDir -Force | Out-Null
$faces = @()
foreach ($m in [regex]::Matches($css, '/\* (\w+) \*/\s*@font-face \{(.*?)\}', 'Singleline')) {
    if ($m.Groups[1].Value -ne 'latin') { continue }
    $body = $m.Groups[2].Value
    $fam = ([regex]::Match($body, "font-family: '([^']+)'")).Groups[1].Value
    $wt = ([regex]::Match($body, 'font-weight: (\d+)')).Groups[1].Value
    $url = ([regex]::Match($body, 'url\((https://[^)]+\.woff2)\)')).Groups[1].Value
    $fn = ($fam -replace ' ', '') + "-$wt.woff2"
    Invoke-WebRequest -Uri $url -OutFile (Join-Path $fontsDir $fn) -UseBasicParsing
    $faces += "@font-face{font-family:'$fam';font-style:normal;font-weight:$wt;font-display:swap;src:url('/static/fonts/$fn') format('woff2');}"
}
Write-Host "Fuentes: $($faces.Count)"

# 2. input.css + config en TEMP
$inputCss = ($faces -join "`n") + "`n@tailwind base;`n@tailwind components;`n@tailwind utilities;`n"
Set-Content -LiteralPath (Join-Path $tmp 'input.css') -Value $inputCss -Encoding utf8 -NoNewline
$v2s = $v2 -replace '\\', '/'
$cfg = "module.exports = { content: ['$v2s/templates/**/*.html', '$v2s/static/JS/**/*.js'], theme: { extend: {} }, plugins: [] };"
Set-Content -LiteralPath (Join-Path $tmp 'tailwind.config.js') -Value $cfg -Encoding utf8 -NoNewline

# 3. Build v3 -> static/CSS/app.css
$cssOut = Join-Path $v2 'static\CSS\app.css'
Push-Location $tmp
& npx -y -p tailwindcss@3 tailwindcss -i input.css -o $cssOut --minify
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "tailwind fallo ($LASTEXITCODE)" }
Pop-Location

# 4. Hash ?v= en plantillas que referencian app.css
$hash = (Get-FileHash -LiteralPath $cssOut -Algorithm SHA256).Hash.Substring(0, 8).ToLower()
$n = 0
Get-ChildItem (Join-Path $v2 'templates\*.html') | ForEach-Object {
    $t = [IO.File]::ReadAllText($_.FullName)
    $t2 = [regex]::Replace($t, '/static/CSS/app\.css\?v=[0-9a-f]+', "/static/CSS/app.css?v=$hash")
    if ($t2 -ne $t) { [IO.File]::WriteAllText($_.FullName, $t2); $n++ }
}
Write-Host "OK app.css ?v=$hash ($n plantillas)"
