"""
Utility functions for Zync plugin.
"""
from functools import wraps
from importlib import import_module
import os
import sys

from zync_c4d_constants import PLUGIN_DIR

c4d = import_module('c4d')

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
        c4d.gui.MessageDialog('%s:\n\n%s' % (err.__class__.__name__, unicode(err)))
        err.exception_already_shown = True
      raise

  return _wrapped

@show_exceptions
def import_zync_module(zync_module_name):
  """
  Imports and returns a module from zync-python.

  Reads the plugin config file to find the path to zync-python.
  """
  old_sys_path = list(sys.path)

  try:
    if os.environ.get('ZYNC_API_DIR'):
      api_dir = os.environ.get('ZYNC_API_DIR')
    else:
      config_path = os.path.join(PLUGIN_DIR, 'config_c4d.py')
      if not os.path.exists(config_path):
        raise Exception(
          'Plugin configuration incomplete: zync-python path not provided.\n\n'
          'Re-installing the plugin may solve the problem.')
      import imp
      config_c4d = imp.load_source('config_c4d', config_path)
      api_dir = config_c4d.API_DIR
      if not isinstance(api_dir, basestring):
        raise Exception('API_DIR defined in config_c4d.py is not a string')

    sys.path.append(api_dir)
    return import_module(zync_module_name)
  finally:
    sys.path = old_sys_path

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
