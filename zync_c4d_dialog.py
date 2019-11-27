""" Contains main dialog used in Zync plugins. """
from importlib import import_module
import glob
import re
import webbrowser
import os
import time
import traceback

import zync_c4d_constants
from zync_c4d_pvm_consent_dialog import PvmConsentDialog
from zync_c4d_utils import show_exceptions, import_zync_module, init_c4d_resources
from zync_c4d_vray_exporter import VRayExporter
SYMBOLS = zync_c4d_constants.SYMBOLS

c4d = import_module('c4d')
zync = import_zync_module('zync')
zync_threading = import_zync_module('zync_threading')
default_thread_pool = import_zync_module('zync_threading.default_thread_pool')

__res__ = init_c4d_resources()

def _get_vray_render_settings():
  """
  Returns the first found V-Ray render settings.

  :raises:
    zync.ZyncError: if V-Ray render settings are not found.
  :return c4d.documents.BaseVideoPost:
  """
  for video_post in _generate_render_settings([zync_c4d_constants.VRAY_BRIDGE_PLUGIN_ID]):
    return video_post
  raise zync.ZyncError('Unable to get V-Ray render settings')


def _get_arnold_render_settings():
  """
  Returns the first found Arnold render settings.

  :raises:
    zync.ZyncError: if Arnold render settings are not found.
  :return c4d.documents.BaseVideoPost:
  """
  for video_post in _generate_render_settings([zync_c4d_constants.ARNOLD_RENDERER]):
    return video_post
  raise zync.ZyncError('Unable to get Arnold render settings')


def _generate_redshift_render_settings():
  """
  Generates Redshift render settings.

  :return collections.Iterable[c4d.documents.BaseVideoPost]:
  """
  return _generate_render_settings(zync_c4d_constants.REDSHIFT_VIDEOPOSTS)


def _generate_render_settings(video_post_types):
  """
  Generates render settings of specified types.

  :param collections.Iterable[int] video_post_types: collection of video post types.
  :return collections.Iterable[c4d.documents.BaseVideoPost]:
  """
  rdata = c4d.documents.GetActiveDocument().GetActiveRenderData()
  video_post = rdata.GetFirstVideoPost()
  while video_post:
    if video_post.GetType() in video_post_types:
      yield video_post
    video_post = video_post.GetNext()


class ValidationError(Exception):
  """ Error in user-specified parameters or scene settings. """


