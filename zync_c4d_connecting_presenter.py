""" Contains ConnectingPresenter class. """
from zync_c4d_constants import SYMBOLS, RendererNames
from zync_c4d_presenter import Presenter
from zync_c4d_utils import import_zync_module

zync = import_zync_module('zync')
zync_threading = import_zync_module('zync_threading')
async_call = zync_threading.AsyncCaller.async_call


class ConnectingPresenter(Presenter, zync_threading.AsyncCaller):
  """
  Implements presenter for connection view.

  :param zync_c4d_dialog.ZyncDialog dialog:
  :param zync_c4d_main_presenter.MainPresenter main_presenter:
  :param zync_threading.thread_pool.ThreadPool thread_pool:
  :param zync_threading.thread_synchronization.ThreadSynchronizationFactory thread_synchronization_factory:
  :param zync_c4d_facade.C4dFacade c4d_facade:
  """

  def __init__(self, dialog, main_presenter, thread_pool,
      thread_synchronization_factory, c4d_facade):
    zync_threading.AsyncCaller.__init__(self, thread_pool,
                                        thread_synchronization_factory)
    self._dialog = dialog
    self._main_presenter = main_presenter
    self._c4d_facade = c4d_facade

  def activate(self):
    """ Activates the connecting view. """
    self._dialog.load_layout('CONN_DIALOG')
    self._connect_to_zync()

  def deactivate(self):
    """ Deactivates the presenter. """
    self.interrupt_all_async_calls()

  def on_scene_changed(self):
    """ Called when C4D scene is changed to a different scene. """
    # Connecting view doesn't care about scene changes
    pass

  def on_command(self, command_id):
    """
    Called when user interacts with a dialog widget.

    :param int command_id: Id of the widget.
    """
    if command_id == SYMBOLS['CANCEL_CONN']:
      self._main_presenter.on_logging_in_aborted()

  def _on_connected(self, connection_data):
    zync_connection, zync_cache = connection_data
    self._main_presenter.on_logged_in(zync_connection, zync_cache)

  def _on_connection_error(self, exception, traceback):
    self._c4d_facade.show_message_box('Connection Error: {0}',
                                      exception.message)
    print 'Connection error'
    print traceback
    self._main_presenter.on_logging_in_aborted()

  @async_call(_on_connected, _on_connection_error)
  def _connect_to_zync(self):
    zync_connection = zync.Zync(application='c4d')
    zync_cache = dict(
        instance_types={
            renderer_name: self._get_instance_types(zync_connection,
                                                    renderer_name) for
            renderer_name
            in [
                None,
                RendererNames.ARNOLD,
                RendererNames.REDSHIFT
            ]
        },
        email=zync_connection.email,
        project_name_hint=zync_connection.get_project_name(
            self._c4d_facade.get_scene_settings().get_scene_name()),
    )
    return zync_connection, zync_cache

  @staticmethod
  def _get_instance_types(zync_connection, renderer_name):
    instance_types_dict = zync_connection.get_instance_types(
        renderer=renderer_name,
        usage_tag='c4d_redshift' if renderer_name == RendererNames.REDSHIFT
        else None)

    def _safe_format_cost(cost):
      try:
        return "$%.2f" % float(cost)
      except ValueError:
        return cost

    instance_types = [
        {
            'order': properties['order'],
            'name': name,
            'cost': properties['cost'],
            'label': '%s (%s)' % (
                name, _safe_format_cost(properties['cost'])),
        }
        for name, properties in instance_types_dict.iteritems()
    ]
    instance_types.sort(key=lambda instance_type: instance_type['order'])
    return instance_types
