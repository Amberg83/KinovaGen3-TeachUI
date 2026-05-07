import os
import urllib.request
import urllib.error

# Directory to save assets
ASSETS_DIR = os.path.join("view", "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# Icons to download
# Map of local_filename: (icon_name, color, family)
ICONS_MAP = {
    "load.png": ("folder_open", "white", "baseline"),
    "save.png": ("save", "white", "baseline"),
    "copy.png": ("content_copy", "white", "baseline"),
    "paste.png": ("content_paste", "white", "baseline"),
    "duplicate.png": ("library_add", "white", "baseline"),
    "play.png": ("play_arrow", "white", "baseline"),
    "play_selection.png": ("play_circle_outline", "white", "baseline"),
    "pause.png": ("pause", "white", "baseline"),
    "stop.png": ("stop", "white", "baseline"),
    "bolt.png": ("flash_on", "white", "baseline"),
    "disconnected.png": ("power_off", "white", "baseline"),
    "connected.png": ("power", "white", "baseline"),
    "participant.png": ("person", "white", "baseline"),
    "task.png": ("assignment", "white", "baseline"),
    "add_waypoint.png": ("add", "white", "baseline"),
    "reconnect.png": ("refresh", "white", "baseline"),
    "delete.png": ("delete", "white", "baseline"),
    "clear.png": ("delete_sweep", "white", "baseline"),
    "wrench.png": ("build", "white", "baseline"),
    "undo.png": ("undo", "white", "baseline"),
    "redo.png": ("redo", "white", "baseline"),
    "arrow_up.png": ("arrow_upward", "white", "baseline"),
    "arrow_down.png": ("arrow_downward", "white", "baseline"),
    "fault.png": ("report_problem", "white", "baseline"),
    "healthy.png": ("check_circle", "white", "baseline"),
    "lightbulb.png": ("lightbulb", "white", "baseline"),
    "estop.png": ("report", "white", "baseline")
}

print("Starting asset download from material-icons-png library...")
success_count = 0

for filename, (name, color, family) in ICONS_MAP.items():
    # URL structure: https://material-icons.github.io/material-icons-png/png/{color}/{name}/{family}.png
    url = f"https://material-icons.github.io/material-icons-png/png/{color}/{name}/{family}.png"
    target_path = os.path.join(ASSETS_DIR, filename)
    
    print(f"Downloading {name} ({color}) -> {target_path}...")
    try:
        # Material Icons PNG uses standard user-agent otherwise GitHub Pages might block
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
            out_file.write(response.read())
        print(f"Successfully downloaded {filename}")
        success_count += 1
    except urllib.error.HTTPError as e:
        print(f"HTTP Error for {name}: {e.code} {e.reason} (URL: {url})")
    except Exception as e:
        print(f"Failed to download {name}: {e}")

print(f"\nDownload completed. Successfully downloaded {success_count}/{len(ICONS_MAP)} assets.")
