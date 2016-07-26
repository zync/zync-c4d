import c4d
from c4d import gui, plugins
import os, sys, re, thread, webbrowser
import traceback
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

dir, file = os.path.split(__file__)

PLUGIN_ID = 1000001  # TODO: get own one, this is test one

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


class FilesDialog(gui.GeDialog):

    def __init__(self, auto_files, user_files):
        self.auto_files = auto_files
        self.user_files = user_files
        # Box info format: (path, state)
        # State meaning:
        #  state = 0: unchecked,
        #  state = 1: checked,
        #  state = 2: checked permanently (checked & disabled)
        self.boxes = []
        for path in self.auto_files:
            self.boxes.append((path, 2))
        for path in self.user_files:
            self.boxes.append((path, 1))
        super(FilesDialog, self).__init__()

    def CreateLayout(self):
        self.LoadDialogResource(symbols['FILES_DIALOG'])

        self.RefreshCheckboxes()

        return True

    def RefreshCheckboxes(self):
        self.LayoutFlushGroup(symbols['FILES_LIST_GROUP'])
        for i, (path, state) in enumerate(self.boxes):
            checkbox = self.AddCheckbox(symbols['FILES_LIST_OPTIONS']+i, c4d.BFH_LEFT, 0, 0, name=path)
            self.SetBool(checkbox, state > 0)
            if state > 1:
                self.Enable(checkbox, False)
        self.LayoutChanged(symbols['FILES_LIST_GROUP'])

    def ReadCheckboxes(self):
        self.boxes = [
            (path, 2 if oldstate == 2 else int(self.GetBool(symbols['FILES_LIST_OPTIONS']+i)))
            for i, (path, oldstate) in enumerate(self.boxes)
        ]

    def Command(self, id, msg):
        if id == symbols["CLOSE"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
            self.Close()
        elif id == symbols["OK"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
            self.ReadCheckboxes()
            self.user_files = [
                path for path, state in self.boxes
                if state == 1
            ]
            self.Close()
        elif id == symbols["ADD_FILE"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
            self.AddFile()
        return True

    def AddFile(self):
        self.ReadCheckboxes()
        fname = c4d.storage.LoadDialog()
        if fname is not None:
            self.boxes.append((fname, 1))
            self.RefreshCheckboxes()


class ZyncDialog(gui.GeDialog):

    class ValidationError(Exception):
        pass

    def __init__(self, plugin_instance, document):
        self.pool = ThreadPool(processes = 1)
        self.plugin_instance = plugin_instance
        self.document = document
        self.ConnectToZync(plugin_instance.zync_python)
        super(ZyncDialog, self).__init__()

    def ConnectToZync(self, zync_python):
        if hasattr(self.plugin_instance, 'zync_conn'):
            self.zync_conn = self.plugin_instance.zync_conn
            self.FetchCache()
        else:
            self.async_callback = self.OnConnection
            self.async_result = self.pool.apply_async(lambda: zync_python.Zync(application='c4d'))

    def OnConnection(self, zync_conn):
        self.plugin_instance.zync_conn = self.zync_conn = zync_conn
        self.FetchCache()

    def FetchCache(self):
        self.async_callback = self.OnFetch
        self.async_result = self.pool.apply_async(self._FetchCache)

    def _FetchCache(self):
      """Fetches from server all data needed to show the dialog"""
      self.zync_cache = {}
      self.zync_cache['instance_types'] = self.zync_conn.INSTANCE_TYPES
      self.zync_cache['project_list'] = self.zync_conn.get_project_list()
      self.zync_cache['email'] = self.zync_conn.email
      self.zync_cache['project_name_hint'] = (
          self.zync_conn.get_project_name(self.document.GetDocumentName()))  # TODO: fix web implementation

    def OnFetch(self, _):
        self.CreateMainDialogLayout()

    def CreateLayout(self):
        """Called when dialog opens; creates initial dialog content"""
        self.GroupBegin(symbols['DIALOG_TOP_GROUP'], c4d.BFH_SCALEFIT, 1)

        self.LoadDialogResource(symbols['CONN_DIALOG'])
        self.SetTimer(100)

        self.GroupEnd()

        return True

    def Timer(self, msg):
        if getattr(self, 'async_result', None):
            try:
                result = self.async_result.get(0)
                del self.async_result
                self.async_callback(result)
            except multiprocessing.TimeoutError:
                return
            except Exception as e:
                traceback.print_exc()
                gui.MessageDialog(e.message)
                self.Close()

    def Close(self):
        self.plugin_instance.dialog = False
        self.pool.terminate()
        return super(ZyncDialog, self).Close()

    def Command(self, id, msg):
        if id == symbols["CLOSE"]:
            self.Close()
            self.plugin_instance.Fail()
        elif id == symbols["LOGOUT"]:
            self.plugin_instance.connection_state = None
            self.plugin_instance.zync_conn.logout()
            del self.plugin_instance.zync_conn
            self.Close()
            gui.MessageDialog("Logged out from Zync")
            self.plugin_instance.active = False
        elif id == symbols["COST_CALC_LINK"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
            webbrowser.open('http://zync.cloudpricingcalculator.appspot.com')
        elif id == symbols["LAUNCH"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
            self.LaunchJob()
        elif id == symbols["VMS_NUM"] or id == symbols["VMS_TYPE"]:
            self.UpdatePrice()
        elif id == symbols["FILES_LIST"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
            self.ShowFilesList()
        elif id == symbols["OUTPUT_DIR_BTN"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
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
        elif id == symbols['RENDER_JOB']:
          pass  # TODO: enable all settings
        elif id == symbols['UPLOAD_JOB']:
          pass  # TODO: disable inapplicable settings
        return True

    def ShowFilesList(self):
        dialog = FilesDialog(self.auto_files, self.user_files)
        # That is a bit hacky, but it is needed for RestoreLayout in order
        # to call restore on proper window
        self.plugin_instance.dialog = dialog
        try:
            dialog.Open(dlgtype=c4d.DLG_TYPE_MODAL_RESIZEABLE, pluginid=PLUGIN_ID)
            self.user_files = dialog.user_files
        finally:
            self.plugin_instance.dialog = self

    def CreateMainDialogLayout(self):
        self.LayoutFlushGroup(symbols['DIALOG_TOP_GROUP'])

        self.LoadDialogResource(symbols['ZYNC_DIALOG'])

        document = self.document

        self.textures = self.GetDocumentTextures()
        self.auto_files = self.textures
        self.user_files = []

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

        # Login info
        self.SetString(symbols['LOGGED_LABEL'], 'Logged in as {}'.format(self.zync_cache['email']))  # TODO: gettext?

        self.LayoutChanged(symbols['DIALOG_TOP_GROUP'])

    def SetComboboxContent(self, widget_id, child_id_base, options):
        self.FreeChildren(widget_id)
        for i, option in enumerate(options):
            self.AddChild(widget_id, child_id_base+i, option)
        if options:
            # select the first option
            self.SetInt32(widget_id, child_id_base)

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

    def GetDocumentTextures(self):
        return [path for id, path in self.document.GetAllTextures()
                if not path.startswith('preset:')]

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

    def LaunchJob(self):
        try:
            params = self.CollectParams()
        except self.ValidationError, e:
            gui.MessageDialog(e.message)
        else:
            if '(ALPHA)' in params['instance_type']:
                # TODO: replace standard dialog with something better, without this deceptive call to action on YES
                if not c4d.gui.QuestionDialog(
                        'You\'ve selected an instance type for your job which is '
                        'still in alpha, and could be unstable for some workloads.\n\n'
                        'Submit the job anyway?'):
                    return
            doc_dirpath = self.document.GetDocumentPath()
            doc_name = self.document.GetDocumentName()
            doc_path = os.path.join(doc_dirpath, doc_name)
            self.plugin_instance.SubmitJob(doc_path, params)

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
        params['scene_info'] = {
            'dependencies': self.LocateTextures(self.textures) + self.user_files,
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


class ZyncException(Exception):
    """Zync Exception class

    Nothing special, just to filter our own exceptions.
    """


class ZyncPlugin(c4d.plugins.CommandData):

    dialog = None
    active = False
    connecting = False
    connection_state = None

    def Execute(self, doc):
        try:
            document = c4d.documents.GetActiveDocument()
            if (document.GetDocumentPath() == '' or document.GetChanged()):
                gui.MessageDialog("You must save the active document before rendering it with Zync.")
                return True

            if not hasattr(self, 'zync_python'):
                self.zync_python = self.ImportZyncPython()

            self.dialog = ZyncDialog(self, document)
            if not self.dialog.Open(dlgtype=c4d.DLG_TYPE_MODAL, pluginid=PLUGIN_ID):
                raise Exception("Failed to open dialog window")
        except Exception, e:
            traceback.print_exc()
            c4d.gui.MessageDialog(e.message)
            self.dialog = None
            return False

        return True

    def Fail(self):
        # flushes state in case of closing dialog
        self.dialog = None

    def RestoreLayout(self, sec_ref):
        if self.dialog:
            return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)
        else:
            return True

    def ImportZyncPython(self):
        if os.environ.get('ZYNC_API_DIR'):
            API_DIR = os.environ.get('ZYNC_API_DIR')
        else:
            config_path = os.path.join(os.path.dirname(__file__), 'config_c4d.py')
            if not os.path.exists(config_path):
                raise ZyncException("config_c4d.py file not found")
            import imp
            try:
                config = imp.load_source('config_c4d', config_path)
            except ImportError, e:
                raise ZyncException("Unable to import config_c4d.py:\n" + e.message)
            try:
                API_DIR = config.API_DIR
            except AttributeError:
                raise ZyncException("API_DIR not found in config_c4d.py")
            if not isinstance(API_DIR, basestring):
                raise ZyncException("API_DIR defined in config_c4d.py is not a string")

        sys.path.append(API_DIR)
        import zync

        return zync

    def SubmitJob(self, scene_path, params):
        try:
          self.zync_conn.submit_job('c4d', scene_path, params)
        except self.zync_python.ZyncPreflightError, e:
          gui.MessageDialog("Preflight Check failed:\n{}".format(e))
        except self.zync_python.ZyncError, e:
          gui.MessageDialog("Zync Error:\n{}".format(e))
        except:
          gui.MessageDialog("Unexpected error during job submission")
          raise
        else:
          gui.MessageDialog("Boom!\n\nJob submitted!")
        finally:
          self.dialog.Close()
          self.dialog = None
          self.active = False


if __name__ == '__main__':
    bmp = c4d.bitmaps.BaseBitmap()
    bmp.InitWith(os.path.join(dir, "res", "zync.png"))
    plugins.RegisterCommandPlugin(
        PLUGIN_ID, "Render with Zync...", 0, bmp, "Render scene using Zync cloud service", ZyncPlugin())
