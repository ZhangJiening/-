#define AppVersion "0.1.0"
#define AppName "乳腺癌药物先导化合物筛选优化平台"
#define AppPublisher "乳腺癌药物先导化合物筛选优化平台"
#define ProjectDir ".."
#define AppSource "..\\dist\\ERLeadPlatform"
#define CustomerDocs "..\\docs\\customer"

[Setup]
AppId={{D7D6B42E-DA8F-4E70-9E8C-1F2D5B9F7C10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\ERLeadPlatform
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile={#ProjectDir}\assets\app.ico
UninstallDisplayIcon={app}\ERLeadPlatform.exe
OutputDir={#ProjectDir}\release\installer
OutputBaseFilename=ERLeadPlatform-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#AppVersion}.0
VersionInfoDescription={#AppName} 安装程序
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
Uninstallable=yes

[Languages]
Name: "default"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=欢迎安装 {#AppName}
WelcomeLabel2=此向导将引导您完成安装。安装后，训练好的模型会随程序一起加载。
SelectDirLabel3=程序将安装到以下文件夹。
SelectTasksDesc=选择附加任务
SelectTasksLabel1=选择附加任务
SelectAdditionalTasks=选择附加任务
SelectTasksLabel2=请选择安装过程中要执行的附加任务，然后点击“下一步”。
ReadyLabel1=安装程序已准备好开始安装 {#AppName}。
ReadyLabel2a=点击“安装”开始安装。
InstallingLabel=正在安装 {#AppName}，请稍候。
FinishedHeadingLabel=安装完成
FinishedLabel=安装已完成。点击“完成”退出安装向导。
ButtonNext=下一步
ButtonBack=上一步
ButtonCancel=取消
ButtonInstall=安装
ButtonFinish=完成

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#CustomerDocs}\*"; DestDir: "{app}\docs\customer"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ERLeadPlatform.exe"; WorkingDir: "{app}"
Name: "{group}\使用说明 PDF"; Filename: "{app}\docs\customer\ERLeadPlatform-User-Guide.pdf"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ERLeadPlatform.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ERLeadPlatform.exe"; Description: "启动 {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
