""" Contains LoginPresenter class. """
from zync_c4d_constants import SYMBOLS
from zync_c4d_presenter import Presenter


class LoginPresenter(Presenter):
  """
  Implements presenter for login view.

  :param zync_c4d_dialog.ZyncDialog dialog:
  :param zync_c4d_main_presenter.MainPresenter main_presenter:
  """

  def __init__(self, dialog, main_presenter):
    self._dialog = dialog
    self._main_presenter = main_presenter

  def activate(self):
    """ Activates the login view. """
    self._dialog.load_layout('LOGIN_DIALOG')

  def deactivate(self):
    """ Does nothing. """
    pass

  def on_scene_changed(self):
    """ Called when C4D scene is changed to a different scene. """
    # Login view doesn't care about scene changes
    pass

  def on_command(self, command_id):
    """
    Called when user interacts with a dialog widget.

    :param int command_id: Id of the widget.
    """
    if command_id == SYMBOLS['LOGIN']:
      self._main_presenter.start_logging_in()
