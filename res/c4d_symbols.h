// To be parsable by read_c4d_symbols(), this file must
// obey some simple rules:
//  - Every symbol must be defined on single, separate line,
//  - Every symbol must have explicit value assigned.
enum {
	zyncdialog = 5555,
	DIALOG_TOP_GROUP = 1000,
	VMS_NUM = 1001,
	VMS_TYPE = 1024,
	EST_PRICE = 1026,
	COST_CALC_LINK = 1027,
	
	EXISTING_PROJ = 1002,
	EXISTING_PROJ_NAME = 1023,
	NEW_PROJ = 1003,
	NEW_PROJ_NAME = 1004,
	
	JOB_PRIORITY = 1005,
	OUTPUT_DIR = 1025,
	JUST_UPLOAD = 1006,
	NO_UPLOAD = 1007,
	IGN_MISSING_PLUGINS = 1008,
	
	RENDERER = 1009,
	REND_C4D = 1010,
	FRAMES = 1020,
	STEP = 1021,
	CHUNK = 1022,
	
	CAMERA = 1028,
	RES_X = 1031,
	RES_Y = 1032,
	
	LOGIN = 1033,
	LOGOUT = 1034,
	LOGGED_LABEL = 1035,
	LAUNCH = 1036,
	
	CLOSE = 1037,
	
	VMS_TYPE_OPTIONS = 2000,
	PROJ_NAME_OPTIONS = 3000,
	RENDERER_OPTIONS = 4000,
	CAMERA_OPTIONS = 4200,
	
	FOO = 9998,
	BAR = 9997,
	BAZ = 9996
}