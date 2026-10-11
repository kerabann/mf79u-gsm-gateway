-- Compatibility launcher. Run Python directly for live logs.
on run argv
    set commandText to "/opt/homebrew/bin/python3 <historical-workspace>/outputs/utm-usb-autoconnect.py"
    if argv contains "dry-run" then set commandText to commandText & " --dry-run"
    do shell script commandText
end run
