#define Root "D:\volleytrak"
#define AppName "VolleyTrak"
#define AppVersion "0.3.13"
#define AppPublisher "VolleyTrak Local"

[Setup]
AppId={{5E8C2A0D-3B7B-4B5A-9B0E-3C8D5A7F1E21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
SetupIconFile={#Root}\installer\VolleyTrak.ico
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
UninstallDisplayIcon={app}\VolleyTrak.ico
ExtraDiskSpaceRequired=3221225472
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Ãrea de Trabalho"; GroupDescription: "Atalhos:"

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
Source: "{#Root}\installer\Abrir VolleyTrak (app).cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\installer\VolleyTrak.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Root}\desktop.py"; DestDir: "{app}"; Flags: ignoreversion
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
Name: "{group}\VolleyTrak"; Filename: "{app}\portable-python\pythonw.exe"; Parameters: """{app}\desktop.py"""; WorkingDir: "{app}"; IconFilename: "{app}\VolleyTrak.ico"
Name: "{group}\VolleyTrak (navegador)"; Filename: "{app}\Abrir VolleyTrak.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\VolleyTrak.ico"
Name: "{group}\VolleyTrak (janela web)"; Filename: "{app}\Abrir VolleyTrak (app).cmd"; WorkingDir: "{app}"; IconFilename: "{app}\VolleyTrak.ico"
Name: "{group}\Desinstalar VolleyTrak"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VolleyTrak"; Filename: "{app}\portable-python\pythonw.exe"; Parameters: """{app}\desktop.py"""; WorkingDir: "{app}"; IconFilename: "{app}\VolleyTrak.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\portable-python\pythonw.exe"; Parameters: """{app}\desktop.py"""; Description: "Abrir o VolleyTrak agora"; Flags: nowait postinstall skipifsilent
