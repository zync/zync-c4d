import os
from importlib import import_module
from zync_c4d_utils import import_zync_module

zync = import_zync_module('zync')
zync_threading = import_zync_module('zync_threading')
c4d = import_module('c4d')


class VRayExporter(zync_threading.BackgroundTask):
  """
  Exports V-Ray scene to stand-alone file.

  :param str vrscene_path: Output path for vrscene file.
  :param dict params: Job parameters.
  :param function send_vray_scene: A function that submits the job to Zync.
  :param function error_handler:
  """
  def __init__(self, executor, vrscene_path, params, render_data, send_vray_scene, get_vray_render_settings, error_handler):
    super(VRayExporter, self).__init__(executor, error_handler=error_handler)
    self._compressed = None
    self._end_frame = None
    self._export = None
    self._export_geom = None
    self._export_light = None
    self._export_mat = None
    self._export_tex = None
    self._external = None
    self._filename = None
    self._mesh_hex = None
    self._mirror = None
    self._multi_save_image = None
    self._per_frame = None
    self._render = None
    self._resumable = None
    self._save_image = None
    self._separate_files = None
    self._show_vfb = None
    self._start_frame = None
    self._step = None
    self._trans_hex = None
    self._vbf = None
    self._xres = None
    self._yres = None
    self._vrscene_path = vrscene_path
    self._params = params
    self._render_data = render_data
    self._send_vray_scene = send_vray_scene
    self._get_vray_render_settings = get_vray_render_settings

  def run(self):
    """
    Executes stand-alone export and sends a V-Ray job to Zync.

    Methods run in the main thread and must be split into few operations, because C4D
    requires them to go through event handling loop in order to be propagated between calls.
    """
    try:
      self._prepare_settings()
      self._export_scene()
      self.run_on_main_thread(lambda: self._send_vray_scene(self._vrscene_path, self._params))
      self._restore_settings()
    except zync_threading.TaskInterruptedException:
      pass

  @zync_threading.BackgroundTask.main_thread
  def _export_scene(self):
    """
    Exports the scene to vrscene_path.

    :raises:
      zync.ZyncError: if export fails.
    """
    # We just want to trigger rendering, params are arbitrary.
    # Nothing will be rendered as we disabled rendering in prepare_settings and enabled export.
    doc = c4d.documents.GetActiveDocument()
    xres = int(self._render_data[c4d.RDATA_XRES])
    yres = int(self._render_data[c4d.RDATA_YRES])

    bitmap = c4d.bitmaps.MultipassBitmap(xres, yres, c4d.COLORMODE_RGB)
    bitmap.AddChannel(True, True)
    res = c4d.documents.RenderDocument(doc, self._render_data, bitmap,
                                       c4d.RENDERFLAGS_EXTERNAL)
    if res != c4d.RENDERRESULT_OK or not os.listdir(
        os.path.dirname(self._vrscene_path)):
      raise zync.ZyncError('Unable to export vray scene. Error: %d' % res)

  @zync_threading.BackgroundTask.main_thread
  def _prepare_settings(self):
    """
    Saves the current V-Ray render settings and replaces them with a configuration
    for stand-alone exporting.
    """
    vray_bridge = self._get_vray_render_settings()
    rdata = c4d.documents.GetActiveDocument().GetActiveRenderData()

    self._compressed = vray_bridge[c4d.VP_VRAYBRIDGE_TR_COMPRESSED]
    self._end_frame = rdata[c4d.RDATA_FRAMETO]
    self._export = vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT]
    self._export_geom = vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_GEOM]
    self._export_light = vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_LIGHT]
    self._export_mat = vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_MATS]
    self._export_tex = vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_TEXTURES]
    self._external = vray_bridge[c4d.VP_VRAYBRIDGE_TR_RENDER_EXT]
    self._filename = vray_bridge[c4d.VP_VRAYBRIDGE_TR_FILE_NAME]
    self._mesh_hex = vray_bridge[c4d.VP_VRAYBRIDGE_TR_MESH_HEX]
    self._mirror = vray_bridge[c4d.VP_VRAYBRIDGE_VFB_MIRROR_CHANNELS]
    self._multi_save_image = rdata[c4d.RDATA_MULTIPASS_SAVEIMAGE]
    self._per_frame = vray_bridge[c4d.VP_VRAYBRIDGE_TR_PER_FRAME]
    self._render = vray_bridge[c4d.VP_VRAYBRIDGE_TR_RENDER]
    self._resumable = vray_bridge[c4d.VP_VB_RESUMABLERENDER_ENABLE]
    self._save_image = rdata[c4d.RDATA_SAVEIMAGE]
    self._separate_files = vray_bridge[c4d.VP_VRAYBRIDGE_TR_SEPARATE_FILES]
    self._show_vfb = vray_bridge[c4d.VP_VB_SHOW_VFB_WINDOW]
    self._start_frame = rdata[c4d.RDATA_FRAMEFROM]
    self._step = rdata[c4d.RDATA_FRAMESTEP]
    self._trans_hex = vray_bridge[c4d.VP_VRAYBRIDGE_TR_TRANS_HEX]
    self._vbf = vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_SAVE]
    self._xres = rdata[c4d.RDATA_XRES]
    self._yres = rdata[c4d.RDATA_YRES]

    vray_bridge[c4d.VP_VRAYBRIDGE_TR_RENDER] = 0
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_FILE_NAME] = self._vrscene_path
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_SEPARATE_FILES] = 0
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_LIGHT] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_GEOM] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_MATS] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_TEXTURES] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_PER_FRAME] = 0
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_MESH_HEX] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_TRANS_HEX] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_COMPRESSED] = 1
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_RENDER_EXT] = 0
    vray_bridge[c4d.VP_VRAYBRIDGE_VFB_MIRROR_CHANNELS] = 0
    vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_SAVE] = 0
    vray_bridge[c4d.VP_VB_RESUMABLERENDER_ENABLE] = 0
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_PER_FRAME] = 0
    fps = c4d.documents.GetActiveDocument().GetFps()
    rdata = c4d.documents.GetActiveDocument().GetActiveRenderData().GetDataInstance()
    rdata[c4d.RDATA_FRAMEFROM] = c4d.BaseTime(self._params['frame_begin'], fps)
    rdata[c4d.RDATA_FRAMETO] = c4d.BaseTime(self._params['frame_end'], fps)
    rdata[c4d.RDATA_FRAMESTEP] = int(self._params['step'])
    rdata[c4d.RDATA_SAVEIMAGE] = 0
    rdata[c4d.RDATA_MULTIPASS_SAVEIMAGE] = 0
    rdata[c4d.RDATA_XRES] = float(self._params['xres'])
    rdata[c4d.RDATA_YRES] = float(self._params['yres'])
    vray_bridge[c4d.VP_VB_SHOW_VFB_WINDOW] = 0

  @zync_threading.BackgroundTask.main_thread
  def _restore_settings(self):
    """
    Restores the saved V-Ray render settings.
    """
    vray_bridge = self._get_vray_render_settings()
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_RENDER] = self._render
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT] = self._export
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_FILE_NAME] = self._filename
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_SEPARATE_FILES] = self._separate_files
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_LIGHT] = self._export_light
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_GEOM] = self._export_geom
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_MATS] = self._export_mat
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_EXPORT_TEXTURES] = self._export_tex
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_PER_FRAME] = self._per_frame
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_MESH_HEX] = self._mesh_hex
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_TRANS_HEX] = self._trans_hex
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_COMPRESSED] = self._compressed
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_RENDER_EXT] = self._external
    vray_bridge[c4d.VP_VRAYBRIDGE_VFB_MIRROR_CHANNELS] = self._mirror or 0
    vray_bridge[c4d.VP_VRAYBRIDGE_VFB_IMAGE_SAVE] = self._vbf
    vray_bridge[c4d.VP_VB_RESUMABLERENDER_ENABLE] = self._resumable
    vray_bridge[c4d.VP_VRAYBRIDGE_TR_PER_FRAME] = self._per_frame
    rdata = c4d.documents.GetActiveDocument().GetActiveRenderData()
    rdata[c4d.RDATA_FRAMEFROM] = self._start_frame
    rdata[c4d.RDATA_FRAMETO] = self._end_frame
    rdata[c4d.RDATA_FRAMESTEP] = self._step
    rdata[c4d.RDATA_SAVEIMAGE] = self._save_image
    rdata[c4d.RDATA_MULTIPASS_SAVEIMAGE] = self._multi_save_image
    rdata[c4d.RDATA_XRES] = self._xres
    rdata[c4d.RDATA_YRES] = self._yres
    vray_bridge[c4d.VP_VB_SHOW_VFB_WINDOW] = self._show_vfb or 0
