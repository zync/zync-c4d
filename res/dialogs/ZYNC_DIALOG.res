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

      GROUP {  // what to do row
          SCALE_H;
          FIT_V;
          SPACE 2,2;
          BORDERSIZE 4,4,4,4;
          BORDERSTYLE BORDER_GROUP_IN;

          STATICTEXT { NAME TAKE_CAPTION; }
          COMBOBOX TAKE { SCALE_H; }
      }  // what to do row end

      GROUP {  // Output row
          SCALE_H;
          FIT_V;
          SPACE 2,2;
          BORDERSIZE 4,4,4,4;
          BORDERSTYLE BORDER_GROUP_IN;
          COLUMNS 1;
          NAME OUTPUT_TITLE;		  
		  
          GROUP {
            SCALE_H;
            COLUMNS 3;

            STATICTEXT { NAME OUTPUT_CAPTION; }
            EDITTEXT OUTPUT_PATH { SCALE_H; }
            BUTTON OUTPUT_PATH_BTN { NAME DOTS; }
          }
          GROUP {
            SCALE_H;
            COLUMNS 3;

            STATICTEXT { NAME MULTIPASS_OUTPUT_CAPTION; }
            EDITTEXT MULTIPASS_OUTPUT_PATH { SCALE_H; }
            BUTTON MULTIPASS_OUTPUT_PATH_BTN { NAME DOTS; }
          }
      }  // Output row end

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
            COLUMNS 1;
            CHECKBOX NOTIFY_COMPLETE { NAME NOTIFY_COMPLETE_CAPTION; }
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
            CHECKBOX UPLOAD_ONLY { NAME UPLOAD_ONLY_CAPTION; }
          }

          GROUP {
            COLUMNS 1;
            FIT_H;
            BUTTON FILES_LIST { NAME FILES_LIST_CAPTION; }
            STATICTEXT AUX_FILES_SUMMARY { CENTER_H; NAME AUX_FILES_SUMMARY; }
          }
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
          COLUMNS 4;
          NAME FRAMES_TITLE;

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
          STATICTEXT RENDERER {
            SCALE_H;
          }

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
          COLUMNS 2;
        }
      }

      GROUP {
          CENTER_H;

        BUTTON ADD_FILE {
          SIZE 0, 16;
          NAME ADD_FILE;
        }

        BUTTON ADD_DIR {
          SIZE 0, 16;
          NAME ADD_DIR;
        }
      }

      GROUP {
        SCALE_H;

        BUTTON OK_FILES {NAME BACK; }
      }
    }
  }
}
