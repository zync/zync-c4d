""" Contains Presenter interface. """

from abc import ABCMeta, abstractmethod


class Presenter(object):
  """ Interface for presenters. """

  __metaclass__ = ABCMeta

  @abstractmethod
  def activate(self):
    """ Activates the presenter. """
    raise NotImplementedError()

  @abstractmethod
  def deactivate(self):
    """ Deactivates the presenter. """
    raise NotImplementedError()

  @abstractmethod
  def on_scene_changed(self):
    """ Called when C4D scene is changed to a different scene. """
    raise NotImplementedError()

  @abstractmethod
  def on_command(self, command_id):
    """
    Called when user interacts with a dialog widget.

    :param int command_id: Id of the widget.
    """
    raise NotImplementedError()
