# FileTrack

A Home Assistant custom component that monitors folders and exposes a `fileList` sensor attribute — designed as a companion for the [Camera Gallery Card](https://github.com/TheScubadiver/camera-gallery-card).

## Installation

1. Add this repository as a custom repository in HACS
2. Download **FileTrack** via HACS
3. Restart Home Assistant — FileTrack activates automatically

## Usage

Sensors are created directly from the **Camera Gallery Card editor** — no YAML, no manual setup.

## Sensor attributes

| Attribute | Description |
|---|---|
| `fileList` | Sorted list of file paths in the monitored folder |
| `number_of_files` | Total number of files |
| `path` | Monitored folder path |
| `filter` | Active file filter (default: `*`) |
| `sort` | Sort method: `date`, `name`, or `size` |
