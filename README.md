# FileTrack

A Home Assistant custom component that monitors folders and exposes their total size as a sensor, along with file count and a `fileList` attribute. It is perfectly designed as a companion for the [Camera Gallery Card](https://github.com/TheScubadiver/camera-gallery-card), but can also be used as a standalone integration.


## Installation

### HACS (Recommended)
1. Add this repository as a custom repository in HACS.
2. Download **FileTrack** via HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration → FileTrack**. The setup completes instantly, no initial configuration needed.

---

## Usage & Configuration

How to make a sensor:

### Method 1 — Camera Gallery Card
Sensors are created directly from the **[Camera Gallery Card](https://github.com/TheScubadiver/camera-gallery-card) Editor** — no YAML, service calls, or manual setup required.

<img width="418" height="380" alt="image" src="https://github.com/user-attachments/assets/e0c5b505-f94b-48f8-b8a3-dbadee3cd41b" />

### Method 2 — YAML
Add sensors directly to your `configuration.yaml` file:

```yaml
sensor:
  - platform: filetrack
    folder: /config/www/snapshots
    filter: '*.jpg'
    name: snapshots
    unique_id: snapshots_jpg
    sort: date
    recursive: True
```

#### YAML Configuration Variables

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| platform | string | **Required** | `filetrack`
| folder | string | **Required** | Folder to scan. Must begin with /config/www/\<your-folder\>
| name | string | **Required** | The entity ID for the sensor
| unique_id | string | **Optional** | Allows an entity to be customized/deleted correctly. `Default: none`
| sort | string | **Optional** | One of 'name', 'date', or 'size'. Determines the sort order for viewing. `Default: date`
| recursive | boolean | **Optional** | True or False; If True, the pattern filter `**` will match any files and zero or more directories, subdirectories and symbolic links to directories. **Note:** Using the `**` pattern in large directory trees will add significant delay. `Default: False`

*Note: Restart Home Assistant after adding YAML entries.*

---

## Removing Sensors

* **UI/Service Sensors:** Go to **Settings → Devices & Services → FileTrack → Configure** to select and remove sensors added via the UI.
* **YAML Sensors:** Remove the relevant entries from your `configuration.yaml` file and restart Home Assistant.
