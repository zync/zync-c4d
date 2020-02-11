""" Contains JobPresenter class. """
import os
import re
import traceback

import time
import webbrowser

from functools import partial

import plugin_version
import zync_c4d_constants
import zync_c4d_utils
from zync_c4d_pvm_consent_dialog import get_pvm_consent_from_the_user
from zync_c4d_render_settings import C4dRenderFormatUnsupportedException
from zync_c4d_render_settings import C4dRendererSettingsUnavailableException
from zync_c4d_utils import import_zync_module
from zync_c4d_vray_exporter import VRayExporter
from zync_c4d_vray_settings import C4dVrayVersionException

SYMBOLS = zync_c4d_constants.SYMBOLS
from zync_c4d_presenter import Presenter

zync = import_zync_module('zync')
zync_preflights = import_zync_module('zync_preflights')
common_preflights = import_zync_module('zync_preflights.common_checks')


class ValidationError(Exception):
  """ Error in user-specified parameters or scene settings. """


class JobPresenter(Presenter):
  """
  Implements presenter for job view.

  :param zync_c4d_dialog.ZyncDialog dialog:
  :param zync_c4d_main_presenter.MainPresenter main_presenter:
  :param zync.Zync zync_connection:
  :param dict[Any, Any] zync_cache:
  :param zync_c4d_scene_settings.C4dSceneSettings scene_settings:
  :param zync_c4d_facade.C4dFacade c4d_facade:
  :param zync_threading.default_hread_pool.DefaultThreadPool thread_pool:
  :param zync_threading.MainThreadExecutor main_thread_executor:
  """

  # list of widgets that should be disabled for upload only jobs
  RENDER_ONLY_SETTINGS = ['JOB_SETTINGS_G', 'VMS_SETTINGS_G', 'FRAMES_G',
                          'RENDER_G', 'TAKE']
  C4D_RENDERERS = [zync_c4d_constants.RendererNames.STANDARD,
                   zync_c4d_constants.RendererNames.PHYSICAL]
  SUPPORTED_RENDERERS = C4D_RENDERERS + [
      zync_c4d_constants.RendererNames.ARNOLD,
      zync_c4d_constants.RendererNames.REDSHIFT,
      zync_c4d_constants.RendererNames.VRAY
  ]

  def __init__(self, dialog, main_presenter, zync_connection, zync_cache,
      scene_settings, c4d_facade, thread_pool, main_thread_executor):
    self._dialog = dialog
    self._main_presenter = main_presenter
    self._zync_connection = zync_connection
    self._zync_cache = zync_cache
    self._scene_settings = scene_settings
    self._c4d_facade = c4d_facade
    self._thread_pool = thread_pool
    self._main_thread_executor = main_thread_executor
    self._available_instance_types = []
    self._project_list = []
    self._project_names = []
    self._all_take_settings = []
    self._file_boxes = []
    self._selected_take_settings = None
    self._render_settings = None

  def activate(self):
    """ Activates the job view. """
    self._dialog.load_layout('ZYNC_DIALOG')
    self._initialize_controls()

  def deactivate(self):
    """ Does nothing """
    pass

  def _initialize_controls(self):
    with self._dialog.change_menu():
      self._dialog.add_menu_entry('Logged in as %s' % self._zync_cache['email'])
      self._dialog.add_menu_entry('Log out', 'LOGOUT', 'Log out from Zync')

    self._available_instance_types = []

    # VMs settings
    self._dialog.set_int32('VMS_NUM', 1, min_value=1)

    # Storage settings (zync project)
    self._project_list = self._zync_connection.get_project_list()
    self._project_names = [project['name'] for project in self._project_list]
    project_name_hint = re.sub(r'\.c4d$', '',
                               self._scene_settings.get_scene_name())
    self._dialog.set_combobox_content('EXISTING_PROJ_NAME', self._project_names)
    self._dialog.set_string('NEW_PROJ_NAME', project_name_hint)
    if project_name_hint in self._project_names:
      self._enable_existing_project_widget()
      self._dialog.set_combobox_index('EXISTING_PROJ_NAME',
                                      + self._project_names.index(
                                          project_name_hint))
    else:
      self._enable_new_project_widget()

    # General job settings
    self._dialog.set_int32('JOB_PRIORITY', 50, min_value=0)
    self._dialog.set_string('OUTPUT_PATH', self._default_output_path())
    self._dialog.set_string('MULTIPASS_OUTPUT_PATH',
                            self._default_output_path('_multi'))

    # Renderer settings
    self._dialog.set_int32('CHUNK', 10, min_value=1)

    # File management
    self._dialog.set_bool('UPLOAD_ONLY', False)

    self._file_boxes = []
    self._update_file_checkboxes()

    # Take
    self._selected_take_settings = None
    self._recreate_take_list()

  def _default_output_path(self, suffix=''):
    return os.path.abspath(
        os.path.join(self._scene_settings.get_scene_path(), 'renders', '$take',
                     self._scene_settings.get_scene_name_without_extension() + suffix))

  def _update_file_checkboxes(self):
    with self._dialog.change_layout('FILES_LIST_GROUP'):
      for index, (path, checked, is_dir) in enumerate(self._file_boxes):
        self._dialog.add_checkbox_to_group('FILES_LIST_OPTIONS', path, index)
        self._dialog.set_group_bool('FILES_LIST_OPTIONS', checked, index)
        if is_dir:
          self._dialog.add_button_to_group('FILES_LIST_UNFOLD_BTNS', 'Unfold',
                                           index)
        else:
          self._dialog.add_filler()
    dirs_count = sum(int(is_dir) for (_, _, is_dir) in self._file_boxes)
    files_count = len(self._file_boxes) - dirs_count
    self._dialog.set_string('AUX_FILES_SUMMARY',
                            '%d files, %d folders' % (files_count, dirs_count))

  def _recreate_take_list(self):
    self._all_take_settings = self._scene_settings.get_all_take_settings()
    take_labels = [take_settings.get_indented_name() for take_settings in
                   self._all_take_settings]
    self._dialog.set_combobox_content('TAKE', take_labels)

    # set_combobox_content selected first entry, but we want to keep
    # previous selection if that take still exists:
    for i, take_settings in enumerate(self._all_take_settings):
      if take_settings == self._selected_take_settings:
        # Previously selected take found, select it again
        self._dialog.set_combobox_index('TAKE', i)
        return

    # Previously selected take not found, just switch to first one
    self._handle_take_change()

  def _handle_take_change(self):
    take_settings = self._dialog.get_combobox_option('TAKE',
                                                     self._all_take_settings)
    # TODO(grz): is this right way?
    if not take_settings.is_valid():
      self._c4d_facade.show_message_box(
          'Please load or create a scene with at least one valid take before using Zync plugin.')
      return
    self._selected_take_settings = take_settings
    self._render_settings = self._selected_take_settings.get_render_settings()
    previous_instance_type = self._get_previous_instance_type()
    self._update_renderer_and_available_instance_types()
    self._update_available_instance_types()
    if previous_instance_type:
      self._maybe_restore_previous_instance_type(previous_instance_type)
    self._update_price()
    self._update_resolution_controls()
    self._update_frame_range_controls()
    self._update_output_path_controls()
    self._update_multipass_output_path_controls()

  def _get_previous_instance_type(self):
    previous_instance_type = None
    if self._available_instance_types:
      previous_instance_type = self._dialog.get_combobox_option('VMS_TYPE',
                                                                self._available_instance_types)
    return previous_instance_type

  def _update_renderer_and_available_instance_types(self):
    renderer_name = self._render_settings.get_renderer_name()
    if renderer_name in self.SUPPORTED_RENDERERS:
      self._dialog.set_string('RENDERER', renderer_name)
      external_renderer = renderer_name
      if renderer_name in self.C4D_RENDERERS or renderer_name not in \
          self._zync_cache['instance_types']:
        external_renderer = None
      self._available_instance_types = self._zync_cache['instance_types'][
        external_renderer]
    else:
      self._dialog.set_string('RENDERER', renderer_name + ' (unsupported)')
      self._available_instance_types = []
    if renderer_name == zync_c4d_constants.RendererNames.VRAY:
      self._dialog.set_int32('CHUNK', 1)
      self._dialog.enable_widget('CHUNK', False)
    else:
      self._dialog.enable_widget('CHUNK', True)

  def _update_available_instance_types(self):
    if self._available_instance_types:
      instance_type_labels = [instance_type['label'] for instance_type in
                              self._available_instance_types]
    else:
      instance_type_labels = ['N/A']
    self._dialog.set_combobox_content('VMS_TYPE', instance_type_labels)

  def _maybe_restore_previous_instance_type(self, previous_instance_type):
    for i, instance_type in enumerate(self._available_instance_types):
      if instance_type['name'] == previous_instance_type['name']:
        self._dialog.set_combobox_index('VMS_TYPE', i)
        return

  def _update_price(self):
    if self._available_instance_types:
      instance_count = self._dialog.get_long('VMS_NUM')
      instance_type = self._dialog.get_combobox_option('VMS_TYPE',
                                                       self._available_instance_types)
      instance_cost = instance_type['cost']
      est_price = instance_count * instance_cost
      self._dialog.set_string('EST_PRICE',
                              'Estimated hour cost: $%.2f' % est_price)
    else:
      self._dialog.set_string('EST_PRICE', 'Estimated hour cost: N/A')

  def _update_resolution_controls(self):
    x, y = self._render_settings.get_resolution()
    self._dialog.set_int32('RES_X', x, min_value=1)
    self._dialog.set_int32('RES_Y', y, min_value=1)

  def _update_frame_range_controls(self):
    start_frame, end_frame, frame_step = self._render_settings.get_frame_range(
        self._scene_settings.get_fps())
    self._dialog.set_int32('FRAMES_FROM', start_frame, max_value=end_frame)
    self._dialog.set_int32('FRAMES_TO', end_frame, min_value=start_frame)
    self._dialog.set_int32('STEP', frame_step, min_value=1)

  def _update_output_path_controls(self, ):
    self._dialog.enable_widget('OUTPUT_PATH', self._is_image_saving_enabled())
    self._dialog.enable_widget('OUTPUT_PATH_BTN',
                               self._is_image_saving_enabled())
    if self._is_image_saving_enabled():
      if self._render_settings.has_image_path():
        output_path = os.path.join(self._scene_settings.get_scene_path(),
                                   self._render_settings.get_image_path())
        self._dialog.set_string('OUTPUT_PATH', output_path)
      else:
        self._dialog.set_string('OUTPUT_PATH', self._default_output_path())
    else:
      self._dialog.set_string('OUTPUT_PATH', 'Not enabled')

  def _update_multipass_output_path_controls(self):
    self._dialog.enable_widget('MULTIPASS_OUTPUT_PATH',
                               self._is_multipass_image_saving_enabled())
    self._dialog.enable_widget('MULTIPASS_OUTPUT_PATH_BTN',
                               self._is_multipass_image_saving_enabled())
    if self._is_multipass_image_saving_enabled():
      if self._render_settings.has_multipass_image_path():
        output_path = os.path.abspath(
          os.path.join(self._scene_settings.get_scene_path(),
                       self._render_settings.get_multipass_image_path()))
        self._dialog.set_string('MULTIPASS_OUTPUT_PATH', output_path)
      else:
        self._dialog.set_string('MULTIPASS_OUTPUT_PATH',
                                self._default_output_path('_multi'))
    else:
      self._dialog.set_string('MULTIPASS_OUTPUT_PATH', 'Not enabled')

  def _is_image_saving_enabled(self):
    return self._render_settings.is_saving_globally_enabled() and \
           self._render_settings.is_image_saving_enabled()

  def _is_multipass_image_saving_enabled(self):
    return self._render_settings.is_saving_globally_enabled() and \
           self._render_settings.is_multipass_image_saving_enabled()

  def on_scene_changed(self):
    """ Called when C4D scene is changed to a different scene. """
    self._main_presenter.reload_job_view()

  def on_command(self, command_id):
    """
    Called when user interacts with a dialog widget.

    :param int command_id: Id of the widget.
    """
    if command_id == SYMBOLS['LOGOUT']:
      self._on_logout_clicked()
    elif command_id == SYMBOLS['COST_CALC_LINK']:
      self._on_calculate_cost_clicked()
    elif command_id == SYMBOLS['VMS_NUM']:
      self._on_instance_count_changed()
    elif command_id == SYMBOLS['VMS_TYPE']:
      self._on_instance_type_changed()
    elif command_id == SYMBOLS['FILES_LIST']:
      self._on_select_extra_files_clicked()
    elif command_id == SYMBOLS['ADD_FILE']:
      self._on_add_file_clicked()
    elif command_id == SYMBOLS['ADD_DIR']:
      self._on_add_directory_clicked()
    elif command_id == SYMBOLS['OK_FILES']:
      self._on_select_extra_files_closed()
    elif command_id == SYMBOLS['OUTPUT_PATH_BTN']:
      self._on_enter_output_path_clicked()
    elif command_id == SYMBOLS['MULTIPASS_OUTPUT_PATH_BTN']:
      self._on_enter_multipass_output_path_clicked()
    elif command_id == SYMBOLS['FRAMES_FROM']:
      self._on_start_frame_changed()
    elif command_id == SYMBOLS['FRAMES_TO']:
      self._on_end_frame_changed()
    elif command_id == SYMBOLS['EXISTING_PROJ_NAME']:
      self._on_existing_project_name_selected()
    elif command_id == SYMBOLS['NEW_PROJ_NAME']:
      self._on_new_project_name_selected()
    elif command_id == SYMBOLS['UPLOAD_ONLY']:
      self._on_upload_only_changed()
    elif command_id == SYMBOLS['TAKE']:
      self._on_take_changed()
    elif SYMBOLS['FILES_LIST_UNFOLD_BTNS'] <= command_id < SYMBOLS[
      'FILES_LIST_UNFOLD_BTNS'] + 10000:
      self._on_unfold_directory_clicked(
          command_id - SYMBOLS['FILES_LIST_UNFOLD_BTNS'])
    elif command_id == SYMBOLS['LAUNCH']:
      self._maybe_launch_job()

  def _on_logout_clicked(self):
    """
    Called when user clicks logout button.

    Switches back to login view.
    """
    self._main_presenter.log_out()

  @staticmethod
  def _on_calculate_cost_clicked():
    """ Called when user clicks 'calculate cost' link. """
    webbrowser.open('http://zync.cloudpricingcalculator.appspot.com')

  def _on_instance_count_changed(self):
    """ Called when user changes instance count. """
    self._update_price()

  def _on_instance_type_changed(self):
    """ Called when user changes instance type. """
    self._update_price()

  def _on_select_extra_files_clicked(self):
    """ Called when user clicks 'select extra files' button. """
    self._update_file_checkboxes()
    self._dialog.switch_tab('FILES_TAB')

  def _on_select_extra_files_closed(self):
    """ Called when user clicks ok in 'select extra files' tab. """
    self._read_file_checkboxes()
    self._dialog.switch_tab('SETTINGS_TAB')

  def _on_add_file_clicked(self):
    """ Called when user clicks 'add file' button. """
    self._add_file()

  def _on_add_directory_clicked(self):
    """ Called when user clicks 'add directory' button. """
    self._add_file(directory=True)

  def _add_file(self, directory=False):
    self._read_file_checkboxes()
    path = self._c4d_facade.show_load_dialog(directory)
    if path is not None:
      self._file_boxes.append((path, True, directory))
      self._update_file_checkboxes()

  def _read_file_checkboxes(self):
    self._file_boxes = [
        (path, self._dialog.get_group_bool('FILES_LIST_OPTIONS', index), is_dir)
        for index, (path, _, is_dir) in enumerate(self._file_boxes)
    ]

  def _on_enter_output_path_clicked(self):
    """ Called when user clicks 'enter output path' button. """
    self._prompt_path_and_update_widget('OUTPUT_PATH',
                                        'Set regular image output path...')

  def _on_enter_multipass_output_path_clicked(self):
    """ Called when user clicks 'enter multipass output path' button. """
    self._prompt_path_and_update_widget('MULTIPASS_OUTPUT_PATH',
                                        'Set multi-pass image output path...')

  def _prompt_path_and_update_widget(self, widget_name, prompt_text):
    old_output = self._dialog.get_string(widget_name)
    new_output = self._c4d_facade.show_save_dialog(prompt_text, old_output)
    if new_output:
      self._dialog.set_string(widget_name, new_output)

  def _on_start_frame_changed(self):
    """ Called when user changes 'start frame' field. """
    self._dialog.set_int32(
        'FRAMES_TO',
        self._dialog.get_int32('FRAMES_TO'),
        min_value=self._dialog.get_int32('FRAMES_FROM'))

  def _on_end_frame_changed(self):
    """ Called when user changes 'end frame' field. """
    self._dialog.set_int32(
        'FRAMES_FROM',
        self._dialog.get_int32('FRAMES_FROM'),
        max_value=self._dialog.get_int32('FRAMES_TO'))

  def _on_existing_project_name_selected(self):
    """ Called when user selects 'existing project name' radio. """
    self._enable_existing_project_widget()

  def _on_new_project_name_selected(self):
    """ Called when user selects 'new project name' radio. """
    self._enable_new_project_widget()

  def _enable_existing_project_widget(self):
    self._dialog.set_bool('NEW_PROJ', False)
    self._dialog.set_bool('EXISTING_PROJ', True)

  def _enable_new_project_widget(self):
    self._dialog.set_bool('EXISTING_PROJ', False)
    self._dialog.set_bool('NEW_PROJ', True)

  def _on_upload_only_changed(self):
    """ Called when user changes 'upload only' checkbox. """
    upload_only = self._dialog.get_bool('UPLOAD_ONLY')
    for item_name in self.RENDER_ONLY_SETTINGS:
      self._dialog.enable_widget(item_name, not upload_only)

  def _on_take_changed(self):
    """ Called when user changes 'take' combo. """
    self._handle_take_change()

  def _on_unfold_directory_clicked(self, dir_index):
    """
    Called when user clicks 'unfold' button for a directory.

    :param int dir_index: Index of the directory to unfold, in the order
    as it appears in the GUI.
    """
    self._read_file_checkboxes()

    def _generate_new_fboxes(file_boxes):
      for i in xrange(dir_index):
        yield file_boxes[i]

      dir_path, _checked, _is_dir = file_boxes[dir_index]
      for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        if os.path.isfile(file_path):
          yield (file_path, True, False)
        elif os.path.isdir(file_path):
          yield (file_path, True, True)

      for i in xrange(dir_index + 1, len(file_boxes)):
        yield file_boxes[i]

    new_file_boxes = list(_generate_new_fboxes(self._file_boxes))
    self._file_boxes = new_file_boxes
    self._update_file_checkboxes()

  def _maybe_launch_job(self):
    if not self._ensure_scene_saved():
      return
    try:
      params = self._collect_params()
    except ValidationError as err:
      self._c4d_facade.show_message_box(err.message)
    else:
      if ('PREEMPTIBLE' in params[
        'instance_type']) and not get_pvm_consent_from_the_user():
        return
      if '(ALPHA)' in params[
        'instance_type'] and not self._get_alpha_consent_from_the_user():
        return
      if self._zync_connection.is_experiment_enabled('EXPERIMENT_PREFLIGHTS'):
        self._run_preflights(params)
      else:
        self._launch_job(params)

  def _get_alpha_consent_from_the_user(self):
    return self._c4d_facade.show_question_dialog(
        'You\'ve selected an instance type for your job which is '
        'still in alpha, and could be unstable for some workloads.\n\n'
        'Submit the job anyway?')

  def _launch_job(self, params):
    try:
      if self._render_settings.get_renderer_name() == zync_c4d_constants.RendererNames.VRAY:
        self._start_vray_job_submission(params)
      else:
        self._submit_c4d_job(params)
    except ValidationError as err:
      self._c4d_facade.show_message_box(err.message)

  def _run_preflights(self, params):
    def _on_status_change(preflight_check, status):
      print 'Preflight Check Status Change ', preflight_check.preflight_name, ' ---> ', status

    def _on_result(result):
      print 'Preflight Check Result ', result

    preflights = [
        common_preflights.DependencyCheck(params['scene_info']['dependencies'],
                                          _on_result)]
    _on_finished = partial(self._launch_job, params)
    suite = zync_preflights.PreflightCheckSuite(self._thread_pool,
                                                self._thread_pool.create_lock(),
                                                _on_status_change, _on_finished,
                                                preflights)
    suite.start()

  def _show_job_successfuly_submitted_dialog(self):
    self._c4d_facade.show_message_box(
        'Job submitted!\n\nYou can check the status of job in Zync console.\n\n'
        'Don\'t turn off the client app before upload is complete.')

  def _submit_c4d_job(self, params):
    # TODO: Make it async, also: async calls should disable UI
    try:
      doc_dirpath = self._scene_settings.get_scene_path()
      doc_name = self._scene_settings.get_scene_name()
      doc_path = os.path.join(doc_dirpath, doc_name)
      self._zync_connection.submit_job('c4d', doc_path, params)
      self._show_job_successfuly_submitted_dialog()
    except (zync.ZyncPreflightError, zync.ZyncError) as err:
      self._c4d_facade.show_message_box('{0}:\n\n{1}', err.__class__.__name__, zync_c4d_utils.to_unicode(err))
    except:
      self._c4d_facade.show_message_box('Unexpected error during job submission')
      zync_c4d_utils.post_plugin_error(traceback.format_exc())

  def _start_vray_job_submission(self, params):
    print 'Vray job, collecting additional info...'

    if self._is_image_saving_enabled() and self._is_multipass_image_saving_enabled():
      if not self._render_settings.is_multipass_image_format_same_as_regular():
        self._c4d_facade.show_message_box(
            'WARNING: Regular output format is different than multipass output format. '
            'Vray jobs support only one output format. Regular output format will be used.'
        )
      if self._dialog.get_string('OUTPUT_PATH') != self._dialog.get_string(
          'MULTIPASS_OUTPUT_PATH'):
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
      output_path = self._dialog.get_string('OUTPUT_PATH')
    output_path = self._render_settings.convert_tokens(output_path)
    print 'output_path: %s' % output_path
    params['output_dir'], params['output_name'] = self._split_output_path(
        output_path)
    params['scene_info'][
      'camera'] = self._selected_take_settings.get_camera_name()
    doc_dirpath = self._scene_settings.get_scene_path()
    doc_name = self._scene_settings.get_scene_name()
    path = os.path.join(doc_dirpath, '__zync', str(time.time()))
    if not os.path.exists(path):
      os.makedirs(path)
    vrscene_path = os.path.join(path, os.path.splitext(doc_name)[0])
    vrscene_exporter = VRayExporter(self._main_thread_executor, vrscene_path,
                                    params,
                                    self._scene_settings, self._render_settings,
                                    lambda: self._send_vray_scene(vrscene_path,
                                                                  params))
    self._thread_pool.add_task(vrscene_exporter)

  def _send_vray_scene(self, vrscene_path, params):
    try:
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
      self._zync_connection.submit_job('c4d_vray', vrscene, params=render_params)
      self._show_job_successfuly_submitted_dialog()
    except (zync.ZyncPreflightError, zync.ZyncError) as err:
      self._c4d_facade.show_message_box('{0}:\n\n{1}', err.__class__.__name__, zync_c4d_utils.to_unicode(err))
    except:
      self._c4d_facade.show_message_box('Unexpected error during job submission')
      zync_c4d_utils.post_plugin_error(traceback.format_exc())

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
      if renderer_name not in self.SUPPORTED_RENDERERS:
        raise ValidationError(
            'Renderer \'%s\' is not currently supported by Zync' % renderer_name)
      params['renderer'] = renderer_name
      params['plugin_version'] = plugin_version.__version__
      params['take'] = self._selected_take_settings.get_take_name()
      params['num_instances'] = self._dialog.get_long('VMS_NUM')
      if self._available_instance_types:
        params['instance_type'] = \
          self._dialog.get_combobox_option('VMS_TYPE',
                                           self._available_instance_types)[
            'name']
      else:
        raise ValidationError('No machine type available for this type of job')

      params['proj_name'] = self._read_project_name()
      params['job_subtype'] = 'render'
      params['priority'] = self._dialog.get_long('JOB_PRIORITY')
      params['notify_complete'] = int(self._dialog.get_bool('NOTIFY_COMPLETE'))
      params['upload_only'] = int(self._dialog.get_bool('UPLOAD_ONLY'))

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

      params['frame_begin'] = self._dialog.get_int32('FRAMES_FROM')
      params['frame_end'] = self._dialog.get_int32('FRAMES_TO')
      params['step'] = str(self._dialog.get_int32('STEP'))
      params['chunk_size'] = str(self._dialog.get_int32('CHUNK'))
      params['xres'] = str(self._dialog.get_int32('RES_X'))
      params['yres'] = str(self._dialog.get_int32('RES_Y'))
      user_files = [path for (path, checked, _) in self._file_boxes if checked]
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

  def _maybe_update_multipass_image_params(self, params):
    if self._is_multipass_image_saving_enabled() and self._render_settings.get_renderer_name() != \
        zync_c4d_constants.RendererNames.VRAY:
      out_path = self._dialog.get_string('MULTIPASS_OUTPUT_PATH')
      params['multipass_output_dir'], params[
        'multipass_output_name'] = self._split_output_path(
          out_path)
      try:
        params['format'] = self._render_settings.get_multipass_image_format()
      except C4dRenderFormatUnsupportedException as err:
        raise ValidationError(err.message)

  def _maybe_update_regular_image_params(self, params):
    if self._is_image_saving_enabled():
      out_path = self._dialog.get_string('OUTPUT_PATH')
      params['output_dir'], params['output_name'] = self._split_output_path(
          out_path)
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
        user_path = os.path.join(self._c4d_facade.get_user_library_path(),
                                 'browser', preset_pack)
        glob_path = os.path.join(self._c4d_facade.get_library_path(), 'browser',
                                 preset_pack)
        if os.path.exists(user_path):
          preset_files.add(user_path)
        elif os.path.exists(glob_path):
          preset_files.add(glob_path)
        else:
          raise ValidationError(
              'Unable to locate asset \'%s\'' % asset['filename'])
      else:
        asset_files.add(asset['filename'])
    self._add_ocio_assets(asset_files)
    return asset_files, preset_files

  def _add_ocio_assets(self, asset_files):
    if self._render_settings.get_renderer_name() == zync_c4d_constants.RendererNames.REDSHIFT:
      for ocio_config_path in self._render_settings.get_redshift_settings().get_ocio_config_paths():
        asset_files.update(zync.get_ocio_files(ocio_config_path))

  def _read_project_name(self):
    if self._dialog.get_bool('NEW_PROJ'):
      proj_name = self._dialog.get_string('NEW_PROJ_NAME')
      proj_name = proj_name.strip()
      try:
        proj_name = str(proj_name)
      except ValueError:
        raise ValidationError(
            'Project name \'%s\' contains illegal characters.' % proj_name)
      if re.search(r'[/\\]', proj_name):
        raise ValidationError(
            'Project name \'%s\' contains illegal characters.' % proj_name)
      if proj_name == '':
        raise ValidationError(
            'You must choose existing project or give valid name for a new one.')
      if proj_name in self._project_names:
        raise ValidationError(
            'Project named \'%s\' already exists.' % proj_name)
      return proj_name
    else:
      return self._dialog.get_combobox_option('EXISTING_PROJ_NAME',
                                              self._project_names)
