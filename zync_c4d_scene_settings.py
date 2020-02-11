""" Contains C4dSceneSettings class. """

from importlib import import_module
import re

from zync_c4d_take_settings import C4dTakeSettings
import zync_c4d_utils

zync_threading = zync_c4d_utils.import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
c4d = import_module('c4d')

win_drive_letter_regex = re.compile('^[a-zA-Z]:$')


class C4dSceneSettings(zync_threading.MainThreadCaller):
  """
  Implements various scene-related operations using C4D API.

  :param zync_threading.MainThreadExecutor main_thread_executor:
  :param c4d.documents.BaseDocument document:
  """

  def __init__(self, main_thread_executor, document):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)
    self._document = document

  @main_thread
  def get_all_assets(self):
    """
    Returns all scene assets.

    :return Iterable[str]:
    """
    return c4d.documents.GetAllAssets(self._document, False, '')

  @main_thread
  def get_all_take_settings(self):
    """
    Returns a list of take settings for all takes in the scene.

    :return list[C4dTakeSettings]:
    """
    take_settings = []
    take_data = self._document.GetTakeData()

    def _traverse(take, depth):
      take_settings.append(
          C4dTakeSettings(self._main_thread_executor, take, take_data, depth,
                          self._document))
      for child_take in take.GetChildren():
        _traverse(child_take, depth + 1)

    _traverse(take_data.GetMainTake(), 0)
    return take_settings

  @main_thread
  def get_fps(self):
    """
    Returns FPS of the scene.

    :return int:
    """
    return self._document.GetFps()

  @main_thread
  def get_scene_name(self):
    """
    Returns name of the scene.

    :return str:
    """
    return self._document.GetDocumentName()

  def get_scene_name_without_extension(self):
    """
    Returns name of the scene without extension.

    :return str:
    """
    return re.sub(r'\.c4d$', '', self.get_scene_name())

  @main_thread
  def get_scene_path(self):
    """
    Returns the path of the scene.

    :return str:
    """
    return self._maybe_fix_windows_path(self._document.GetDocumentPath())

  @staticmethod
  def _maybe_fix_windows_path(path):
    # When path is just a drive letter on Windows, it has no trailing \ character and such path
    # can't be merged correctly with file name, because on Windows C:\directory is different thing
    # than C:directory and both are valid paths. This method appends missing \ character.
    if zync_c4d_utils.is_windows():
      if win_drive_letter_regex.match(path):
        path += '\\'
    return path

  @main_thread
  def has_the_same_document(self, document):
    """
    Checks if the provided document is the same as the one with which this instance was initialized.

    :param c4d.documents.BaseDocument document:
    :return bool:
    """
    try:
      return document == self._document and document.GetDocumentPath() == \
             self._document.GetDocumentPath()
    except ReferenceError:
      return False

  @main_thread
  def is_saved(self):
    """
    Checks if the scene is saved.

    :return bool:
    """
    return self.get_scene_path() != '' and not self._document.GetChanged()
