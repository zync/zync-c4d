""" Contains C4dVraySettings class. """
import glob
from importlib import import_module
import re

import zync_c4d_utils

zync_threading = zync_c4d_utils.import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
c4d = import_module('c4d')


class C4dVrayVersionException(Exception):
  """
  Indicates error when retrieving V-Ray version.

  :param str message:
  """

  def __init__(self, message):
    super(C4dVrayVersionException, self).__init__(message)


class C4dVraySettings(zync_threading.MainThreadCaller):
  """
  Implements V-Ray-specific operations.

  :param zync_threading.MainThreadExecutor main_thread_executor:
  """

  def __init__(self, main_thread_executor, vray_bridge):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)
    self._vray_bridge = vray_bridge

  supported_formats = {
    110: 'VrImg',
    0: 'TGA',
    10: 'BMP',
    20: 'HDR',
    30: 'JPG',
    40: 'PNG',
    50: 'PNG',  # 16 bit
    60: 'SGI',
    70: 'TIF',
    80: 'TIF',  # 16 bit
    90: 'EXR',  # 16
    100: 'EXR',  # 32
  }

  @staticmethod
  def get_version_from_vrscene(vrscene_path):
    """
    Returns V-Ray version using *.vrscene file.

    :param str vrscene_path:
    :return str:
    :raises:
      C4dVrayVersionException: if version can't be determined.
    """
    version_files = glob.glob(vrscene_path + '*')
    if not version_files:
      print 'Cannot determine vray version from %s' % vrscene_path
      raise C4dVrayVersionException(
        'Unable to determine V-Ray version. Exported vrscene file was not found.')

    version_file = list(version_files)[0]
    with open(version_file) as myfile:
      head = [next(myfile) for _ in xrange(10)]
    first_10_lines = '\n'.join(head)

    # Version numbers written by exporter may be inconsistent, for example
    # V-Ray 3.7 writes both lines:
    # // V-Ray core version is 3.60.05
    # // Exported by V-Ray 3.7
    match = re.search('Exported by V-Ray (?P<major>\\d)\\.(?P<minor>\\d+)', first_10_lines)
    if match:
      return match.group('major') + '.' + match.group('minor')
    match = re.search(
      'V-Ray core version is (?P<major>\\d)\\.(?P<minor>\\d{2})\\.(?P<patch>\\d{2})',
      first_10_lines)
    if match:
      return match.group('major') + '.' + match.group('minor') + '.' + match.group('patch')
    print 'Vray scene header: %s' % first_10_lines
    raise C4dVrayVersionException('Unable to determine V-Ray version')

  @main_thread
  def get_image_format(self):
    """
    Returns the image format.

    :return str:
    """
    image_format = self._vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_EXT]
    return self.supported_formats[image_format]

  @main_thread
  def get_image_path(self):
    """
    Returns the image save path.

    :return str:
    """
    return self._vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_FILE]

  @main_thread
  def is_image_saving_enabled(self):
    """
    Checks if image saving is enabled.

    :return bool:
    """
    return bool(self._vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_SAVE])

  @main_thread
  def set_state(self, state):
    """
    Restores the state of vray bridge from dict.

    :param dict[Any,Any] state:
    """
    for key, value in state.items():
      if value is not None:
        self._vray_bridge[key] = value

  @main_thread
  def get_state(self, vray_bridge_fields_to_save):
    """
    Saves the state of vray bridge in a dict.

    :param collections.Iterable[Any] vray_bridge_fields_to_save: A collection of fields to save.
    :return dict[Any,Any]:
    """
    state = dict()
    for key in vray_bridge_fields_to_save:
      value = self._vray_bridge[key]
      if value is not None:
        state[key] = value
    return state
