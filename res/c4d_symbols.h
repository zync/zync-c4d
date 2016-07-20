// To be parsable by read_c4d_symbols(), this file must
// obey some simple rules:
//  - Every symbol must be defined on single, separate line,
//  - Every symbol must have explicit value assigned.
enum {
  ZYNC_DIALOG = 100000,

  DIALOG_TOP_GROUP = 100001,

  VMS_NUM = 101001,
  VMS_TYPE = 101002,
  EST_PRICE = 101003,
  COST_CALC_LINK = 101004,

  EXISTING_PROJ = 102001,
  EXISTING_PROJ_NAME = 102002,
  NEW_PROJ = 102003,
  NEW_PROJ_NAME = 102004,

  JOB_PRIORITY = 103001,
  IGN_MISSING_PLUGINS = 103002,
  OUTPUT_DIR = 103003,
  OUTPUT_DIR_BTN = 103004,

  JUST_UPLOAD = 104001,
  NO_UPLOAD = 104002,
  FILES_LIST = 104003,

  RENDERER = 105001,
  FRAMES = 105002,
  STEP = 105003,
  CHUNK = 105004,

  CAMERA = 106001,
  RES_X = 106002,
  RES_Y = 106003,

  LOGGED_LABEL = 107001,
  LOGOUT = 107002,

  LAUNCH = 108001,

  CLOSE = 109001,
  OK = 109002,
  ADD_FILE = 109003,
  FILES_LIST_GROUP = 109004,

  VMS_TYPE_OPTIONS = 210000,
  PROJ_NAME_OPTIONS = 220000,
  RENDERER_OPTIONS = 230000,
  CAMERA_OPTIONS = 240000,
  FILES_LIST_OPTIONS = 250000,


  FOO = 9998,
  BAR = 9997,
  BAZ = 9996
}