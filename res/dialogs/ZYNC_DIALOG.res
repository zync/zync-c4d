DIALOG ZYNC_DIALOG {
  NAME DIALOG_TITLE;

  // How the columns work:
  //
  // I didn't find any official documentation about that, but apparently
  // subsequent items are put in subsequent columns. That is, if the
  // number of columns is not set each item will get one column, and
  // if number is set to e.g. 2, the first item will go to column 1,
  // second to col 2, third to col 1 and so on.

  TAB DIALOG_TABS {
    SCALE_H;
    FIT_V;
    SELECTION_NONE;

    GROUP SETTINGS_TAB {  // First tab - normal dialog content
      SCALE_H;
      FIT_V;
      COLUMNS 1;
      NAME RENDER_JOB_NAME;

      GROUP {  // what to do row
          SCALE_H;
          FIT_V;
          SPACE 2,2;
          BORDERSIZE 4,4,4,4;
          BORDERSTYLE BORDER_GROUP_IN;
          COLUMNS 1;
          NAME WHAT_TO_DO_TITLE;

          RADIOGROUP JOB_KIND {
              GROUP {
                  COLUMNS 2;

                  RADIOGADGET RENDER_JOB {
                    NAME RENDER_JOB_NAME;
                  }
                  RADIOGADGET UPLOAD_JOB {
                    NAME UPLOAD_JOB_NAME;
                  }
              }
          }
      }  // what to do row end

      GROUP {  // settings row
        SCALE_H;
        COLUMNS 2;

        GROUP JOB_SETTINGS_G {  // job settings section
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

          GROUP {
            SCALE_H;
            COLUMNS 3;

            STATICTEXT { NAME OUTPUT_CAPTION; }
            EDITTEXT OUTPUT_DIR { SCALE_H; }
            BUTTON OUTPUT_DIR_BTN { NAME DOTS; }
          }
        }  // job settings section end

        GROUP VMS_SETTINGS_G {  // vms section
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

        GROUP JOB_FILES_G {  // job files section
          SCALE_H;
          FIT_V;
          SPACE 2,2;
          BORDERSIZE 4,4,4,4;
          BORDERSTYLE BORDER_GROUP_IN;
          COLUMNS 2;
          NAME FILES_TITLE;

          GROUP {
              COLUMNS 1;
              CHECKBOX NO_UPLOAD { NAME NO_UPLOAD_CAPTION; }
              CHECKBOX IGN_MISSING_PLUGINS { NAME IGN_MISSING_PLUGINS_CAPTION; }
          }

          BUTTON FILES_LIST { ALIGN_RIGHT; SIZE 0,-20; NAME FILES_LIST_CAPTION; }
        }  // job files section end

        GROUP GCS_G {  // cloud storage section
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

        GROUP FRAMES_G {  // frames section
          SCALE_H;
          FIT_V;
          SPACE 2,2;
          BORDERSIZE 4,4,4,4;
          BORDERSTYLE BORDER_GROUP_IN;
          COLUMNS 1;
          NAME FRAMES_TITLE;
          COLUMNS 4;

          STATICTEXT { NAME FRAMES_CAPTION; }
          EDITNUMBERARROWS FRAMES_FROM { SIZE 100,0; }
          STATICTEXT { NAME DASH; }
          EDITNUMBERARROWS FRAMES_TO { SIZE 100,0; }

          STATICTEXT { NAME STEP_CAPTION; }
          EDITNUMBERARROWS STEP { SIZE 100,0; }
          GROUP {}  // alignment correction
          GROUP {}

          STATICTEXT { NAME CHUNK_CAPTION; }
          EDITNUMBERARROWS CHUNK { SIZE 100,0; }
          GROUP {}  // alignment correction
          GROUP {}
        }  // frames section end

        GROUP RENDER_G {  // render settings section
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

        BUTTON LAUNCH { SCALE_H; SIZE 0, 20; NAME LAUNCH_CAPTION; }
      }  // nav row end
    }
    GROUP FILES_TAB {
      NAME RENDER_JOB_NAME;
      FIT_H;
      FIT_V;
      COLUMNS 1;

      SCROLLGROUP {
        SIZE 500, 200;
        FIT_H;
        FIT_V;
        SCROLL_V;
        SCROLL_H;
        SCROLL_BORDER;

        GROUP FILES_LIST_GROUP {
          SCALE_H;
          FIT_H;
          ALIGN_TOP;
          COLUMNS 1;
        }
      }

      BUTTON ADD_FILE {
        CENTER_H;
        SIZE 0, 16;
        NAME ADD_FILE;
      }

      GROUP {
        SCALE_H;

        BUTTON OK_FILES {NAME BACK; }
      }
    }
  }
}
