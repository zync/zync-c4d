""" Contains main dialog used in Zync plugins. """
from contextlib import contextmanager
from importlib import import_module

import zync_c4d_constants
from zync_c4d_presenter_factory import PresenterFactory
from zync_c4d_utils import show_exceptions, import_zync_module, init_c4d_resources

SYMBOLS = zync_c4d_constants.SYMBOLS

c4d = import_module('c4d')
zync_threading = import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread

__res__ = init_c4d_resources()


class ZyncDialog(zync_threading.MainThreadCaller, c4d.gui.GeDialog):
  """
  Implements the main dialog window of Zync plugin.

  :param zync_threading.default_thread_pool.DefaultThreadPool thread_pool:
  :param zync_threading.MainThreadExecutor main_thread_executor:
  :param zync_c4d_facade.C4dFacade c4d_facade:
  """

  WIDGET_TO_OPTIONS_MAP = {
      'EXISTING_PROJ_NAME': 'PROJ_NAME_OPTIONS',
      'TAKE': 'TAKE_OPTIONS',
      'VMS_TYPE': 'VMS_TYPE_OPTIONS',
  }

  def __init__(self, thread_pool, main_thread_executor, c4d_facade):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)
    c4d.gui.GeDialog.__init__(self)
    self._thread_pool = thread_pool
    self._c4d_facade = c4d_facade
    self._scene_settings = None
    self._all_take_settings = []
    self._selected_take_settings = None
    self._render_settings = None
    self._active_presenter = None
    presenter_factory = PresenterFactory(self, self._c4d_facade, self._thread_pool, main_thread_executor)
    self._main_presenter = presenter_factory.create_main_presenter()

  @show_exceptions
  def CoreMessage(self, msg_id, msg):
    """
    Handles C4D core messages.

    :param int msg_id:
    :param c4d.BaseContainer msg:
    """
    if msg_id == c4d.EVMSG_CHANGE:
      self._main_presenter.on_scene_changed()
    elif msg_id == zync_c4d_constants.PLUGIN_ID:
      self._main_thread_executor.maybe_execute_action()
    return super(ZyncDialog, self).CoreMessage(msg_id, msg)

  @show_exceptions
  def CreateLayout(self):
    """ Creates UI controls. """
    self.GroupBegin(SYMBOLS['DIALOG_TOP_GROUP'], c4d.BFH_SCALEFIT & c4d.BFV_SCALEFIT, 1)
    self.GroupEnd()
    self._main_presenter.activate()
    return True

  @show_exceptions
  def Open(self, *args, **kwargs):
    """ Opens the dialog window. """
    self._scene_settings = self._c4d_facade.get_scene_settings()
    return super(ZyncDialog, self).Open(*args, **kwargs)

  @show_exceptions
  def Close(self):
    """ Closes the dialog window. """
    return super(ZyncDialog, self).Close()

  @show_exceptions
  def Command(self, cmd_id, _msg):
    """
    Handles user commands.

    :param int cmd_id:
    :param c4d.BaseContainer _msg:
    """
    self._main_presenter.on_command(cmd_id)
    return True

  @main_thread
  def load_layout(self, layout_name):
    """
    Loads the specified dialog layout.

    :param str layout_name:
    """
    self.LayoutFlushGroup(SYMBOLS['DIALOG_TOP_GROUP'])
    with self.change_menu():
      pass
    self.LoadDialogResource(SYMBOLS[layout_name])
    self.LayoutChanged(SYMBOLS['DIALOG_TOP_GROUP'])

  @main_thread
  def add_button_to_group(self, widget_group_name, caption, index):
    """
    Adds new button to the widget group.

    :param str widget_group_name: Name of the widget group.
    :param str caption: Button caption.
    :param int index: Index within the group.
    """
    self.AddButton(SYMBOLS[widget_group_name] + index, 0, name=caption)

  @main_thread
  def add_checkbox_to_group(self, widget_group_name, caption, index):
    """
    Adds new checkbox to the widget group.
    
    :param str widget_group_name: Name of the widget group.
    :param str caption: Checkbox caption.
    :param int index: Index within the group.
    """
    self.AddCheckbox(SYMBOLS[widget_group_name] + index, c4d.BFH_LEFT, 0, 0, name=caption)

  @main_thread
  def add_filler(self):
    """ Adds new filler. """
    self.AddStaticText(0, 0)

  @contextmanager
  def change_layout(self, widget_group_name):
    """
    Returns a context manager for changing the layout of the widget group.

    It clears the widget group on enter and notifies C4D about the changes on exit.

    :param str widget_group_name: Name of the widget group.
    """
    self.run_on_main_thread(lambda: self.LayoutFlushGroup(SYMBOLS[widget_group_name]))
    yield
    self.run_on_main_thread(lambda: self.LayoutChanged(SYMBOLS[widget_group_name]))

  @contextmanager
  def change_menu(self):
    """
    Returns a context manager for changing the dialog menu.

    It clears the menu on enter and notifies C4D about the changes on exit.
    """
    self.run_on_main_thread(lambda: self.MenuFlushAll())
    yield
    self.run_on_main_thread(lambda: self.MenuFinished())

  @main_thread
  def add_menu_entry(self, caption, submenu_symbol=None, submenu_caption=None):
    """
    Adds new entry to menu.

    Creates an entry with caption and optionally a clickable item.

    :param str caption: Entry caption.
    :param Optional[str] submenu_symbol: Name of the clickable item.
    :param Optional[str] submenu_caption: Caption of the clickable item.
    """
    self.MenuSubBegin(caption)
    if submenu_symbol:
      self.MenuAddString(SYMBOLS[submenu_symbol], submenu_caption)
    self.MenuSubEnd()

  @main_thread
  def enable_widget(self, widget_name, enable):
    """ Sets the enable state of the widget. """
    self.Enable(SYMBOLS[widget_name], enable)

  @main_thread
  def get_bool(self, widget_name):
    """ Returns boolean value of the widget. """
    return self.GetBool(SYMBOLS[widget_name])

  @main_thread
  def get_group_bool(self, widget_group_name, index):
    """ Returns boolean value of a child widget of the group at the index. """
    return self.GetBool(SYMBOLS[widget_group_name] + index)

  def get_combobox_option(self, widget_name, options):
    """ Returns the element of options at the index taken from the combobox widget. """
    return options[self.get_combobox_index(widget_name)]

  def get_combobox_index(self, widget_name):
    """ Returns the index selected in the combobox widget. """
    return self.get_int32(widget_name) - SYMBOLS[self.WIDGET_TO_OPTIONS_MAP[widget_name]]

  @main_thread
  def get_int32(self, widget_name):
    """ Returns the int32 value of the widget. """
    return self.GetInt32(SYMBOLS[widget_name])

  @main_thread
  def get_long(self, widget_name):
    """ Returns the long value of the widget. """
    return self.GetLong(SYMBOLS[widget_name])

  @main_thread
  def get_string(self, widget_name):
    """ Returns the string value of the widget. """
    return self.GetString(SYMBOLS[widget_name])

  @main_thread
  def set_bool(self, widget_name, value):
    """ Sets the boolean value of the widget. """
    self.SetBool(SYMBOLS[widget_name], value)

  @main_thread
  def set_group_bool(self, widget_group_name, value, index):
    """ Sets the boolean value of a child widget of the group at the index. """
    self.SetBool(SYMBOLS[widget_group_name] + index, value)

  @main_thread
  def set_int32(self, widget_name, value, min_value=None, max_value=None):
    """
    Sets the int32 value of the widget.

    Optionally sets the minimum and maximum values allowed for the widget.

    :param str widget_name:
    :param int value:
    :param Optional[int] min_value:
    :param Optional[int] max_value:
    """
    kwargs = {}
    if min_value is not None:
      kwargs['min'] = min_value
    if max_value is not None:
      kwargs['max'] = max_value
    self.SetInt32(SYMBOLS[widget_name], value, **kwargs)

  @main_thread
  def set_string(self, widget_name, value):
    """ Sets the string value of the widget. """
    self.SetString(SYMBOLS[widget_name], value)

  @main_thread
  def set_combobox_content(self, widget_name, options):
    """
    Fills the combobox widget with values from options in order as they appear in
    the options.

    :param str widget_name:
    :param collections.Iterable options:
    """
    child_base_name = self.WIDGET_TO_OPTIONS_MAP[widget_name]
    self.FreeChildren(SYMBOLS[widget_name])
    for i, option in enumerate(options):
      self.AddChild(SYMBOLS[widget_name], SYMBOLS[child_base_name] + i, option)
    # select the first option or make blank if no options
    self.set_int32(widget_name, SYMBOLS[child_base_name] if options else 0)

  def set_combobox_index(self, widget_name, index):
    """
    Sets the selected index of the combobox widget.

    :param str widget_name:
    :param int index:
    """
    self.set_int32(widget_name, SYMBOLS[self.WIDGET_TO_OPTIONS_MAP[widget_name]] + index)

  def switch_tab(self, tab_name):
    """
    Switches the current tab of the dialog.

    :param str tab_name:
    """
    self.set_int32('DIALOG_TABS', SYMBOLS[tab_name])
