#!/usr/bin/env python3
"""
设置脚本：创建 macOS launchd plist，实现开机自动启动监控
"""

import os
import subprocess
import sys

PLIST_LABEL = "com.birdwatcher.monitor"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(SCRIPT_DIR, "main.py")
LOG_PATH = os.path.expanduser("~/Library/Logs/BirdWatcher.log")
PYTHON_PATH = sys.executable


def create_plist():
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON_PATH}</string>
        <string>{MAIN_SCRIPT}</string>
        <string>--watch</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>{LOG_PATH}</string>

    <key>StandardErrorPath</key>
    <string>{LOG_PATH}</string>

    <key>WorkingDirectory</key>
    <string>{SCRIPT_DIR}</string>
</dict>
</plist>
"""
    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
    with open(PLIST_PATH, "w") as f:
        f.write(plist_content)
    print(f"✅ 已创建启动项: {PLIST_PATH}")


def load_plist():
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
    result = subprocess.run(["launchctl", "load", PLIST_PATH], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ 观鸟助手已加载，将在后台持续监控内存卡")
    else:
        print(f"⚠️  加载失败: {result.stderr}")


def unload_plist():
    result = subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ 已停止观鸟助手后台监控")
    else:
        print(f"⚠️  停止失败: {result.stderr}")
    if os.path.exists(PLIST_PATH):
        os.remove(PLIST_PATH)
        print(f"   已删除启动项文件: {PLIST_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="观鸟助手 - 开机自启设置")
    parser.add_argument("action", choices=["install", "uninstall"], help="install=开机自启, uninstall=取消自启")
    args = parser.parse_args()

    if args.action == "install":
        create_plist()
        load_plist()
        print(f"\n📋 日志文件: {LOG_PATH}")
        print("   运行后台守护进程已启动，插入内存卡即可自动处理！")
    else:
        unload_plist()
