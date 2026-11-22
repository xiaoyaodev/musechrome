; MuseChrome 安装包脚本（NSIS）：文件夹版整包安装，可选安装目录、
; 桌面快捷方式、开始菜单、卸载项。升级安装时只替换程序文件，
; MuseChromeData（账号数据）永远不动。
; 构建：makensis -DVERSION=1.9.1 -DAPP_DIR=<dist 文件夹路径> -DOUTFILE=<输出 setup 路径> installer.nsi
Unicode true

!ifndef VERSION
  !define VERSION "1.9.1"
!endif
!ifndef APP_DIR
  !error "需要 -DAPP_DIR=PyInstaller 文件夹版输出目录"
!endif
!ifndef OUTFILE
  !define OUTFILE "MuseChrome-Setup-v${VERSION}.exe"
!endif

Name "Muse 账号管理器"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\MuseChrome"
RequestExecutionLevel user
SetCompressor zlib

!include "MUI2.nsh"
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\MuseChrome.exe"
!define MUI_FINISHPAGE_RUN_TEXT "运行 Muse 账号管理器"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "Muse 账号管理器 MuseChrome"
VIAddVersionKey "FileDescription" "Muse 多账号管理器（每账号独立 Chrome 配置）"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "MIT License"

Section "安装" SecMain
  ; 升级：先清掉旧版程序文件（_internal 整目录是纯程序文件，可安全清），
  ; MuseChromeData 不在清理范围内，账号数据原样保留
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\MuseChrome.exe"

  SetOutPath "$INSTDIR"
  File /r "${APP_DIR}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; 桌面快捷方式
  CreateShortCut "$DESKTOP\Muse 账号管理器.lnk" "$INSTDIR\MuseChrome.exe" "" "$INSTDIR\MuseChrome.exe" 0
  ; 开始菜单
  CreateDirectory "$SMPROGRAMS\Muse 账号管理器"
  CreateShortCut "$SMPROGRAMS\Muse 账号管理器\Muse 账号管理器.lnk" "$INSTDIR\MuseChrome.exe" "" "$INSTDIR\MuseChrome.exe" 0
  CreateShortCut "$SMPROGRAMS\Muse 账号管理器\卸载.lnk" "$INSTDIR\Uninstall.exe"

  ; 卸载登记（当前用户，无需管理员）
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseChrome" "DisplayName" "Muse 账号管理器"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseChrome" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseChrome" "Publisher" "xiaoyaodev"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseChrome" "DisplayIcon" "$INSTDIR\MuseChrome.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseChrome" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseChrome" "UninstallString" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Muse 账号管理器.lnk"
  Delete "$SMPROGRAMS\Muse 账号管理器\Muse 账号管理器.lnk"
  Delete "$SMPROGRAMS\Muse 账号管理器\卸载.lnk"
  RMDir "$SMPROGRAMS\Muse 账号管理器"
  Delete "$INSTDIR\MuseChrome.exe"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\Uninstall.exe"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseChrome"
  ; 只删程序文件；MuseChromeData（账号数据）保留，目录非空时 RMDir 自动跳过
  RMDir "$INSTDIR"
SectionEnd
