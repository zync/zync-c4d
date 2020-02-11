""" Contains MainPresenter class. """
from zync_c4d_presenter import Presenter
import zync_c4d_utils

class MainPresenter(Presenter):
  """
  Presenter that Controls transitions between different dialog sub-presenters
  and delegates work to them.

  :param zync_c4d_facade.C4dFacade c4d_facade:
  :param zync_c4d_presenter_factory.PresenterFactory presenter_factory:
  """

  def __init__(self, c4d_facade, presenter_factory):
    self._c4d_facade = c4d_facade
    self._auto_login = True
    self._logged_in = False
    self._zync_connection = None
    self._zync_cache = None
    self._presenter_factory = presenter_factory
    self._active_presenter = None

  def activate(self):
    """
    Starts the flow controller.

    Depending on the login state it switches to job or login view.
    """
    if self._auto_login:
      self._auto_login = False
      self.start_logging_in()
    elif self._zync_connection is not None:
      self._switch_to_job_view()
    else:
      self._switch_to_login_view()

  def deactivate(self):
    """ Does nothing. """
    pass

  def start_logging_in(self):
    """ Initiates Zync connection and switches between different dialogs depending on the result. """
    self._switch_to_connecting_view()

  def on_logging_in_aborted(self):
    """ Switches back to login view. """
    self._switch_to_login_view()

  def on_logged_in(self, zync_connection, zync_cache):
    """ Switches to job view. """
    self._zync_connection = zync_connection
    self._zync_cache = zync_cache
    self._switch_to_job_view()

  def log_out(self):
    """ Logs out and switches to login view. """
    if self._zync_connection is not None:
      self._zync_connection.logout()
      self._zync_connection = None
      self._zync_cache = None
    self._c4d_facade.show_message_box('Logged out from Zync')
    self._switch_to_login_view()

  def reload_job_view(self):
    """ Reloads job view. """
    self._switch_to_job_view()

  def on_scene_changed(self):
    """ Called when C4D scene is changed by the user. """
    if self._active_presenter:
      self._active_presenter.on_scene_changed()
    else:
      err_msg = 'Error: on_scene_changed called, but no active presenter'
      zync_c4d_utils.post_plugin_error(err_msg)
      print(err_msg)

  def on_command(self, command_id):
    """
    Called when user interacts with a dialog widget.

    :param int command_id: Id of the widget.
    """
    if self._active_presenter:
      self._active_presenter.on_command(command_id)
    else:
      err_msg = 'Error: on_command %d called, but no active presenter' % command_id
      print(err_msg)
      zync_c4d_utils.post_plugin_error(err_msg)

  def _switch_to_connecting_view(self):
    """ Switches to connecting view. """
    self._set_active_presenter(
        self._presenter_factory.create_connecting_presenter(self))

  def _switch_to_login_view(self):
    """ Switches to login view. """
    self._set_active_presenter(self._presenter_factory.create_login_presenter(self))

  def _switch_to_job_view(self):
    """ Switches to job view. """
    self._set_active_presenter(
        self._presenter_factory.create_job_presenter(self,
                                                     self._zync_connection,
                                                     self._zync_cache,
                                                     self._c4d_facade.get_scene_settings()))

  def _set_active_presenter(self, presenter):
    """
    Makes the presenter active.

    :param zync_c4d_presenter.Presenter presenter:
    """
    if self._active_presenter:
      self._active_presenter.deactivate()
    self._active_presenter = presenter
    presenter.activate()
