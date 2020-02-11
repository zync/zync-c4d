""" Contains PresenterFactory class. """
from zync_c4d_connecting_presenter import ConnectingPresenter
from zync_c4d_job_presenter import JobPresenter
from zync_c4d_login_presenter import LoginPresenter
from zync_c4d_main_presenter import MainPresenter


class PresenterFactory(object):
  """
  Creates presenters.
  
  :param zync_c4d_dialog.ZyncDialog dialog:
  :param zync_c4d_facade.C4dFacade c4d_facade:
  :param zync_threading.default_thread_pool.DefaultThreadPool thread_pool:
  :param zync_threading.MainThreadExecutor main_thread_executor:
  """

  def __init__(self, dialog, c4d_facade, thread_pool, main_thread_executor):
    self._dialog = dialog
    self._c4d_facade = c4d_facade
    self._thread_pool = thread_pool
    self._main_thread_executor = main_thread_executor

  def create_connecting_presenter(self, main_presenter):
    """
    Creates a presenter for connecting view.

    :param zync_c4d_main_presenter.MainPresenter main_presenter:
    :return ConnectingPresenter:
    """
    return ConnectingPresenter(self._dialog, main_presenter, self._thread_pool,
                               self._thread_pool, self._c4d_facade)

  def create_login_presenter(self, main_presenter):
    """
    Creates a presenter for login view.

    :param zync_c4d_main_presenter.MainPresenter main_presenter:
    :return LoginPresenter:
    """
    return LoginPresenter(self._dialog, main_presenter)

  def create_job_presenter(self, main_presenter, zync_connection, zync_cache,
      scene_settings):
    """
    Creates a presenter for job view.

    :param zync_c4d_main_presenter.MainPresenter main_presenter:
    :param zync.Zync zync_connection:
    :param dict[Any, Any] zync_cache:
    :param zync_c4d_scene_settings.C4dSceneSettings scene_settings:
    :return JobPresenter:
    """
    return JobPresenter(self._dialog, main_presenter, zync_connection,
                        zync_cache, scene_settings, self._c4d_facade,
                        self._thread_pool, self._main_thread_executor)

  def create_main_presenter(self):
    """
    Creates a presenter for main view.

    :return MainPresenter:
    """
    return MainPresenter(self._c4d_facade, self)
