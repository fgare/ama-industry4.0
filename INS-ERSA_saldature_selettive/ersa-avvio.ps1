# Variabili dei percorsi
$converterDir = Get-Location
$fileMoverDir = "C:\Users\admin.mies\Documents\file_copy_and_delete"
$tempQueueDir = "$converterDir\temp_files_queue"

$trendFolder = "\\10.107.64.1\Trend"
$xmlFolder = "\\10.107.64.1\Protocol\XML"

$tempArchiveDir = "C:\Oneview_ARCHIVIO_TEMPORANEO"
$permArchiveDir = "C:\Oneview_ARCHIVIO_PERMANENTE"

# 1. Crea la cartella temporanea
New-Item -ItemType Directory -Path $tempQueueDir -Force

# 2. Esegui il convertitore Python
Set-Location $converterDir
python ".\ERSA converter.py" $trendFolder $xmlFolder $tempQueueDir

# sposta i file generati
Set-Location $fileMoverDir
python .\copy_and_delete.py $tempQueueDir $permArchiveDir $tempArchiveDir

# 3. Elimina la cartella temporanea al termine
Remove-Item -Path $tempQueueDir -Recurse -Force