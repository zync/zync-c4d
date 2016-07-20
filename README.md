# Zync Plugin for Cinema 4D

Tested with Cinema 4D R17.

## zync-python

This plugin depends on zync-python, the Zync Python API.

Before trying to install zync-c4d, make sure to [download zync-python](https://github.com/zync/zync-python) and follow the setup instructions there.

## Clone the Repository

Clone this repository to the plugin directory of your Cinema 4D installation. For Mac OS it is `~/Library/Preferences/MAXON/CINEMA 4D R17_<some number>/plugins`, for Windows it is yet to be discovered.

## Config File

Contained in this folder you'll find a file called ```config_c4d.py.example```. Make a copy of this file in the same directory, and rename it ```config_c4d.py```.

Edit ```config_c4d.py``` in a Text Editor. It defines one config variable - `API_DIR` - the full path to your zync-python directory.

Set `API_DIR` to point to the zync-python you installed earlier, save the file, and close it.
