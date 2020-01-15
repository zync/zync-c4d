""" Contains C4dRenderSettings class. """

from importlib import import_module
from zync_c4d_arnold_settings import C4dArnoldSettings
import zync_c4d_constants
from zync_c4d_redshift_settings import C4dRedshiftSettings
import zync_c4d_utils
from zync_c4d_vray_settings import C4dVraySettings

zync_threading = zync_c4d_utils.import_zync_module('zync_threading')
main_thread = zync_threading.MainThreadCaller.main_thread
c4d = import_module('c4d')


class C4dRenderFormatUnsupportedException(Exception):
  """
  Indicates that render format is unsupported.

  :param str message:
  """

  def __init__(self, message):
    super(C4dRenderFormatUnsupportedException, self).__init__(message)


class C4dRendererSettingsUnavailableException(Exception):
  """
  Indicates that renderer settings are unavailable.
  """


class C4dRenderingFailedException(Exception):
  """
  Indicates that rendering failed.

  :param int render_result:
  """
  def __init__(self, render_result):
    super(C4dRenderingFailedException, self).__init__('Error code: %d' % render_result)


class C4dRenderSettings(zync_threading.MainThreadCaller):
  """
  Implements various renderer-related operations using C4D API.

  :param zync_threading.MainThreadExecutor main_thread_executor:
  :param c4d.documents.RenderData render_data:
  :param c4d.documents.BaseDocument document:
  :param c4d.modules.takesystem.BaseTake:
  """

  def __init__(self, main_thread_executor, render_data, document, take):
    zync_threading.MainThreadCaller.__init__(self, main_thread_executor)
    self._render_data = render_data
    self._document = document
    self._take = take

  renderer_name_map = {
    c4d.RDATA_RENDERENGINE_STANDARD: zync_c4d_constants.RendererNames.STANDARD,
    c4d.RDATA_RENDERENGINE_PHYSICAL: zync_c4d_constants.RendererNames.PHYSICAL,
    zync_c4d_constants.RDATA_RENDERENGINE_ARNOLD: zync_c4d_constants.RendererNames.ARNOLD,
    zync_c4d_constants.RDATA_RENDERENGINE_VRAY: zync_c4d_constants.RendererNames.VRAY,
    zync_c4d_constants.RDATA_RENDERENGINE_REDSHIFT: zync_c4d_constants.RendererNames.REDSHIFT,
  }

  supported_formats = {
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
    c4d.FILTER_TIF: 'TIFF'
  }

  @main_thread
  def convert_tokens(self, path):
    """
    Returns the path with tokens converted.

    :param str path:
    :return str:
    """
    render_path_data = {
      '_doc': self._document,
      '_rData': self._render_data,
      '_rBc': self._render_data.GetData(),
      '_take': self._take
    }
    return c4d.modules.tokensystem.StringConvertTokens(path, render_path_data).replace('\\', '/')

  def get_arnold_settings(self):
    """
    Returns Arnold settings.

    :return C4dArnoldSettings:
    :raises:
      C4dRendererSettingsUnavailableException: If settings can't be retrieved.
    """
    video_posts = self._get_video_posts([zync_c4d_constants.ARNOLD_RENDERER])
    return C4dArnoldSettings(self._main_thread_executor, video_posts[0], self._document)

  @main_thread
  def _get_video_posts(self, video_post_types):
    """
    Generates render settings of specified types.

    :param collections.Iterable[int] video_post_types: collection of video post types.
    :return list[c4d.documents.BaseVideoPost]:
    :raises:
      C4dRendererSettingsUnavailableException: If no matching video post is found.
    """
    video_posts = []
    video_post = self._render_data.GetFirstVideoPost()
    while video_post:
      if video_post.GetType() in video_post_types:
        video_posts.append(video_post)
      video_post = video_post.GetNext()
    if not video_posts:
      raise C4dRendererSettingsUnavailableException()
    return video_posts

  @main_thread
  def get_frame_range(self, fps):
    """
    Returns a tuple containing start frame, end frame and frame step.

    :param int fps: FPS from scene settings.
    :return (int, int, int):
    """
    start_frame = self._render_data[c4d.RDATA_FRAMEFROM].GetFrame(fps)
    end_frame = self._render_data[c4d.RDATA_FRAMETO].GetFrame(fps)
    frame_step = self._render_data[c4d.RDATA_FRAMESTEP]
    return start_frame, end_frame, frame_step

  @main_thread
  def get_frame_rate(self):
    """
    Returns the frame rate.

    :return int:
    """
    return self._render_data[c4d.RDATA_FRAMERATE]

  @main_thread
  def get_image_format(self):
    """
    Returns the image format.

    :return str:
    :raises:
      C4dRenderFormatUnsupportedException: If format is unsupported.
    """
    image_format = self._render_data[c4d.RDATA_FORMAT]
    if image_format in self.supported_formats:
      return self.supported_formats[image_format]
    else:
      raise C4dRenderFormatUnsupportedException(
        'Regular image output format not supported. Supported formats: ' +
        ', '.join(self.supported_formats.values()))

  @main_thread
  def get_image_path(self):
    """
    Returns the image save path.

    :return str:
    """
    return self._render_data[c4d.RDATA_PATH]

  @main_thread
  def get_multipass_image_format(self):
    """
    Returns the multipass image format.

    :return str:
    :raises:
      C4dRenderFormatUnsupportedException: If format is unsupported.
    """
    image_format = self._render_data[c4d.RDATA_MULTIPASS_SAVEFORMAT]
    if image_format in self.supported_formats:
      return self.supported_formats[image_format]
    else:
      raise C4dRenderFormatUnsupportedException(
        'Multi-pass image output format not supported. Supported formats: ' +
        ', '.join(self.supported_formats.values()))

  @main_thread
  def get_multipass_image_path(self):
    """
    Returns the multipass image save path.

    :return str:
    """
    return self._render_data[c4d.RDATA_MULTIPASS_FILENAME]

  def get_redshift_settings(self):
    """
    Returns Redshift settings.

    :return C4dRedshiftSettings:
    :raises:
      C4dRendererSettingsUnavailableException: If settings can't be retrieved.
    """
    video_posts = self._get_video_posts(zync_c4d_constants.REDSHIFT_VIDEOPOSTS)
    return C4dRedshiftSettings(self._main_thread_executor, video_posts)

  def get_render_data(self):
    """
    Returns the render data.

    :return c4d.documents.RenderData:
    """
    return self._render_data

  @main_thread
  def get_renderer_name(self):
    """
    Returns the renderer name.

    :return Optional[str]:
    """
    renderer_id = self._render_data[c4d.RDATA_RENDERENGINE]
    if renderer_id is None:
      return None
    elif renderer_id in self.renderer_name_map:
      return self.renderer_name_map[renderer_id]
    else:
      plugin = c4d.plugins.FindPlugin(renderer_id)
      return plugin.GetName() if plugin else str(renderer_id)

  @main_thread
  def get_resolution(self):
    """
    Returns the resolution as a tuple with width and height.

    :return (int, int):
    """
    return int(self._render_data[c4d.RDATA_XRES]), int(self._render_data[c4d.RDATA_YRES])

  def get_vray_settings(self):
    """
    Returns V-Ray settings.

    :return C4dVraySettings:
    :raises:
      C4dRendererSettingsUnavailableException: If settings can't be retrieved.
    """
    video_posts = self._get_video_posts([zync_c4d_constants.VRAY_BRIDGE_PLUGIN_ID])
    return C4dVraySettings(self._main_thread_executor, video_posts[0])

  @main_thread
  def has_image_path(self):
    """
    Checks if image save path is set.

    :return bool:
    """
    return bool(self.get_image_path())

  @main_thread
  def has_multipass_image_path(self):
    """
    Checks if multipass image save path is set.

    :return bool:
    """
    return bool(self.get_multipass_image_path())

  @main_thread
  def is_saving_globally_enabled(self):
    """
    Checks if saving is enabled globally.

    :return bool:
    """
    return self._render_data[c4d.RDATA_GLOBALSAVE]

  @main_thread
  def is_image_saving_enabled(self):
    """
    Checks if image saving is enabled.

    :return bool:
    """
    return self._render_data[c4d.RDATA_SAVEIMAGE]

  @main_thread
  def is_multipass_image_saving_enabled(self):
    """
    Checks if multipass image saving is enabled.

    :return bool:
    """
    return self._render_data[c4d.RDATA_MULTIPASS_SAVEIMAGE] and self._render_data[
      c4d.RDATA_MULTIPASS_ENABLE]

  @main_thread
  def is_multipass_image_format_same_as_regular(self):
    """
    Checks if multipass image format is the same as regular image format.

    :return bool:
    """
    return self._render_data[c4d.RDATA_FORMAT] == self._render_data[c4d.RDATA_MULTIPASS_SAVEFORMAT]

  @main_thread
  def render(self):
    """ Triggers rendering. """
    xres, yres = self.get_resolution()
    bitmap = c4d.bitmaps.MultipassBitmap(xres, yres, c4d.COLORMODE_RGB)
    bitmap.AddChannel(True, True)
    result = c4d.documents.RenderDocument(self._document, self._render_data.GetData(), bitmap,
                                          c4d.RENDERFLAGS_EXTERNAL)
    if result != c4d.RENDERRESULT_OK:
      raise C4dRenderingFailedException(result)

  @main_thread
  def set_state(self, state):
    """
    Sets the state of render data from dict.

    :param dict[Any,Any] state:
    """
    for key, value in state.items():
      if value is not None:
        self._render_data[key] = value

  @main_thread
  def get_state(self, render_data_fields_to_save):
    """
    Gets the state of selected render data fields as a dict.

    :param collections.Iterable[Any] render_data_fields_to_save: A collection of fields to save.
    :return dict[Any,Any]:
    """
    state = dict()
    for key in render_data_fields_to_save:
      value = self._render_data[key]
      if value is not None:
        state[key] = value
    return state
