import c4d
from c4d import gui, plugins
import os


PLUGIN_ID = 1000001  # TODO: get own one, this is test one

class ZyncDialog(gui.GeDialog):

    def CreateLayout(self):
        self.LoadDialogResource(5555)

        return True

    def InitValues(self):
        return True
    
    def Command(self, id, msg):
        if id==BTN_FOO["id"]:
            self.SetString(TXT_LABEL["id"], 'Foo')
            
        return True

    def AskClose(self):
        return False  # change to True to disallow closing - to be used during execution?


class ZyncPlugin(c4d.plugins.CommandData):

    dialog = None
    
    def Execute(self, doc):
        self.CreateDialog()
        
        self.document = c4d.documents.GetActiveDocument()
        # print 'GetChanged', self.document.GetChanged()
        # print 'GetObjects', self.document.GetObjects()
        
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=400, defaulth=300)

    def RestoreLayout(self, sec_ref):
        self.CreateDialog()
        return self.dialog.Restore(pluginid=PLUGIN_ID, secret=sec_ref)
    
    def CreateDialog(self):
        if self.dialog is None:
            self.dialog = ZyncDialog()

def load_icon():
    bmp = c4d.bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    icon_path = os.path.join(dir, "res", "zync.png")
    bmp.InitWith(icon_path)
    return bmp

if __name__ == '__main__':
    bmp = load_icon()
    plugins.RegisterCommandPlugin(
        PLUGIN_ID, "Render with Zync...", 0, bmp, "Render scene using Zync cloud service", ZyncPlugin())
