; Inno Setup script of the Windows installer. Installs for the current user, without
; administrator rights, into %LOCALAPPDATA%\Programs\pii-roundtrip.
; iscc /DVersion=0.5.2 scripts\windows.iss   (run in desktop\, after the PyInstaller build)

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
; paths below are relative to desktop\, one level above this script
SourceDir=..
AppId={{6E8B2C5A-3F1D-4C8E-9A7B-0D5F2E4C1A93}
AppName=pii-roundtrip
AppVersion={#Version}
AppPublisher=Besk Tech
AppPublisherURL=https://pii-roundtrip.besk.tech
DefaultDirName={localappdata}\Programs\pii-roundtrip
DefaultGroupName=pii-roundtrip
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=pii-roundtrip-windows-setup
SetupIconFile=pii_roundtrip_desktop\icon.ico
UninstallDisplayIcon={app}\pii-roundtrip.exe
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
LicenseFile=..\LICENSE

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "dist\pii-roundtrip\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\pii-roundtrip"; Filename: "{app}\pii-roundtrip.exe"
Name: "{userdesktop}\pii-roundtrip"; Filename: "{app}\pii-roundtrip.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\pii-roundtrip.exe"; Description: "{cm:LaunchProgram,pii-roundtrip}"; Flags: nowait postinstall skipifsilent
