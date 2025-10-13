# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6 import QtWidgets
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPen, QIcon, QPixmap, QPolygonF
from PySide6.QtWidgets import QMenu
from VeraGrid.Gui.gui_functions import add_menu_entry
from VeraGrid.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Polygon, Square
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from VeraGrid.Gui.Diagrams.Editors.RmsModelEditor.rms_model_editor_dialogue import RmsChoiceDialog
from VeraGrid.Gui.Diagrams.Editors.RmsModelEditor.rms_model_editor_engine import RmsModelEditorGUI
from VeraGrid.Gui.messages import yes_no_question
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Utils.Symbolic.block import Var, DynamicVarType
from VeraGrid.Gui.Diagrams.Editors.RmsModelEditor.rms_model_editor_dialogue import RmsParameterDialog
from VeraGridEngine.Templates.Rms.rms_templates_catalogue import get_load_catalogue
from VeraGridEngine.Utils.Symbolic.symbolic import Const

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class LoadGraphicItem(InjectionTemplateGraphicItem):

    def __init__(self, parent, api_obj: Load, editor: SchematicWidget):
        """

        :param parent:
        :param api_obj:
        :param editor:
        """
        InjectionTemplateGraphicItem.__init__(self,
                                              parent=parent,
                                              api_obj=api_obj,
                                              editor=editor,
                                              device_type_name='load',
                                              w=20,
                                              h=20)

        # triangle
        self.set_glyph(glyph=Polygon(self,
                                     polygon=QPolygonF([QPointF(0, 0),
                                                        QPointF(self.w, 0),
                                                        QPointF(self.w / 2, self.h)]),
                                     update_nexus_fcn=self.update_nexus)
                       )

    @property
    def api_object(self) -> Load:
        return self._api_object

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        """
        Display context menu
        @param event:
        @return:
        """
        if self.api_object is not None:
            menu = QMenu()
            menu.addSection("Load")


            add_menu_entry(menu=menu,
                        text="Rms Editor",
                        function_ptr=self.edit_rms,
                        icon_path=":/Icons/icons/edit.png")

            menu.exec(event.screenPos())
        else:
            pass

    def edit_rms(self):
        # connect generator with connection bus by assigning Va and Vm variables
        self.api_object.assign_input_vars_and_params()

        # load templates
        templates_list, templates_catalogue = get_load_catalogue()

        # add templates to rms choice dialog
        choice_dialog = RmsChoiceDialog(templates_list, parent=self.editor)
        if choice_dialog.exec() == QtWidgets.QDialog.Accepted:

            if choice_dialog.choice == "template":

                # select template
                load_template = templates_catalogue[choice_dialog.selected_template]


                # set parameter values from user input using RmsParameterDialog
                param_dialog = RmsParameterDialog(load_template, parent=self.editor)
                if param_dialog.exec() == QtWidgets.QDialog.Accepted:
                    new_values = param_dialog.get_values()
                    for param, value in new_values.items():
                        setattr(load_template, param, Const(value))  # set parameter value

                # relate Va and Vm variables from template to Va and Vm variables from api_object (which are related to connection bus)

                load_template.Vm = self._api_object.Vm
                load_template.Va = self._api_object.Va

                # assign template to api object
                self.api_object.rms_model.template = load_template

            elif choice_dialog.choice == "editor":

                self.api_object.rms_model.model.external_mapping = {
                    DynamicVarType.P: self.api_object.Pl,
                    DynamicVarType.Q: self.api_object.Ql,

                }
                if self.api_object.Pl not in self.api_object.rms_model.model.algebraic_vars and self.api_object.Ql not in self.api_object.rms_model.model.algebraic_vars:
                    self.api_object.rms_model.model.algebraic_vars.append(self.api_object.Pl)
                    self.api_object.rms_model.model.algebraic_vars.append(self.api_object.Ql)

                if self.api_object.Vm not in self.api_object.rms_model.model.in_vars and self.api_object.Va not in self.api_object.rms_model.model.in_vars:
                    self.api_object.rms_model.model.in_vars.append(self.api_object.Vm)
                    self.api_object.rms_model.model.in_vars.append(self.api_object.Va)

                # if self.api_object.Q_g not in self.api_object.rms_model.model.algebraic_vars:
                #     self.api_object.rms_model.model.algebraic_vars.append(self.api_object.Q_g)
                dlg = RmsModelEditorGUI(self.api_object.rms_model, parent=self.editor)
                dlg.show()