""" Contains C4dFacade class. """
from importlib import import_module

from zync_c4d_scene_settings import C4dSceneSettings
import zync_c4d_utils

zync = zync_c4d_utils.import_zync_module('zync')
zync_threading = zync_c4d_utils.import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
c4d = import_module('c4d')


class C4dFacade(zync_threading.MainThreadCaller):
  """
  Implements various operations using C4d API.

  :param zync_threading.MainThreadExecutor main_thread_executor:
  """

  def __init__(self, main_thread_executor):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)

  @main_thread
  def are_scene_settings_active(self, scene_settings):
    """
    Checks if scene settings are referencing the current document.

    :param C4dSceneSettings scene_settings:
    :return bool:
    """
    return scene_settings.has_the_same_document(c4d.documents.GetActiveDocument())

  @main_thread
  def get_c4d_version(self):
    """
    Returns C4D version.

    :return str:
    """
    return 'r%d.%03d' % (c4d.GetC4DVersion() / 1000, c4d.GetC4DVersion() % 1000)

  @main_thread
  def get_global_texture_paths(self):
    """
    Returns global texture paths.

    See https://developers.maxon.net/docs/Cinema4DPythonSDK/html/modules/c4d/index.html#c4d
    .GetGlobalTexturePath

    :return [str]:
    """
    num_of_glob_tex_paths = 10
    glob_tex_paths = [c4d.GetGlobalTexturePath(i) for i in range(num_of_glob_tex_paths)]
    glob_tex_paths = [path for path in glob_tex_paths if path]
    return glob_tex_paths

  @main_thread
  def get_library_path(self):
    """
    Returns the path to C4D library.

    :return str:
    """
    return c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY)

  @main_thread
  def get_scene_settings(self):
    """
    Returns the scene settings.

    :return C4dSceneSettings:
    """
    return C4dSceneSettings(self._main_thread_executor, c4d.documents.GetActiveDocument())

  @main_thread
  def get_user_library_path(self):
    """
    Returns the path to C4D user-specific library.

    :return str:
    """
    return c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY_USER)

  @main_thread
  def show_load_dialog(self, directory=False):
    """
    Shows a 'load file' dialog and returns the path selected by an user or None if the user cancels.

    :param bool directory: If True, the dialog will select a directory instead of file.
    :return Optional[str]:
    """
    return c4d.storage.LoadDialog(flags=c4d.FILESELECT_DIRECTORY if directory else c4d.FILESELECT_LOAD)

  @main_thread
  def show_message_box(self, msg_format, *format_args):
    """
    Shows a simple message dialog with text and OK button.

    Parameters msg_format and *format_args have the same semantics as in str.format.

    :param str msg_format:
    :param *object format_args:
    """
    c4d.gui.MessageDialog(msg_format.format(*format_args))

  @main_thread
  def show_question_dialog(self, message):
    """
    Shows a question dialog.

    :param str message:
    :return bool: Returns True if the user clicks Yes and False if No.
    """
    return c4d.gui.QuestionDialog(message)

  @main_thread
  def show_save_dialog(self, title, default_path):
    """
    Shows a 'save file' dialog and returns the path selected by an user or None if the user cancels.

    :param str title:
    :param str default_path:
    :return Optional[str]:
    """
    return c4d.storage.SaveDialog(title=title, def_path=default_path)
