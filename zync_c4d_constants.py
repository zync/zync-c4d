"""
Contains definitions of common constants.
"""
import os
import re

PLUGIN_DIR = os.path.dirname(__file__)


def _read_c4d_symbols():
  """
  Returns a dictionary of symbols defined in c4d_symbols.h

  Ids for dialog controls are defined in c4d_symbols.h file in an enum
  definition. These definitions are necessary for dialog layout file,
  and therefore cannot be moved. In order to avoid duplication, this
  function reads the symbols.

  It uses regex to find the lines in which symbols are defined, so it
  is very fragile and will fail if enum definition differs from expected.
  We just need to write the symbols standard way.

  :return dict[string, int]:
  """
  symbols = {}
  with open(os.path.join(PLUGIN_DIR, 'res', 'c4d_symbols.h'), 'r') as symbols_file:
    lines = symbols_file.readlines()
  regex = re.compile(r'\s*(\w+)\s*=\s*(\d+)\s*,?\s*(?://.*)?')
  for line in lines:
    match = regex.match(line)
    if match:
      symbols[match.group(1)] = int(match.group(2))
  return symbols


SYMBOLS = _read_c4d_symbols()
PLUGIN_ID = 1038932

ZYNC_DOWNLOAD_MENU_ID = 1039086
ZYNC_SUBMENU_PCMD = "IDS_ZYNC_SUBMENU"
PIPELINE_MENU_PCMD = "IDS_EDITOR_PIPELINE"

# See https://support.solidangle.com/display/AFCUG/Get+current+version+%7C+python
ARNOLD_SCENE_HOOK = 1032309
ARNOLD_RENDERER = 1029988
C4DTOA_MSG_TYPE = 1000
C4DTOA_MSG_GET_VERSION = 1040
C4DTOA_MSG_RESP1 = 2011
VRAY_BRIDGE_PLUGIN_ID = 1019782
REDSHIFT_VIDEOPOSTS = [1036219, 1040189]

RDATA_RENDERENGINE_ARNOLD = 1029988
RDATA_RENDERENGINE_REDSHIFT = 1036219
RDATA_RENDERENGINE_VRAY = VRAY_BRIDGE_PLUGIN_ID


class RendererNames(object):
  """ Enumerates renderer names supported by Zync. """
  STANDARD = 'Standard'
  PHYSICAL = 'Physical'
  ARNOLD = 'Arnold'
  VRAY = 'V-Ray'
  REDSHIFT = 'Redshift'
