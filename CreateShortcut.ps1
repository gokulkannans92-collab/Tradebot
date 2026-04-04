$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\TradeBot.lnk")
$Shortcut.TargetPath = "C:\Users\Admin\Documents\TradeBot\dist\TradeBot\TradeBot.exe"
$Shortcut.WorkingDirectory = "C:\Users\Admin\Documents\TradeBot\dist\TradeBot"
$Shortcut.IconLocation = "C:\Users\Admin\Documents\TradeBot\TradeBot.ico"
$Shortcut.Description = "TradeBot Trading Dashboard"
$Shortcut.Save()

Write-Host "✅ TradeBot Desktop Shortcut created successfully with icon!" -ForegroundColor Green
