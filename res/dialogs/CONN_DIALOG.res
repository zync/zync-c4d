DIALOG CONN_DIALOG {
  NAME DIALOG_TITLE;

  GROUP {
    SPACE 16, 16;
    COLUMNS 1;

    STATICTEXT {
      SIZE 500, 0;
      CENTER_V;
      NAME DIALOG_TITLE;
    }

    BUTTON CLOSE {
      CENTER_H;
      CENTER_V;
      SIZE 0, 20;
      NAME CANCEL;
    }
  }
}
