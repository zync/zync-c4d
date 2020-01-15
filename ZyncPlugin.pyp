"""
Implements Zync plugin for C4D.
"""

from __future__ import division

from importlib import import_module
import os
import sys

# Required for importing of other modules, because C4D doesn't automatically add the plugin
# directory to the search path.
PLUGIN_DIR = os.path.dirname(__file__)
sys.path.append(PLUGIN_DIR)

c4d = import_module('c4d')

from zync_c4d_utils import show_exceptions
import zync_c4d_constants

__version__ = '0.10.1'


class ZyncPlugin(c4d.plugins.CommandData):
  """
  Implements Zync plugin for C4D.
  """

  def __init__(self):
    self._dialog = None

  @show_exceptions
  def Execute(self, _doc):
    """
    Opens Zync plugin dialog window.
    """
    self._maybe_create_dialog()
    if not self._dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=zync_c4d_constants.PLUGIN_ID):
      raise Exception('Failed to open dialog window')
    return True

  def _maybe_create_dialog(self):
    if not self._dialog:
      from zync_c4d_dialog import ZyncDialog
      self._dialog = ZyncDialog(__version__)

  @show_exceptions
  def RestoreLayout(self, sec_ref):
    """
    Restore the dialog.
    """
    self._maybe_create_dialog()
    return self._dialog.Restore(pluginid=zync_c4d_constants.PLUGIN_ID, secret=sec_ref)


def _plugin_cmd(plug_id):
  return "PLUGIN_CMD_" + str(plug_id)


class ResourceWithAncestorPath(object):
  """
  Describes C4D menu resource.

  It remembers path from root and it's able to update ansestors.
  History is represented as a list of dicts.
  Each element has two keys:
    'item' is the resource.
    'index' An integer telling the index of the resource in the parent container

  Most of methods return the resource object, so it's possible to chain
  operations. Find method returns boolean.
  e.g.
  res = ResourceWithHistory(main_menu)
  if res.find(c4d.MENURESOURCE_COMMAND, _plugin_cmd(ZYNC_DOWNLOAD_MENU_ID)):
    res.pop().append_zync_command().update_parents()
  """

  def __init__(self, root):
    self.root = root
    self.ancestor_path = []

  def append_zync_command(self):
    """
    Adds Zync command to the resource.
    """
    item = self.ancestor_path[-1]['item']

    zync_menu_clone = item.GetClone(c4d.COPYFLAGS_0)
    item.FlushAll()

    item.InsData(c4d.MENURESOURCE_COMMAND, _plugin_cmd(zync_c4d_constants.PLUGIN_ID))
    item.InsData(c4d.MENURESOURCE_SEPERATOR, True)

    for idx, value in list(zync_menu_clone):
      item.InsData(idx, value)

    self.ancestor_path[-1]['item'] = item
    return self

  def append_zync_menu(self):
    """
    Adds Zync Submenu to the resource and changes current resource to the created submenu.
    """
    bc_zync_menu = c4d.BaseContainer()
    bc_zync_menu.InsData(c4d.MENURESOURCE_SUBTITLE, zync_c4d_constants.ZYNC_SUBMENU_PCMD)
    if hasattr(c4d, 'MENURESOURCE_SUBTITLE_ICONID'):
      bc_zync_menu.InsData(c4d.MENURESOURCE_SUBTITLE_ICONID, zync_c4d_constants.PLUGIN_ID)
    self.ancestor_path[-1]['item'].InsData(c4d.MENURESOURCE_SUBMENU,
                                           bc_zync_menu)
    self.ancestor_path.append(
      dict(item=bc_zync_menu,
           index=len(self.ancestor_path[-1]['item']) - 1))
    return self

  def pop(self):
    """
    Changes current resource to it's parent.
    """
    self.ancestor_path.pop()
    return self

  def _find(self, attribute, value, root):
    """
    Recursively looks for a resource which `attribute` equals to `value`.

    Internal implementation of `find` method.

    Args:
      attribute: int, C4D attribute description. e.g. c4d.MENURESOURCE_SUBTITLE
      value: object, Desired value of the attribute.
      root: c4d.BaseContainer, Current root of the lookup.

    Returns: boolean, [dict()] First element tells if search was successful.
        The other is a path form `bc` to found element.
    """
    if root is not None:
      for i, (attr, current) in enumerate(root):
        if attr == c4d.MENURESOURCE_SUBMENU and isinstance(current, c4d.BaseContainer):
          result, current_path = self._find(attribute, value, current)
          if result:
            current_path.append(dict(item=current, index=i))
            return True, current_path
        elif attr == attribute and current == value:
          return True, [dict(item=current, index=i)]
    return False, [dict(item=None, index=0)]

  def find(self, attribute, value, root=None):
    """
    Recursively looks for a resource which `attribute` equals to `value`.

    Args:
      attribute: int, C4D attribute description. e.g. c4d.MENURESOURCE_SUBTITLE
      value: object, Desired value of the attribute.
      root: c4d.BaseContainer, Current root of the lookup.

    Returns: boolean, True if element was found.
    """
    if root is None:
      root = self.root
    result, result_path = self._find(attribute, value, root)
    if result:
      self.ancestor_path = list(reversed(result_path))
    return result

  def update_parents(self):
    """Follows the path an replaces all resources on the path with a copy hold
       in the path structure."""
    for i in reversed(range(len(self.ancestor_path))[1:]):
      self.ancestor_path[i - 1]['item'].SetIndexData(
        self.ancestor_path[i]['index'],
        self.ancestor_path[i]['item'])
    self.root.SetIndexData(self.ancestor_path[0]['index'],
                           self.ancestor_path[0]['item'])
    return self


