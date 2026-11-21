# Adapted from hssling/india-tb-diabetes-gap v1.0.0 (MIT), tools/word_count_word.ps1 (itself adapted from hssling/india-tb-priority-tool, hssling/india-tb-acf-campaign and hssling/india-state-tb-score); modified: the Transactions of The Royal Society of Tropical Medicine and Hygiene sections (Introduction, Materials and methods, Results, Discussion as level-2 headings, with level-3 subsection headings inside them) and the structured abstract
# Count the abstract and the main text of the manuscript in Microsoft Word.
# Usage: powershell -NoProfile -File word_count_word.ps1 <docx> <out.json>
# Opens its own Word instance (read-only, hidden) and quits only that instance.
# Abstract: the paragraphs between the "Abstract" heading and the Keywords line (Keywords excluded;
# the run-in labels Background, Methods, Results and Conclusions included).
# Main text: the text under the level-2 headings Introduction, Materials and methods, Results and
# Discussion, headings excluded; level-3 subsection headings stay inside the section and are counted
# only in main_with_headings. It ends at any other level-2 heading (Authors' contributions). Tables
# are excluded.
param([string]$Docx, [string]$Out)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $d = $word.Documents.Open($Docx, $false, $true)
  $state = ""; $abs = 0; $main = 0; $heads = 0; $sec = [ordered]@{}; $cur = ""
  foreach ($p in $d.Paragraphs) {
    $t = $p.Range.Text.Trim()
    if ($p.Range.Information(12)) { continue }          # inside a table
    $n = $p.Range.ComputeStatistics(0)
    $lvl = $p.OutlineLevel
    if ($lvl -lt 10) {
      if ($lvl -le 2) {
        if ($t -eq "Abstract") { $state = "abs" }
        elseif ($t -match '^(Introduction|Materials and methods|Results|Discussion)$') { $state = "main"; $cur = $Matches[1]; $sec[$cur] = 0 }
        else { $state = "" }
      } elseif ($state -eq "main") { $heads += $n }
      continue
    }
    if ($t -like "Keywords:*") { $state = ""; continue }
    if ($state -eq "abs") { $abs += $n }
    if ($state -eq "main") { $main += $n; $sec[$cur] += $n }
  }
  $pages = $d.ComputeStatistics(2)
  $d.Close(0)
  $parts = @()
  foreach ($k in $sec.Keys) { $parts += ('"' + $k + '": ' + $sec[$k]) }
  $json = '{"abstract": ' + $abs + ', "main_text": ' + $main + ', "main_with_headings": ' + ($main + $heads) + ', "sections": {' + ($parts -join ', ') + '}, "pages": ' + $pages + '}'
  Set-Content -Path $Out -Value $json -Encoding ascii
} finally { $word.Quit() }
