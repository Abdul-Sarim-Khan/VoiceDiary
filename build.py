#!/usr/bin/env python3
"""Build and Setup Generator for VoiceDiary.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.

Usage:
    python build.py --setup      # Build standalone exe + themed Windows installer + portable package
    python build.py --installer  # Build exe + installer
    python build.py --exe        # Build executable only
    python build.py --proto      # Compile proto files only
    python build.py --clean      # Clean build artifacts
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src')
DIST = os.path.join(ROOT, 'dist')
BUILD = os.path.join(ROOT, 'build')
SETUP = os.path.join(ROOT, 'setup')
BRANDING = os.path.join(ROOT, 'Branding')


def generate_wizard_assets():
    """Generate modern, professional themed bitmap assets for Inno Setup wizard."""
    try:
        from PIL import Image, ImageDraw

        logo_path = os.path.join(BRANDING, 'Voice Diary Logo.png')
        if not os.path.exists(logo_path):
            return

        logo = Image.open(logo_path).convert('RGBA')

        # 1. Wizard Large Splash Banner (164x314 px) - Obsidian to Indigo Gradient
        w_large, h_large = 164, 314
        splash = Image.new('RGB', (w_large, h_large), '#080C14')
        draw = ImageDraw.Draw(splash)
        for y in range(h_large):
            ratio = y / h_large
            r = int(8 * (1 - ratio) + 30 * ratio)
            g = int(12 * (1 - ratio) + 27 * ratio)
            b = int(20 * (1 - ratio) + 75 * ratio)
            draw.line([(0, y), (w_large, y)], fill=(r, g, b))

        logo_resized = logo.resize((120, 120), Image.Resampling.LANCZOS)
        splash.paste(logo_resized, (22, 40), logo_resized)
        splash.save(os.path.join(BRANDING, 'wizard_large.bmp'), 'BMP')

        # 2. Wizard Small Header Banner (55x58 px)
        w_small, h_small = 55, 58
        small = Image.new('RGB', (w_small, h_small), '#080C14')
        logo_small = logo.resize((48, 48), Image.Resampling.LANCZOS)
        small.paste(logo_small, (4, 5), logo_small)
        small.save(os.path.join(BRANDING, 'wizard_small.bmp'), 'BMP')

        print('Branded wizard installer bitmaps generated successfully.')
    except Exception as e:
        print(f'Note: Could not generate wizard bitmaps: {e}')


def compile_proto():
    """Compile .proto files to Python bindings."""
    proto_dir = os.path.join(SRC, 'proto')
    proto_file = os.path.join(proto_dir, 'voicediary.proto')

    if not os.path.exists(proto_file):
        print(f'ERROR: Proto file not found: {proto_file}')
        return False

    print('Compiling protobuf definitions...')
    try:
        subprocess.run(
            [sys.executable, '-m', 'grpc_tools.protoc',
             f'-I{proto_dir}',
             f'--python_out={proto_dir}',
             proto_file],
            check=True,
            cwd=ROOT,
        )
        print('Proto compiled successfully.')
        return True
    except Exception as e:
        print(f'Proto compilation failed: {e}')
        return False


def build_exe():
    """Build the executable using PyInstaller."""
    spec_file = os.path.join(ROOT, 'voicediary.spec')

    if not os.path.exists(spec_file):
        print(f'ERROR: Spec file not found: {spec_file}')
        return False

    # 1. Compile protos first
    compile_proto()

    # 2. Generate wizard bitmaps
    generate_wizard_assets()

    print('Building executable with PyInstaller...')
    try:
        subprocess.run(
            [sys.executable, '-m', 'PyInstaller', spec_file, '--noconfirm'],
            check=True,
            cwd=ROOT,
        )

        # 3. Sync static UI assets to dist
        src_static = os.path.join(SRC, 'ui', 'static')
        dst_static = os.path.join(DIST, 'VoiceDiary', '_internal', 'ui', 'static')
        if os.path.exists(dst_static):
            for item in os.listdir(src_static):
                s = os.path.join(src_static, item)
                d = os.path.join(dst_static, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

        print(f'Executable built successfully in {os.path.join(DIST, "VoiceDiary")}/')
        return True
    except subprocess.CalledProcessError as e:
        print(f'Build failed: {e}')
        return False


def build_installer():
    """Build the Windows installer using Inno Setup and create standalone setup package."""
    installer_dir = os.path.join(ROOT, 'installer')
    os.makedirs(installer_dir, exist_ok=True)
    iss_file = os.path.join(installer_dir, 'voicediary.iss')
    os.makedirs(SETUP, exist_ok=True)

    # Auto-generate Inno Setup script if missing
    if not os.path.exists(iss_file):
        iss_content = r"""; Inno Setup Script for VoiceDiary
