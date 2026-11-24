param([string]$SourceFile,[string]$Destination)
$ErrorActionPreference = "Stop"
$app = New-Object -ComObject PowerPoint.Application
try {
    $app.AutomationSecurity = 3
    $deck = $app.Presentations.Open($SourceFile, -1, 0, 0)
    try {
        foreach ($slide in $deck.Slides) {
            $slide.HeadersFooters.SlideNumber.Visible = 0
            $slide.SlideShowTransition.Hidden = 0
        }
        $deck.SaveAs($Destination, 32)
    } finally { $deck.Close() }
} finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
