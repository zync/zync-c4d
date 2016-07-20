import c4d
from c4d import gui, plugins
import os, sys, re, thread, webbrowser


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
        self.SetTitle("Files to upload")

        self.GroupBegin(symbols['BAZ'], c4d.BFH_SCALEFIT, 1)

        self.GroupBegin(symbols['FILES_LIST_GROUP'], c4d.BFH_SCALEFIT, 1)
        self.GroupEnd()

        self.AddButton(symbols['ADD_FILE'], c4d.BFH_CENTER | c4d.BFV_CENTER, name='Add file...')

        self.GroupBegin(symbols['BAR'], c4d.BFH_SCALEFIT, 2)
        self.AddButton(symbols['CLOSE'], c4d.BFH_CENTER | c4d.BFV_CENTER, name='Cancel')
        self.AddButton(symbols['OK'], c4d.BFH_CENTER | c4d.BFV_CENTER, name='Ok')
        self.GroupEnd()

        self.GroupEnd()

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
        self.plugin_instance = plugin_instance
        self.document = document
        super(ZyncDialog, self).__init__()

    def CreateLayout(self):
        self.GroupBegin(symbols['DIALOG_TOP_GROUP'], c4d.BFH_SCALEFIT, 1)

        self.SetTitle("Connecting to Zync...")

        # TODO: make that text sensible
        self.AddStaticText(
            id=symbols['FOO'],
            flags=c4d.BFH_LEFT | c4d.BFV_CENTER | c4d.BFH_SCALE,
            initw=500,
            inith=20,
            name="Connecting to Zync...")
        self.AddButton(symbols['CLOSE'], c4d.BFH_CENTER | c4d.BFV_CENTER, name='Cancel')
        self.SetTimer(100)

        self.GroupEnd()

        return True

    def InitValues(self):
        return True

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
        return True

    def ShowFilesList(self):
        dialog = FilesDialog(self.auto_files, self.user_files)
        # That is a bit hacky, but it is needed for RestoreLayout in order
        # to call restore on proper window
        self.plugin_instance.dialog = dialog
        try:
            dialog.Open(dlgtype=c4d.DLG_TYPE_MODAL, pluginid=PLUGIN_ID)
            self.user_files = dialog.user_files
        finally:
            self.plugin_instance.dialog = self

    def Timer(self, msg):
        # There seems to be no good way to create timer outside the dialog,
        # thats why it's here and not directly in ZyncPlugin.

        c4d.gui.SetMousePointer(c4d.MOUSE_BUSY)
        if self.plugin_instance.connection_state:
            self.SetTimer(0)
            if self.plugin_instance.connection_state == 'success':
                self.LayoutFlushGroup(symbols['DIALOG_TOP_GROUP'])
                self.CreateMainDialogLayout()
                self.LayoutChanged(symbols['DIALOG_TOP_GROUP'])
            else:
                gui.MessageDialog("Error while connecting to Zync:\n\n" + self.plugin_instance.connection_state[1])
                self.Close()
                self.plugin_instance.Fail()

    def CreateMainDialogLayout(self):
        # TODO: move fetching data somewhere else

        self.LoadDialogResource(symbols['ZYNC_DIALOG'])

        zync = self.plugin_instance.zync_conn
        document = self.document

        self.textures = self.GetDocumentTextures()
        self.auto_files = self.textures
        self.user_files = []

        self.instance_types = zync.INSTANCE_TYPES
        self.instance_type_names = self.instance_types.keys()

        # VMs settings
        self.SetLong(symbols['VMS_NUM'], 1)
        self.SetComboboxContent(symbols['VMS_TYPE'],
                                symbols['VMS_TYPE_OPTIONS'],
                                self.instance_type_names)
        self.UpdatePrice()

        # Storage settings (zync project)
        self.project_list = zync.get_project_list()
        self.project_names = [p['name'] for p in self.project_list]
        self.SetComboboxContent(symbols['EXISTING_PROJ_NAME'],
                                symbols['PROJ_NAME_OPTIONS'],
                                self.project_names)
        self.SetBool(symbols['NEW_PROJ'], True)
        new_project_name = zync.get_project_name(document.GetDocumentName())  # TODO: anything more sensible? Update web part?
        self.SetString(symbols['NEW_PROJ_NAME'], new_project_name)

        # General job settings
        self.SetLong(symbols['JOB_PRIORITY'], 50)
        self.SetString(symbols['OUTPUT_DIR'], self.DefaultOutputDir(document))

        # Renderer settings
        self.renderers_list = ['Cinema 4D Standard', 'Cinema 4D Physical']
        self.SetComboboxContent(symbols['RENDERER'],
                                symbols['RENDERER_OPTIONS'],
                                self.renderers_list)
        fps = document.GetFps()
        first_frame = document.GetMinTime().GetFrame(fps)
        last_frame  = document.GetMaxTime().GetFrame(fps)
        self.SetString(symbols['FRAMES'], "{}-{}".format(first_frame, last_frame))
        self.SetLong(symbols['STEP'], 1)
        self.SetLong(symbols['CHUNK'], 10)

        # Camera selection
        self.cameras = self.CollectCameras(document)
        self.SetComboboxContent(symbols['CAMERA'],
                                symbols['CAMERA_OPTIONS'],
                                (c['name'] for c in self.cameras))

        # Resolution
        render_data = document.GetActiveRenderData()
        self.SetLong(symbols['RES_X'], render_data[c4d.RDATA_XRES])
        self.SetLong(symbols['RES_Y'], render_data[c4d.RDATA_YRES])

        # Login info
        self.SetString(symbols['LOGGED_LABEL'], 'Logged in as {}'.format(zync.email))  # TODO: gettext?

    def SetComboboxContent(self, widget_id, child_id_base, options):
        self.FreeChildren(widget_id)
        for i, option in enumerate(options):
            self.AddChild(widget_id, child_id_base+i, option)
        if options:
            # select the first option
            self.SetLong(widget_id, child_id_base)

    def UpdatePrice(self):
        if self.instance_type_names:
            instances_count = self.GetLong(symbols['VMS_NUM'])
            instance_index = self.GetLong(symbols['VMS_TYPE']) - symbols['VMS_TYPE_OPTIONS']
            instance_name = self.instance_type_names[instance_index]
            instance_cost = self.plugin_instance.zync_conn.INSTANCE_TYPES[instance_name]['cost']
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
        params['start_new_slots'] = 1  # value copied from Maya plugin
        params['notify_complete'] = 0  # value copied from Maya plugin
        params['upload_only'] = self.GetBool(symbols['JUST_UPLOAD'])
        params['skip_check'] = self.GetBool(symbols['NO_UPLOAD'])
        params['ignore_plugin_errors'] = self.GetBool(symbols['IGN_MISSING_PLUGINS'])
        params['sync_extra_assets'] = int(bool(self.user_files))  # ??? how does it work?

        params['project'] = self.document.GetDocumentPath()
        params['out_path'] = self.GetString(symbols['OUTPUT_DIR'])
        if not os.path.isabs(params['out_path']):
            params['out_path'] = os.path.abspath(os.path.join(params['project'],
                                                              params['out_path']))

        params['renderer'] = self.ReadComboboxOption(symbols['RENDERER'],
                                                     symbols['RENDERER_OPTIONS'],
                                                     self.renderers_list)
        params['use_standalone'] = 0
        params['frange'] = self.GetString(symbols['FRAMES'])
        params['step'] = self.GetString(symbols['STEP'])
        params['chunk_size'] = self.GetString(symbols['CHUNK'])
        params['xres'] = self.GetString(symbols['RES_X'])
        params['yres'] = self.GetString(symbols['RES_Y'])
        camera = self.ReadComboboxOption(symbols['CAMERA'],
                                         symbols['CAMERA_OPTIONS'],
                                         self.cameras)
        params['camera'] = str(camera)  # TODO: convert camera object to anything sensible
        # TODO:renderer specific params??
        params['texturepaths'] = self.LocateTextures(self.textures)  ## TODO: temporary, for testing
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

    def AskClose(self):
        return False  # change to True to disallow closing - to be used during execution?


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
        if self.active:
            # TODO: restore? reopen? anything?
            # TODO: if we turn modal, then it should never happen
            return True
        self.active = True
        if self.connection_state != 'success':
            self.connection_state = None
        document = c4d.documents.GetActiveDocument()
        if (document.GetDocumentPath() == '' or document.GetChanged()):
            gui.MessageDialog("You must save the active document before rendering it with Zync.")
            self.active = False
            return True

        if not hasattr(self, 'zync_conn') and not self.connecting:
            try:
                self.zync_python = self.ImportZyncPython()
            except ZyncException, e:
                gui.MessageDialog(e.message)
                print e
                return False

            # ZyncDialog will be polling for the result of connection in its Timer() method.
            self.connecting = True
            thread.start_new_thread(self.ConnectToZync, (self.zync_python,))

        self.dialog = ZyncDialog(self, document)
        self.dialog.Open(dlgtype=c4d.DLG_TYPE_MODAL, pluginid=PLUGIN_ID)

        return True

    def Fail(self):
        # flushes state in case of closing dialog
        self.dialog = None
        self.active = False

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

    def ConnectToZync(self, zync_python):
        try:
            self.zync_conn = zync_python.Zync(application='maya')  # TODO: change for c4d
            self.connection_state = 'success'
        except Exception, e:
            self.connection_state = ('error', e.message)
            print e
        finally:
            self.connecting = False

    def SubmitJob(self, scene_path, params):
        try:
          ####
          texturepaths = params.pop('texturepaths')
          gui.MessageDialog("Params:\n\n{}\n\nTexturepaths:\n\n{}".format(
            '\n'.join(map(str, params.iteritems())),
            '\n'.join(texturepaths)))
          ####
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
