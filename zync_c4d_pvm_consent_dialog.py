""" Contains PVM consent dialog used in Zync plugin. """
from importlib import import_module
import webbrowser

from zync_c4d_constants import SYMBOLS
from zync_c4d_utils import init_c4d_resources, show_exceptions

c4d = import_module('c4d')
__res__ = init_c4d_resources()


class PvmConsentDialog(c4d.gui.GeDialog):
  """
  Implements the PVM consent dialog.

  This dialog informs the user about the risks of using preemptible instances.
  """

  def __init__(self):
    self.document = None
    self.result = None
    self.dont_show = None
    super(PvmConsentDialog, self).__init__()

  @show_exceptions
  def CreateLayout(self):
    """
    Creates UI controls.
    """
    self.LoadDialogResource(SYMBOLS['PVM_CONSENT_DIALOG'])
    return True

  @show_exceptions
  def Command(self, cmd_id, msg):
    """
    Handles user commands.
    """
    if cmd_id == SYMBOLS['LEARN_MORE']:
      webbrowser.open(
        'https://cloud.google.com/compute/docs/instances/preemptible')
    elif cmd_id == SYMBOLS['DONT_SHOW']:
      pass
    elif cmd_id == c4d.GEMB_R_OK:
      self.result = True
      self.dont_show = self.GetBool(SYMBOLS['DONT_SHOW'])
      self.Close()
    elif cmd_id == c4d.GEMB_R_CANCEL:
      self.result = False
      self.dont_show = False
      self.Close()
    else:
      raise Exception('Unknown command %s' % cmd_id)
    return super(PvmConsentDialog, self).Command(cmd_id, msg)
