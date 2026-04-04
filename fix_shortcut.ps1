$s = (New-Object -ComObject WScript.Shell).CreateShortcut("C:\Users\Admin\Desktop\TradeBot.lnk")
$s.TargetPath = "C:\Users\Admin\Documents\TradeBot\TradeBot.bat"
$s.WorkingDirectory = "C:\Users\Admin\Documents\TradeBot"
$s.Description = "TradeBot Desktop App"
$s.Save()