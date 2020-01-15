""" Contains main dialog used in Zync plugins. """
from importlib import import_module
import re
import webbrowser
import os
import time

from functools import partial
import zync_c4d_constants
from zync_c4d_pvm_consent_dialog import PvmConsentDialog
from zync_c4d_facade import C4dFacade
from zync_c4d_render_settings import C4dRenderFormatUnsupportedException, \
  C4dRendererSettingsUnavailableException
from zync_c4d_utils import show_exceptions, import_zync_module, init_c4d_resources
from zync_c4d_vray_exporter import VRayExporter
from zync_c4d_vray_settings import C4dVrayVersionException

SYMBOLS = zync_c4d_constants.SYMBOLS

c4d = import_module('c4d')
zync = import_zync_module('zync')
zync_threading = import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
async_call = zync_threading.AsyncCaller.async_call
zync_preflights = import_zync_module('zync_preflights')
common_preflights = import_zync_module('zync_preflights.common_checks')
default_thread_pool = import_zync_module('zync_threading.default_thread_pool')

__res__ = init_c4d_resources()


class ValidationError(Exception):
  """ Error in user-specified parameters or scene settings. """


class ZyncDialog(zync_threading.AsyncCaller, zync_threading.MainThreadCaller, c4d.gui.GeDialog):
  """
  Implements the main dialog window of Zync plugin.
  """

  c4d_renderers = [zync_c4d_constants.RendererNames.STANDARD,
                   zync_c4d_constants.RendererNames.PHYSICAL]
  supported_renderers = c4d_renderers + [
    zync_c4d_constants.RendererNames.ARNOLD,
    zync_c4d_constants.RendererNames.REDSHIFT,
    zync_c4d_constants.RendererNames.VRAY
  ]

  # list of widgets that should be disabled for upload only jobs
  render_only_settings = ['JOB_SETTINGS_G', 'VMS_SETTINGS_G', 'FRAMES_G', 'RENDER_G', 'TAKE']

  def __init__(self, version):
    self._version = version
    self._thread_pool = default_thread_pool.DefaultThreadPool(
      error_handler=self._handle_background_task_error)
    self._main_thread_executor = zync_threading.MainThreadExecutor(self._thread_pool,
                                                                   self._push_special_event,
                                                                   self._push_special_event)
    zync_threading.AsyncCaller.__init__(self, self._thread_pool, self._thread_pool.create_lock())
    zync_threading.MainThreadCaller.__init__(self, self._main_thread_executor)
    c4d.gui.GeDialog.__init__(self)
    self._c4d_facade = C4dFacade(self._main_thread_executor)
    self._scene_settings = None
    self._all_take_settings = []
    self._selected_take_settings = None
    self._render_settings = None
    self.logged_out = True
    self.logged_in = False
    self.auto_login = True
    self.available_instance_types = None
    self.project_names = None
    self.file_boxes = None
    self.project_list = None
    self.pvm_consent_dialog = None

  @staticmethod
  def _push_special_event():
    c4d.SpecialEventAdd(zync_c4d_constants.PLUGIN_ID)

  def _handle_background_task_error(self, task_name, err, traceback_str):
    print 'Exception ', err, 'in task ', task_name
    print 'Traceback: ', traceback_str
    if isinstance(err, ValidationError):
      self._c4d_facade.show_message_box('{0}', err.message)
    elif isinstance(err, zync.ZyncPreflightError) or isinstance(err, zync.ZyncError):
      self._c4d_facade.show_message_box('{0}:\n\n{1}', err.__class__.__name__, unicode(err))

  @show_exceptions
  def CoreMessage(self, msg_id, msg):
    """ Handles C4D core messages. """
    if msg_id == c4d.EVMSG_CHANGE:
      self._handle_document_change()
    elif msg_id == zync_c4d_constants.PLUGIN_ID:
      self._main_thread_executor.maybe_execute_action()
    return super(ZyncDialog, self).CoreMessage(msg_id, msg)

  @show_exceptions
  def CreateLayout(self):
    """ Creates UI controls. """
    self.GroupBegin(SYMBOLS['DIALOG_TOP_GROUP'], c4d.BFH_SCALEFIT & c4d.BFV_SCALEFIT, 1)
    self.GroupEnd()
    if self.auto_login:
      # auto login should happen only first time the window is opened
      self.auto_login = False
      self._login()
    elif getattr(self, 'zync_conn', None):
      self._load_layout('ZYNC_DIALOG')
      self._initialize_controls()
    elif self.logged_out:
      self._load_layout('LOGIN_DIALOG')
    else:
      self._load_layout('CONN_DIALOG')
    return True

  def Open(self, *args, **kwargs):
    """ Opens the dialog window. """
    self._scene_settings = self._c4d_facade.get_scene_settings()
    return super(ZyncDialog, self).Open(*args, **kwargs)

  @show_exceptions
  def Close(self):
    """ Closes the dialog window. """
    self.interrupt_all_async_calls()
    return super(ZyncDialog, self).Close()

  @main_thread
  def _login(self):
    self._connect_to_zync()
    self._load_layout('CONN_DIALOG')

  @main_thread
  def _on_connected(self, connection):
    self.zync_conn = connection
    self._fetch_available_settings()

  @main_thread
  def _on_login_fail(self, _exception):
    self._logout()

  @async_call(_on_connected, _on_login_fail)
  def _connect_to_zync(self):
    return zync.Zync(application='c4d')

  @main_thread
  def _on_fetched(self, zync_cache):
    self.zync_cache = zync_cache
    self._load_layout('ZYNC_DIALOG')
    self.logged_in = True
    self._initialize_controls()

  @async_call(_on_fetched, _on_login_fail)
  def _fetch_available_settings(self):
    return dict(
      instance_types={
        renderer_name: self._get_instance_types(renderer_name) for renderer_name in [
          None,
          zync_c4d_constants.RendererNames.ARNOLD,
          zync_c4d_constants.RendererNames.REDSHIFT
        ]
      },
      email=self.zync_conn.email,
      project_name_hint=self.zync_conn.get_project_name(self._scene_settings.get_scene_name()),
    )

  def _get_instance_types(self, renderer_name):
    instance_types_dict = self.zync_conn.get_instance_types(
      renderer=renderer_name,
      usage_tag='c4d_redshift' if renderer_name == zync_c4d_constants.RendererNames.REDSHIFT else
      None)

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

  def _load_layout(self, layout_name):
    self.LayoutFlushGroup(SYMBOLS['DIALOG_TOP_GROUP'])
    self.MenuFlushAll()
    self.MenuFinished()
    self.LoadDialogResource(SYMBOLS[layout_name])
    self.LayoutChanged(SYMBOLS['DIALOG_TOP_GROUP'])

  def _initialize_controls(self):
    self.MenuFlushAll()
    self.MenuSubBegin('Logged in as %s' % self.zync_cache['email'])
    self.MenuSubEnd()
    self.MenuSubBegin('Log out')
    self.MenuAddString(SYMBOLS['LOGOUT'], 'Log out from Zync')
    self.MenuSubEnd()
    self.MenuFinished()

    self.available_instance_types = []

    # VMs settings
    self.SetInt32(SYMBOLS['VMS_NUM'], 1, min=1)

    # Storage settings (zync project)
    self.project_list = self.zync_conn.get_project_list()
    self.project_names = [project['name'] for project in self.project_list]
    project_name_hint = re.sub(r'\.c4d$', '', self._scene_settings.get_scene_name())
    self._set_combobox_content(SYMBOLS['EXISTING_PROJ_NAME'], SYMBOLS['PROJ_NAME_OPTIONS'],
                               self.project_names)
    self.SetString(SYMBOLS['NEW_PROJ_NAME'], project_name_hint)
    if project_name_hint in self.project_names:
      self._enable_existing_project_widget()
      self.SetInt32(SYMBOLS['EXISTING_PROJ_NAME'],
                    SYMBOLS['PROJ_NAME_OPTIONS'] + self.project_names.index(project_name_hint))
    else:
      self._enable_new_project_widget()

    # General job settings
    self.SetInt32(SYMBOLS['JOB_PRIORITY'], 50, min=0)
    self.SetString(SYMBOLS['OUTPUT_PATH'], self._default_output_path())
    self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'], self._default_multipass_output_path())

    # Renderer settings
    self.SetInt32(SYMBOLS['CHUNK'], 10, min=1)

    # File management
    self.SetBool(SYMBOLS['UPLOAD_ONLY'], False)

    self.file_boxes = []
    self._update_file_checkboxes()

    # Take
    self._selected_take_settings = None
    self._recreate_take_list()

  def _enable_existing_project_widget(self):
    self.SetBool(SYMBOLS['NEW_PROJ'], False)
    self.SetBool(SYMBOLS['EXISTING_PROJ'], True)

  def _enable_new_project_widget(self):
    self.SetBool(SYMBOLS['EXISTING_PROJ'], False)
    self.SetBool(SYMBOLS['NEW_PROJ'], True)

  def _set_combobox_content(self, widget_id, child_id_base, options):
    self.FreeChildren(widget_id)
    for i, option in enumerate(options):
      self.AddChild(widget_id, child_id_base + i, option)
    # select the first option or make blank if no options
    self.SetInt32(widget_id, child_id_base if options else 0)

  def _default_output_path(self):
    return os.path.abspath(
      os.path.join(self._scene_settings.get_scene_path(), 'renders', '$take',
                   self._get_scene_name_with_no_extension()))

  def _default_multipass_output_path(self):
    return os.path.abspath(os.path.join(self._scene_settings.get_scene_path(), 'renders', '$take',
                                        self._get_scene_name_with_no_extension() + '_multi'))

  def _get_scene_name_with_no_extension(self):
    return re.sub(r'\.c4d$', '', self._scene_settings.get_scene_name())

  def _handle_document_change(self):
    # Reinitialize dialog in case active document was changed.
    if self.logged_in:
      if self._c4d_facade.are_scene_settings_active(self._scene_settings):
        self._recreate_take_list()
      else:
        self._scene_settings = self._c4d_facade.get_scene_settings()
        self._initialize_controls()

  def _recreate_take_list(self):
    self._all_take_settings = self._scene_settings.get_all_take_settings()
    take_labels = [take_settings.get_indented_name() for take_settings in self._all_take_settings]
    self._set_combobox_content(SYMBOLS['TAKE'], SYMBOLS['TAKE_OPTIONS'], take_labels)

    # _set_combobox_content selected first entry, but we want to keep
    # previous selection if that take still exists:
    for i, take_settings in enumerate(self._all_take_settings):
      if take_settings == self._selected_take_settings:
        # Previously selected take found, select it again
        self.SetInt32(SYMBOLS['TAKE'], SYMBOLS['TAKE_OPTIONS'] + i)
        return

    # Previously selected take not found, just switch to first one
    self._handle_take_change()

  def _handle_take_change(self):
    take_settings = self._read_combobox_option(SYMBOLS['TAKE'], SYMBOLS['TAKE_OPTIONS'],
                                               self._all_take_settings)
    if not take_settings.is_valid():
      self._c4d_facade.show_message_box(
        'Please load or create a scene with at least one valid take before using Zync plugin.')
      return
    self._selected_take_settings = take_settings
    self._render_settings = self._selected_take_settings.get_render_settings()
    previous_instance_type = self._save_previous_instance_type()
    self._update_renderer_and_available_instance_types()
    self._update_available_instance_types()
    self._maybe_restore_previous_instance_type(previous_instance_type)
    self._update_price()
    self._update_resolution_controls()
    self._update_frame_range_controls()
    self._update_output_path_controls()
    self._update_multipass_output_path_controls()

  def _update_renderer_and_available_instance_types(self):
    renderer_name = self._render_settings.get_renderer_name()
    if renderer_name in self.supported_renderers:
      self.SetString(SYMBOLS['RENDERER'], renderer_name)
      external_renderer = renderer_name
      if renderer_name in self.c4d_renderers or renderer_name not in self.zync_cache[
        'instance_types']:
        external_renderer = None
      self.available_instance_types = self.zync_cache['instance_types'][external_renderer]
    else:
      self.SetString(SYMBOLS['RENDERER'], renderer_name + ' (unsupported)')
      self.available_instance_types = []
    if renderer_name == zync_c4d_constants.RendererNames.VRAY:
      self.SetInt32(SYMBOLS['CHUNK'], 1)
      self.Enable(SYMBOLS['CHUNK'], False)
    else:
      self.Enable(SYMBOLS['CHUNK'], True)

  def _save_previous_instance_type(self):
    previous_instance_type = None
    if getattr(self, 'available_instance_types', None):
      previous_instance_type = self._read_combobox_option(SYMBOLS['VMS_TYPE'],
                                                          SYMBOLS['VMS_TYPE_OPTIONS'],
                                                          self.available_instance_types)
    return previous_instance_type

  def _update_available_instance_types(self):
    if self.available_instance_types:
      instance_type_labels = [instance_type['label'] for instance_type in
                              self.available_instance_types]
    else:
      instance_type_labels = ['N/A']
    self._set_combobox_content(SYMBOLS['VMS_TYPE'], SYMBOLS['VMS_TYPE_OPTIONS'],
                               instance_type_labels)

  def _maybe_restore_previous_instance_type(self, previous_instance_type):
    if previous_instance_type:
      for i, instance_type in enumerate(self.available_instance_types):
        if instance_type['name'] == previous_instance_type['name']:
          self.SetInt32(SYMBOLS['VMS_TYPE'], SYMBOLS['VMS_TYPE_OPTIONS'] + i)

  def _update_resolution_controls(self):
    x, y = self._render_settings.get_resolution()
    self.SetInt32(SYMBOLS['RES_X'], x, min=1)
    self.SetInt32(SYMBOLS['RES_Y'], y, min=1)

  def _update_frame_range_controls(self):
    start_frame, end_frame, frame_step = self._render_settings.get_frame_range(
      self._scene_settings.get_fps())
    self.SetInt32(SYMBOLS['FRAMES_FROM'], start_frame, max=end_frame)
    self.SetInt32(SYMBOLS['FRAMES_TO'], end_frame, min=start_frame)
    self.SetInt32(SYMBOLS['STEP'], frame_step, min=1)

  def _update_output_path_controls(self, ):
    self.Enable(SYMBOLS['OUTPUT_PATH'], self._is_image_saving_enabled())
    self.Enable(SYMBOLS['OUTPUT_PATH_BTN'], self._is_image_saving_enabled())
    if self._is_image_saving_enabled():
      if self._render_settings.has_image_path():
        self.SetString(SYMBOLS['OUTPUT_PATH'], os.path.join(self._scene_settings.get_scene_path(),
                                                            self._render_settings.get_image_path()))
      else:
        self.SetString(SYMBOLS['OUTPUT_PATH'], self._default_output_path())
    else:
      self.SetString(SYMBOLS['OUTPUT_PATH'], 'Not enabled')

  def _update_multipass_output_path_controls(self):
    self.Enable(SYMBOLS['MULTIPASS_OUTPUT_PATH'], self._is_multipass_image_saving_enabled())
    self.Enable(SYMBOLS['MULTIPASS_OUTPUT_PATH_BTN'], self._is_multipass_image_saving_enabled())
    if self._is_multipass_image_saving_enabled():
      if self._render_settings.has_multipass_image_path():
        self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'], os.path.abspath(
          os.path.join(self._scene_settings.get_scene_path(),
                       self._render_settings.get_multipass_image_path())))
      else:
        self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'], self._default_multipass_output_path())
    else:
      self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'], 'Not enabled')

  @show_exceptions
  def Command(self, cmd_id, _msg):
    """ Handles user commands. """
    if cmd_id == SYMBOLS['LOGIN']:
      self._login()
    elif cmd_id == SYMBOLS['LOGOUT']:
      self._logout()
      self._c4d_facade.show_message_box('Logged out from Zync')
    elif cmd_id == SYMBOLS['CANCEL_CONN']:
      self._logout()
    elif cmd_id == SYMBOLS['COST_CALC_LINK']:
      webbrowser.open('http://zync.cloudpricingcalculator.appspot.com')
    elif cmd_id == SYMBOLS['VMS_NUM'] or cmd_id == SYMBOLS['VMS_TYPE']:
      self._update_price()
    elif cmd_id == SYMBOLS['FILES_LIST']:
      self._update_file_checkboxes()
      self.SetInt32(SYMBOLS['DIALOG_TABS'], SYMBOLS['FILES_TAB'])
    elif cmd_id == SYMBOLS['ADD_FILE']:
      self._add_file()
    elif cmd_id == SYMBOLS['ADD_DIR']:
      self._add_file(directory=True)
    elif cmd_id == SYMBOLS['OK_FILES']:
      self._read_file_checkboxes()
      self.SetInt32(SYMBOLS['DIALOG_TABS'], SYMBOLS['SETTINGS_TAB'])
    elif cmd_id == SYMBOLS['OUTPUT_PATH_BTN']:
      self._prompt_path_and_update_widget('OUTPUT_PATH', 'Set regular image output path...')
    elif cmd_id == SYMBOLS['MULTIPASS_OUTPUT_PATH_BTN']:
      self._prompt_path_and_update_widget('MULTIPASS_OUTPUT_PATH',
                                          'Set multi-pass image output path...')
    elif cmd_id == SYMBOLS['FRAMES_FROM']:
      self.SetInt32(SYMBOLS['FRAMES_TO'], value=self.GetInt32(SYMBOLS['FRAMES_TO']),
                    min=self.GetInt32(SYMBOLS['FRAMES_FROM']))
    elif cmd_id == SYMBOLS['FRAMES_TO']:
      self.SetInt32(SYMBOLS['FRAMES_FROM'], value=self.GetInt32(SYMBOLS['FRAMES_FROM']),
                    max=self.GetInt32(SYMBOLS['FRAMES_TO']))
    elif cmd_id == SYMBOLS['EXISTING_PROJ_NAME']:
      self._enable_existing_project_widget()
    elif cmd_id == SYMBOLS['NEW_PROJ_NAME']:
      self._enable_new_project_widget()
    elif cmd_id == SYMBOLS['UPLOAD_ONLY']:
      self._set_upload_only(self.GetBool(SYMBOLS['UPLOAD_ONLY']))
    elif cmd_id == SYMBOLS['LAUNCH']:
      self._maybe_launch_job()
    elif cmd_id == SYMBOLS['TAKE']:
      self._handle_take_change()
    elif SYMBOLS['FILES_LIST_UNFOLD_BTNS'] <= cmd_id < SYMBOLS['FILES_LIST_UNFOLD_BTNS'] + 10000:
      self._unfold_dir(cmd_id - SYMBOLS['FILES_LIST_UNFOLD_BTNS'])
    return True

  def _prompt_path_and_update_widget(self, widget_name, prompt_text):
    old_output = self.GetString(SYMBOLS[widget_name])
    new_output = self._c4d_facade.show_save_dialog(prompt_text, old_output)
    if new_output:
      self.SetString(SYMBOLS[widget_name], new_output)

  def _set_upload_only(self, upload_only):
    for item_name in self.render_only_settings:
      self.Enable(SYMBOLS[item_name], not upload_only)

  def _unfold_dir(self, dir_index):
    self._read_file_checkboxes()

    def _generate_new_fboxes():
      for i in xrange(dir_index):
        yield self.file_boxes[i]

      dir_path, _checked, _is_dir = self.file_boxes[dir_index]
      for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        if os.path.isfile(file_path):
          yield (file_path, True, False)
        elif os.path.isdir(file_path):
          yield (file_path, True, True)

      for i in xrange(dir_index + 1, len(self.file_boxes)):
        yield self.file_boxes[i]

    new_file_boxes = list(_generate_new_fboxes())
    self.file_boxes = new_file_boxes
    self._update_file_checkboxes()

  def _update_file_checkboxes(self):
    self.LayoutFlushGroup(SYMBOLS['FILES_LIST_GROUP'])
    for i, (path, checked, is_dir) in enumerate(self.file_boxes):
      checkbox = self.AddCheckbox(SYMBOLS['FILES_LIST_OPTIONS'] + i, c4d.BFH_LEFT, 0, 0, name=path)
      self.SetBool(checkbox, checked)
      if is_dir:
        self.AddButton(SYMBOLS['FILES_LIST_UNFOLD_BTNS'] + i, 0, name='Unfold')
      else:
        # Layout filler
        self.AddStaticText(0, 0)
    self.LayoutChanged(SYMBOLS['FILES_LIST_GROUP'])
    dirs_count = sum(int(is_dir) for (_, _, is_dir) in self.file_boxes)
    files_count = len(self.file_boxes) - dirs_count
    self.SetString(SYMBOLS['AUX_FILES_SUMMARY'], '%d files, %d folders' % (files_count, dirs_count))

  def _read_file_checkboxes(self):
    self.file_boxes = [
      (path, self.GetBool(SYMBOLS['FILES_LIST_OPTIONS'] + i), is_dir)
      for i, (path, _, is_dir) in enumerate(self.file_boxes)
    ]

  def _add_file(self, directory=False):
    self._read_file_checkboxes()
    fname = self._c4d_facade.show_load_dialog(directory)
    if fname is not None:
      self.file_boxes.append((fname, True, directory))
      self._update_file_checkboxes()

  def _logout(self):
    self.logged_in = False
    self.logged_out = True
    self._load_layout('LOGIN_DIALOG')
    self.interrupt_all_async_calls()
    zync_conn = getattr(self, 'zync_conn', None)
    if zync_conn:
      del self.zync_conn
      zync_conn.logout()

  def _update_price(self):
    if self.available_instance_types:
      instances_count = self.GetLong(SYMBOLS['VMS_NUM'])
      instance_type = self._read_combobox_option(SYMBOLS['VMS_TYPE'], SYMBOLS['VMS_TYPE_OPTIONS'],
                                                 self.available_instance_types)
      instance_cost = instance_type['cost']
      est_price = instances_count * instance_cost
      self.SetString(SYMBOLS['EST_PRICE'], 'Estimated hour cost: $%.2f' % est_price)
    else:
      self.SetString(SYMBOLS['EST_PRICE'], 'Estimated hour cost: N/A')

  def _maybe_launch_job(self):
    if not self._ensure_scene_saved():
      return
    try:
      params = self._collect_params()
    except ValidationError as err:
      c4d.gui.MessageDialog(err.message)
    else:
      settings = import_zync_module('settings')
      if ('PREEMPTIBLE' in params['instance_type']) and not settings.Settings.get().get_pvm_ack():
        self.pvm_consent_dialog = PvmConsentDialog()
        self.pvm_consent_dialog.Open(dlgtype=c4d.DLG_TYPE_MODAL)
        if not self.pvm_consent_dialog.result:
          return
        if self.pvm_consent_dialog.dont_show:
          settings.Settings.get().put_pvm_ack(True)
      if '(ALPHA)' in params['instance_type']:
        # TODO: replace standard dialog with something better, without this deceptive
        #  call to action on YES
        alpha_confirmed = self._c4d_facade.show_question_dialog(
          'You\'ve selected an instance type for your job which is '
          'still in alpha, and could be unstable for some workloads.\n\n'
          'Submit the job anyway?')
        if not alpha_confirmed:
          return

      if self.zync_conn.is_experiment_enabled('EXPERIMENT_PREFLIGHTS'):
        self._run_preflights(params)
      else:
        self._launch_job(params)

  @main_thread
  def _launch_job(self, params):
    try:
      if self._render_settings.get_renderer_name() == zync_c4d_constants.RendererNames.VRAY:
        self._start_vray_job_submission(params)
      else:
        self._submit_c4d_job(params)
    except ValidationError as err:
      self._c4d_facade.show_message_box('{0}', err.message)
    except (zync.ZyncError, zync.ZyncPreflightError) as err:
      self._c4d_facade.show_message_box('{0}:\n\n{1}', err.__class__.__name__, unicode(err))
    except:
      self._c4d_facade.show_message_box('Unexpected error during job submission')

  def _run_preflights(self, params):
    def _on_status_change(preflight_check, status):
      print 'Preflight Check Status Change ', preflight_check.preflight_name, ' ---> ', status

    def _on_result(result):
      print 'Preflight Check Result ', result

    preflights = [
      common_preflights.DependencyCheck(params['scene_info']['dependencies'], _on_result)]
    _on_finished = partial(self._launch_job, params)
    suite = zync_preflights.PreflightCheckSuite(self._thread_pool, self._thread_pool.create_lock(),
                                                _on_status_change, _on_finished, preflights)
    suite.start()

  def _show_job_successfuly_submitted_dialog(self):
    self._c4d_facade.show_message_box(
      'Job submitted!\n\nYou can check the status of job in Zync console.\n\n'
      'Don\'t turn off the client app before upload is complete.')

  def _submit_c4d_job(self, params):
    # TODO: Make it async, also: async calls should disable UI
    doc_dirpath = self._scene_settings.get_scene_path()
    doc_name = self._scene_settings.get_scene_name()
    doc_path = os.path.join(doc_dirpath, doc_name)
    self.zync_conn.submit_job('c4d', doc_path, params)
    self._show_job_successfuly_submitted_dialog()

  def _start_vray_job_submission(self, params):
    print 'Vray job, collecting additional info...'

    if self._is_image_saving_enabled() and self._is_multipass_image_saving_enabled():
      if not self._render_settings.is_multipass_image_format_same_as_regular():
        self._c4d_facade.show_message_box(
          'WARNING: Regular output format is different than multipass output format. '
          'Vray jobs support only one output format. Regular output format will be used.'
        )
      if self.GetString(SYMBOLS['OUTPUT_PATH']) != self.GetString(SYMBOLS['MULTIPASS_OUTPUT_PATH']):
        self._c4d_facade.show_message_box(
          'WARNING: Regular output path is different than multipass output path. Vray '
          'jobs support only one output path. Regular output path will be used for all '
          'render elements.'
        )

    try:
      vray_settings = self._render_settings.get_vray_settings()
    except C4dRendererSettingsUnavailableException:
      raise ValidationError('Unable to get V-Ray render settings')
    if vray_settings.is_image_saving_enabled():
      output_path = vray_settings.get_image_path()
      params['format'] = self._get_vfb_format(vray_settings)
    else:
      output_path = self.GetString(SYMBOLS['OUTPUT_PATH'])
    output_path = self._render_settings.convert_tokens(output_path)
    print 'output_path: %s' % output_path
    params['output_dir'], params['output_name'] = self._split_output_path(output_path)
    params['scene_info']['camera'] = self._selected_take_settings.get_camera_name()
    doc_dirpath = self._scene_settings.get_scene_path()
    doc_name = self._scene_settings.get_scene_name()
    path = os.path.join(doc_dirpath, '__zync', str(time.time()))
    if not os.path.exists(path):
      os.makedirs(path)
    vrscene_path = os.path.join(path, os.path.splitext(doc_name)[0])
    vrscene_exporter = VRayExporter(self._main_thread_executor, vrscene_path, params,
                                    self._scene_settings, self._render_settings,
                                    lambda: self._send_vray_scene(vrscene_path, params))
    self._thread_pool.add_task(vrscene_exporter)

  @show_exceptions
  @main_thread
  def _send_vray_scene(self, vrscene_path, params):
    copy_keys = [
      'renderer', 'plugin_version', 'num_instances', 'instance_type',
      'proj_name', 'job_subtype', 'priority', 'notify_complete',
      'upload_only', 'xres', 'yres', 'chunk_size', 'scene_info',
      'take', 'output_dir', 'output_name',
      'format', 'frame_begin', 'frame_end', 'step'
    ]
    render_params = {key: params[key] for key in copy_keys}

    try:
      vray_version = self._render_settings.get_vray_settings().get_version_from_vrscene(
        vrscene_path)
    except C4dVrayVersionException as err:
      raise zync.ZyncError(err.message)
    print 'Detected vray version: %s' % vray_version
    render_params['scene_info']['vray_version'] = vray_version
    vrscene = vrscene_path + '*.vrscene'
    self.zync_conn.submit_job('c4d_vray', vrscene, params=render_params)
    self._show_job_successfuly_submitted_dialog()

  @staticmethod
  def _get_vfb_format(vray_settings):
    output_path = vray_settings.get_image_path()
    _, extension = os.path.splitext(output_path)
    if extension:
      return extension  # vray bridge ignores format when file name contains extension
    return vray_settings.get_image_format()

  def _ensure_scene_saved(self):
    if not self._scene_settings.is_saved():
      self._c4d_facade.show_message_box(
        'The scene file must be saved in order to be uploaded to Zync.')
      return False
    elif self._scene_settings.get_scene_name().startswith('preset:'):
      self._c4d_facade.show_message_box(
        'Rendering scenes directly from preset files is not supported. Please save the '
        'scene in a separate file.')
      return False
    return True

  def _split_output_path(self, out_path):
    out_dir, out_name = os.path.split(out_path)
    while '$' in out_dir:
      out_dir, dir1 = os.path.split(out_dir)
      out_name = os.path.join(dir1, out_name)
    if not os.path.isabs(out_dir):
      out_dir = os.path.join(self._scene_settings.get_scene_path(), out_dir)
    out_dir = os.path.abspath(out_dir)
    return out_dir, out_name

  def _collect_params(self):
    try:
      params = {}

      renderer_name = self._render_settings.get_renderer_name()
      if renderer_name not in self.supported_renderers:
        raise ValidationError('Renderer \'%s\' is not currently supported by Zync' % renderer_name)
      params['renderer'] = renderer_name
      params['plugin_version'] = self._version
      params['take'] = self._selected_take_settings.get_take_name()
      params['num_instances'] = self.GetLong(SYMBOLS['VMS_NUM'])
      if self.available_instance_types:
        params['instance_type'] = self._read_combobox_option(
          SYMBOLS['VMS_TYPE'],
          SYMBOLS['VMS_TYPE_OPTIONS'],
          self.available_instance_types)['name']
      else:
        raise ValidationError('No machine type available for this type of job')

      params['proj_name'] = self._read_project_name()
      params['job_subtype'] = 'render'
      params['priority'] = self.GetLong(SYMBOLS['JOB_PRIORITY'])
      params['notify_complete'] = int(self.GetBool(SYMBOLS['NOTIFY_COMPLETE']))
      params['upload_only'] = int(self.GetBool(SYMBOLS['UPLOAD_ONLY']))

      self._maybe_update_regular_image_params(params)
      self._maybe_update_multipass_image_params(params)
      if not self._is_output_enabled:
        raise ValidationError(
          'No output is enabled. Please either enable regular image ' +
          'or multi-pass image output from the render settings.')

      out_fps = self._render_settings.get_frame_rate()
      proj_fps = self._scene_settings.get_fps()
      if out_fps != proj_fps:
        raise ValidationError(
          'Output framerate (%.2f) doesn\'t match project framerate (%.2f). '
          'Using output framerates different from project fps is currently '
          'not supported by Zync.\n\n'
          'Please adjust the values to be equal.' % (out_fps, proj_fps))

      params['frame_begin'] = self.GetInt32(SYMBOLS['FRAMES_FROM'])
      params['frame_end'] = self.GetInt32(SYMBOLS['FRAMES_TO'])
      params['step'] = str(self.GetInt32(SYMBOLS['STEP']))
      params['chunk_size'] = str(self.GetInt32(SYMBOLS['CHUNK']))
      params['xres'] = str(self.GetInt32(SYMBOLS['RES_X']))
      params['yres'] = str(self.GetInt32(SYMBOLS['RES_Y']))
      user_files = [path for (path, checked, _) in self.file_boxes if checked]
      asset_files, preset_files = self._get_assets_and_presets()
      params['scene_info'] = {
        'dependencies': list(asset_files) + list(preset_files) + user_files,
        'preset_files': list(preset_files),
        'glob_tex_paths': self._c4d_facade.get_global_texture_paths(),
        'lib_path_global': self._c4d_facade.get_library_path(),
        'lib_path_user': self._c4d_facade.get_user_library_path(),
        'c4d_version': self._c4d_facade.get_c4d_version(),
      }

      self._add_render_specific_params(params)
      return params
    except C4dRendererSettingsUnavailableException:
      raise ValidationError(
        'Unable to get %s render settings' % self._render_settings.get_renderer_name())

  @property
  def _is_output_enabled(self):
    return self._render_settings.get_renderer_name() == zync_c4d_constants.RendererNames.VRAY or \
           self._is_image_saving_enabled() or self._is_multipass_image_saving_enabled()

  def _is_image_saving_enabled(self):
    return self._render_settings.is_saving_globally_enabled() and \
           self._render_settings.is_image_saving_enabled()

  def _is_multipass_image_saving_enabled(self):
    return self._render_settings.is_saving_globally_enabled() and \
           self._render_settings.is_multipass_image_saving_enabled()

  def _maybe_update_multipass_image_params(self, params):
    if self._is_multipass_image_saving_enabled() and self._render_settings.get_renderer_name() != \
        zync_c4d_constants.RendererNames.VRAY:
      out_path = self.GetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'])
      params['multipass_output_dir'], params['multipass_output_name'] = self._split_output_path(
        out_path)
      try:
        params['format'] = self._render_settings.get_multipass_image_format()
      except C4dRenderFormatUnsupportedException as err:
        raise ValidationError(err.message)

  def _maybe_update_regular_image_params(self, params):
    if self._is_image_saving_enabled():
      out_path = self.GetString(SYMBOLS['OUTPUT_PATH'])
      params['output_dir'], params['output_name'] = self._split_output_path(out_path)
      try:
        params['format'] = self._render_settings.get_image_format()
      except C4dRenderFormatUnsupportedException as err:
        raise ValidationError(err.message)

  def _add_render_specific_params(self, params):
    if self._render_settings.get_renderer_name() == zync_c4d_constants.RendererNames.ARNOLD:
      arnold_settings = self._render_settings.get_arnold_settings()
      params['scene_info']['c4dtoa_version'] = arnold_settings.get_version()
      if arnold_settings.is_skip_license_check_enabled():
        raise ValidationError(
          'Please disable "Skip license check" in your '
          'Arnold settings to avoid rendering with a watermark.')
    elif self._render_settings.get_renderer_name() == zync_c4d_constants.RendererNames.REDSHIFT:
      params['scene_info'][
        'redshift_version'] = self._render_settings.get_redshift_settings().get_version()

  def _get_assets_and_presets(self):
    assets = self._scene_settings.get_all_assets()
    if assets is None:
      raise ValidationError(
        'Error:\n\nUnable to locate some assets. '
        'Please fix scene dependencies before submitting the job.\n\n'
        'Try going to Textures tab in Project Info and using '
        'Mark Missing Textures button to find possible problems.')
    asset_files = set()
    preset_files = set()
    preset_re = re.compile(r'preset://([^/]+)/')
    for asset in assets:
      match = preset_re.match(asset['filename'])
      if match:
        preset_pack = match.group(1)
        # preset path candidates:
        user_path = os.path.join(self._c4d_facade.get_user_library_path(), 'browser', preset_pack)
        glob_path = os.path.join(self._c4d_facade.get_library_path(), 'browser', preset_pack)
        if os.path.exists(user_path):
          preset_files.add(user_path)
        elif os.path.exists(glob_path):
          preset_files.add(glob_path)
        else:
          raise ValidationError('Unable to locate asset \'%s\'' % asset['filename'])
      else:
        asset_files.add(asset['filename'])
    self._add_ocio_assets(asset_files)
    return asset_files, preset_files

  def _add_ocio_assets(self, asset_files):
    if self._render_settings.get_renderer_name() == zync_c4d_constants.RendererNames.REDSHIFT:
      for ocio_config_path in self._render_settings.get_redshift_settings().get_ocio_config_paths():
        asset_files.update(zync.get_ocio_files(ocio_config_path))

  def _read_project_name(self):
    if self.GetBool(SYMBOLS['NEW_PROJ']):
      proj_name = self.GetString(SYMBOLS['NEW_PROJ_NAME'])
      proj_name = proj_name.strip()
      try:
        proj_name = str(proj_name)
      except ValueError:
        raise ValidationError('Project name \'%s\' contains illegal characters.' % proj_name)
      if re.search(r'[/\\]', proj_name):
        raise ValidationError('Project name \'%s\' contains illegal characters.' % proj_name)
      if proj_name == '':
        raise ValidationError('You must choose existing project or give valid name for a new one.')
      if proj_name in self.project_names:
        raise ValidationError('Project named \'%s\' already exists.' % proj_name)
      return proj_name
    else:
      return self._read_combobox_option(SYMBOLS['EXISTING_PROJ_NAME'], SYMBOLS['PROJ_NAME_OPTIONS'],
                                        self.project_names)

  def _read_combobox_option(self, widget_id, child_id_base, options):
    return options[self._read_combobox_index(widget_id, child_id_base)]

  def _read_combobox_index(self, widget_id, child_id_base):
    return self.GetLong(widget_id) - child_id_base
