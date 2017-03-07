from __future__ import division

import c4d
from c4d import gui, plugins
import functools, os, sys, re, thread, traceback, webbrowser
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool
import json


__version__ = '0.5.9'


zync = None

PLUGIN_ID = 1038932

plugin_dir = os.path.dirname(__file__)


def show_exceptions(func):
  '''Error-showing decorator for all entry points
  Catches all exceptions and shows them on the screen and in console before
  re-raising. Uses `exception_already_shown` attribute to prevent showing
  the same exception twice.
  '''
  @functools.wraps(func)
  def wrapped(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except Exception as e:
      if not getattr(e, 'exception_already_shown', False):
        gui.MessageDialog('%s:\n\n%s' % (e.__class__.__name__, unicode(e)))
        e.exception_already_shown = True
      raise
  return wrapped

# Importing zync-python is deferred until user's action (i.e. attempt
# to open plugin window), because we are not able to reliably show message
# windows any time earlier. Zync-python is not needed for plugin to load.
@show_exceptions
def import_zync_python():
  '''Imports zync-python'''
  global zync
  if zync:
    return

  if os.environ.get('ZYNC_API_DIR'):
    API_DIR = os.environ.get('ZYNC_API_DIR')
  else:
    config_path = os.path.join(plugin_dir, 'config_c4d.py')
    if not os.path.exists(config_path):
      raise Exception(
        'Plugin configuration incomplete: zync-python path not provided.\n\n'
        'Re-installing the plugin may solve the problem.')
    import imp
    config_c4d = imp.load_source('config_c4d', config_path)
    API_DIR = config_c4d.API_DIR
    if not isinstance(API_DIR, basestring):
      raise Exception('API_DIR defined in config_c4d.py is not a string')

  sys.path.append(API_DIR)
  import zync

def read_c4d_symbols():
  '''Returns a dictionary of symbols defined in c4d_symbols.h

  Ids for dialog controls are defined in c4d_symbols.h file in an enum
  definition. These definitions are necessary for dialog layout file,
  and therefore cannot be moved. In order to avoid duplication, this
  function reads the symbols.

  It uses regex to find the lines in which symbols are defined, so it
  is very fragile and will fail if enum definition differs from expected.
  We just need to write the symbols standard way.
  '''
  symbols = {}
  with open(os.path.join(plugin_dir, 'res', 'c4d_symbols.h'), 'r') as f:
    lines = f.readlines()
  regex = re.compile(r'\s*(\w+)\s*=\s*(\d+)\s*,?\s*(?://.*)?')
  for line in lines:
    m = regex.match(line)
    if m:
      symbols[m.group(1)] = int(m.group(2))
  return symbols

symbols = read_c4d_symbols()


class ZyncDialog(gui.GeDialog):

  class ValidationError(Exception):
    pass

  # These lists are lists of enums values/PLUGIN_IDs, not names!
  c4d_renderers = [c4d.RDATA_RENDERENGINE_STANDARD,
                   c4d.RDATA_RENDERENGINE_PHYSICAL]
  RDATA_RENDERENGINE_ARNOLD = 1029988
  supported_renderers = c4d_renderers + [RDATA_RENDERENGINE_ARNOLD]

  supported_oformats = {
    c4d.FILTER_B3D: 'B3D',
    c4d.FILTER_BMP: 'BMP',
    c4d.FILTER_DPX: 'DPX',
    c4d.FILTER_EXR: 'EXR',
    c4d.FILTER_HDR: 'HDR',
    c4d.FILTER_IFF: 'IFF',
    c4d.FILTER_JPG: 'JPG',
    c4d.FILTER_PICT: 'PICT',
    c4d.FILTER_PNG: 'PNG',
    c4d.FILTER_PSB: 'PSB',
    c4d.FILTER_PSD: 'PSD',
    c4d.FILTER_RLA: 'RLA',
    c4d.FILTER_RPF: 'RPF',
    c4d.FILTER_TGA: 'TGA',
    c4d.FILTER_TIF: 'TIFF',
  }

  def __init__(self):
    self.logged_out = True
    self.logged_in = False
    self.autologin = True
    self.document = c4d.documents.GetActiveDocument()
    super(ZyncDialog, self).__init__()

  @show_exceptions
  def CreateLayout(self):
    '''Called when dialog opens; creates initial dialog content'''
    self.GroupBegin(symbols['DIALOG_TOP_GROUP'], c4d.BFH_SCALEFIT & c4d.BFV_SCALEFIT, 1)
    self.GroupEnd()

    if self.autologin:
      # autologin should happen only first time the window is opened
      self.autologin = False
      self.Login()
    elif getattr(self, 'zync_conn', None):
      self.LoadLayout('ZYNC_DIALOG')
      self.InitializeControls()
    elif self.logged_out:
      self.LoadLayout('LOGIN_DIALOG')
    else:
      self.LoadLayout('CONN_DIALOG')

    return True

  @show_exceptions
  def Timer(self, msg):
    '''Checks for results of asynchronous calls.

    Calls the main thread callbacks after getting the async call result.
    '''
    try:
      async_result, callback, err_callback = self.async_call
    except AttributeError:
      return  # no async call running
    try:
      result = async_result.get(timeout=0)
    except multiprocessing.TimeoutError:
      return  # no result yet
    except Exception as e:
      # exception thrown by async call
      if err_callback and err_callback(e):
        return  # err_calback was called and handled the exception
      raise
    else:
      self.SetTimer(0)  # turn timer off
      del self.async_call
      if callback:
        callback(result)

  def Open(self, *args, **kwargs):
    self.document = c4d.documents.GetActiveDocument()
    return super(ZyncDialog, self).Open(*args, **kwargs)

  @show_exceptions
  def Close(self):
    self.KillAsyncCall()
    return super(ZyncDialog, self).Close()

  def StartAsyncCall(self, func, callback = None, err_callback = None):
    '''Starts asynchronous call in separate thread.

    Caveats:
      - only one async call at time is supported
      - if called before CreateLayout, SetTimer call will have no effect, so
        + don't call it before CreateLayout in the first place
        + if you really must, get some other function to call SetTimer for you
    '''
    assert not hasattr(self, 'async_call')
    if not hasattr(self, 'pool'):
      self.pool = ThreadPool(processes=1)
    self.async_call = (self.pool.apply_async(func), callback, err_callback)
    self.SetTimer(100)

  def KillAsyncCall(self):
    if hasattr(self, 'async_call'):
      del self.async_call
      self.pool.terminate()
      del self.pool

  def OnConnected(self, connection):
    self.zync_conn = connection
    self.StartAsyncCall(self.FetchAvailableSettings, self.OnFetched,
                        self.OnLoginFail)

  def OnLoginFail(self, exception=None):
    del exception
    self.Logout()

  def FetchAvailableSettings(self):
    return {
      'instance_types': {
        external_renderer: self.GetInstanceTypes(external_renderer)
        for external_renderer in [self.RDATA_RENDERENGINE_ARNOLD]
      },
      'project_list': self.zync_conn.get_project_list(),
      'email': self.zync_conn.email,
      'project_name_hint': self.zync_conn.get_project_name(
        self.document.GetDocumentName()),  # TODO: fix web implementation
    }

  def OnFetched(self, zync_cache):
    self.zync_cache = zync_cache
    self.LoadLayout('ZYNC_DIALOG')
    self.logged_in = True
    self.InitializeControls()

  def GetInstanceTypes(self, external_renderer):
    renderer_plugin = c4d.plugins.FindPlugin(external_renderer)
    renderer_name = renderer_plugin.GetName() if renderer_plugin else str(external_renderer)

    instance_types_dict = self.zync_conn.get_instance_types(
      renderer=renderer_name)
    instance_types = [
      {
        'order': properties['order'],
        'name': name,
        'cost': properties['cost'],
        'label': '%s ($%s)' % (name, properties['cost']),
      }
      for name, properties in instance_types_dict.iteritems()
    ]
    instance_types.sort(key=lambda instance_type: instance_type['order'])

    return instance_types

  def LoadLayout(self, layout_name):
    self.LayoutFlushGroup(symbols['DIALOG_TOP_GROUP'])
    self.MenuFlushAll()
    self.MenuFinished()
    self.LoadDialogResource(symbols[layout_name])
    self.LayoutChanged(symbols['DIALOG_TOP_GROUP'])

  def InitializeControls(self):
    document = self.document

    self.MenuFlushAll()
    self.MenuSubBegin('Logged in as %s' % self.zync_cache['email'])
    self.MenuSubEnd()
    self.MenuSubBegin('Log out')
    self.MenuAddString(symbols['LOGOUT'], 'Log out from Zync')
    self.MenuSubEnd()
    self.MenuFinished()

    self.available_instance_types = []

    # VMs settings
    self.SetInt32(symbols['VMS_NUM'], 1, min=1)

    # Storage settings (zync project)
    self.project_list = self.zync_cache['project_list']
    self.project_names = [p['name'] for p in self.project_list]
    project_name_hint = re.sub(r'\.c4d$', '', document.GetDocumentName())
    self.SetComboboxContent(symbols['EXISTING_PROJ_NAME'],
                            symbols['PROJ_NAME_OPTIONS'],
                            self.project_names)
    self.SetString(symbols['NEW_PROJ_NAME'], project_name_hint)
    if project_name_hint in self.project_names:
      self.SetBool(symbols['EXISTING_PROJ'], True)
      self.SetBool(symbols['NEW_PROJ'], False)
      self.SetInt32(symbols['EXISTING_PROJ_NAME'],
                    symbols['PROJ_NAME_OPTIONS'] + self.project_names.index(project_name_hint))
    else:
      self.SetBool(symbols['EXISTING_PROJ'], False)
      self.SetBool(symbols['NEW_PROJ'], True)

    # General job settings
    self.SetInt32(symbols['JOB_PRIORITY'], 50, min=0)
    self.SetString(symbols['OUTPUT_PATH'], self.DefaultOutputPath())
    self.SetString(symbols['MULTIPASS_OUTPUT_PATH'], self.DefaultMultipassOutputPath())

    # Renderer settings
    self.SetInt32(symbols['CHUNK'], 10, min=1)

    # File management
    self.SetBool(symbols['UPLOAD_ONLY'], False)

    self.file_boxes = []
    self.UpdateFileCheckboxes()

    # Take
    self.take = None
    self.RecreateTakeList()

  def SetComboboxContent(self, widget_id, child_id_base, options):
    self.FreeChildren(widget_id)
    for i, option in enumerate(options):
      self.AddChild(widget_id, child_id_base+i, option)
    # select the first option or make blank if no options
    self.SetInt32(widget_id, child_id_base if options else 0)

  def DefaultOutputPath(self):
    return os.path.join(self.document.GetDocumentPath(), 'renders', '$take',
                        re.sub(r'\.c4d$', '', self.document.GetDocumentName()))

  def DefaultMultipassOutputPath(self):
    return os.path.join(self.document.GetDocumentPath(), 'renders', '$take',
                        re.sub(r'\.c4d$', '', self.document.GetDocumentName()) + '_multi')

  @show_exceptions
  def CoreMessage(self, id, msg):
    if id == c4d.EVMSG_CHANGE:
      self.HandleDocumentChange()
    return super(ZyncDialog, self).CoreMessage(id, msg)

  def HandleDocumentChange(self):
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
        self.InitializeControls()
      else:
        # The active document is still the same one, but it could have
        # been changed
        self.RecreateTakeList()
        # TODO:
        # We could add support for render data changes, project info changes

  def RecreateTakeList(self):
    self.take_names, self.take_labels, self.takes = self.CollectTakes()
    self.SetComboboxContent(symbols['TAKE'],
                            symbols['TAKE_OPTIONS'],
                            self.take_labels)

    # SetComboboxContent selected first entry, but we want to keep
    # previous selection if that take still exists:
    for i, take in enumerate(self.takes):
      if take == self.take:
        # Previously selected take found, select it again
        self.SetInt32(symbols['TAKE'], symbols['TAKE_OPTIONS'] + i)
        return

    # Previously selected take not found, just switch to first one
    self.HandleTakeChange()

  def CollectTakes(self):
    '''Collects all takes in scene

    Returns:
      ([str], [str], [BaseTake]): list of names, list of labels, list of takes

    Labels are names preceded with indentation creating tree layout.
    All lists are in the same order.
    '''
    takes = []
    def traverse(take, depth):
      takes.append((take.GetName(), (depth * '   ') + take.GetName(), take))
      for child in take.GetChildren():
        traverse(child, depth+1)
    traverse(self.document.GetTakeData().GetMainTake(), 0)
    return zip(*takes)

  def HandleTakeChange(self):
    self.take = self.ReadComboboxOption(symbols['TAKE'],
                                        symbols['TAKE_OPTIONS'],
                                        self.takes)
    self.render_data = self.take.GetEffectiveRenderData(self.document.GetTakeData())[0]
    self.renderer = self.take.GetEffectiveRenderData(self.document.GetTakeData())[0][c4d.RDATA_RENDERENGINE]
    if self.renderer == c4d.RDATA_RENDERENGINE_STANDARD:
      self.renderer_name = 'Standard'
    elif self.renderer == c4d.RDATA_RENDERENGINE_PREVIEWSOFTWARE:
      self.renderer_name = 'Software'
    elif self.renderer == c4d.RDATA_RENDERENGINE_PREVIEWHARDWARE:
      self.renderer_name = 'Hardware'
    elif self.renderer == c4d.RDATA_RENDERENGINE_PHYSICAL:
      self.renderer_name = 'Pysical'
    elif self.renderer == c4d.RDATA_RENDERENGINE_CINEMAN:
      self.renderer_name = 'Cineman'
    else:
      renderer_plugin = c4d.plugins.FindPlugin(self.renderer)
      self.renderer_name = renderer_plugin.GetName() if renderer_plugin else str(self.renderer)

    previous_instance_type = None
    if getattr(self, 'available_instance_types', None):
      previous_instance_type = self.ReadComboboxOption(
        symbols['VMS_TYPE'],
        symbols['VMS_TYPE_OPTIONS'],
        self.available_instance_types)

    # Renderer
    if self.renderer in self.supported_renderers:
      self.SetString(symbols['RENDERER'], self.renderer_name)
      external_renderer = self.renderer
      if self.renderer in self.c4d_renderers or (not self.renderer in self.zync_cache['instance_types']):
        external_renderer = None
      self.available_instance_types = self.zync_cache['instance_types'][external_renderer]
    else:
      self.SetString(symbols['RENDERER'], self.renderer_name + ' (unsupported)')
      self.available_instance_types = []

    # VMs settings
    if self.available_instance_types:
      instance_type_labels = [instance_type['label']
                              for instance_type
                              in self.available_instance_types]
    else:
      instance_type_labels = ['N/A']
    self.SetComboboxContent(symbols['VMS_TYPE'],
                            symbols['VMS_TYPE_OPTIONS'],
                            instance_type_labels)

    # If there was some machine type selected and it's still available, select it again
    if previous_instance_type:
      for i, instance_type in enumerate(self.available_instance_types):
        if instance_type['name'] == previous_instance_type['name']:
          self.SetInt32(symbols['VMS_TYPE'], symbols['VMS_TYPE_OPTIONS']+i)

    self.UpdatePrice()

    # Resolution
    self.SetInt32(symbols['RES_X'], self.render_data[c4d.RDATA_XRES], min=1)
    self.SetInt32(symbols['RES_Y'], self.render_data[c4d.RDATA_YRES], min=1)

    # Renderer settings
    fps = self.document.GetFps()
    start_frame = self.render_data[c4d.RDATA_FRAMEFROM].GetFrame(fps)
    end_frame = self.render_data[c4d.RDATA_FRAMETO].GetFrame(fps)
    self.SetInt32(symbols['FRAMES_FROM'], start_frame, max=end_frame)
    self.SetInt32(symbols['FRAMES_TO'], end_frame, min=start_frame)
    self.SetInt32(symbols['STEP'], self.render_data[c4d.RDATA_FRAMESTEP], min=1)

    # Regular image output path
    self.regular_image_save_enabled = bool(self.render_data[c4d.RDATA_GLOBALSAVE] and
        self.render_data[c4d.RDATA_SAVEIMAGE])
    self.Enable(symbols['OUTPUT_PATH'], int(self.regular_image_save_enabled))
    self.Enable(symbols['OUTPUT_PATH_BTN'], int(self.regular_image_save_enabled))
    if self.regular_image_save_enabled:
      if self.render_data[c4d.RDATA_PATH]:
        self.SetString(symbols['OUTPUT_PATH'], os.path.join(
            self.document.GetDocumentPath(),
            self.render_data[c4d.RDATA_PATH]))
      else:
        self.SetString(symbols['OUTPUT_PATH'], self.DefaultOutputPath())
    else:
      self.SetString(symbols['OUTPUT_PATH'], 'Not enabled')

    # Multi-pass image output path
    self.multipass_image_save_enabled = bool(self.render_data[c4d.RDATA_GLOBALSAVE] and
        self.render_data[c4d.RDATA_MULTIPASS_SAVEIMAGE] and
        self.render_data[c4d.RDATA_MULTIPASS_ENABLE])
    self.Enable(symbols['MULTIPASS_OUTPUT_PATH'], int(self.multipass_image_save_enabled))
    self.Enable(symbols['MULTIPASS_OUTPUT_PATH_BTN'], int(self.multipass_image_save_enabled))
    if self.multipass_image_save_enabled:
      if self.render_data[c4d.RDATA_MULTIPASS_FILENAME]:
        self.SetString(symbols['MULTIPASS_OUTPUT_PATH'], os.path.join(
            self.document.GetDocumentPath(),
            self.render_data[c4d.RDATA_MULTIPASS_FILENAME]))
      else:
        self.SetString(symbols['MULTIPASS_OUTPUT_PATH'], self.DefaultMultipassOutputPath())
    else:
      self.SetString(symbols['MULTIPASS_OUTPUT_PATH'], 'Not enabled')

  # list of widgets that should be disabled for upload only jobs
  render_only_settings = ['JOB_SETTINGS_G', 'VMS_SETTINGS_G', 'FRAMES_G',
                          'RENDER_G', 'TAKE']

  @show_exceptions
  def Command(self, id, msg):
    if id == symbols['LOGIN']:
      self.Login()
    elif id == symbols['LOGOUT']:
      self.Logout()
      gui.MessageDialog('Logged out from Zync')
    elif id == symbols['CANCEL_CONN']:
      self.Logout()
    elif id == symbols['COST_CALC_LINK']:
      webbrowser.open('http://zync.cloudpricingcalculator.appspot.com')
    elif id == symbols['VMS_NUM'] or id == symbols['VMS_TYPE']:
      self.UpdatePrice()
    elif id == symbols['FILES_LIST']:
      self.UpdateFileCheckboxes()
      self.SetInt32(symbols['DIALOG_TABS'], symbols['FILES_TAB'])
    elif id == symbols['ADD_FILE']:
      self.AddFile()
    elif id == symbols['ADD_DIR']:
      self.AddFile(directory=True)
    elif id == symbols['OK_FILES']:
      self.ReadFileCheckboxes()
      self.SetInt32(symbols['DIALOG_TABS'], symbols['SETTINGS_TAB'])
    elif id == symbols['OUTPUT_PATH_BTN']:
      old_output = self.GetString(symbols['OUTPUT_PATH'])
      new_output = c4d.storage.SaveDialog(title='Set regular image output path...',
                                          def_path=old_output)
      if new_output:
        self.SetString(symbols['OUTPUT_PATH'], new_output)
    elif id == symbols['MULTIPASS_OUTPUT_PATH_BTN']:
      old_output = self.GetString(symbols['MULTIPASS_OUTPUT_PATH'])
      new_output = c4d.storage.SaveDialog(title='Set multi-pass image output path...',
                                          def_path=old_output)
      if new_output:
        self.SetString(symbols['MULTIPASS_OUTPUT_PATH'], new_output)
    elif id == symbols['FRAMES_FROM']:
      self.SetInt32(symbols['FRAMES_TO'],
                    value=self.GetInt32(symbols['FRAMES_TO']),
                    min=self.GetInt32(symbols['FRAMES_FROM']))
    elif id == symbols['FRAMES_TO']:
      self.SetInt32(symbols['FRAMES_FROM'],
                    value=self.GetInt32(symbols['FRAMES_FROM']),
                    max=self.GetInt32(symbols['FRAMES_TO']))
    elif id == symbols['EXISTING_PROJ_NAME']:
      self.SetBool(symbols['NEW_PROJ'], False)
      self.SetBool(symbols['EXISTING_PROJ'], True)
    elif id == symbols['NEW_PROJ_NAME']:
      self.SetBool(symbols['EXISTING_PROJ'], False)
      self.SetBool(symbols['NEW_PROJ'], True)
    elif id == symbols['UPLOAD_ONLY']:
      render_job = not self.GetBool(symbols['UPLOAD_ONLY'])
      for item_name in self.render_only_settings:
        self.Enable(symbols[item_name], render_job)
    elif id == symbols['LAUNCH']:
      self.LaunchJob()
    elif id == symbols['TAKE']:
      self.HandleTakeChange()
    elif id >= symbols['FILES_LIST_UNFOLD_BTNS'] and id < symbols['FILES_LIST_UNFOLD_BTNS'] + 10000:
      self.UnfoldDir(id - symbols['FILES_LIST_UNFOLD_BTNS'])
    return True

  def UnfoldDir(self, dir_index):
    '''Unfolds directory entry in aux files list'''
    self.ReadFileCheckboxes()

    def generate_new_fboxes():
      for i in xrange(dir_index):
        yield self.file_boxes[i]

      dirpath, checked, _ = self.file_boxes[dir_index]
      for fname in os.listdir(dirpath):
        fpath = os.path.join(dirpath, fname)
        if os.path.isfile(fpath):
          yield (fpath, True, False)
        elif os.path.isdir(fpath):
          yield (fpath, True, True)

      for i in xrange(dir_index+1, len(self.file_boxes)):
        yield self.file_boxes[i]

    new_file_boxes = list(generate_new_fboxes())
    self.file_boxes = new_file_boxes
    self.UpdateFileCheckboxes()

  def UpdateFileCheckboxes(self):
    self.LayoutFlushGroup(symbols['FILES_LIST_GROUP'])
    for i, (path, checked, is_dir) in enumerate(self.file_boxes):
      checkbox = self.AddCheckbox(symbols['FILES_LIST_OPTIONS'] + i, c4d.BFH_LEFT, 0, 0, name=path)
      self.SetBool(checkbox, checked)
      if is_dir:
        self.AddButton(symbols['FILES_LIST_UNFOLD_BTNS'] + i, 0, name='Unfold')
      else:
        # Layout filler
        self.AddStaticText(0, 0)
    self.LayoutChanged(symbols['FILES_LIST_GROUP'])
    dirs_count = sum(int(is_dir) for (_, _, is_dir) in self.file_boxes)
    files_count = len(self.file_boxes) - dirs_count
    self.SetString(symbols['AUX_FILES_SUMMARY'], '%d files, %d folders' % (files_count, dirs_count))

  def ReadFileCheckboxes(self):
    self.file_boxes = [
      (path, self.GetBool(symbols['FILES_LIST_OPTIONS']+i), is_dir)
      for i, (path, _, is_dir) in enumerate(self.file_boxes)
    ]

  def AddFile(self, directory=False):
    self.ReadFileCheckboxes()
    flags = c4d.FILESELECT_LOAD
    if directory:
      flags = c4d.FILESELECT_DIRECTORY
    fname = c4d.storage.LoadDialog(flags=flags)
    if fname is not None:
      self.file_boxes.append((fname, True, directory))
      self.UpdateFileCheckboxes()

  def Login(self):
    import_zync_python()
    self.StartAsyncCall(lambda: zync.Zync(application='c4d'), self.OnConnected,
                    self.OnLoginFail)
    self.LoadLayout('CONN_DIALOG')

  def Logout(self):
    self.logged_in = False
    self.logged_out = True
    self.LoadLayout('LOGIN_DIALOG')
    self.KillAsyncCall()
    zync_conn = getattr(self, 'zync_conn', None)
    if zync_conn:
      del self.zync_conn
      zync_conn.logout()

  def UpdatePrice(self):
    if self.available_instance_types:
      instances_count = self.GetLong(symbols['VMS_NUM'])
      instance_type = self.ReadComboboxOption(symbols['VMS_TYPE'],
                                              symbols['VMS_TYPE_OPTIONS'],
                                              self.available_instance_types)
      instance_cost = instance_type['cost']
      est_price = instances_count * instance_cost
      self.SetString(symbols['EST_PRICE'], 'Estimated hour cost: $%.2f' % est_price)
    else:
      self.SetString(symbols['EST_PRICE'], 'Estimated hour cost: N/A')

  def LaunchJob(self):
    if not self.EnsureSceneSaved():
      return
    try:
      params = self.CollectParams()
    except self.ValidationError, e:
      gui.MessageDialog(e.message)
    else:
      if '(ALPHA)' in params['instance_type']:
        # TODO: replace standard dialog with something better, without this deceptive call to action on YES
        alpha_confirmed = gui.QuestionDialog(
          'You\'ve selected an instance type for your job which is '
          'still in alpha, and could be unstable for some workloads.\n\n'
          'Submit the job anyway?')
        if not alpha_confirmed:
          return
      doc_dirpath = self.document.GetDocumentPath()
      doc_name = self.document.GetDocumentName()
      doc_path = os.path.join(doc_dirpath, doc_name)

      try:
        self.zync_conn.submit_job('c4d', doc_path, params)
      except (zync.ZyncPreflightError, zync.ZyncError) as e:
        gui.MessageDialog('%s:\n\n%s' % (e.__class__.__name__, unicode(e)))
        traceback.print_exc()
      except:
        gui.MessageDialog('Unexpected error during job submission')
        raise
      else:
        gui.MessageDialog('Job submitted!\n\nYou can check the status of job in Zync console.\n\nDon\'t turn of the client app before upload is complete.')
        # TODO: working link to zync console (or yes/no dialog as easier solution, but it may be annoying)

  def EnsureSceneSaved(self):
    if self.document.GetDocumentPath() == '' or self.document.GetChanged():
      gui.MessageDialog(
          'The scene file must be saved in order to be uploaded to Zync.')
      return False
    elif self.document.GetDocumentPath().startswith('preset:'):
      gui.MessageDialog('Rendering scenes directly from preset files is not supported. Please save the scene in a separate file.')
      return False
    return True

  def SplitOutputPath(self, control_with_path):
    out_path = self.GetString(control_with_path)
    out_dir, out_name = os.path.split(out_path)
    while '$' in out_dir:
      out_dir, dir1 = os.path.split(out_dir)
      out_name = os.path.join(dir1, out_name)
    if not os.path.isabs(out_dir):
      out_dir = os.path.abspath(os.path.join(self.document.GetDocumentPath(), out_dir))

    return out_dir, out_name

  def CollectParams(self):
    params = {}

    if self.renderer not in self.supported_renderers:
      raise self.ValidationError('Renderer \'%s\' is not currently supported by Zync' % self.renderer_name)
    params['renderer'] = self.renderer_name
    params['plugin_version'] = __version__

    take = self.ReadComboboxOption(symbols['TAKE'],
                                   symbols['TAKE_OPTIONS'],
                                   self.take_names)
    params['take'] = take

    params['num_instances'] = self.GetLong(symbols['VMS_NUM'])
    if self.available_instance_types:
      params['instance_type'] = self.ReadComboboxOption(
        symbols['VMS_TYPE'],
        symbols['VMS_TYPE_OPTIONS'],
        self.available_instance_types)['name']
    else:
      raise self.ValidationError('No machine type available for this type of job')

    params['proj_name'] = self.ReadProjectName()

    params['job_subtype'] = 'render'
    params['priority'] = self.GetLong(symbols['JOB_PRIORITY'])
    params['notify_complete'] = int(self.GetBool(symbols['NOTIFY_COMPLETE']))
    params['upload_only'] = int(self.GetBool(symbols['UPLOAD_ONLY']))

    if self.regular_image_save_enabled:
      prefix, suffix = self.SplitOutputPath(symbols['OUTPUT_PATH'])
      params['output_dir'], params['output_name'] = prefix, suffix
      try:
        params['format'] = self.supported_oformats[self.render_data[c4d.RDATA_FORMAT]]
      except KeyError:
        raise self.ValidationError('Regular image output format not supported. Supported formats: ' +
                                   ', '.join(self.supported_oformats.values()))
    if self.multipass_image_save_enabled:
      prefix, suffix = self.SplitOutputPath(symbols['MULTIPASS_OUTPUT_PATH'])
      params['multipass_output_dir'], params['multipass_output_name'] = prefix, suffix
      try:
        params['format'] = self.supported_oformats[self.render_data[c4d.RDATA_MULTIPASS_SAVEFORMAT]]
      except KeyError:
        raise self.ValidationError('Multi-pass image output format not supported. Supported formats: ' +
                                   ', '.join(self.supported_oformats.values()))
    if not (self.regular_image_save_enabled or self.multipass_image_save_enabled):
      raise self.ValidationError('No output is enabled. Please either enable regular image ' +
                                 'or multi-pass image output from the render settings.')


    out_fps = self.render_data[c4d.RDATA_FRAMERATE]
    proj_fps = self.document.GetFps()
    if out_fps != proj_fps:
      raise self.ValidationError('Output framerate (%.2f) doesn\'t match project framerate (%.2f). '
                                 'Using output framerates different from project fps is currently '
                                 'not supported by Zync.\n\n'
                                 'Please adjust the values to be equal.' % (out_fps, proj_fps))

    params['frame_begin'] = self.GetInt32(symbols['FRAMES_FROM'])
    params['frame_end'] = self.GetInt32(symbols['FRAMES_TO'])
    params['step'] = str(self.GetInt32(symbols['STEP']))
    params['chunk_size'] = str(self.GetInt32(symbols['CHUNK']))
    params['xres'] = str(self.GetInt32(symbols['RES_X']))
    params['yres'] = str(self.GetInt32(symbols['RES_Y']))
    user_files = [path for (path, checked, is_dir) in self.file_boxes if checked]
    assets = c4d.documents.GetAllAssets(self.document, False, '')
    if assets is None:
      # c4d.documents.GetAllAssets returned None. That means that some assets are missing
      # and C4D wasn't able to locate them. This also means that we are not going to get
      # any information using GetAllAssets until the dependencies are fixed.
      raise self.ValidationError('Error:\n\nUnable to locate some assets. '
                                 'Please fix scene dependencies before submitting the job.\n\n'
                                 'Try going to Textures tab in Project Info and using '
                                 'Mark Missing Textures button to find possible problems.')
    asset_files = set()
    preset_files = set()
    preset_re = re.compile(r'preset://([^/]+)/')
    for asset in assets:
        m = preset_re.match(asset['filename'])
        if m:
            preset_pack = m.group(1)
            # preset path candidates:
            userpath = os.path.join(c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY_USER), 'browser', preset_pack)
            globpath = os.path.join(c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY), 'browser', preset_pack)
            if os.path.exists(userpath):
                preset_files.add(userpath)
            elif os.path.exists(globpath):
                preset_files.add(globpath)
            else:
                raise self.ValidationError('Unable to locate asset \'%s\'' % asset['filename'])
        else:
            asset_files.add(asset['filename'])
    params['scene_info'] = {
        'dependencies': list(asset_files) + list(preset_files) + user_files,
        'preset_files': list(preset_files),
        'glob_tex_paths': [c4d.GetGlobalTexturePath(i) for i in range(10)],
        'lib_path_global': c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY),
        'lib_path_user': c4d.storage.GeGetC4DPath(c4d.C4D_PATH_LIBRARY_USER),
        'c4d_version': 'r18',  # TODO: send actual version
    }
    # TODO:renderer specific params??
    return params

  def ReadProjectName(self):
    if self.GetBool(symbols['NEW_PROJ']):
      proj_name = self.GetString(symbols['NEW_PROJ_NAME'])
      proj_name = proj_name.strip()
      try:
        proj_name = str(proj_name)
      except ValueError:
        raise self.ValidationError('Project name \'%s\' contains illegal characters.' % proj_name)
      if re.search(r'[/\\]', proj_name):
        raise self.ValidationError('Project name \'%s\' contains illegal characters.' %  proj_name)
      if proj_name == '':
        raise self.ValidationError('You must choose existing project or give valid name for a new one.')
      if proj_name in self.project_names:
        raise self.ValidationError('Project named \'%s\' already exists.' % proj_name)
      return proj_name
    else:
      return self.ReadComboboxOption(symbols['EXISTING_PROJ_NAME'],
                                     symbols['PROJ_NAME_OPTIONS'],
                                     self.project_names)

  def ReadComboboxOption(self, widget_id, child_id_base, options):
    return options[self.ReadComboboxIndex(widget_id, child_id_base)]

  def ReadComboboxIndex(self, widget_id, child_id_base):
    return self.GetLong(widget_id) - child_id_base


class ZyncPlugin(c4d.plugins.CommandData):

  def __init__(self):
    self.dialog = ZyncDialog()

  @show_exceptions
  def Execute(self, doc):
    import_zync_python()
    if not self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID):
      raise Exception('Failed to open dialog window')
    return True

  @show_exceptions
  def RestoreLayout(self, sec_ref):
    '''Makes some c4d magic to keep dialogs working'''
    return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)


if __name__ == '__main__':
    bmp = c4d.bitmaps.BaseBitmap()
    bmp.InitWith(os.path.join(plugin_dir, 'res', 'zync.png'))
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str='Render with Zync...',
        info=c4d.PLUGINFLAG_COMMAND_ICONGADGET,
        icon=bmp,
        help='Render scene using Zync cloud service',
        dat=ZyncPlugin())
