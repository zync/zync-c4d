// To be parsable by read_c4d_symbols(), this file must
// obey some simple rules:
//  - Every symbol must be defined on single, separate line,
//  - Every symbol must have explicit value assigned.
enum {
  ZYNC_DIALOG = 100,
  CONN_DIALOG = 300,
  LOGIN_DIALOG = 400,
  PVM_CONSENT_DIALOG = 400,

  DIALOG_TOP_GROUP = 100001,
  DIALOG_TABS = 100002,
  SETTINGS_TAB = 100003,
  FILES_TAB = 100004,

  TAKE = 100501,
  UPLOAD_ONLY = 100502,

  VMS_SETTINGS_G = 101000,
  VMS_NUM = 101001,
  VMS_NUM = 101001,
  VMS_TYPE = 101002,
  EST_PRICE = 101003,
  COST_CALC_LINK = 101004,

  GCS_G = 102000,
  EXISTING_PROJ = 102001,
  EXISTING_PROJ_NAME = 102002,
  NEW_PROJ = 102003,
  NEW_PROJ_NAME = 102004,

  JOB_SETTINGS_G = 103000,
  JOB_PRIORITY = 103001,
  OUTPUT_PATH = 103003,
  OUTPUT_PATH_BTN = 103004,
  MULTIPASS_OUTPUT_PATH = 103005,
  MULTIPASS_OUTPUT_PATH_BTN = 103006,
  NOTIFY_COMPLETE = 103007,

  JOB_FILES_G = 104000,
  FILES_LIST = 104003,
  AUX_FILES_SUMMARY = 104004,

  FRAMES_G = 105000,
  FRAMES_FROM = 105002,
  FRAMES_TO = 105003,
  STEP = 105004,
  CHUNK = 105005,

  RENDER_G = 106000,
  RENDERER = 106001,
  RES_X = 106003,
  RES_Y = 106004,

  LOGGED_LABEL = 107001,
  LOGOUT = 107002,
  LOGIN = 107003,

  LAUNCH = 108001,

  OK_FILES = 109002,
  ADD_FILE = 109003,
  ADD_DIR = 109004,
  FILES_LIST_GROUP = 109005,
  CANCEL_FILES = 109006,
  CANCEL_CONN = 109007,

  VMS_TYPE_OPTIONS = 210000,
  PROJ_NAME_OPTIONS = 220000,
  RENDERER_OPTIONS = 230000,
  FILES_LIST_OPTIONS = 240000,
  FILES_LIST_UNFOLD_BTNS = 250000,
  TAKE_OPTIONS = 260000,
  OFORMAT_OPTIONS = 270000,

  IDS_ZYNC_SUBMENU = 300000
}
