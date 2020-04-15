""" Contains C4dRedshiftSettings class. """
from importlib import import_module
import traceback

import zync_c4d_utils

zync_threading = zync_c4d_utils.import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
c4d = import_module('c4d')


class C4dRedshiftSettings(zync_threading.MainThreadCaller):
  """
  Implements Redshift-specific operations.

  :param zync_threading.MainThreadExecutor main_thread_executor:
  :param collections.Iterable[c4d.documents.BaseVideoPost]:
  """

  def __init__(self, main_thread_executor, video_posts):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)
    self._video_posts = video_posts

  @main_thread
  def get_ocio_config_paths(self):
    """
    Returns OCIO paths.

    :return list[str]:
    """
    ocio_config_paths = []
    # This feature is not available with all RedShift versions
    if hasattr(c4d, 'REDSHIFT_POSTEFFECTS_COLORMANAGEMENT_OCIO_FILE'):
      for video_post in self._video_posts:
        ocio_config_path = video_post[c4d.REDSHIFT_POSTEFFECTS_COLORMANAGEMENT_OCIO_FILE]
        if ocio_config_path:
          ocio_config_paths.append(ocio_config_path)
    return ocio_config_paths

  @main_thread
  def get_version(self):
    """
    Returns Redshift version.

    :return str:
    """
    try:
      redshift = import_module('redshift')
      return redshift.GetCoreVersion()
    except (ImportError, AttributeError):
      print 'Error getting RedShift version, assuming <2.6.23'
      traceback.print_exc()
      return '2.6.0'
