"""" Contains C4dArnoldSettings class. """

from importlib import import_module
import zync_c4d_constants
import zync_c4d_utils

zync_threading = zync_c4d_utils.import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
c4d = import_module('c4d')


class C4dArnoldSettings(zync_threading.MainThreadCaller):
  """
  Implements Arnold-specific operations.

  :param zync_threading.MainThreadExecutor main_thread_executor:
  :param c4d.documents.BaseVideoPost video_post:
  :param c4d.documents.BaseDocument document:
  """

  def __init__(self, main_thread_executor, video_post, document):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)
    self._video_post = video_post
    self._document = document

  @main_thread
  def is_skip_license_check_enabled(self):
    """
    Checks if license check is enabled.

    :return bool:
    """
    return self._video_post[c4d.C4DAIP_OPTIONS_SKIP_LICENSE_CHECK]

  @main_thread
  def get_version(self):
    """
    Returns C4DtoA version.

    :return str:
    """
    arnold_hook = self._document.FindSceneHook(zync_c4d_constants.ARNOLD_SCENE_HOOK)
    if arnold_hook is None:
      return ""

    msg = c4d.BaseContainer()
    msg.SetInt32(zync_c4d_constants.C4DTOA_MSG_TYPE, zync_c4d_constants.C4DTOA_MSG_GET_VERSION)
    arnold_hook.Message(c4d.MSG_BASECONTAINER, msg)
    return msg.GetString(zync_c4d_constants.C4DTOA_MSG_RESP1)