class ZyncDialog(zync_threading.AsyncCaller, c4d.gui.GeDialog):
  """
  Implements the main dialog window of Zync plugin.
  """

  RDATA_RENDERENGINE_ARNOLD = 1029988
  RDATA_RENDERENGINE_REDSHIFT = 1036219
  RDATA_RENDERENGINE_VRAY = zync_c4d_constants.VRAY_BRIDGE_PLUGIN_ID

  c4d_renderers = [c4d.RDATA_RENDERENGINE_STANDARD, c4d.RDATA_RENDERENGINE_PHYSICAL]
  supported_renderers = c4d_renderers + [RDATA_RENDERENGINE_ARNOLD, RDATA_RENDERENGINE_VRAY,
                                         RDATA_RENDERENGINE_REDSHIFT]

  renderer_name_map = {c4d.RDATA_RENDERENGINE_STANDARD: 'Standard',
                       c4d.RDATA_RENDERENGINE_PREVIEWHARDWARE: 'Hardware',
                       c4d.RDATA_RENDERENGINE_PHYSICAL: 'Physical',
                       c4d.RDATA_RENDERENGINE_CINEMAN: 'Cineman',
                       RDATA_RENDERENGINE_ARNOLD: 'Arnold', RDATA_RENDERENGINE_VRAY: 'V-Ray',
                       RDATA_RENDERENGINE_REDSHIFT: 'Redshift', }

  supported_oformats = {c4d.FILTER_B3D: 'B3D', c4d.FILTER_BMP: 'BMP', c4d.FILTER_DPX: 'DPX',
                        c4d.FILTER_EXR: 'EXR', c4d.FILTER_HDR: 'HDR', c4d.FILTER_IFF: 'IFF',
                        c4d.FILTER_JPG: 'JPG', c4d.FILTER_PICT: 'PICT', c4d.FILTER_PNG: 'PNG',
                        c4d.FILTER_PSB: 'PSB', c4d.FILTER_PSD: 'PSD', c4d.FILTER_RLA: 'RLA',
                        c4d.FILTER_RPF: 'RPF', c4d.FILTER_TGA: 'TGA', c4d.FILTER_TIF: 'TIFF', }

  supported_vray_oformats = {
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

  # list of widgets that should be disabled for upload only jobs
  render_only_settings = ['JOB_SETTINGS_G', 'VMS_SETTINGS_G', 'FRAMES_G', 'RENDER_G', 'TAKE']

  def __init__(self, version):

    self._thread_pool = default_thread_pool.DefaultThreadPool(error_handler=self._handle_background_task_error)
    self._main_thread_executor = zync_threading.MainThreadExecutor(self._thread_pool, self._push_special_event, self._push_special_event)
    super(ZyncDialog, self).__init__(self._thread_pool, self._thread_pool.create_lock(), self._main_thread_executor)
    self._version = version
    self.logged_out = True
    self.logged_in = False
    self.auto_login = True
    self.document = None
    self.take_labels = None
    self.regular_image_save_enabled = None
    self.available_instance_types = None
    self.render_data = None
    self.project_names = None
    self.take_names = None
    self.renderer_name = None
    self.renderer = None
    self.take = None
    self.multipass_image_save_enabled = None
    self.file_boxes = None
    self.takes = None
    self.project_list = None
    self.pvm_consent_dialog = None

  @staticmethod
  def _push_special_event():
    c4d.SpecialEventAdd(zync_c4d_constants.PLUGIN_ID)

  @staticmethod
  def _handle_background_task_error(task_name, exception, traceback_str):
    print 'Exception ', exception, 'in task ', task_name
    print 'Traceback: ', traceback_str

  @staticmethod
  def _handle_submission_error(exception, traceback_str):
    print 'Submission error: ', exception
    print 'Traceback: ', traceback_str
    if isinstance(exception, zync.ZyncPreflightError) or isinstance(exception, zync.ZyncError):
      c4d.gui.MessageDialog('%s:\n\n%s' % (exception.__class__.__name__, unicode(exception)))
    else:
      c4d.gui.MessageDialog('Unexpected error during job submission')
    return True

  @show_exceptions
  def CoreMessage(self, msg_id, msg):
    """
    Handles C4D core messages.
    """
    if msg_id == c4d.EVMSG_CHANGE:
      self._handle_document_change()
    elif msg_id == zync_c4d_constants.PLUGIN_ID:
      self._main_thread_executor.maybe_execute_action()
    return super(ZyncDialog, self).CoreMessage(msg_id, msg)

  @show_exceptions
  def CreateLayout(self):
    """
    Creates UI controls.
    """
    self.GroupBegin(SYMBOLS['DIALOG_TOP_GROUP'],
                    c4d.BFH_SCALEFIT & c4d.BFV_SCALEFIT, 1)
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

  @staticmethod
  def _get_redshift_version():
    try:
      redshift = import_module('redshift')
      return redshift.GetCoreVersion()
    except (ImportError, AttributeError):
      print 'Error getting RedShift version, assuming <2.6.23'
      traceback.print_exc()
      return '2.6.0'

  @staticmethod
  def _get_c4dtoa_version():
    document = c4d.documents.GetActiveDocument()
    arnold_hook = document.FindSceneHook(zync_c4d_constants.ARNOLD_SCENE_HOOK)
    if arnold_hook is None:
      return ""

    msg = c4d.BaseContainer()
    msg.SetInt32(zync_c4d_constants.C4DTOA_MSG_TYPE, zync_c4d_constants.C4DTOA_MSG_GET_VERSION)
    arnold_hook.Message(c4d.MSG_BASECONTAINER, msg)
    return msg.GetString(zync_c4d_constants.C4DTOA_MSG_RESP1)

  def Open(self, *args, **kwargs):
    """
    Opens the dialog window.
    """
    self.document = c4d.documents.GetActiveDocument()
    return super(ZyncDialog, self).Open(*args, **kwargs)

  @show_exceptions
  def Close(self):
    """
    Closes the dialog window.
    """
    self.interrupt_all_async_calls()
    return super(ZyncDialog, self).Close()

  def _login(self):
    self._connect_to_zync()
    self._load_layout('CONN_DIALOG')

  def _on_connected(self, connection):
    self.zync_conn = connection
    self._fetch_available_settings()

  def _on_login_fail(self, _exception):
    self._logout()

  @zync_threading.AsyncCaller.async_call(_on_connected, _on_login_fail)
  def _connect_to_zync(self):
    return zync.Zync(application='c4d')

  def _on_fetched(self, zync_cache):
    self.zync_cache = zync_cache
    self._load_layout('ZYNC_DIALOG')
    self.logged_in = True
    self._initialize_controls()

  @zync_threading.AsyncCaller.async_call(_on_fetched, _on_login_fail)
  def _fetch_available_settings(self):
    return dict(
      instance_types={
        external_renderer: self._get_instance_types(
          external_renderer)
        for external_renderer in
        [None, self.RDATA_RENDERENGINE_ARNOLD,
         self.RDATA_RENDERENGINE_REDSHIFT]
      },
      email=self.zync_conn.email,
      project_name_hint=self.zync_conn.get_project_name(
        c4d.documents.GetActiveDocument().GetDocumentName()),
    )

  def _get_instance_types(self, renderer_id):
    renderer_name = self._get_renderer_name(renderer_id)
    instance_types_dict = self.zync_conn.get_instance_types(
      renderer=renderer_name,
      usage_tag='c4d_redshift' if renderer_id == self.RDATA_RENDERENGINE_REDSHIFT else None)

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
    document = c4d.documents.GetActiveDocument()

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
    self.project_names = [p['name'] for p in self.project_list]
    project_name_hint = re.sub(r'\.c4d$', '', document.GetDocumentName())
    self._set_combobox_content(SYMBOLS['EXISTING_PROJ_NAME'],
                               SYMBOLS['PROJ_NAME_OPTIONS'],
                               self.project_names)
    self.SetString(SYMBOLS['NEW_PROJ_NAME'], project_name_hint)
    if project_name_hint in self.project_names:
      self._enable_existing_project_widget()
      self.SetInt32(SYMBOLS['EXISTING_PROJ_NAME'],
                    SYMBOLS['PROJ_NAME_OPTIONS'] + self.project_names.index(
                      project_name_hint))
    else:
      self._enable_new_project_widget()

    # General job settings
    self.SetInt32(SYMBOLS['JOB_PRIORITY'], 50, min=0)
    self.SetString(SYMBOLS['OUTPUT_PATH'], self._default_output_path())
    self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'],
                   self._default_multipass_output_path())

    # Renderer settings
    self.SetInt32(SYMBOLS['CHUNK'], 10, min=1)

    # File management
    self.SetBool(SYMBOLS['UPLOAD_ONLY'], False)

    self.file_boxes = []
    self._update_file_checkboxes()

    # Take
    self.take = None
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

  @staticmethod
  def _default_output_path():
    document = c4d.documents.GetActiveDocument()
    return os.path.abspath(os.path.join(document.GetDocumentPath(),
                                        'renders', '$take',
                                        re.sub(r'\.c4d$', '',
                                               document.GetDocumentName())))

  @staticmethod
  def _default_multipass_output_path():
    document = c4d.documents.GetActiveDocument()
    return os.path.abspath(os.path.join(document.GetDocumentPath(),
                                        'renders', '$take',
                                        re.sub(r'\.c4d$', '',
                                               document.GetDocumentName()) + '_multi'))

  def _handle_document_change(self):
    # Reinitialize dialog in case active document was changed.
    # TODO: change launch button if document is in dirty state?
    document = c4d.documents.GetActiveDocument()
    if self.logged_in:
      try:
        # comparison may fail with ReferenceError if old scene object
        # is already dead
        doc_switched = (self.document != document or
                        self.document.GetDocumentPath() != document.GetDocumentPath())
      except ReferenceError:
        doc_switched = True
      if doc_switched:
        self.document = document
        self._initialize_controls()
      else:
        # The active document is still the same one, but it could have
        # been changed
        self._recreate_take_list()
        # TODO:
        # We could add support for render data changes, project info changes

  def _recreate_take_list(self):
    self.take_names, self.take_labels, self.takes = self._collect_takes()
    self._set_combobox_content(SYMBOLS['TAKE'],
                               SYMBOLS['TAKE_OPTIONS'],
                               self.take_labels)

    # _set_combobox_content selected first entry, but we want to keep
    # previous selection if that take still exists:
    for i, take in enumerate(self.takes):
      if take == self.take:
        # Previously selected take found, select it again
        self.SetInt32(SYMBOLS['TAKE'], SYMBOLS['TAKE_OPTIONS'] + i)
        return

    # Previously selected take not found, just switch to first one
    self._handle_take_change()

  @staticmethod
  def _collect_takes():
    """
    Collects all takes in scene

    Returns:
      ([str], [str], [BaseTake]): list of names, list of labels, list of takes

    Labels are names preceded with indentation creating tree layout.
    All lists are in the same order.
    """
    take_names = []
    take_labels = []
    takes = []

    def _traverse(take, depth):
      take_names.append(take.GetName())
      take_labels.append(depth * '   ' + take.GetName())
      takes.append(take)
      for child in take.GetChildren():
        _traverse(child, depth + 1)

    _traverse(c4d.documents.GetActiveDocument().GetTakeData().GetMainTake(),
              0)
    return take_names, take_labels, takes

  def _get_renderer_name(self, renderer_id):
    """Returns Zync renderer name given C4D renderer ID"""
    if renderer_id in self.renderer_name_map:
      return self.renderer_name_map[renderer_id]
    elif not renderer_id:
      return None
    renderer_plugin = c4d.plugins.FindPlugin(renderer_id)
    return renderer_plugin.GetName() if renderer_plugin else str(renderer_id)

  def _handle_take_change(self):
    document = c4d.documents.GetActiveDocument()
    self.take = self._read_combobox_option(SYMBOLS['TAKE'],
                                           SYMBOLS['TAKE_OPTIONS'],
                                           self.takes)
    if not self.take.GetEffectiveRenderData(document.GetTakeData()):
      c4d.gui.MessageDialog(
        'Please load or create a scene with at least one valid take before using Zync '
        'plugin.')
      return
    self.render_data = self.take.GetEffectiveRenderData(document.GetTakeData())[0]
    previous_instance_type = self._save_previous_instance_type()
    self._update_renderer_and_available_instance_types(document)
    self._update_available_instance_types()
    self._maybe_restore_previous_instance_type(previous_instance_type)
    self._update_price()
    self._update_resolution_controls()
    self._update_frame_range_controls(document)
    self._update_output_path_controls(document)
    self._update_multipass_output_path_controls(document)

  def _update_renderer_and_available_instance_types(self, document):
    self.renderer = \
      self.take.GetEffectiveRenderData(document.GetTakeData())[0][
        c4d.RDATA_RENDERENGINE]
    self.renderer_name = self._get_renderer_name(self.renderer)
    if self.renderer in self.supported_renderers:
      self.SetString(SYMBOLS['RENDERER'], self.renderer_name)
      external_renderer = self.renderer
      if self.renderer in self.c4d_renderers or self.renderer not in self.zync_cache[
        'instance_types']:
        external_renderer = None
      self.available_instance_types = self.zync_cache['instance_types'][
        external_renderer]
    else:
      self.SetString(SYMBOLS['RENDERER'],
                     self.renderer_name + ' (unsupported)')
      self.available_instance_types = []
    if self.renderer == self.RDATA_RENDERENGINE_VRAY:
      self.SetInt32(SYMBOLS['CHUNK'], 1)
      self.Enable(SYMBOLS['CHUNK'], 0)

  def _save_previous_instance_type(self):
    previous_instance_type = None
    if getattr(self, 'available_instance_types', None):
      previous_instance_type = self._read_combobox_option(
        SYMBOLS['VMS_TYPE'],
        SYMBOLS['VMS_TYPE_OPTIONS'],
        self.available_instance_types)
    return previous_instance_type

  def _update_available_instance_types(self):
    if self.available_instance_types:
      instance_type_labels = [instance_type['label']
                              for instance_type
                              in self.available_instance_types]
    else:
      instance_type_labels = ['N/A']
    self._set_combobox_content(SYMBOLS['VMS_TYPE'],
                               SYMBOLS['VMS_TYPE_OPTIONS'],
                               instance_type_labels)

  def _maybe_restore_previous_instance_type(self, previous_instance_type):
    if previous_instance_type:
      for i, instance_type in enumerate(self.available_instance_types):
        if instance_type['name'] == previous_instance_type['name']:
          self.SetInt32(SYMBOLS['VMS_TYPE'], SYMBOLS['VMS_TYPE_OPTIONS'] + i)

  def _update_resolution_controls(self):
    self.SetInt32(SYMBOLS['RES_X'], self.render_data[c4d.RDATA_XRES], min=1)
    self.SetInt32(SYMBOLS['RES_Y'], self.render_data[c4d.RDATA_YRES], min=1)

  def _update_frame_range_controls(self, document):
    fps = document.GetFps()
    start_frame = self.render_data[c4d.RDATA_FRAMEFROM].GetFrame(fps)
    end_frame = self.render_data[c4d.RDATA_FRAMETO].GetFrame(fps)
    self.SetInt32(SYMBOLS['FRAMES_FROM'], start_frame, max=end_frame)
    self.SetInt32(SYMBOLS['FRAMES_TO'], end_frame, min=start_frame)
    self.SetInt32(SYMBOLS['STEP'], self.render_data[c4d.RDATA_FRAMESTEP], min=1)

  def _update_output_path_controls(self, document):
    self.regular_image_save_enabled = self.render_data[c4d.RDATA_GLOBALSAVE] and \
                                      self.render_data[c4d.RDATA_SAVEIMAGE]
    self.Enable(SYMBOLS['OUTPUT_PATH'], int(self.regular_image_save_enabled))
    self.Enable(SYMBOLS['OUTPUT_PATH_BTN'], int(self.regular_image_save_enabled))
    if self.regular_image_save_enabled:
      if self.render_data[c4d.RDATA_PATH]:
        self.SetString(SYMBOLS['OUTPUT_PATH'], os.path.join(
          document.GetDocumentPath(),
          self.render_data[c4d.RDATA_PATH]))
      else:
        self.SetString(SYMBOLS['OUTPUT_PATH'],
                       self._default_output_path())
    else:
      self.SetString(SYMBOLS['OUTPUT_PATH'], 'Not enabled')

  def _update_multipass_output_path_controls(self, document):
    # Multi-pass image output path
    self.multipass_image_save_enabled = self.render_data[c4d.RDATA_GLOBALSAVE] and \
                                        self.render_data[c4d.RDATA_MULTIPASS_SAVEIMAGE] and \
                                        self.render_data[c4d.RDATA_MULTIPASS_ENABLE]
    self.Enable(SYMBOLS['MULTIPASS_OUTPUT_PATH'],
                int(self.multipass_image_save_enabled))
    self.Enable(SYMBOLS['MULTIPASS_OUTPUT_PATH_BTN'],
                int(self.multipass_image_save_enabled))
    if self.multipass_image_save_enabled:
      if self.render_data[c4d.RDATA_MULTIPASS_FILENAME]:
        self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'],
                       os.path.abspath(os.path.join(
                         document.GetDocumentPath(),
                         self.render_data[
                           c4d.RDATA_MULTIPASS_FILENAME])))
      else:
        self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'],
                       self._default_multipass_output_path())
    else:
      self.SetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'], 'Not enabled')

  @show_exceptions
  def Command(self, cmd_id, _msg):
    """
    Handles user commands.
    """
    if cmd_id == SYMBOLS['LOGIN']:
      self._login()
    elif cmd_id == SYMBOLS['LOGOUT']:
      self._logout()
      c4d.gui.MessageDialog('Logged out from Zync')
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
      self.SetInt32(SYMBOLS['FRAMES_TO'],
                    value=self.GetInt32(SYMBOLS['FRAMES_TO']),
                    min=self.GetInt32(SYMBOLS['FRAMES_FROM']))
    elif cmd_id == SYMBOLS['FRAMES_TO']:
      self.SetInt32(SYMBOLS['FRAMES_FROM'],
                    value=self.GetInt32(SYMBOLS['FRAMES_FROM']),
                    max=self.GetInt32(SYMBOLS['FRAMES_TO']))
    elif cmd_id == SYMBOLS['EXISTING_PROJ_NAME']:
      self._enable_existing_project_widget()
    elif cmd_id == SYMBOLS['NEW_PROJ_NAME']:
      self._enable_new_project_widget()
    elif cmd_id == SYMBOLS['UPLOAD_ONLY']:
      self._set_upload_only(self.GetBool(SYMBOLS['UPLOAD_ONLY']))
    elif cmd_id == SYMBOLS['LAUNCH']:
      self._launch_job()
    elif cmd_id == SYMBOLS['TAKE']:
      self._handle_take_change()
    elif SYMBOLS['FILES_LIST_UNFOLD_BTNS'] <= cmd_id < SYMBOLS[
      'FILES_LIST_UNFOLD_BTNS'] + 10000:
      self._unfold_dir(cmd_id - SYMBOLS['FILES_LIST_UNFOLD_BTNS'])
    return True

  def _prompt_path_and_update_widget(self, widget_name, prompt_text):
    old_output = self.GetString(SYMBOLS[widget_name])
    new_output = c4d.storage.SaveDialog(title=prompt_text, def_path=old_output)
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
      checkbox = self.AddCheckbox(SYMBOLS['FILES_LIST_OPTIONS'] + i,
                                  c4d.BFH_LEFT, 0, 0, name=path)
      self.SetBool(checkbox, checked)
      if is_dir:
        self.AddButton(SYMBOLS['FILES_LIST_UNFOLD_BTNS'] + i, 0,
                       name='Unfold')
      else:
        # Layout filler
        self.AddStaticText(0, 0)
    self.LayoutChanged(SYMBOLS['FILES_LIST_GROUP'])
    dirs_count = sum(int(is_dir) for (_, _, is_dir) in self.file_boxes)
    files_count = len(self.file_boxes) - dirs_count
    self.SetString(SYMBOLS['AUX_FILES_SUMMARY'],
                   '%d files, %d folders' % (files_count, dirs_count))

  def _read_file_checkboxes(self):
    self.file_boxes = [
      (path, self.GetBool(SYMBOLS['FILES_LIST_OPTIONS'] + i), is_dir)
      for i, (path, _, is_dir) in enumerate(self.file_boxes)
    ]

  def _add_file(self, directory=False):
    self._read_file_checkboxes()
    flags = c4d.FILESELECT_LOAD
    if directory:
      flags = c4d.FILESELECT_DIRECTORY
    fname = c4d.storage.LoadDialog(flags=flags)
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
      instance_type = self._read_combobox_option(SYMBOLS['VMS_TYPE'],
                                                 SYMBOLS[
                                                   'VMS_TYPE_OPTIONS'],
                                                 self.available_instance_types)
      instance_cost = instance_type['cost']
      est_price = instances_count * instance_cost
      self.SetString(SYMBOLS['EST_PRICE'],
                     'Estimated hour cost: $%.2f' % est_price)
    else:
      self.SetString(SYMBOLS['EST_PRICE'], 'Estimated hour cost: N/A')

  def _launch_job(self):
    if not self._ensure_scene_saved():
      return
    try:
      params = self._collect_params()
    except ValidationError as err:
      c4d.gui.MessageDialog(err.message)
    else:
      settings = import_zync_module('settings')
      if ('PREEMPTIBLE' in params[
        'instance_type']) and not settings.Settings.get().get_pvm_ack():
        self.pvm_consent_dialog = PvmConsentDialog()
        self.pvm_consent_dialog.Open(dlgtype=c4d.DLG_TYPE_MODAL)
        if not self.pvm_consent_dialog.result:
          return
        if self.pvm_consent_dialog.dont_show:
          settings.Settings.get().put_pvm_ack(True)
      if '(ALPHA)' in params['instance_type']:
        # TODO: replace standard dialog with something better, without this deceptive
        #  call to action on YES
        alpha_confirmed = c4d.gui.QuestionDialog(
          'You\'ve selected an instance type for your job which is '
          'still in alpha, and could be unstable for some workloads.\n\n'
          'Submit the job anyway?')
        if not alpha_confirmed:
          return

      try:
        if self.renderer == self.RDATA_RENDERENGINE_VRAY:
          self._submit_vray_job(params)
        else:
          self._submit_c4d_job(params)
      except BaseException as err:
        self._handle_submission_error(err, traceback.format_exc())

  @staticmethod
  def _show_job_successfuly_submitted_dialog():
    # TODO: working link to zync console (or yes/no dialog as easier solution, but it may be
    #  annoying)
    c4d.gui.MessageDialog(
      'Job submitted!\n\nYou can check the status of job in Zync console.\n\n'
      'Don\'t turn off the client app before upload is complete.')

  def _submit_c4d_job(self, params):
    # TODO(b/144898948): Make it async, also: async calls should disable UI
    document = c4d.documents.GetActiveDocument()
    doc_dirpath = document.GetDocumentPath()
    doc_name = document.GetDocumentName()
    doc_path = os.path.join(doc_dirpath, doc_name)
    self.zync_conn.submit_job('c4d', doc_path, params)
    self._show_job_successfuly_submitted_dialog()

  def _submit_vray_job(self, params):
    print 'Vray job, collecting additional info...'

    if self.regular_image_save_enabled and self.multipass_image_save_enabled:
      if self.render_data[c4d.RDATA_FORMAT] != self.render_data[
        c4d.RDATA_MULTIPASS_SAVEFORMAT]:
        c4d.gui.MessageDialog(
          'WARNING: Regular output format is different than multipass output format. '
          'Vray jobs support only one output format. Regular output format will be used.'
        )
      if self.GetString(SYMBOLS['OUTPUT_PATH']) != self.GetString(
          SYMBOLS['MULTIPASS_OUTPUT_PATH']):
        c4d.gui.MessageDialog(
          'WARNING: Regular output path is different than multipass output path. Vray '
          'jobs support only one output path. Regular output path will be used for all '
          'render elements.'
        )

    vray_bridge = _get_vray_render_settings()
    if vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_SAVE] == 1:
      params['output_path'] = vray_bridge[
        c4d.VP_VRAYBRIDGE_VFB_IMAGE_FILE]
      params['format'] = self._get_vfb_format()
    else:
      params['output_path'] = self.GetString(SYMBOLS['OUTPUT_PATH'])

    document = c4d.documents.GetActiveDocument()
    doc_dirpath = document.GetDocumentPath()
    doc_name = document.GetDocumentName()

    path = os.path.join(doc_dirpath, '__zync', str(time.time()))
    if not os.path.exists(path):
      os.makedirs(path)

    vrscene_path = os.path.join(path, os.path.splitext(doc_name)[0])
    vrscene_exporter = VRayExporter(self._main_thread_executor, vrscene_path, params, self.render_data.GetData(), self._send_vray_scene, _get_vray_render_settings, self._handle_submission_error)
    self._thread_pool.add_task(vrscene_exporter)

  def _send_vray_scene(self, vrscene_path, params):
    copy_keys = [
      'renderer', 'plugin_version', 'num_instances', 'instance_type',
      'proj_name', 'job_subtype', 'priority', 'notify_complete',
      'upload_only', 'xres', 'yres', 'chunk_size', 'scene_info',
      'take',
      'format', 'frame_begin', 'frame_end', 'step'
    ]
    render_params = {key: params[key] for key in copy_keys}

    vray_version = self._get_vray_version_from_vrscene(vrscene_path)
    print 'Detected vray version: %s' % vray_version
    render_params['scene_info']['vray_version'] = vray_version

    document = c4d.documents.GetActiveDocument()
    camera = self.take.GetCamera(document.GetTakeData())
    if camera:
      render_params['scene_info']['camera'] = camera.GetName()
    else:
      render_params['scene_info']['camera'] = ''

    render_path_data = {
      '_doc': document,
      '_rData': self.render_data,
      '_rBc': self.render_data.GetData(),
      '_take': self.take
    }
    output_path = c4d.modules.tokensystem.StringConvertTokens(
      params['output_path'], render_path_data)
    output_path = output_path.replace('\\', '/')
    print 'output_path: %s' % output_path
    render_params['output_dir'], output_name = self._split_output_path(
      output_path)
    render_params['output_name'] = output_name
    vrscene = vrscene_path + '*.vrscene'
    self.zync_conn.submit_job('c4d_vray', vrscene, params=render_params)
    self._show_job_successfuly_submitted_dialog()

  def _get_vfb_format(self):
    vray_bridge = _get_vray_render_settings()
    output_path = vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_FILE]
    _, extension = os.path.splitext(output_path)
    if extension:
      return extension  # vray bridge ignores format when file name contains extension
    return self.supported_vray_oformats[
      vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_EXT]]

  @staticmethod
  def _get_vray_version_from_vrscene(vrscene_path):
    version_files = glob.glob(vrscene_path + '*')
    if not version_files:
      print 'Cannot determine vray version from %s' % vrscene_path
      raise zync.ZyncError(
        'Cannot determine vray version. vrscene was not found.')

    version_file = list(version_files)[0]
    with open(version_file) as myfile:
      head = [next(myfile) for _ in xrange(10)]
    first_10_lines = '\n'.join(head)

    # Version numbers written by exporter may be inconsistent, for example
    # V-Ray 3.7 writes both lines:
    # // V-Ray core version is 3.60.05
    # // Exported by V-Ray 3.7
    match = re.search('Exported by V-Ray (?P<major>\\d)\\.(?P<minor>\\d+)',
                      first_10_lines)
    if match:
      return match.group('major') + '.' + match.group('minor')
    match = re.search(
      'V-Ray core version is (?P<major>\\d)\\.(?P<minor>\\d{2})\\.(?P<patch>\\d{2})',
      first_10_lines)
    if match:
      return match.group('major') + '.' + match.group(
        'minor') + '.' + match.group('patch')

    print 'Vray scene header: %s' % first_10_lines
    raise zync.ZyncError('Cannot determine vray version')

  @staticmethod
  def _ensure_scene_saved():
    document = c4d.documents.GetActiveDocument()
    if document.GetDocumentPath() == '' or document.GetChanged():
      c4d.gui.MessageDialog(
        'The scene file must be saved in order to be uploaded to Zync.')
      return False
    elif document.GetDocumentPath().startswith('preset:'):
      c4d.gui.MessageDialog(
        'Rendering scenes directly from preset files is not supported. Please save the '
        'scene in a separate file.')
      return False
    return True

  @staticmethod
  def _split_output_path(out_path):
    out_dir, out_name = os.path.split(out_path)
    while '$' in out_dir:
      out_dir, dir1 = os.path.split(out_dir)
      out_name = os.path.join(dir1, out_name)
    if not os.path.isabs(out_dir):
      out_dir = os.path.join(
        c4d.documents.GetActiveDocument().GetDocumentPath(),
        out_dir)

    # This will remove the .. and . in the path
    out_dir = os.path.abspath(out_dir)
    return out_dir, out_name

  def _collect_params(self):
    params = {}

    if self.renderer not in self.supported_renderers:
      raise ValidationError(
        'Renderer \'%s\' is not currently supported by Zync' % self.renderer_name)
    params['renderer'] = self.renderer_name
    params['plugin_version'] = self._version

    take = self._read_combobox_option(SYMBOLS['TAKE'],
                                      SYMBOLS['TAKE_OPTIONS'],
                                      self.take_names)
    params['take'] = take

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

    out_fps = self.render_data[c4d.RDATA_FRAMERATE]
    document = c4d.documents.GetActiveDocument()
    proj_fps = document.GetFps()
    if out_fps != proj_fps:
      raise ValidationError(
        'Output framerate (%.2f) doesn\'t match project framerate (%.2f). '
        'Using output framerates different from project fps is currently '
        'not supported by Zync.\n\n'
        'Please adjust the values to be equal.' % (
          out_fps, proj_fps))

    params['frame_begin'] = self.GetInt32(SYMBOLS['FRAMES_FROM'])
    params['frame_end'] = self.GetInt32(SYMBOLS['FRAMES_TO'])
    params['step'] = str(self.GetInt32(SYMBOLS['STEP']))
    params['chunk_size'] = str(self.GetInt32(SYMBOLS['CHUNK']))
    params['xres'] = str(self.GetInt32(SYMBOLS['RES_X']))
    params['yres'] = str(self.GetInt32(SYMBOLS['RES_Y']))
    user_files = [path for (path, checked, _) in self.file_boxes if
                  checked]
    asset_files, preset_files = self._get_assets_and_presets(document)
    params['scene_info'] = {
      'dependencies': list(asset_files) + list(
        preset_files) + user_files,
      'preset_files': list(preset_files),
      'glob_tex_paths': self._get_glob_tex_paths(),
      'lib_path_global': c4d.storage.GeGetC4DPath(
        c4d.C4D_PATH_LIBRARY),
      'lib_path_user': c4d.storage.GeGetC4DPath(
        c4d.C4D_PATH_LIBRARY_USER),
      'c4d_version': 'r%d.%03d' % (
        c4d.GetC4DVersion() / 1000, c4d.GetC4DVersion() % 1000),
    }

    self._add_render_specific_params(params)
    return params

  @property
  def _is_output_enabled(self):
    return self.regular_image_save_enabled or self.multipass_image_save_enabled or \
           self.renderer == self.RDATA_RENDERENGINE_VRAY

  def _maybe_update_multipass_image_params(self, params):
    if self.multipass_image_save_enabled and self.renderer != self.RDATA_RENDERENGINE_VRAY:
      out_path = self.GetString(SYMBOLS['MULTIPASS_OUTPUT_PATH'])
      prefix, suffix = self._split_output_path(out_path)
      params['multipass_output_dir'], params[
        'multipass_output_name'] = prefix, suffix
      try:
        params['format'] = self.supported_oformats[
          self.render_data[c4d.RDATA_MULTIPASS_SAVEFORMAT]]
      except KeyError:
        raise ValidationError(
          'Multi-pass image output format not supported. Supported formats: ' +
          ', '.join(self.supported_oformats.values()))

  def _maybe_update_regular_image_params(self, params):
    if self.regular_image_save_enabled:
      out_path = self.GetString(SYMBOLS['OUTPUT_PATH'])
      prefix, suffix = self._split_output_path(out_path)
      params['output_dir'], params['output_name'] = prefix, suffix
      try:
        params['format'] = self.supported_oformats[
          self.render_data[c4d.RDATA_FORMAT]]
      except KeyError:
        raise ValidationError(
          'Regular image output format not supported. Supported formats: ' +
          ', '.join(self.supported_oformats.values()))

  @staticmethod
  def _get_glob_tex_paths():
    # https://developers.maxon.net/docs/Cinema4DPythonSDK/html/modules/c4d/index.html#c4d
    # .GetGlobalTexturePath
    num_of_glob_tex_paths = 10
    glob_tex_paths = [c4d.GetGlobalTexturePath(i) for i in
                      range(num_of_glob_tex_paths)]
    glob_tex_paths = [path for path in glob_tex_paths if path]
    return glob_tex_paths

  def _add_render_specific_params(self, params):
    if self.renderer == self.RDATA_RENDERENGINE_ARNOLD:
      params['scene_info']['c4dtoa_version'] = self._get_c4dtoa_version()
      arnold_render_settings = _get_arnold_render_settings()
      if arnold_render_settings[c4d.C4DAIP_OPTIONS_SKIP_LICENSE_CHECK]:
        raise ValidationError(
          'Please disable "Skip license check" in your '
          'Arnold settings to avoid rendering with a watermark.')
    elif self.renderer == self.RDATA_RENDERENGINE_REDSHIFT:
      params['scene_info'][
        'redshift_version'] = self._get_redshift_version()

  def _get_assets_and_presets(self, document):
    assets = c4d.documents.GetAllAssets(document, False, '')
    if assets is None:
      # c4d.documents.GetAllAssets returned None. That means that some assets are missing
      # and C4D wasn't able to locate them. This also means that we are not going to get
      # any information using GetAllAssets until the dependencies are fixed.
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
        user_path = os.path.join(
          c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY_USER),
          'browser',
          preset_pack)
        glob_path = os.path.join(
          c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY),
          'browser', preset_pack)
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
    if self.renderer == self.RDATA_RENDERENGINE_REDSHIFT:
      for redshift_videopost in _generate_redshift_render_settings():
        ocio_config_path = redshift_videopost[
          c4d.REDSHIFT_POSTEFFECTS_COLORMANAGEMENT_OCIO_FILE]
        if ocio_config_path:
          asset_files.update(zync.get_ocio_files(ocio_config_path))

  def _read_project_name(self):
    if self.GetBool(SYMBOLS['NEW_PROJ']):
      proj_name = self.GetString(SYMBOLS['NEW_PROJ_NAME'])
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
      if proj_name in self.project_names:
        raise ValidationError(
          'Project named \'%s\' already exists.' % proj_name)
      return proj_name
    else:
      return self._read_combobox_option(SYMBOLS['EXISTING_PROJ_NAME'],
                                        SYMBOLS['PROJ_NAME_OPTIONS'],
                                        self.project_names)

  def _read_combobox_option(self, widget_id, child_id_base, options):
    return options[self._read_combobox_index(widget_id, child_id_base)]

  def _read_combobox_index(self, widget_id, child_id_base):
    return self.GetLong(widget_id) - child_id_base
