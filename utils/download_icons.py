import os
import urllib.request
import urllib.error

# Directory to save assets
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "view", "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# Map of local_filename: google_icon_name
ICONS_MAP = {
    "load.svg": "folder_open",
    "save.svg": "save",
    "copy.svg": "content_copy",
    "paste.svg": "content_paste",
    "duplicate.svg": "library_add",
    "play.svg": "play_arrow",
    "play_selection.svg": "play_circle_outline",  # Might fall back to play_circle
    "pause.svg": "pause",
    "stop.svg": "stop",
    "bolt.svg": "flash_on",
    "disconnected.svg": "power_off",
    "connected.svg": "power",
    "participant.svg": "person",
    "task.svg": "assignment",
    "add_waypoint.svg": "add",
    "reconnect.svg": "refresh",
    "delete.svg": "delete",
    "clear.svg": "delete_sweep",
    "wrench.svg": "build",
    "undo.svg": "undo",
    "redo.svg": "redo",
    "arrow_up.svg": "arrow_upward",
    "arrow_down.svg": "arrow_downward",
    "fault.svg": "report_problem",
    "healthy.svg": "check_circle",
    "lightbulb.svg": "lightbulb",
    "estop.svg": "report",
    "speed.svg": "speed"
}

FILLED_ICONS = {"play.svg", "pause.svg", "stop.svg", "estop.svg"}

print("Starting SVG asset download from Google Fonts / unpkg (Material Symbols Outlined) CDN...")
success_count = 0

for filename, name in ICONS_MAP.items():
    target_path = os.path.join(ASSETS_DIR, filename)
    downloaded = False
    
    # List of candidate names to try in case of CDN naming differences
    candidates = [name]
    if "_outline" in name:
        candidates.append(name.replace("_outline", ""))
    if name == "power_off":
        candidates.append("power_settings_new") # potential fallback
        
    for candidate in candidates:
        if filename in FILLED_ICONS:
            # Try to fetch the filled version from unpkg
            url = f"https://unpkg.com/@material-symbols/svg-400/outlined/{candidate}-fill.svg"
            print(f"Trying to download filled {candidate} -> {url}...")
        else:
            url = f"https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/{candidate}/default/24px.svg"
            print(f"Trying to download {candidate} -> {url}...")
            
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req) as response:
                svg_data = response.read()
            with open(target_path, 'wb') as out_file:
                out_file.write(svg_data)
            print(f"Successfully downloaded {filename} (using '{candidate}')")
            success_count += 1
            downloaded = True
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # If filled version fails, try the standard outlined fallback from gstatic
                if filename in FILLED_ICONS:
                    fallback_url = f"https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/{candidate}/default/24px.svg"
                    print(f"Filled version 404'd. Trying fallback outline {candidate} -> {fallback_url}...")
                    try:
                        req_fb = urllib.request.Request(
                            fallback_url, 
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        )
                        with urllib.request.urlopen(req_fb) as response_fb:
                            svg_data = response_fb.read()
                        with open(target_path, 'wb') as out_file:
                            out_file.write(svg_data)
                        print(f"Successfully downloaded {filename} (using outline '{candidate}')")
                        success_count += 1
                        downloaded = True
                        break
                    except Exception as fe:
                        print(f"Fallback outline failed for {candidate}: {fe}")
                continue
            else:
                print(f"HTTP Error {e.code} {e.reason} for {candidate}")
        except Exception as e:
            print(f"Failed to download {candidate}: {e}")
            
    if not downloaded:
        print(f"ERROR: Could not download SVG for icon '{name}'")

print(f"\nDownload completed. Successfully downloaded {success_count}/{len(ICONS_MAP)} assets.")
# Delete old PNG files to clean up view/assets
print("Cleaning up old PNG files in view/assets...")
png_deleted = 0
for f in os.listdir(ASSETS_DIR):
    if f.endswith(".png") and f.replace(".png", ".svg") in ICONS_MAP:
        try:
            os.remove(os.path.join(ASSETS_DIR, f))
            png_deleted += 1
        except Exception as e:
            print(f"Could not remove old PNG {f}: {e}")
print(f"Removed {png_deleted} old PNG file(s).")
