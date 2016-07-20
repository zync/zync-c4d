DIALOG ZYNC_DIALOG {
  NAME DIALOG_TITLE;

  // How the columns work:
  //
  // I didn't find any official documentation about that, but apparently
  // subsequent items are put in subsequent columns. That is, if the
  // number of columns is not set each item will get one column, and
  // if number is set to e.g. 2, the first item will go to column 1,
  // second to col 2, third to col 1 and so on.

  GROUP {  // login row
    SPACE 2,2;
    BORDERSIZE 4,4,4,4;
    COLUMNS 2;
    NAME ACCOUNT_TITLE;

    STATICTEXT LOGGED_LABEL { }
    BUTTON LOGOUT { NAME LOGOUT_CAPTION; }
  }  // login row end

  GROUP {  // settings row
    SCALE_H;
    COLUMNS 2;

    GROUP {  // job settings section
      SCALE_H;
      FIT_V;
      SPACE 2,2;
      BORDERSIZE 4,4,4,4;
      BORDERSTYLE BORDER_GROUP_IN;
      COLUMNS 1;
      NAME JOB_TITLE;

      GROUP {
        SCALE_H;
        COLUMNS 2;

        STATICTEXT { NAME JOB_PRIORITY_CAPTION; }
        EDITNUMBERARROWS JOB_PRIORITY { SIZE 30,0; }
      }

      CHECKBOX IGN_MISSING_PLUGINS { NAME IGN_MISSING_PLUGINS_CAPTION; }

      GROUP {
        SCALE_H;
        COLUMNS 3;

        STATICTEXT { NAME OUTPUT_CAPTION; }
        EDITTEXT OUTPUT_DIR { SCALE_H; }
        BUTTON OUTPUT_DIR_BTN { NAME DOTS; }
      }
    }  // job settings section end

    GROUP {  // vms section
      SCALE_H;
      FIT_V;
      SPACE 2,2;
      BORDERSIZE 4,4,4,4;
      BORDERSTYLE BORDER_GROUP_IN;
      COLUMNS 2;
      NAME VMS_TITLE;


      STATICTEXT { NAME VMS_NUM_CAPTION; }
      EDITNUMBERARROWS VMS_NUM { SCALE_H; }

      STATICTEXT { NAME VMS_TYPE_CAPTION; }
      COMBOBOX VMS_TYPE {
        SCALE_H;
      }

      GROUP {}  // just to push next group to right column

      GROUP {
        SCALE_H;
        COLUMNS 2;

        STATICTEXT EST_PRICE { ALIGN_RIGHT; SCALE_H; NAME EST_COST; }
        BUTTON COST_CALC_LINK { ALIGN_RIGHT; SIZE 0, 10; NAME COST_CALC; }
      }
    }  // vms section end

    GROUP {  // job files section
      SCALE_H;
      FIT_V;
      SPACE 2,2;
      BORDERSIZE 4,4,4,4;
      BORDERSTYLE BORDER_GROUP_IN;
      COLUMNS 2;
      NAME FILES_TITLE;

      GROUP {
          COLUMNS 1;
          CHECKBOX JUST_UPLOAD { NAME JUST_UPLOAD_CAPTION; }
          CHECKBOX NO_UPLOAD { NAME NO_UPLOAD_CAPTION; }
      }

      BUTTON FILES_LIST { ALIGN_RIGHT; SIZE 0,-20; NAME FILES_LIST_CAPTION; }
    }  // job files section end

    GROUP {  // cloud storage section
      SCALE_H;
      FIT_V;
      SPACE 2,2;
      BORDERSIZE 4,4,4,4;
      BORDERSTYLE BORDER_GROUP_IN;
      COLUMNS 1;
      NAME PROJ_TITLE;

      RADIOGROUP {
        SCALE_H;
        COLUMNS 1;

        GROUP {
          SCALE_H;
          COLUMNS 2;

          GROUP {
            COLUMNS 1;

            RADIOGADGET EXISTING_PROJ {
              NAME EXISTING_PROJ_NAME;
            }
            RADIOGADGET NEW_PROJ {
              NAME NEW_PROJ_NAME;
            }
          }
          GROUP {
            SCALE_H;
            COLUMNS 1;

            COMBOBOX EXISTING_PROJ_NAME { SCALE_H; }
            EDITTEXT NEW_PROJ_NAME { SCALE_H; }
          }
        }
      }
    }  // cloud storage section end

    GROUP {  // frames section
      SCALE_H;
      FIT_V;
      SPACE 2,2;
      BORDERSIZE 4,4,4,4;
      BORDERSTYLE BORDER_GROUP_IN;
      COLUMNS 1;
      NAME FRAMES_TITLE;
      COLUMNS 2;

      STATICTEXT { ALIGN_LEFT; NAME FRAMES_CAPTION; }
      EDITTEXT FRAMES { ALIGN_RIGHT; SIZE 100,0; }

      STATICTEXT { ALIGN_LEFT; NAME STEP_CAPTION; }
      EDITNUMBER STEP { ALIGN_RIGHT; SIZE 100,0; }

      STATICTEXT { ALIGN_LEFT; NAME CHUNK_CAPTION; }
      EDITNUMBER CHUNK { ALIGN_RIGHT; SIZE 100,0; }
    }  // frames section end

    GROUP {  // render settings section
      SCALE_H;
      FIT_V;
      SPACE 2,2;
      BORDERSIZE 4,4,4,4;
      BORDERSTYLE BORDER_GROUP_IN;
      COLUMNS 2;
      NAME RENDER_TITLE;

      STATICTEXT { NAME RENDERER_CAPTION; }
      COMBOBOX RENDERER {
        SCALE_H;
        CHILDS {
          REND_C4D, REND_C4D_NAME;
        }
      }

      STATICTEXT { NAME CAMERA_CAPTION; }
      COMBOBOX CAMERA { SCALE_H; }

      STATICTEXT { NAME RESOLUTION_CAPTION; }
      GROUP {
        COLUMNS 3;

        EDITNUMBERARROWS RES_X { SIZE 60,0; }
        STATICTEXT { NAME RESOLUTION_CAPTION2; }
        EDITNUMBERARROWS RES_Y { SIZE 60,0; }
      }
    }  // render settings section end
  }  // settings row end

  GROUP {  // nav row
    SCALE_H;
    CENTER_H;
    COLUMNS 2;
    BORDERSIZE 8,8,8,12;

    BUTTON CLOSE { SCALE_H; SIZE 0, 20; NAME CANCEL; }
    BUTTON LAUNCH { SCALE_H; SIZE 0, 20; NAME LAUNCH_CAPTION; }
  }  // nav row end
}