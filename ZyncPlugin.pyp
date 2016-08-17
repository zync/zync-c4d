import c4d
from c4d import gui, plugins
import functools, os, sys, re, thread, webbrowser
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

zync = None

PLUGIN_ID = 1000001  # TODO: get own one, this is test one


def show_exceptions(func):
  """Error-showing decorator for all entry points
  Catches all exceptions and shows them on the screen and in console before
  re-raising. Uses `exception_already_shown` attribute to prevent showing
  the same exception twice.
  """
  @functools.wraps(func)
  def wrapped(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except Exception as e:
      if not getattr(e, 'exception_already_shown', False):
        gui.MessageDialog('Error:\n\n' + e.message)
        e.exception_already_shown = True
      raise
  return wrapped

# Importing zync-python is deferred until user's action (i.e. attempt
# to open plugin window), because we are not able to reliably show message
# windows any time earlier. Zync-python is not needed for plugin to load.
@show_exceptions
def import_zync_python():
  """Imports zync-python"""
  global zync
  if zync:
    return

  if os.environ.get('ZYNC_API_DIR'):
    API_DIR = os.environ.get('ZYNC_API_DIR')
  else:
    config_path = os.path.join(os.path.dirname(__file__), 'config_c4d.py')
    if not os.path.exists(config_path):
      raise Exception(
        "Plugin configuration incomplete: zync-python path not provided.\n\n"
        "Re-installing the plugin may solve the problem.")
    import imp
    config_c4d = imp.load_source('config_c4d', config_path)
    API_DIR = config_c4d.API_DIR
    if not isinstance(API_DIR, basestring):
      raise Exception("API_DIR defined in config_c4d.py is not a string")

  sys.path.append(API_DIR)
  import zync


dir, file = os.path.split(__file__)

def read_c4d_symbols():
  """Returns a dictionary of symbols defined in c4d_symbols.h

  Ids for dialog controls are defined in c4d_symbols.h file in an enum
  definition. These definitions are necessary for dialog layout file,
  and therefore cannot be moved. In order to avoid duplication, this
  function reads the symbols.

  It uses regex to find the lines in which symbols are defined, so it
  is very fragile and will fail if enum definition differs from expected.
  We just need to write the symbols standard way.
  """
  symbols = {}
  with open(os.path.join(dir, "res", "c4d_symbols.h"), 'r') as f:
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

  def __init__(self):
    self.logged_out = True
    self.logged_in = False
    self.autologin = True
    super(ZyncDialog, self).__init__()

  @show_exceptions
  def CreateLayout(self):
    """Called when dialog opens; creates initial dialog content"""
    self.GroupBegin(symbols['DIALOG_TOP_GROUP'], c4d.BFH_SCALEFIT & c4d.BFV_SCALEFIT, 1)
    self.GroupEnd()

    if self.autologin:
      # autologin happens first time the window is opened
      self.autologin = False
      self.Login()
    elif getattr(self, 'zync_conn', None):
      self.LoadLayout('ZYNC_DIALOG')
      # TODO: update widgets?
    elif self.logged_out:
      self.LoadLayout('LOGIN_DIALOG')
    else:
      self.LoadLayout('CONN_DIALOG')

    return True

  @show_exceptions
  def Timer(self, msg):
    """Checks for results of asynchronous calls.

    Calls the main thread callbacks after getting the async call result.
    """
    try:
      async_result, callback, err_callback = self.async_call
    except AttributeError:
      return  # no async call running
    try:
      result = async_result.get(0)
    except multiprocessing.TimeoutError:
      return  # no result yet
    except Exception as e:
      # exception thrown by async call
      if err_callback and err_callback(e):
        return  # err_calback was called and handled the exception
      raise

    self.SetTimer(0)
    del self.async_call
    if callback:
      callback(result)

  def Open(self, *args, **kwargs):
    self.document = c4d.documents.GetActiveDocument()
    return super(ZyncDialog, self).Open(*args, **kwargs)

  def Close(self):
    self.KillAsyncCall()
    return super(ZyncDialog, self).Close()

  def StartAsyncCall(self, func, callback = None, err_callback = None):
    """Starts asynchronous call in separate thread.

    Caveats:
      - only one async call at time is supported
      - if called before CreateLayout, SetTimer call will have no effect, so
        + don't call it before CreateLayout in the first place
        + if you really must, get some other function to call SetTimer for you
    """
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
      'instance_types': self.zync_conn.INSTANCE_TYPES,
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

  def LoadLayout(self, layout_name):
    self.LayoutFlushGroup(symbols['DIALOG_TOP_GROUP'])
    self.MenuFlushAll()
    self.MenuFinished()
    self.LoadDialogResource(symbols[layout_name])
    self.LayoutChanged(symbols['DIALOG_TOP_GROUP'])

  def InitializeControls(self):
    document = self.document

    self.MenuFlushAll()
    self.MenuSubBegin('Logged in as {}'.format(self.zync_cache['email']))
    self.MenuAddString(symbols['LOGOUT'], 'Log out')
    self.MenuSubEnd()
    self.MenuFinished()

    self.file_boxes = []

    self.instance_types = self.zync_cache['instance_types']
    self.instance_type_names = self.instance_types.keys()

    # Job type
    self.SetBool(symbols['RENDER_JOB'], True)

    # VMs settings
    self.SetInt32(symbols['VMS_NUM'], 1, min=1)
    self.SetComboboxContent(symbols['VMS_TYPE'],
                            symbols['VMS_TYPE_OPTIONS'],
                            self.instance_type_names)
    self.UpdatePrice()

    # Storage settings (zync project)
    self.project_list = self.zync_cache['project_list']
    self.project_names = [p['name'] for p in self.project_list]
    self.SetComboboxContent(symbols['EXISTING_PROJ_NAME'],
                            symbols['PROJ_NAME_OPTIONS'],
                            self.project_names)
    self.SetBool(symbols['NEW_PROJ'], True)
    self.SetString(symbols['NEW_PROJ_NAME'], self.zync_cache['project_name_hint'])

    # General job settings
    self.SetInt32(symbols['JOB_PRIORITY'], 50, min=0)
    self.SetString(symbols['OUTPUT_DIR'], self.DefaultOutputDir(document))

    # Renderer settings
    self.renderers_list = ['Cinema 4D Standard', 'Cinema 4D Physical']
    self.SetComboboxContent(symbols['RENDERER'],
                            symbols['RENDERER_OPTIONS'],
                            self.renderers_list)
    fps = document.GetFps()
    self.first_frame = document.GetMinTime().GetFrame(fps)
    self.last_frame  = document.GetMaxTime().GetFrame(fps)
    self.SetInt32(symbols['FRAMES_FROM'], self.first_frame,
                  min=self.first_frame, max=self.last_frame)
    self.SetInt32(symbols['FRAMES_TO'], self.last_frame,
                  min=self.first_frame, max=self.last_frame)
    self.SetInt32(symbols['STEP'], 1, min=1)
    self.SetInt32(symbols['CHUNK'], 10, min=1)

    # Camera selection
    self.cameras = self.CollectCameras(document)
    self.SetComboboxContent(symbols['CAMERA'],
                            symbols['CAMERA_OPTIONS'],
                            (c['name'] for c in self.cameras))

    # Resolution
    render_data = document.GetActiveRenderData()
    self.SetInt32(symbols['RES_X'], render_data[c4d.RDATA_XRES], min=1)
    self.SetInt32(symbols['RES_Y'], render_data[c4d.RDATA_YRES], min=1)

    self.files_boxes = []

  def SetComboboxContent(self, widget_id, child_id_base, options):
    self.FreeChildren(widget_id)
    for i, option in enumerate(options):
      self.AddChild(widget_id, child_id_base+i, option)
    if options:
      # select the first option
      self.SetInt32(widget_id, child_id_base)

  def DefaultOutputDir(self, document):
    # TODO: something sensible
    return os.path.join(document.GetDocumentPath(), 'output')

  def CollectCameras(self, document):
    # TODO: default cameras
    cameras = []
    for obj in document.GetObjects():
      if isinstance(obj, c4d.CameraObject):
        cameras.append({
          'name': obj.GetName(),
          'camera': obj
        })
    return cameras

  @show_exceptions
  def CoreMessage(self, id, msg):
    if id == c4d.EVMSG_CHANGE:
      self.HandleDocumentChange()
    return super(ZyncDialog, self).CoreMessage(id, msg)

  def HandleDocumentChange(self):
    # Reinitialize dialog in case active document was changed.
    # TODO: change launch button if document is in dirty state?
    document = c4d.documents.GetActiveDocument()
    if self.logged_in and self.document is not document:
      self.document = document
      self.InitializeControls()

  # list of widgets that should be disabled for upload (no render) jobs
  render_only_settings = ['JOB_SETTINGS_G', 'VMS_SETTINGS_G', 'FRAMES_G',
                          'RENDER_G', 'NO_UPLOAD', 'IGN_MISSING_PLUGINS']

  @show_exceptions
  def Command(self, id, msg):
    if id == symbols['LOGIN']:
      self.Login()
    elif id == symbols["LOGOUT"]:
      self.Logout()
      gui.MessageDialog("Logged out from Zync")
    elif id == symbols["CANCEL_CONN"]:
      self.Logout()
    elif id == symbols["COST_CALC_LINK"]:
      webbrowser.open('http://zync.cloudpricingcalculator.appspot.com')
    elif id == symbols["VMS_NUM"] or id == symbols["VMS_TYPE"]:
      self.UpdatePrice()
    elif id == symbols["FILES_LIST"]:
      self.UpdateFileCheckboxes()
      self.SetInt32(symbols["DIALOG_TABS"], symbols["FILES_TAB"])
    elif id == symbols["ADD_FILE"]:
      self.AddFile()
    elif id == symbols["OK_FILES"]:
      self.ReadFileCheckboxes()
      self.SetInt32(symbols["DIALOG_TABS"], symbols["SETTINGS_TAB"])
    elif id == symbols["OUTPUT_DIR_BTN"]:
      old_output = self.GetString(symbols["OUTPUT_DIR"])
      new_output = c4d.storage.LoadDialog(title="Select output directory...",
                                          flags=c4d.FILESELECT_DIRECTORY,
                                          def_path=old_output)
      if new_output:
        self.SetString(symbols["OUTPUT_DIR"], new_output)
    elif id == symbols['FRAMES_FROM']:
      self.SetInt32(symbols['FRAMES_TO'],
                    value=self.GetInt32(symbols['FRAMES_TO']),
                    min=self.GetInt32(symbols['FRAMES_FROM']),
                    max=self.last_frame)
    elif id == symbols['FRAMES_TO']:
      self.SetInt32(symbols['FRAMES_FROM'],
                    value=self.GetInt32(symbols['FRAMES_FROM']),
                    min=self.first_frame,
                    max=self.GetInt32(symbols['FRAMES_TO']))
    elif id == symbols['EXISTING_PROJ_NAME']:
      self.SetBool(symbols['NEW_PROJ'], False)
      self.SetBool(symbols['EXISTING_PROJ'], True)
    elif id == symbols['NEW_PROJ_NAME']:
      self.SetBool(symbols['EXISTING_PROJ'], False)
      self.SetBool(symbols['NEW_PROJ'], True)
    elif id == symbols['JOB_KIND']:
      render_job = self.GetBool(symbols['RENDER_JOB'])
      for item_name in self.render_only_settings:
        self.Enable(symbols[item_name], render_job)
      if not render_job:
        self.SetBool(symbols['NO_UPLOAD'], False)
    elif id == symbols["LAUNCH"]:
      self.LaunchJob()
    return True

  def UpdateFileCheckboxes(self):
    self.LayoutFlushGroup(symbols['FILES_LIST_GROUP'])
    for i, (path, checked) in enumerate(self.file_boxes):
      checkbox = self.AddCheckbox(symbols['FILES_LIST_OPTIONS']+i, c4d.BFH_LEFT, 0, 0, name=path)
      self.SetBool(checkbox, checked)
    self.LayoutChanged(symbols['FILES_LIST_GROUP'])

  def ReadFileCheckboxes(self):
    self.file_boxes = [
      (path, self.GetBool(symbols['FILES_LIST_OPTIONS']+i))
      for i, (path, _) in enumerate(self.file_boxes)
    ]

  def AddFile(self):
    self.ReadFileCheckboxes()
    fname = c4d.storage.LoadDialog()
    if fname is not None:
      self.file_boxes.append((fname, True))
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
    if self.instance_type_names:
      instances_count = self.GetLong(symbols['VMS_NUM'])
      instance_type_name = self.ReadComboboxOption(symbols['VMS_TYPE'],
                                                   symbols['VMS_TYPE_OPTIONS'],
                                                   self.instance_type_names)
      instance_cost = self.instance_types[instance_type_name]['cost']
      est_price = instances_count * instance_cost
    else:
      est_price = 0
    self.SetString(symbols['EST_PRICE'], 'Estimated hour cost: ${:.2f}'.format(est_price))

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
      except zync.ZyncPreflightError, e:
        gui.MessageDialog("Preflight Check failed:\n{}".format(e))
      except zync.ZyncError, e:
        gui.MessageDialog("Zync Error:\n{}".format(e))
      except:
        gui.MessageDialog("Unexpected error during job submission")
        raise
      else:
        gui.MessageDialog("Job submitted!\n\nYou can check the status of job in Zync console.\n\nDon't turn of the client app before upload is complete.")
        # TODO: info about client app
        # TODO: link to zync console
      finally:
        pass  # TODO??

  def EnsureSceneSaved(self):
    if self.document.GetDocumentPath() == '' or self.document.GetChanged():
      gui.MessageDialog(
          'The scene file must be saved in order to be uploaded to Zync.')
      return False
    return True

  def CollectParams(self):
      params = {}
      params['num_instances'] = self.GetLong(symbols['VMS_NUM'])
      instance_type_name = self.ReadComboboxOption(symbols['VMS_TYPE'],
                                                   symbols['VMS_TYPE_OPTIONS'],
                                                   self.instance_type_names)
      params['instance_type'] = instance_type_name

      params['proj_name'] = self.ReadProjectName()

      params['job_subtype'] = 'render'  # ???
      params['priority'] = self.GetLong(symbols['JOB_PRIORITY'])
      params['start_new_slots'] = 1  # value copied from Maya plugin  ####  TODO: what is that? do we need that?
      params['notify_complete'] = 0  # value copied from Maya plugin  ####  TODO: what is that? do we need that?
      params['upload_only'] = int(self.GetBool(symbols['UPLOAD_JOB']))
      params['skip_check'] = int(self.GetBool(symbols['NO_UPLOAD']))
      params['ignore_plugin_errors'] = int(self.GetBool(symbols['IGN_MISSING_PLUGINS']))

      params['project'] = self.document.GetDocumentPath()
      params['output_dir'] = self.GetString(symbols['OUTPUT_DIR'])
      if not os.path.isabs(params['output_dir']):
          params['output_dir'] = os.path.abspath(os.path.join(params['project'],
                                                              params['output_dir']))

      params['renderer'] = self.ReadComboboxOption(symbols['RENDERER'],
                                                   symbols['RENDERER_OPTIONS'],
                                                   self.renderers_list)
      params['frame_begin'] = self.GetInt32(symbols['FRAMES_FROM'])
      params['frame_end'] = self.GetInt32(symbols['FRAMES_TO'])
      params['step'] = str(self.GetInt32(symbols['STEP']))
      params['chunk_size'] = str(self.GetInt32(symbols['CHUNK']))
      params['xres'] = str(self.GetInt32(symbols['RES_X']))
      params['yres'] = str(self.GetInt32(symbols['RES_Y']))
      camera = self.ReadComboboxOption(symbols['CAMERA'],
                                       symbols['CAMERA_OPTIONS'],
                                       self.cameras)
      params['camera'] = camera['name']  # TODO: convert camera object to anything sensible
      user_files = [path for (path, checked) in self.file_boxes if checked]
      params['scene_info'] = {
          'dependencies': self.LocateTextures(self.GetDocumentTextures()) + user_files,
          'c4d_version': 'Maya2015'  # TODO: actual c4d version, but now let's find some actual package
      }
      # TODO:renderer specific params??
      return params

  def ReadProjectName(self):
    if self.GetBool(symbols['NEW_PROJ']):
      proj_name = self.GetString(symbols['NEW_PROJ_NAME'])
      proj_name = proj_name.strip()
      if proj_name == '':
        raise self.ValidationError('You must choose existing project or give valid name for a new one.')
      if not re.match(r'^[-\w]*$', proj_name):  # TODO: check the regex vs actual rules
        raise self.ValidationError('Project name \'{}\' contains illegal characters.'.format(proj_name))
      if proj_name in self.project_names:
        raise self.ValidationError('Project named \'{}\' already exists.'.format(proj_name))
      return proj_name
    else:
      return self.ReadComboboxOption(symbols['EXISTING_PROJ_NAME'],
                                     symbols['PROJ_NAME_OPTIONS'],
                                     self.project_names)

  def ReadComboboxOption(self, widget_id, child_id_base, options):
    return options[self.ReadComboboxIndex(widget_id, child_id_base)]

  def ReadComboboxIndex(self, widget_id, child_id_base):
    return self.GetLong(widget_id) - child_id_base

  def GetDocumentTextures(self):
    return [path for id, path in self.document.GetAllTextures()
      if not path.startswith('preset:')]

  def LocateTextures(self, textures):
      """Converts relative texture paths to absolute ones"""
      doc_path = self.document.GetDocumentPath()
      doc_tex_path = os.path.join(doc_path, 'tex')
      tex_paths = [doc_tex_path]
      for i in range(10):
          glob_path = c4d.GetGlobalTexturePath(i)
          if glob_path != '':
              tex_paths.append(glob_path)
      return [self.LocateTexture(tex, tex_paths) for tex in textures]

  def LocateTexture(self, texture, tex_paths):
      if os.path.isabs(texture):
          return texture
      for tex_path in tex_paths:
          abs_path = os.path.join(tex_path, texture)
          if os.path.exists(abs_path):
              return abs_path
      raise self.ValidationError("Unable to locate the texture \"{}\"".format(texture))


class ZyncPlugin(c4d.plugins.CommandData):

  def __init__(self):
    self.dialog = ZyncDialog()

  @show_exceptions
  def Execute(self, doc):
    import_zync_python()
    if not self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID):
      raise Exception("Failed to open dialog window")
    self.dialog.HandleDocumentChange()
    return True

  def RestoreLayout(self, sec_ref):
    """Makes some c4d magic to keep dialogs working"""
    return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)


if __name__ == '__main__':
    bmp = c4d.bitmaps.BaseBitmap()
    bmp.InitWith(os.path.join(dir, "res", "zync.png"))
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID,
        str="Render with Zync...",
        info=c4d.PLUGINFLAG_COMMAND_ICONGADGET,
        icon=bmp,
        help="Render scene using Zync cloud service",
        dat=ZyncPlugin())
