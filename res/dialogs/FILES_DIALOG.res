DIALOG FILES_DIALOG {
  NAME DIALOG_TITLE;
  SCALE_H;
  FIT_H;
  SCALE_V;
  FIT_V;

  GROUP {
    SCALE_H;
    FIT_H;
    SCALE_V;
    FIT_V;
    COLUMNS 1;

    SCROLLGROUP {
      SIZE 500, 200;
      SCALE_H;
      FIT_H;
      SCALE_V;
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

      BUTTON CLOSE { NAME CANCEL; }
      BUTTON OK {NAME OK; }
    }
  }
}
