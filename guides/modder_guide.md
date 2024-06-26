<h4>WWMI Tools Modder Guide</h4>

<h4>Frame Dump Objects Export</h4>
1. Start the game with **WWMI Loader.exe**
2. (Optional) Lower game resolution to reduce Frame Dump folder size
3. Disable any active mods for desired object
    * Make desired object dissapear from screen (i.e. switch to another character)
    * Move all active mods for the object outside of Mods folder
    * Press [F10] to reload WWMI
4. Make desired object visible on screen (i.e. open character screen)
5. Press [0] button on your **NumPad** to enable **Hunting Mod**
6. Press [F8] to create a Frame Dump
7. Dump **FrameAnalysis-DATETIME** will be located in the same folder with **WWMI Loader.exe** 

<h4>Frame Dump Objects Extraction</h4>
1. Go to **Sidebar > Tool > WWMI Tools**
2. Select Mode: **Extract Objects From Dump**
3. Configure **Frame Dump** field: input path to dump data folder **FrameAnalysis-DATETIME**
4. Configure **Output Folder** filed: input path to folder where you want to store extracted objects 
5. Press [Extract Objects From Dump] button
Extracted object will be placed in separate folders named after VB0 hash parsed from the shader calls. Feel free to fiddle with Texture Filtering options, they indented to filter out garbage textures set by the game but aren't actually used by relevant shaders.

<h4>Extracted Object Import</h4>
1. Go to **Sidebar > Tool > WWMI Tools**
2. Select Mode: **Import Object**
3. Configure **Object Sources** field: input path to hash-named folder containing object data
4. Press [Import Object] button
Imported object components will appear as hash-named collection of Blender objects. 
 
<h4>Extracted Object Edititng</h4>
1. Component Naming:
    * Component ID determines to which set of shaders each object will go in exported mod.
    * Any component object name is valid while it contains 'component' keyword followed by ID (i.e. 'Hat CoMpONEnT- 2 test' is a valid name).
2. Component Structure:
    * There can be any number of Blender objects with same Component ID inside collection. They will be automatically merged on mod export.
    * Every object will have its own drawindexed call inside a call stack with its Component ID. It allows to easily edit mod.ini in a way to make some parts (i.e. hat) dissapear based on if-else conditions.
3. Weights:
    * WWMI dynamically merges bones from all components into single skeleton, and WWMI Tools additionally remap duplicate bones across components into unique VGs during frame data extraction. It enables similar modding experience to GI/HI/HSR modding.
4. Modifiers:
    * It's a bit tricky to apply modifiers to object with Shape Keys. Use [Apply Modifiers For Object With Shape Keys] tool from **Toolbox** to do so. Credits to przemir for [his work](https://github.com/przemir/ApplyModifierForObjectWithShapeKeys).
    * You can also use 'Apply All Modifiers' checkbox in mod export option to autoamtically apply exisitng modifiers to temp copies during temp merged object creation on mod export.
5. Shape Keys:
    * Some components (like head and shoulders) have shape keys attached.
    * Shape keys are required for procedural animations (i.e. face expressions) to function in exported mod.
    * Custom Shape Keys are supported, just find last used Shape Key Id across component objects, add 1 to it and name you custom shapekey with 'custom' or 'deform' tag ('My defOrm 86 Bow' or 'CUSTom_86 Some KEY' are valid names). Refer to Shape Keys section of WWMI manual for how to set shape key values in mod ini.
6. UV Maps:
    * Each object has 2 UV maps controlling texture application (TEXCOORD.xy for outside, TEXCOORD1.xy for inside).
    * There's also one extra UV map (TEXCOORD2.xy) with frontal projection, potentially used for shading purposes. Documentation TBA.
7. Vertex Colors:
    * There are 2 color attributes (COLOR and COLOR1). Documentation TBA.

<h4>Basic WWMI Mod Export</h4>
1. Open hash-named folder containing extracted object data and remove any unwanted or garbage textures. It'll reduce resulting mod size and mod.ini clutter.
2. Go to **Sidebar > Tool > WWMI Tools**
3. Select Mode: **Export Mod**
4. Configure **Components** field: Select collection with objects for desired components. Skipping arbitrary components is supported, just remove relevant objects from collection. They won't appear in the game.
5. Configure **Object Sources** field: input path to hash-named folder containing object data.
6. Configure **Mod Folder** field: input path where you want the exported mod data to be located.
7. Configure optional mod info fields.
8. Press Export Mod

<h4>Advanced WWMI Mod Export Options</h4>
1. Partial Export:
    * Allows to export selected buffers to lower export time. Comes especially handy for weight painting.
    * Prevents export of any other data (so mod.ini and textures handling will be skipped).
    * Warning! Any changes to vertex count require full export and mod.ini update.
2. Apply All Modifiers:
    * Automatically applies all existing modifiers to temporary copies of objects created during export.
    * Shapekeyed objects are also supported.
3. Copy Textures:
    * Copy textures from **Object Sources** folder to mod folder. Automatically skips already existing textures.
4. Comment Ini Code:
    * Adds comments to the code in mod.ini. May be useful if you want to get idea about what's going on.
5. Remove Temp Object:
    * Uncheck to keep temporary object built from copies of all objects of all components used for export. Primary usecase is WWMI Tools debugging.
