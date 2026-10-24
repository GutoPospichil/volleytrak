#define Root "D:\volleytrak"
#define AppName "VolleyTrak"
#define AppVersion "0.3.10"
#define AppPublisher "VolleyTrak Local"

[Setup]
AppId={{5E8C2A0D-3B7B-4B5A-9B0E-3C8D5A7F1E21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\VolleyTrak
DefaultGroupName=VolleyTrak
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#Root}\installer\Output
OutputBaseFilename=VolleyTrakSetup
Compression=lzma2/fast
SolidCompression=no
WizardStyle=modern
UninstallDisplayName=VolleyTrak
UninstallDisplayIcon={app}\Abrir VolleyTrak.cmd
ExtraDiskSpaceRequired=8589934592
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Ârea de Trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#Root}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\pipeline\*"; DestDir: "{app}\pipeline"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\portable-python\*"; DestDir: "{app}\portable-python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\data\models\*"; DestDir: "{localappdata}\VolleyTrakData\models"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\data\feedback_profile.json"; DestDir: "{localappdata}\VolleyTrakData"; Flags: ignoreversion
Source: "{#Root}\data\feedback_ranker.json"; DestDir: "{localappdata}\VolleyTrakData"; Flags: ignoreversion
Source: "{#Root}\installer\start-portable.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\installer\Abrir VolleyTrak.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\TRANSFER.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\requirements-cv.txt"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{localappdata}\VolleyTrakData"
Name: "{localappdata}\VolleyTrakData\models"
Name: "{localappdata}\VolleyTrakData\videos"
Name: "{localappdata}\VolleyTrakData\jobs"

[Icons]
Name: "{group}\VolleyTrak"; Filename: "{app}\Abrir VolleyTrak.cmd"; WorkingDir: "{app}"; IconFilename: "{sys}\shell32.dll"; IconIndex: 138
Name: "{group}\Desinstalar VolleyTrak"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VolleyTrak"; Filename: "{app}\Abrir VolleyTrak.cmd"; WorkingDir: "{app}"; IconFilename: "{sys}\shell32.dll"; IconIndex: 138; Tasks: desktopicon

[Run]
Filename: "{app}\Abrir VolleyTrak.cmd"; Description: "Abrir o VolleyTrak agora"; Flags: nowait postinstall skipifsilent
