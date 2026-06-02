import os
import urllib.request
import urllib.error
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUNDS_ROOT = os.path.join(BASE_DIR, "sounds")
APPLE_DIR = os.path.join(SOUNDS_ROOT, "apple")

os.makedirs(APPLE_DIR, exist_ok=True)

# Apple iOS Sounds (MP3 format from extratone repository)
APPLE_MAP = {
    "photoShutter.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/photoShutter.mp3",
    "connect_power.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/connect_power.mp3",
    "low_power.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/low_power.mp3",
    "begin_record.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/begin_record.mp3",
    "end_record.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/end_record.mp3",
    "lock.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/lock.mp3",
    "SentMessage.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/SentMessage.mp3",
    "ReceivedMessage.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/ReceivedMessage.mp3",
    "payment_success.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/payment_success.mp3",
    "3rdParty_Failure_Haptic.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/3rdParty_Failure_Haptic.mp3",
    "3rdParty_Success_Haptic.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/3rdParty_Success_Haptic.mp3",
    "3rd_party_critical.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/3rd_party_critical.mp3",
    # Interaction Sounds
    "Tock.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/Tock.mp3",
    "key_press_click.mp3": "https://raw.githubusercontent.com/extratone/iOSSystemSounds/main/mp3/key_press_click.mp3"
}

def download_file(url, target_path):
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        content = response.read()
        with open(target_path, 'wb') as f:
            f.write(content)

print("=== Downloading Official Apple iOS Sound Assets ===")

# Download Apple Sounds
for filename, url in APPLE_MAP.items():
    target_path = os.path.join(APPLE_DIR, filename)
    print(f"Downloading {filename}...")
    try:
        download_file(url, target_path)
        print(f"-> Saved to {target_path} ({os.path.getsize(target_path)} bytes)")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")

# Clean unrecognized files inside 'sounds/apple/'
for entry in os.listdir(APPLE_DIR):
    if entry not in APPLE_MAP:
        full_path = os.path.join(APPLE_DIR, entry)
        if os.path.isfile(full_path):
            print(f"Removing unused Apple asset: {entry}")
            os.remove(full_path)

print("\n=== Sound Download and Maintenance Completed Successfully! ===")