; VoiceDiary © Abdul Sarim Khan. All Rights Reserved.

#define MyAppName "VoiceDiary"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Abdul Sarim Khan"
#define MyAppURL "https://github.com/Abdul-Sarim-Khan/VoiceDiary"
#define MyAppExeName "VoiceDiary.exe"
#define MyAppId "{{D37E8C94-4F91-44B2-9A8C-6893B5BA9920}}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=VoiceDiary (c) Abdul Sarim Khan. All Rights Reserved.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\setup
OutputBaseFilename=VoiceDiary_Setup_v{#MyAppVersion}
SetupIconFile=..\Branding\Voice Diary Icon.ico
UninstallDisplayIcon={app}\_internal\ui\static\assets\icon.ico
WizardStyle=modern
WizardImageFile=..\Branding\wizard_large.bmp
WizardSmallImageFile=..\Branding\wizard_small.bmp
Compression=lzma2/ultra64
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize=max
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableDirPage=no
DisableProgramGroupPage=no
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Create a Quick Launch shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\VoiceDiary\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "data\*.pb,data\sessions\*,data\logs\*,data\cache\*,*.log,*.tmp"
Source: "..\Models\*"; DestDir: "{app}\Models"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\ui\static\assets\icon.ico"; AppUserModelID: "abdulsarimkhan.voicediary.app.1.2.0"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{app}\_internal\ui\static\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\_internal\ui\static\assets\icon.ico"; AppUserModelID: "abdulsarimkhan.voicediary.app.1.2.0"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{userappdata}\VoiceDiary"
Type: filesandordirs; Name: "{localappdata}\VoiceDiary"
Type: filesandordirs; Name: "{group}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDir: String;
  UserDataDir: String;
  LocalDataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    UserDataDir := ExpandConstant('{userappdata}\VoiceDiary');
    LocalDataDir := ExpandConstant('{localappdata}\VoiceDiary');

    if DirExists(AppDir) then DelTree(AppDir, True, True, True);
    if DirExists(UserDataDir) then DelTree(UserDataDir, True, True, True);
    if DirExists(LocalDataDir) then DelTree(LocalDataDir, True, True, True);
  end;
end;
"""
        with open(iss_file, 'w', encoding='utf-8') as f:
            f.write(iss_content)

    # Clean any local developer database/logs from dist before packaging
    dist_data = os.path.join(DIST, 'VoiceDiary', 'data')
    if os.path.exists(dist_data):
        for item in os.listdir(dist_data):
            p = os.path.join(dist_data, item)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif item.endswith('.pb') or item.endswith('.log') or item.endswith('.tmp'):
                os.remove(p)

    # 1. Find Inno Setup compiler
    iscc_paths = [
        shutil.which('iscc'),
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe'),
        os.path.expandvars(r'%USERPROFILE%\AppData\Local\Programs\Inno Setup 6\ISCC.exe'),
        r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        r'C:\Program Files\Inno Setup 6\ISCC.exe',
    ]
    iscc = None
    for p in iscc_paths:
        if p and os.path.exists(p):
            iscc = p
            break

    installer_ok = False
    if iscc:
        print(f'Building Inno Setup Installer using {iscc}...')
        try:
            subprocess.run([iscc, iss_file], check=True)
            print('Windows Installer created successfully in setup/ directory!')
            installer_ok = True
        except subprocess.CalledProcessError as e:
            print(f'Inno Setup compilation failed: {e}')
    else:
        print('Inno Setup compiler not found. Creating portable standalone setup package...')

    # 2. Build Standalone Portable Setup Folder (Machine-Independent, Plug & Play)
    standalone_dir = os.path.join(SETUP, 'VoiceDiary_Standalone')
    print(f'Packaging machine-independent standalone setup in {standalone_dir}...')
    if os.path.exists(standalone_dir):
        shutil.rmtree(standalone_dir, ignore_errors=True)

    # Copy built app
    app_dist = os.path.join(DIST, 'VoiceDiary')
    if os.path.exists(app_dist):
        shutil.copytree(app_dist, standalone_dir)

    # Copy offline Models
    models_src = os.path.join(ROOT, 'Models')
    models_dst = os.path.join(standalone_dir, 'Models')
    if os.path.exists(models_src) and not os.path.exists(models_dst):
        print('Bundling offline AI Models into standalone package...')
        shutil.copytree(models_src, models_dst)

    # Create 1-click Desktop and Start Menu shortcut installer script
    shortcut_vbs = os.path.join(standalone_dir, 'Create_Shortcut.vbs')
    vbs_code = '''Set oWS = WScript.CreateObject("WScript.Shell")
appDir = oWS.CurrentDirectory
exePath = appDir & "\\VoiceDiary.exe"
iconPath = appDir & "\\_internal\\ui\\static\\assets\\icon.ico"

' Desktop Shortcut
desktopPath = oWS.SpecialFolders("Desktop") & "\\VoiceDiary.lnk"
Set oLink = oWS.CreateShortcut(desktopPath)
oLink.TargetPath = exePath
oLink.WorkingDirectory = appDir
oLink.Description = "VoiceDiary - Bilingual Lecture & Diarization Engine"
oLink.IconLocation = iconPath & ", 0"
oLink.Save

' Start Menu Shortcut
programsPath = oWS.SpecialFolders("Programs") & "\\VoiceDiary.lnk"
Set oProgLink = oWS.CreateShortcut(programsPath)
oProgLink.TargetPath = exePath
oProgLink.WorkingDirectory = appDir
oProgLink.Description = "VoiceDiary - Bilingual Lecture & Diarization Engine"
oProgLink.IconLocation = iconPath & ", 0"
oProgLink.Save

MsgBox "VoiceDiary desktop and Start Menu shortcuts created successfully!", 64, "VoiceDiary Installation"
'''
    with open(shortcut_vbs, 'w', encoding='utf-8') as f:
        f.write(vbs_code)

    bat_file = os.path.join(standalone_dir, 'Install_Shortcuts.bat')
    bat_code = '@echo off\r\nwscript.exe "%~dp0Create_Shortcut.vbs"\r\n'
    with open(bat_file, 'w', encoding='utf-8') as f:
        f.write(bat_code)

    print('Standalone machine-independent package created successfully!')

    # Print clean summary of setup/ contents
    print('\n=============================================================')
    print('🎉 ALL SETUP & INSTALLER DELIVERABLES CREATED IN /setup :')
    if os.path.exists(SETUP):
        for item in sorted(os.listdir(SETUP)):
            item_p = os.path.join(SETUP, item)
            if os.path.isdir(item_p):
                print(f'   📁 setup/{item}/ (Portable Standalone Package)')
            else:
                size_mb = os.path.getsize(item_p) / (1024 * 1024)
                print(f'   💾 setup/{item} ({size_mb:.1f} MB Windows Setup Wizard)')
    print('=============================================================\n')
    return True


def clean():
    """Remove build artifacts."""
    dirs_to_clean = [BUILD]
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
            print(f'Removed: {d}')

    # Clean __pycache__
    for root, dirs, files in os.walk(ROOT):
        for d in dirs:
            if d == '__pycache__':
                path = os.path.join(root, d)
                shutil.rmtree(path, ignore_errors=True)
                print(f'Removed: {path}')

    print('Clean complete.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='VoiceDiary Build & Setup Script')
    parser.add_argument('--proto', action='store_true', help='Compile proto files only')
    parser.add_argument('--exe', action='store_true', help='Build executable only')
    parser.add_argument('--installer', action='store_true', help='Build exe + installer')
    parser.add_argument('--setup', action='store_true', help='Full build: exe + installer + standalone package')
    parser.add_argument('--clean', action='store_true', help='Clean build artifacts')
    args = parser.parse_args()

    if args.clean:
        clean()
    elif args.proto:
        compile_proto()
    elif args.exe:
        build_exe()
    elif args.installer or args.setup:
        if build_exe():
            build_installer()
    else:
        # Default: full setup build
        if build_exe():
            build_installer()
