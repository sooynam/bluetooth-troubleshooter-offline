#!/usr/bin/env python3
import json
import subprocess
import sys
import webbrowser
from pathlib import Path

# Paths
VENDORS_FILE = Path("vendors.json")
KNOWN_DEVICES_FILE = Path("known_devices.json")
PROBLEMS_FILE = Path("problems.json")

def load_json(path, fallback):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[warn] failed to load {path}: {e}")
    return fallback

# Embedded fallback data
EMBEDDED_VENDORS = {
    "00:1A:7D": "Apple, Inc.",
    "00:12:EF": "Logitech",
    "58:7E:5A": "Xiaomi / Redmi",
    "A4:5E:60": "Samsung",
    "FC:FB:FB": "JBL",
    "8C:64:A2": "Generic Vendor"
}
EMBEDDED_KNOWN = {
    "Xiaomi": [
        {"model": "Redmi Buds 3", "type": "earphone"},
        {"model": "Redmi Sonic", "type": "headphone"}
    ],
    "Logitech": [
        {"model": "M590", "type": "mouse"},
        {"model": "MX Master 3", "type": "mouse"}
    ],
    "JBL": [
        {"model": "Tune 660NC", "type": "headphone"}
    ]
}
EMBEDDED_PROBS = {
    "no_adapter": {
        "description": "No bluetooth adapter found.",
        "quick_diagnostics": ["lsusb", "dmesg | grep -i bluetooth"],
        "remediation_steps": [
            {"explain":"Check lsusb/lspci","commands":["lsusb","lspci -nn | grep -i bluetooth || true"]},
            {"explain":"Unblock if blocked","commands":["sudo rfkill unblock bluetooth"]}
        ],
        "notes":"Ensure firmware is present."
    },
    "connect_failed_audio": {
        "description": "Audio device pairs but no audio / cannot connect A2DP.",
        "quick_diagnostics": ["pactl list cards short", "pactl list sinks short", "sudo bluetoothctl info <MAC>"],
        "remediation_steps": [
            {"explain": "Install audio Bluetooth modules",
             "commands": ["sudo apt install -y pipewire libspa-0.2-bluetooth || sudo apt install -y pulseaudio pulseaudio-module-bluetooth"]},
            {"explain": "Restart services", "commands": ["sudo systemctl restart bluetooth", "systemctl --user restart pipewire pipewire-pulse || systemctl --user restart pulseaudio || true"]}
        ],
        "notes": "Codec support depends on installed modules."
    }
}

def guess_vendor(mac, vendors):
    if not mac:
        return None
    prefix = ":".join(mac.upper().split(":")[:3])
    return vendors.get(prefix)

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def show_banner_option():
    print("Banner options:")
    print("1) ASCII banner")
    print("2) ANSI color banner")
    print("3) Open HTML preview")
    c = input("Choose (1/2/3) or skip: ").strip()
    if c == "1":
        subprocess.run(["python3", "banners/ascii_banner.py"])
    elif c == "2":
        subprocess.run(["bash", "banners/ansi_banner.sh"])
    elif c == "3":
        path = Path("banners/index.html").absolute().as_uri()
        webbrowser.open(path)

def format_plan(key, probs, mac=None, dev_type=None, vendor=None, model=None, vendor_map=None):
    if key not in probs:
        # try partial match
        for k, v in probs.items():
            if key.lower() in k.lower() or key.lower() in v.get("description","").lower():
                key = k
                break
        else:
            return f"No policy found for '{key}'. Available: {', '.join(probs.keys())}"
    entry = probs[key]
    out = []
    out.append(f"Problem: {entry.get('description')}\n")
    out.append("Quick diagnostics:")
    for c in entry.get("quick_diagnostics", []):
        out.append(f"  $ {c}")
    out.append("\nRemediation steps:")
    for idx, st in enumerate(entry.get("remediation_steps", []), 1):
        out.append(f"\nStep {idx}: {st.get('explain')}")
        for c in st.get("commands", []):
            cmdc = c.replace("<MAC>", mac or "<MAC>").replace("<vendor>", vendor or "<vendor>").replace("<model>", model or "<model>")
            out.append(f"  $ {cmdc}")
    if entry.get("notes"):
        out.append(f"\nNotes: {entry.get('notes')}")
    if mac and vendor_map:
        v = guess_vendor(mac, vendor_map)
        out.append(f"\nVendor guess: {v or 'Unknown'}")
    return "\n".join(out)

def main():
    vendors = load_json(VENDORS_FILE, EMBEDDED_VENDORS)
    known = load_json(KNOWN_DEVICES_FILE, EMBEDDED_KNOWN)
    probs = load_json(PROBLEMS_FILE, EMBEDDED_PROBS)

    print("=== Bluetooth Troubleshooter AI ===")
    show_banner_option()

    dtype = input("Device type (headphone/mouse/earphone): ").strip()
    vname = input("Vendor name: ").strip()
    mname = input("Model name: ").strip()
    mac = input("MAC (AA:BB:CC:DD:EE:FF): ").strip()

    print("\nDetected vendor via MAC:", guess_vendor(mac, vendors))

    print("\nAvailable problem policies:")
    for i, k in enumerate(probs.keys(), start=1):
        print(f"{i}. {k} — {probs[k].get('description')}")

    choice = input("Enter problem key or number: ").strip()
    try:
        idx = int(choice) - 1
        key = list(probs.keys())[idx]
    except:
        key = choice

    plan = format_plan(key, probs, mac=mac, dev_type=dtype, vendor=vname, model=mname, vendor_map=vendors)
    print("\n" + "="*40)
    print(plan)
    print("="*40)

    # Ask for fixing
    do = input("Execute commands automatically? (y/n): ").strip().lower()
    if do == 'y':
        if key in probs:
            for st in probs[key].get("remediation_steps", []):
                for cmd in st.get("commands", []):
                    cexec = cmd.replace("<MAC>", mac or "").replace("<vendor>", vname).replace("<model>", mname)
                    print(f"Running: {cexec}")
                    out = run_command(cexec)
                    print(out)
        else:
            print("No commands found to run.")

if __name__ == "__main__":
    main()

