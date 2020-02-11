"""
Utility functions for Zync plugin.
"""
from functools import wraps
from importlib import import_module
import os
import sys
import traceback

import plugin_version
from zync_c4d_constants import PLUGIN_DIR

c4d = import_module('c4d')

_site_code = None


def get_c4d_version():
  """
  Returns C4D version.

  :return str:
  """
  return 'r%d.%03d' % (c4d.GetC4DVersion() / 1000, c4d.GetC4DVersion() % 1000)


def to_unicode(value):
  # It seems that c4d python uses utf for str objects.
  # https://plugincafe.maxon.net/topic/11943/how-to-handle-c4d-unicode-in-python-scripting
  try:
    return unicode(value)
  except UnicodeDecodeError:
    return str(value)


def show_exceptions(func):
  """
  Error-showing decorator for all entry points.

  Catches all exceptions and shows them on the screen and in console before
  re-raising. Uses `exception_already_shown` attribute to prevent showing
  the same exception twice.
  """

  @wraps(func)
  def _wrapped(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except Exception as err:
      if not getattr(err, 'exception_already_shown', False):
        c4d.gui.MessageDialog(
          '%s:\n\n%s' % (err.__class__.__name__, to_unicode(err)))
        post_plugin_error(traceback.format_exc())
        err.exception_already_shown = True
      raise

  return _wrapped


@show_exceptions
def import_zync_module(zync_module_name):
  """
  Imports and returns a module from zync-python.

  Reads the plugin config file to find the path to zync-python.
  """
  return _import_zync_module(zync_module_name)


def _import_zync_module(zync_module_name):
  old_sys_path = list(sys.path)

  try:
    sys.path.append(_get_api_dir())
    return import_module(zync_module_name)
  finally:
    sys.path = old_sys_path


def _get_api_dir():
  if os.environ.get('ZYNC_API_DIR'):
    return os.environ.get('ZYNC_API_DIR')
  else:
    config_c4d = _get_c4d_config()
    api_dir = config_c4d.API_DIR
    if not isinstance(api_dir, basestring):
      raise Exception('API_DIR defined in config_c4d.py is not a string')
    return api_dir


def _get_c4d_config():
  config_path = os.path.join(PLUGIN_DIR, 'config_c4d.py')
  if not os.path.exists(config_path):
    raise Exception(
        'Plugin configuration incomplete: zync-python path not provided.\n\n'
        'Re-installing the plugin may solve the problem.')
  import imp
  return imp.load_source('config_c4d', config_path)


def _get_zync_config():
  api_dir = _get_api_dir()
  import imp
  return imp.load_source('zync_config', os.path.join(api_dir, 'zync_config.py'))


def post_plugin_error(trace):
  """
  Submits unhandled exception stack trace.

  :param str trace:
  """
  try:
    analytics.post_plugin_error_event(_site_code, 'c4d', get_c4d_version(),
                                      plugin_version.__version__, trace)
  except BaseException as err:
    print('Exception %s when submitting error stacktrace:\n %s' % (err, trace))


def init_c4d_resources():
  """
  Initializes and returns a C4D resource.

  Some C4D functions require global __res__ to be initialized if they are called from a different
  module than the *.pyp file. This function should be used as follows:

  __res__ = init_c4d_resources()
  """
  res = c4d.plugins.GeResource()
  res.Init(PLUGIN_DIR)
  return res


def is_windows():
  """
  Checks if the system is Windows.

  :return bool:
  """
  import sys
  return sys.platform == 'win32'


analytics = _import_zync_module('analytics')
try:
  _site_code = _get_zync_config().ZYNC_URL
except BaseException as err:
  post_plugin_error(traceback.format_exc())
  print('Exception %s when getting site code' % err)
