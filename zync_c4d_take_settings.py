""" Contains C4dTakeSettings class. """

from importlib import import_module
from zync_c4d_render_settings import C4dRenderSettings
import zync_c4d_utils

zync_threading = zync_c4d_utils.import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
c4d = import_module('c4d')


class C4dTakeSettings(zync_threading.MainThreadCaller):
  """
  Implements various take-related operations using C4D API.

  :param zync_threading.MainThreadExecutor main_thread_executor:
  :param c4d.modules.takesystem.BaseTake take:
  :param c4d.modules.takesystem.TakeData take_data:
  :param int take_depth:
  :param c4d.documents.BaseDocument document:
  """

  def __init__(self, main_thread_executor, take, take_data, take_depth, document):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)
    self._take = take
    self._take_data = take_data
    self._take_name = take.GetName()
    self._take_indented_name = take_depth * ' ' + self._take_name
    self._document = document

  @main_thread
  def get_camera_name(self):
    """
    Returns the camera name.

    :return str:
    """
    camera = self._take.GetCamera(self._take_data)
    if camera:
      return camera.GetName()
    else:
      return ''

  def get_indented_name(self):
    """
    Returns the take name indented accordingly to its position in the take hierarchy.

    :return str:
    """
    return self._take_indented_name

  def get_take_name(self):
    """
    Returns the take name.

    :return str:
    """
    return self._take_name

  @main_thread
  def get_render_settings(self):
    """
    Returns render settings.

    :return C4dRenderSettings:
    """
    return C4dRenderSettings(self._main_thread_executor,
                             self._take.GetEffectiveRenderData(self._take_data)[0], self._document,
                             self._take)

  @main_thread
  def is_valid(self):
    """
    Checks if take is valid.

    :return bool:
    """
    return self._take.GetEffectiveRenderData(self._take_data) is not None