def _add_zync_items_to_menu():
  """
  Adds "Render with Zync" command to Pipeline->Zync submenu.

  If parent elements don't exist, tries to create them.

  Returns: bool, True if success.
  """
  main_menu = c4d.gui.GetMenuResource("M_EDITOR")
  if not main_menu:
    print "Not an interactive environment."
    return False  # Probably not a Cinema 4D with GUI or a TRS/TRC environment

  if c4d.gui.SearchMenuResource(main_menu, _plugin_cmd(zync_c4d_constants.PLUGIN_ID)):
    # Zync menu is already present
    return True

  res = ResourceWithAncestorPath(main_menu)
  if res.find(c4d.MENURESOURCE_COMMAND, _plugin_cmd(zync_c4d_constants.ZYNC_DOWNLOAD_MENU_ID)):
    res.pop().append_zync_command().update_parents()
  elif res.find(c4d.MENURESOURCE_SUBTITLE, zync_c4d_constants.PIPELINE_MENU_PCMD):
    res.pop().append_zync_menu().append_zync_command().update_parents()

  return True


def PluginMessage(msg_id, _data):
  """
  Install Zync menu items in C4D.
  """
  # catch C4DPL_BUILDMENU to add Zync items to the menu.
  result = False
  if msg_id == c4d.C4DPL_BUILDMENU:
    result = _add_zync_items_to_menu()
    if not result:
      print "Zync plugin failed to update menu."
  return result


def main():
  """
  Plugin entry point.
  """
  bmp = c4d.bitmaps.BaseBitmap()
  bmp.InitWith(os.path.join(PLUGIN_DIR, 'res', 'zync.png'))

  res_pipeline = c4d.gui.SearchPluginMenuResource(zync_c4d_constants.PIPELINE_MENU_PCMD)
  print "Zync plugin loading..."
  if not c4d.plugins.RegisterCommandPlugin(
      id=zync_c4d_constants.PLUGIN_ID,
      str='Render with Zync...',
      info=c4d.PLUGINFLAG_HIDEPLUGINMENU if res_pipeline else c4d.PLUGINFLAG_COMMAND_ICONGADGET,
      icon=bmp,
      help='Render scene using Zync cloud service',
      dat=ZyncPlugin()):
    print "Zync plugin failed to register command."
  print "Zync plugin loaded."


if __name__ == '__main__':
  main()
