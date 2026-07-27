"""
build_tools/windows/build_exe.py

Advanced PyInstaller compilation script for Windows SpyEye Payload (.exe).
  - Bundles dependencies into a single standalone executable.
  - Hides console window for stealth background operations.
  - Applies custom icon and resource optimization.
"""

import os
import subprocess
import sys

def verify_agent_source():
    target_script = "agent.py"
    if not os.path.exists(target_script):
        print(f"[!] Warning: '{target_script}' not found in root directory. Creating template stub...")
        with open(target_script, "w") as f:
            f.write("# SpyEye Default Windows Agent Stub\nimport time\n\nwhile True:\n    time.sleep(15)\n")

def compile_windows_exe():
    print("[*] Initializing SpyEye Windows Payload (.exe) build sequence...")
    verify_agent_source()

    # PyInstaller advanced arguments
    pyinstaller_args = [
        "pyinstaller",
        "--noconsole",            # Hide the command prompt window completely
        "--onefile",              # Bundle everything into a single standalone .exe file
        "--clean",                # Clear PyInstaller cache prior to build
        "--uac-admin",            # Request appropriate execution level if needed
        "--name=SpyEye_Agent",    # Final output executable filename
        "agent.py"
    ]

    print(f"[*] Executing command: {' '.join(pyinstaller_args)}")
    
    try:
        result = subprocess.run(pyinstaller_args, check=True)
        if result.returncode == 0:
            print("\n[+] SUCCESS: Windows payload compiled successfully!")
            print("[+] Output binary is located in the 'dist/' directory as 'SpyEye_Agent.exe'.")
        else:
            print("\n[!] ERROR: Compilation finished with non-zero exit code.")
    except subprocess.CalledProcessError as e:
        print(f"\n[!] PyInstaller Execution Failed: {e}")
    except FileNotFoundError:
        print("\n[!] ERROR: 'pyinstaller' is not installed or not recognized in your PATH.")

if __name__ == "__main__":
    compile_windows_exe()