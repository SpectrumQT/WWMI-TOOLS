<h1 align="center">WWMI Tools</h1>

<h4 align="center">Blender addon for Wuthering Waves Model Importer</h4>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#how-to-use">How To Use</a> • 
  <a href="#assets">Assets</a> •
  <a href="#installation">Installation</a> •
  <a href="#resources">Resources</a> •
  <a href="#license">License</a>
</p>

## For Mod Authors

**WWMI 0.7.0** and **WWMI Tools 0.9.0** updates resolved issues with blur on movement and component glitches (esp. front hair). To fix existing mods:
1. Update **WWMI** to the [latest version](https://github.com/SpectrumQT/WWMI/releases/latest).
2. Update **WWMI Tools** Blender plugin to the [latest version](https://github.com/SpectrumQT/WWMI-TOOLS/releases/latest).
3. Restart Bledner.
4. If you created WWMI mod before Wuthering Waves 1.0 update, follow [Modder Guide](https://github.com/SpectrumQT/WWMI-TOOLS/blob/main/guides/modder_guide.md#how-to-update-wwmi-10-mod-to-11) instead.
5. Export mod to the new folder (or backup and use existing one).
6. Apply desired manual tweaks to the new mod.ini and move textures.

## Known Issues

- Glitch with duplicate modded objects on screen (Merged Skeleton hard limitation, won't be fixed)

## Disclaimers

- **Alpha-2 Warning** — WWMI is in second alpha testing phase. Feature set and formats are more or less set in stone, but you still can expect some issues here and there.
    
## Features  

- **Frame Dump Data Extraction** — Fully automatic objects extraction from WuWa frame dumps
- **Extracted Object Import** —Imports extracted object into Blender as fully editable mesh
- **WWMI Mod Export** — Builds plug-and-play WWMI-compatible mod out of mesh components
- **Bones Merging** — Automatically merges VG lists merging and joins duplicates 
- **Shape Keys Support** — Automatically handles original shape keys and supports custom ones
- **Customizable Export** — Fast mod export engine with per-buffer export support

## How To Use

All fields and actions of the plugin have basic tooltips. Refer to [Modder Guide](https://github.com/SpectrumQT/WWMI-TOOLS/blob/main/guides/modder_guide.md) for more details.

## Assets  

Already dumped and exported models will be located in [WWMI Assets](https://github.com/SpectrumQT/WWMI-Assets) repository.

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
