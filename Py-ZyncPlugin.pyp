import c4d
from c4d import gui, plugins
import os, re


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

class ZyncDialog(gui.GeDialog):

    def CreateLayout(self):
        self.LoadDialogResource(5555)

        return True

    def InitValues(self):
        return True
    
    def Command(self, id, msg):
        if id==symbols["LAUNCH"]:
            gui.MessageDialog("Boom!")
            
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


if __name__ == '__main__':
    bmp = c4d.bitmaps.BaseBitmap()
    bmp.InitWith(os.path.join(dir, "res", "zync.png"))
    plugins.RegisterCommandPlugin(
        PLUGIN_ID, "Render with Zync...", 0, bmp, "Render scene using Zync cloud service", ZyncPlugin())
