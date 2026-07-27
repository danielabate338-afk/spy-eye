"""
build_tools/android/build_apk.py

Automated Build Script for SpyEye Android Package.
"""

import os
import subprocess
import sys

def compile_apk():
    print("[*] Initializing build environment pipeline...")
    
    # Check where the spec file is located and use the correct path
    if os.path.exists("SpyEye_Agent.spec"):
        spec_path = "SpyEye_Agent.spec"
    elif os.path.exists("../../SpyEye_Agent.spec"):
        spec_path = "../../SpyEye_Agent.spec"
    else:
        print("[!] ERROR: 'SpyEye_Agent.spec' file not found anywhere.")
        return

    print(f"[*] Using spec file at: {spec_path}")
    print("[*] Building package using PyInstaller...")
    
    build_cmd = ["pyinstaller", "--clean", spec_path]
    
    try:
        process = subprocess.Popen(build_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='')
        process.wait()
        
        if process.returncode == 0:
            print("\n[+] SUCCESS: Package compiled successfully!")
            print("[+] Check the 'dist/' directory for the generated output package.")
        else:
            print("\n[!] ERROR: Compilation encountered an issue. Check logs above.")
    except FileNotFoundError:
        print("[!] ERROR: PyInstaller tool is not installed or not available in PATH.")

if __name__ == "__main__":
    compile_apk()