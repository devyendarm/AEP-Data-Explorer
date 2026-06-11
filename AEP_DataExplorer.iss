[Setup]
; App Information
AppName=AEP Data Explorer
AppVersion=1.3.0
AppPublisher=Devyendar

; IMPORTANT: This setting allows users to install the app WITHOUT Admin Rights!
; It installs to %LOCALAPPDATA%\Programs\AEP_DataExplorer instead of C:\Program Files
PrivilegesRequired=lowest

; Output Settings
OutputDir=dist
OutputBaseFilename=AEP_DataExplorer_Setup_v1.3
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\AEP_DataExplorer.exe

; Default Installation Directory for non-admin users
DefaultDirName={localappdata}\Programs\AEP_DataExplorer

; Start Menu
DefaultGroupName=AEP Data Explorer
AllowNoIcons=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Source files (from the PyInstaller 'dist/AEP_DataExplorer' output folder)
Source: "dist\AEP_DataExplorer\AEP_DataExplorer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\AEP_DataExplorer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Create shortcuts in the Start Menu and Desktop
Name: "{group}\AEP Data Explorer"; Filename: "{app}\AEP_DataExplorer.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,AEP Data Explorer}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AEP Data Explorer"; Filename: "{app}\AEP_DataExplorer.exe"; Tasks: desktopicon; IconFilename: "{app}\app_icon.ico"

[Run]
; Option to launch the app immediately after installation finishes
Filename: "{app}\AEP_DataExplorer.exe"; Description: "{cm:LaunchProgram,AEP Data Explorer}"; Flags: nowait postinstall skipifsilent
