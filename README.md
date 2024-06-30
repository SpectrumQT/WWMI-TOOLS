<h1 align="center">WWMI Tools</h1>

<h4 align="center">Blender addon for Wuthering Waves Model Importer</h4>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#assets">Assets</a> •
  <a href="#installation">Installation</a> •
  <a href="#how-to-use">How To Use</a> • 
  <a href="#resources">Resources</a> •
  <a href="#license">License</a>
</p>

## For Mod Authors

The 1.1 update has introduced huge changes into the rendering pipeline and 3d assets, to update mods that were made for 1.0 please follow the steps below:
1. Update your [WWMI Tools Blender plugin to 0.8.0](https://github.com/SpectrumQT/WWMI-TOOLS/releases/tag/v0.8.0).
2. Make a new frame dump of modded object (with mod disabled!) and extract it again.
3. Import newly extracted object into Blender (use default Merged Skeleton setting)
4. Make changed Vertex Groups ids in your custom mesh match ones of new import (you may use [Weight Match Blender Addon](https://gamebanana.com/tools/15699) to speed up the process)
5. Export your updated custom model as new mod into new folder (use default Merged Skeleton setting).
6. Check textures one by one and move the ones you've edited from old to new mod folder.

## Features  

- **Frame Dump Data Extraction** — Fully automatic objects extraction from WuWa frame dumps
- **Extracted Object Import** —Imports extracted object into Blender as fully editable mesh
- **WWMI Mod Export** — Builds plug-and-play WWMI-compatible mod out of mesh components
- **Bones Merging** — Automatically merges VG lists merging and joins duplicates 
- **Shape Keys Support** — Automatically handles original shape keys and supports custom ones
- **Customizable Export** — Fast mod export engine with per-buffer export support

## Disclaimers  

- **Alpha-1 Waring** — WWMI is in early alpha testing phase, so you can expect all kinds of issues. Also, please keep in mind that WWMI feature set and formats are not set in stone and may be subject to change.

## Assets  

Already dumped and exported models will be located in [WWMI Assets](https://github.com/SpectrumQT/WWMI-Assets) repository.

## How To Use

All fields and actions of the plugin have basic tooltips. Refer to [Modder Guide](https://github.com/SpectrumQT/WWMI-TOOLS/blob/main/guides/modder_guide.md) for more details.

## Installation

1. Install [Blender 3.6 LTS](https://www.blender.org/download/lts/3-6) (**Blender 4.0+ is NOT supported yet**)
2. Download the [latest release](https://github.com/SpectrumQT/WWMI-Tools/releases/latest) of **WWMI-Tools-X.X.X.zip**
3. Open Blender, go to **[Edit] -> [Preferences]**
4. Press **[Install]** button to open file selection window
5. Locate downloaded **WWMI-Tools-X.X.X.zip** and select it
6. Press **[Install Addon]** button
7. Start typing  **WWMI** to filter in top-right corner
8. Tick checkbox named **Object: WWMI Tools** to enable addon

![wwmi-tools-installation](https://github.com/SpectrumQT/WWMI-TOOLS/blob/main/public-media/Installation.gif)

## Resources

- [WWMI GitHub](https://github.com/SpectrumQT/WWMI) ([Mirror: Gamebanana](https://gamebanana.com/tools/17252))
- [WWMI Tools GitHub (you're here)] ([Mirror: Gamebanana](https://gamebanana.com/tools/17289))
- [WWMI Assets](https://github.com/SpectrumQT/WWMI-Assets)
  
## License

WWMI Tools is licensed under the [GPLv3 License](https://github.com/SpectrumQT/WWMI-Tools/blob/main/LICENSE).
