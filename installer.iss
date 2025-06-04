; installer.iss

[Setup]
AppName=SplitMe
AppVersion=1.0.0
DefaultDirName={pf}\SplitMe
DefaultGroupName=SplitMe
OutputBaseFilename=SplitMe-1.0.0-Setup
Compression=lzma
SolidCompression=yes

[Files]
; copy everything from dist\SplitMe.exe into {app} folder
Source: "dist\SplitMe.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SplitMe"; Filename: "{app}\SplitMe.exe"
Name: "{userdesktop}\SplitMe"; Filename: "{app}\SplitMe.exe"
