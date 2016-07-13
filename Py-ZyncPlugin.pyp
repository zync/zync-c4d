import c4d
from c4d import gui, plugins
import os, sys, re, thread


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


class ZyncConnectionDialog(gui.GeDialog):
    """This is the dialog shown directly after launching the plugin
    
    This dialog is responsible for:
        - informing the user that plugin is connecting to Zync server
        - informing the user that manual action in browser window may
            be necessary
        - repeatably check connection state and triggering main plugin
            window when connection is ready
    """
    
    def __init__(self, plugin_instance):
        self.plugin_instance = plugin_instance
        super(ZyncConnectionDialog, self).__init__()

    def CreateLayout(self):
        self.SetTitle("Connecting to Zync...")
        self.GroupBegin(symbols['BAR'], 0)
        self.AddStaticText(
            id=symbols['FOO'],
            flags=c4d.BFH_CENTER | c4d.BFV_CENTER,
            initw=1000,
            inith=50,
            name="The plugin is currently connecting to Zync. This operation may take some time.\n\n" +
                 "If the browser window opens, follow the instructions within there \n" +
                 "to connect the plugin to your Google account.")
        self.GroupEnd()
        self.SetTimer(100)
        return True
        
    def Timer(self, msg):
        # There seems to be no good way to create timer outside the dialog,
        # thats why it's here and not directly in ZyncPlugin.
            
        if self.plugin_instance.connection_state:
            c4d.gui.SetMousePointer(c4d.MOUSE_NORMAL)
            if self.plugin_instance.connection_state == 'success':
                self.Close()
                self.plugin_instance.ShowMainWindow()
            else:
                gui.MessageDialog("Error while connecting to Zync:\n\n" + self.plugin_instance.connection_state[1].message)
                self.Close()
                self.plugin_instance.Fail()
            self.SetTimer(0)
        else:
            c4d.gui.SetMousePointer(c4d.MOUSE_BUSY)


class ZyncMainDialog(gui.GeDialog):
    
    def __init__(self, plugin_instance):
        self.plugin_instance = plugin_instance
        super(ZyncMainDialog, self).__init__()

    def CreateLayout(self):
        self.LoadDialogResource(symbols['zyncdialog'])
        self.SetString(symbols['LOGGED_LABEL'], 'Logged in as {}'.format(self.plugin_instance.zync_conn.email))  # TODO: gettext
        return True

    def InitValues(self):
        return True
    
    def Command(self, id, msg):
        if id == symbols["CLOSE"]:
            self.Close()
        elif id == symbols["LAUNCH"] and not msg[c4d.BFM_ACTION_DP_MENUCLICK]:
            self.LaunchJob()
        return True
        
    def LaunchJob(self):
        # TODO: collect actual job data
        self.plugin_instance.LaunchJob()

    def AskClose(self):
        return False  # change to True to disallow closing - to be used during execution?
        
        
class ZyncException(Exception):
    """Zync Exception class
    
    Nothing special, just to filter our own exceptions.
    """


class ZyncPlugin(c4d.plugins.CommandData):

    dialog = None
    active = False
    
    def Execute(self, doc):
        if self.active: return  # prevent opening multiple zync windows
        self.active = True
        self.connection_state = None
        if (c4d.documents.GetActiveDocument().GetDocumentPath() == '' or 
                c4d.documents.GetActiveDocument().GetChanged()):
            gui.MessageDialog("You must save the active document before rendering it with Zync.")
            self.active = False
            return True

        if hasattr(self, 'zync_conn'):
            # no need to connect, just show the window
            self.ShowMainWindow()
            return True

        try:
            zync_python = self.ImportZyncPython()
        except ZyncException, e:
            gui.MessageDialog(e.message)
            print e
            return False

        connection_dialog = ZyncConnectionDialog(self)
        c4d.gui.SetMousePointer(c4d.MOUSE_BUSY)
        self.dialog = connection_dialog
        connection_dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=400, defaulth=300)
        
        # ZyncConnectionDialog will be polling for the result of connection in its Timer() method.
        thread.start_new_thread(self.ConnectToZync, (zync_python,))
        return True
        
    def ShowMainWindow(self):
        document = c4d.documents.GetActiveDocument()
        self.experiment_swapless = self.zync_conn.is_experiment_enabled('EXPERIMENT_SWAPLESS')
        self.new_project_name = self.zync_conn.get_project_name(document.GetDocumentName())

        self.dialog = ZyncMainDialog(self)
        
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=400, defaulth=300)
        
    def Fail(self):
        # called by ZyncConnectionDialog in case of connection failure
        self.dialog = none
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
            self.zync_conn = zync_python.Zync(application='maya')
            self.connection_state = 'success'
        except Exception, e:
            self.connection_state = ('error', e.message)
            print 'Exception in zync.Zync()'
            print e

    def LaunchJob(self):
        self.dialog.Close()
        gui.MessageDialog("Boom!\n\n" + '\n'.join(self.CollectDeps()))
        self.active = True
        
    def CollectDeps(self):
        document = c4d.documents.GetActiveDocument()
        materials = document.GetMaterials()
        # THIS IS THE "PRETTY" WAY TO GET _JUST NORMAL TEXTURES_
        # shaders = (material[c4d.MATERIAL_COLOR_SHADER] for material in materials)
        # texture_paths_with_nones = (shader[c4d.BITMAPSHADER_FILENAME] for shader in shaders)
        # texture_paths = [path for path in texture_paths_with_nones if path is not None]
        
        # THIS IS THE AWFUL WAY, BUT SHOULD FIND ANYTHING THAT COULD BE FOUND
        # IT MAY ALSO FIND _A LOT OF OTHER THINGS_ WHICH WE DO NOT WANT
        
        # This is an ugly hack, but whatever.
        meaningful_indices = set(i for i in c4d.__dict__.itervalues() if isinstance(i, int))
        
        textures = set()
        for material in materials:
            for i in meaningful_indices:
                try:
                    if material[i] and hasattr(material[i], '__getitem__'):
                        textures.add(material[i][c4d.BITMAPSHADER_FILENAME])
                except (AttributeError, IndexError):
                    pass  # just ignore indices throwing exceptions on read

        doc_path = document.GetDocumentPath()
        doc_name = document.GetDocumentName()
        tex_path = os.path.join(doc_path, "tex")
        textures = list(textures)
        for i, t in enumerate(textures):
            if not os.path.isabs(t):
                # TODO: what about c4d.GetGlobalTexturePath()?
                textures[i] = os.path.join(tex_path, t)
        
        return [os.path.join(doc_path, doc_name)] + textures


if __name__ == '__main__':
    bmp = c4d.bitmaps.BaseBitmap()
    bmp.InitWith(os.path.join(dir, "res", "zync.png"))
    plugins.RegisterCommandPlugin(
        PLUGIN_ID, "Render with Zync...", 0, bmp, "Render scene using Zync cloud service", ZyncPlugin())
