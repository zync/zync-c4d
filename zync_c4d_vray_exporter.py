from importlib import import_module
import os

from zync_c4d_render_settings import C4dRenderingFailedException
from zync_c4d_utils import import_zync_module

zync = import_zync_module('zync')
zync_threading = import_zync_module('zync_threading')
main_thread = zync_threading.InterruptibleMainThreadCaller.main_thread
main_thread_ignore_interrupts = \
  zync_threading.InterruptibleMainThreadCaller.main_thread_ignore_interrupts
c4d = import_module('c4d')


class VRayExporter(zync_threading.InterruptibleMainThreadCaller):
  """
  Exports V-Ray scene to stand-alone file.

  While this is a background task, methods run in the main thread and must be split into few
  operations,
  because C4D requires them to go through event handling loop in order to be propagated between
  calls.

  Callback on_export_finished is called after the scene is exported. It accepts two arguments,
  path to exported vrscene(s) and final job params for submission.

  :param zync_threading.MainThreadExecutor executor:
  :param str vrscene_path: Output path for vrscene file.
  :param dict params: Job parameters.
  :param zync_c4d_scene_settings.C4dSceneSettings scene_settings:
  :param zync_c4d_render_settings.C4dRenderSettings render_settings:
  :param (str, dict[Any,Any]) -> None send_vray_job:
  """

  def __init__(self, executor, vrscene_path, params, scene_settings, render_settings,
               send_vray_job):
    zync_threading.InterruptibleMainThreadCaller.__init__(self, executor)
    self._vrscene_path = vrscene_path
    self._params = params
    self._render_settings = render_settings
    self._scene_settings = scene_settings
    self._send_vray_job = send_vray_job
    self._saved_render_settings = None
    self._saved_vray_settings = None

  def run(self):
    """ Executes stand-alone export and calls the callback that sends a V-Ray job to Zync. """
    try:
      self._prepare_settings()
      self._export_scene()
      self._send_vray_job()
    except zync_threading.TaskInterruptedException:
      pass
    finally:
      self._maybe_restore_settings()

  @main_thread
  def _export_scene(self):
    """
    Exports the scene to vrscene_path.

    :raises:
      zync.ZyncError: if export fails.
    """
    # We just want to trigger rendering, params are arbitrary.
    # Nothing will be rendered as we disabled rendering in prepare_settings and enabled export.
    try:
      self._render_settings.render()
      if not os.listdir(os.path.dirname(self._vrscene_path)):
        raise zync.ZyncError(
          'Unable to export vray scene. Exported file(s) %s not found' % self._vrscene_path)
    except C4dRenderingFailedException as err:
      raise zync.ZyncError('Unable to export vray scene. %s' % err.message)

  @main_thread
  def _prepare_settings(self):
    """
    Saves the current V-Ray render settings and replaces them with a configuration
    for stand-alone exporting.
    """
    vray_bridge_export_state = {
      c4d.VP_VRAYBRIDGE_TR_SEPARATE_FILES: 0,
      c4d.VP_VRAYBRIDGE_TR_TRANS_HEX: 1,
      c4d.VP_VRAYBRIDGE_VFB_IMAGE_SAVE: 0,
      c4d.VP_VRAYBRIDGE_TR_PER_FRAME: 0,
      c4d.VP_VRAYBRIDGE_TR_RENDER: 0,
      c4d.VP_VB_RESUMABLERENDER_ENABLE: 0,
      c4d.VP_VRAYBRIDGE_TR_COMPRESSED: 1,
      c4d.VP_VRAYBRIDGE_TR_EXPORT: 1,
      c4d.VP_VRAYBRIDGE_TR_EXPORT_GEOM: 1,
      c4d.VP_VRAYBRIDGE_TR_EXPORT_LIGHT: 1,
      c4d.VP_VRAYBRIDGE_TR_EXPORT_MATS: 1,
      c4d.VP_VRAYBRIDGE_TR_EXPORT_TEXTURES: 1,
      c4d.VP_VRAYBRIDGE_TR_RENDER_EXT: 0,
      c4d.VP_VRAYBRIDGE_TR_MESH_HEX: 1,
      c4d.VP_VRAYBRIDGE_VFB_MIRROR_CHANNELS: 0,
      c4d.VP_VB_SHOW_VFB_WINDOW: 0,
      c4d.VP_VRAYBRIDGE_TR_FILE_NAME: self._vrscene_path,
    }
    vray_settings = self._render_settings.get_vray_settings()
    self._saved_vray_settings = vray_settings.get_state(vray_bridge_export_state.keys())
    vray_settings.set_state(vray_bridge_export_state)

    fps = self._scene_settings.get_fps()
    render_settings_export_state = {
      c4d.RDATA_FRAMEFROM: c4d.BaseTime(self._params['frame_begin'], fps),
      c4d.RDATA_FRAMETO: c4d.BaseTime(self._params['frame_end'], fps),
      c4d.RDATA_FRAMESTEP: int(self._params['step']),
      c4d.RDATA_XRES: float(self._params['xres']),
      c4d.RDATA_YRES: float(self._params['yres']),
      c4d.RDATA_SAVEIMAGE: False,
      c4d.RDATA_MULTIPASS_SAVEIMAGE: False,
    }

    self._saved_render_settings = self._render_settings.get_state(
      render_settings_export_state.keys())
    self._render_settings.set_state(render_settings_export_state)

  @main_thread_ignore_interrupts
  def _maybe_restore_settings(self):
    if self._saved_vray_settings is not None:
      self._render_settings.get_vray_settings().set_state(self._saved_vray_settings)
    if self._saved_render_settings is not None:
      self._render_settings.set_state(self._saved_render_settings)
