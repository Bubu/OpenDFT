#!/usr/bin/python
from __future__ import division
import sys
import os
import numpy as np

os.environ['ETS_TOOLKIT'] = 'qt4'
from pyface.qt import QtGui, QtCore
from visualization import StructureVisualization, BandStructureVisualization, ScfVisualization,OpticalSpectrumVisualization,colormap_list
import solid_state_tools as sst
from solid_state_tools import p_table,p_table_rev
from exciting_handler import Handler as Handler
from little_helpers import no_error_dictionary,CopySelectedCellsAction,PasteIntoTable
import pickle
import time
import threading


try:
    import queue
except:
    import Queue as queue

esc_handler = Handler()
event_queue = queue.Queue()




class MayaviQWidget(QtGui.QWidget):
    def __init__(self, crystal_structure, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.visualization = StructureVisualization(crystal_structure)
        self.ui = self.visualization.edit_traits(parent=self,
                                                 kind='subpanel').control
        layout.addWidget(self.ui)
        self.ui.setParent(self)

    def update_plot(self,keep_view = False):
        self.visualization.update_plot(keep_view=keep_view)

    def update_crystal_structure(self, crystal_structure):
        self.visualization.crystal_structure = crystal_structure

    def do_select_event(self):
        pass


class EntryWithLabel(QtGui.QWidget):
    def __init__(self, parent,label,value=None):
        QtGui.QWidget.__init__(self, parent)
        self.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        self.layout = QtGui.QHBoxLayout(self)
        self.textbox = QtGui.QLineEdit(self)
        self.textbox.setMaximumWidth(200)
        self.label_widget = QtGui.QLabel(label,parent=self)
        self.label_widget.setMaximumWidth(90)
        self.layout.setAlignment(QtCore.Qt.AlignLeft)
        self.layout.addWidget(self.label_widget)
        self.layout.addWidget(self.textbox)
        self.editFinished_command = None

        if value is not None:
            self.textbox.setText(value)

    def get_text(self):
        return self.textbox.text()

    def set_text(self,text):
        self.textbox.setText(text)

    def connect_editFinished(self,command):
        self.editFinished_command = command
        self.textbox.editingFinished.connect(self.handleEditingFinished)

    def handleEditingFinished(self):
        if self.textbox.isModified():
            self.editFinished_command()
        self.textbox.setModified(False)


class OptionFrame(QtGui.QGroupBox):
    def __init__(self, parent,options,title='',tooltips={},checkbuttons=[]):
        QtGui.QGroupBox.__init__(self, parent)
        self.widgets_per_line = 4
        self.setTitle(title)
        self.tooltips = tooltips
        self.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        self.parent = parent
        self.options = options
        self.layout = QtGui.QGridLayout(self)
        # self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.entry_dict = {}
        self.checkbuttons = []
        for text,state in checkbuttons:
            cb = QtGui.QCheckBox(text,parent=self)
            if state:
                cb.nextCheckState()
            self.checkbuttons.append(cb)
            self.layout.addWidget(cb)
        self.make_option_entries()

    def make_option_entries(self):
        counter = len(self.checkbuttons)//self.widgets_per_line+self.widgets_per_line
        for option_key,option_value in self.options.items():
            entry = EntryWithLabel(self,option_key,option_value)
            if option_key in self.tooltips.keys():
                entry.setToolTip(self.tooltips[option_key].replace('\n','<br>'))

            self.layout.addWidget(entry,counter//self.widgets_per_line,counter%self.widgets_per_line)
            self.entry_dict[option_key] = entry
            counter += 1

    def read_all_entries(self):
        for key,entry in self.entry_dict.items():
            self.options[key] = entry.get_text()

    def set_all_entries(self):
        for key,value in self.options.items():
            self.entry_dict[key].set_text(value)

    def read_checkbuttons(self):
        res = {}
        for cb in self.checkbuttons:
            res[cb.text()] = cb.checkState()
        return res


class DftEngineWindow(QtGui.QWidget):
    def __init__(self, parent):
        self.parent = parent
        self.abort_bool = False

        QtGui.QWidget.__init__(self, parent)
        # self.setSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)
        self.layout = QtGui.QGridLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        mygroupbox = QtGui.QWidget()
        myform = QtGui.QFormLayout()

        self.scroll_area = QtGui.QScrollArea(parent=self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(800)
        self.scroll_area.setWidget(mygroupbox)

        self.layout.addWidget(self.scroll_area)

        self.general_option_widget = OptionFrame(self,esc_handler.general_options,title='General options')
        myform.addRow(self.general_option_widget)

        self.scf_option_widget = OptionFrame(self,esc_handler.scf_options,title='Groundstate options',tooltips=esc_handler.scf_options_tooltip)
        myform.addRow(self.scf_option_widget)

        self.bs_option_widget = OptionFrame(self,esc_handler.bs_options,title='Bandstructure options',checkbuttons=[['Calculate',True]])
        myform.addRow(self.bs_option_widget)

        self.relax_option_widget = OptionFrame(self,esc_handler.relax_options,title='Structure relaxation options')
        myform.addRow(self.relax_option_widget)

        self.gw_option_widget = OptionFrame(self,esc_handler.gw_options,title='GW options',tooltips=esc_handler.gw_options_tooltip)
        myform.addRow(self.gw_option_widget)

        self.phonons_option_widget = OptionFrame(self,esc_handler.phonons_options,title='Phonon options')
        myform.addRow(self.phonons_option_widget)

        self.optical_spectrum_option_widget = OptionFrame(self,esc_handler.optical_spectrum_options,title='Excited states options')
        myform.addRow(self.optical_spectrum_option_widget)

        mygroupbox.setLayout(myform)

        self.button_widget = QtGui.QWidget(self)
        self.button_widget.show()
        self.button_layout = QtGui.QHBoxLayout(self.button_widget)
        self.button_layout.setAlignment(QtCore.Qt.AlignLeft)

        self.start_ground_state_calculation_button = QtGui.QPushButton('Start Ground\nState Calculation', self.button_widget)
        self.start_ground_state_calculation_button.setFixedWidth(150)
        self.start_ground_state_calculation_button.setFixedHeight(50)
        self.start_ground_state_calculation_button.clicked.connect(self.start_ground_state_calculation)
        self.button_layout.addWidget(self.start_ground_state_calculation_button)

        self.start_relax_button = QtGui.QPushButton('Start Structure\nRelaxation', self.button_widget)
        self.start_relax_button.setFixedWidth(150)
        self.start_relax_button.setFixedHeight(50)
        self.start_relax_button.clicked.connect(self.start_relax)
        self.button_layout.addWidget(self.start_relax_button)

        self.start_gw_button = QtGui.QPushButton('Start GW', self.button_widget)
        self.start_gw_button.setFixedWidth(150)
        self.start_gw_button.setFixedHeight(50)
        self.start_gw_button.clicked.connect(self.start_gw)
        self.button_layout.addWidget(self.start_gw_button)

        self.start_phonon_button = QtGui.QPushButton('Start Phonon\nBandstructure', self.button_widget)
        self.start_phonon_button.setFixedWidth(150)
        self.start_phonon_button.setFixedHeight(50)
        self.start_phonon_button.clicked.connect(self.start_phonons)
        self.button_layout.addWidget(self.start_phonon_button)

        self.start_optical_spectrum_button = QtGui.QPushButton('Calculate optical\nspectrum', self.button_widget)
        self.start_optical_spectrum_button.setFixedWidth(150)
        self.start_optical_spectrum_button.setFixedHeight(50)
        self.start_optical_spectrum_button.clicked.connect(self.start_optical_spectrum_calculation)
        self.button_layout.addWidget(self.start_optical_spectrum_button)

        self.abort_calculation_button = QtGui.QPushButton('Abort Calculation', self.button_widget)
        self.abort_calculation_button.setFixedWidth(150)
        self.abort_calculation_button.setFixedHeight(50)
        self.abort_calculation_button.clicked.connect(self.abort_calculation)
        self.button_layout.addWidget(self.abort_calculation_button)

        self.execute_error_dialog = QtGui.QErrorMessage(parent=self)
        self.execute_error_dialog.resize(500, 200)

        self.layout.addWidget(self.button_widget)

        trash_bs_points = np.array([[0, 0, 0], [0.750, 0.500, 0.250], [0.500, 0.500, 0.500]
                                       , [0.000, 0.000, 0.000], [0.500, 0.500, 0.000], [0.750, 0.500, 0.250],
                                    [0.750, 0.375, 0.375], [0.000, 0.000, 0.000]])
        trash_bs_labels = ['GAMMA', 'W', 'L', 'GAMMA', 'X', 'W', 'K', 'GAMMA']
        self.band_structure_points = zip(trash_bs_points, trash_bs_labels)
        self.show()

    def update_all(self):
        self.scf_option_widget.set_all_entries()
        self.general_option_widget.set_all_entries()
        self.gw_option_widget.set_all_entries()
        self.bs_option_widget.set_all_entries()
        self.optical_spectrum_option_widget.set_all_entries()

    def do_select_event(self):
        pass

    def check_if_engine_is_running_and_warn_if_so(self):
        if esc_handler.custom_command_active:
            return
        if esc_handler.is_engine_running():
            self.execute_error_dialog.showMessage('Engine is already running')
            raise Exception('Engine is already running')

    def read_all_option_widgets(self):
        self.scf_option_widget.read_all_entries()
        self.general_option_widget.read_all_entries()
        self.gw_option_widget.read_all_entries()
        self.bs_option_widget.read_all_entries()
        self.optical_spectrum_option_widget.read_all_entries()

    def prepare_start(self):
        self.abort_bool = False
        self.check_if_engine_is_running_and_warn_if_so()
        self.read_all_option_widgets()

    def start_ground_state_calculation(self):
        self.prepare_start()

        tasks = []
        if esc_handler.will_scf_run():
            tasks.append('scf')

        bs_checkers = self.bs_option_widget.read_checkbuttons()
        if bs_checkers['Calculate']:
            bs_points = self.band_structure_points
            tasks.append('bandstructure')
        else:
            bs_points = None
        try:
            esc_handler.start_ground_state_calculation(self.parent.crystal_structure, band_structure_points=bs_points)
            QtCore.QTimer.singleShot(1000,lambda: self.parent.check_engine(tasks))
        except Exception as e:
            error_message = 'Could not perform Dft Calculation. Task failed with message:<br><br>' + repr(
                e) + '<br><br>Try following<br>: 1.Check if the selected dft engine is correctly installed<br>' \
                     '2. Check if the input file was correctly parsed into the respective folder (e.g. input.xml in exciting_files for exciting)'
            self.execute_error_dialog.showMessage(error_message)
        else:
            self.parent.status_bar.set_engine_status(True)

    def start_relax(self):
        self.prepare_start()
        tasks = ['relax']
        try:
            esc_handler.start_relax(self.parent.crystal_structure)
            QtCore.QTimer.singleShot(1000,lambda: self.parent.check_engine(tasks))
        except Exception as e:
            error_message = 'Could not perform Dft Calculation. Task failed with message:<br><br>' + repr(
                e) + '<br><br>Try following<br>: 1.Check if the selected dft engine is correctly installed<br>' \
                     '2. Check if the input file was correctly parsed into the respective folder (e.g. input.xml in exciting_files for exciting)'
            self.execute_error_dialog.showMessage(error_message)
        else:
            self.parent.status_bar.set_engine_status(True)

    def start_gw(self):
        self.prepare_start()

        tasks = []
        if esc_handler.will_scf_run():
            tasks.append('scf')
        bs_checkers = self.bs_option_widget.read_checkbuttons()
        if bs_checkers['Calculate']:
            tasks.append('bandstructure')
        tasks.extend(['g0w0','g0w0 bands'])
        try:
            esc_handler.start_gw(self.parent.crystal_structure,self.band_structure_points)
            QtCore.QTimer.singleShot(1000,lambda: self.parent.check_engine(tasks))
        except Exception as e:
            error_message = 'Could not perform Dft Calculation. Task failed with message:<br><br>' + repr(
                e) + '<br><br>Try following<br>: 1.Check if the selected dft engine is correctly installed<br>' \
                     '2. Check if the input file was correctly parsed into the respective folder (e.g. input.xml in exciting_files for exciting)'
            self.execute_error_dialog.showMessage(error_message)
        else:
            self.parent.status_bar.set_engine_status(True)

    def start_phonons(self):
        self.prepare_start()

        tasks = ['phonons']
        try:
            esc_handler.start_phonon_calculation(self.parent.crystal_structure,self.band_structure_points)
            QtCore.QTimer.singleShot(2000,lambda: self.parent.check_engine(tasks))
        except Exception as e:
            error_message = 'Could not perform Dft Calculation. Task failed with message:<br><br>' + repr(
                e) + '<br><br>Try following<br>: 1.Check if the selected dft engine is correctly installed<br>' \
                     '2. Check if the input file was correctly parsed into the respective folder (e.g. input.xml in exciting_files for exciting)'
            self.execute_error_dialog.showMessage(error_message)
        else:
            self.parent.status_bar.set_engine_status(True)

    def start_optical_spectrum_calculation(self):
        self.prepare_start()

        tasks = ['optical spectrum']
        try:
            esc_handler.start_optical_spectrum(self.parent.crystal_structure)
            QtCore.QTimer.singleShot(2000,lambda: self.parent.check_engine(tasks))
        except Exception as e:
            error_message = 'Could not perform Dft Calculation. Task failed with message:<br><br>' + repr(
                e) + '<br><br>Try following<br>: 1.Check if the selected dft engine is correctly installed<br>' \
                     '2. Check if the input file was correctly parsed into the respective folder (e.g. input.xml in exciting_files for exciting)'
            self.execute_error_dialog.showMessage(error_message)
        else:
            self.parent.status_bar.set_engine_status(True)

    def abort_calculation(self):
        self.abort_bool = True
        esc_handler.kill_engine()


class ScfWindow(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.scf_widget = ScfVisualization(parent=self)
        layout.addWidget(self.scf_widget)

    def do_select_event(self):
        pass


class PlotWithTreeview(QtGui.QWidget):
    def __init__(self,Visualizer,data_dictionary,parent=None):
        QtGui.QWidget.__init__(self)
        self.parent = parent
        self.data_dictionary = data_dictionary
        self.layout = QtGui.QHBoxLayout(self)
        self.plot_widget = Visualizer(parent=self)
        self.treeview = QtGui.QTreeWidget(parent=self)
        self.treeview.setMaximumWidth(200)
        self.treeview.setHeaderHidden(True)
        self.treeview.itemSelectionChanged.connect(self.handle_item_changed)

        self.treeview.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.treeview.customContextMenuRequested.connect(self.openMenu)

        self.layout.addWidget(self.plot_widget)
        self.layout.addWidget(self.treeview)

        self.show()

    def delete_selected_item(self):
        index = self.treeview.selectedIndexes()[0]
        item = self.treeview.itemFromIndex(index)
        bs_name = item.text(0)
        del self.data_dictionary[bs_name]
        self.update_tree()

    # def rename_selected_item(self):
    #     index = self.treeview.selectedIndexes()[0]
    #     item = self.treeview.itemFromIndex(index)
    #     bs_name = item.text(0)


    def openMenu(self, position):
        indexes = self.treeview.selectedIndexes()
        if len(indexes) > 0:

            level = 0
            index = indexes[0]
            while index.parent().isValid():
                index = index.parent()
                level += 1

        menu = QtGui.QMenu()
        menu.addAction('Delete',self.delete_selected_item)
        # menu.addAction('Rename', self.rename_selected_item)
        menu.exec_(self.treeview.viewport().mapToGlobal(position))


    def handle_item_changed(self):
        indexes = self.treeview.selectedIndexes()
        if len(indexes) == 0:
            return
        item = self.treeview.itemFromIndex(indexes[0])
        bs_name = item.text(0)
        self.plot_widget.plot(self.data_dictionary[bs_name])

    def add_result_key(self, title):
        item = QtGui.QTreeWidgetItem(self.treeview.invisibleRootItem(), [title])
        return item

    def clear_treeview(self):
        self.treeview.clear()

    def update_tree(self):
        self.treeview.clear()
        for key,value in self.data_dictionary.items():
            self.add_result_key(key)

    def do_select_event(self):
        self.update_tree()


class StatusBar(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self)
        # self.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        self.running_text = 'Engine is running'
        self.not_running_text = 'Engine is stopped'
        # self.setMaximumHeight(20)
        self.layout = QtGui.QVBoxLayout(self)
        self.layout.setAlignment(QtCore.Qt.AlignRight)
        self.status_label = QtGui.QLabel(self.not_running_text)
        # self.status_label.setMaximumHeight(20)
        self.layout.addWidget(self.status_label)
        self.show()

    def set_engine_status(self,status,tasks=None):
        if status:
            if tasks:
                tasks_string = ', '.join(tasks)
                tasks_string2 = ' with Tasks: '+tasks_string
            else:
                tasks_string2 = ''
            self.status_label.setText(self.running_text+tasks_string2)
        else:
            self.status_label.setText(self.not_running_text)


class EngineOptionsDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        super(EngineOptionsDialog, self).__init__(parent)

        self.parent = parent
        self.command_filename = ''

        self.buttonBox = QtGui.QDialogButtonBox(self)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Apply)

        self.buttonBox.accepted.connect(self.accept_own)
        self.buttonBox.rejected.connect(self.reject_own)
        self.buttonBox.button(QtGui.QDialogButtonBox.Apply).clicked.connect(self.apply)


        self.grid_layout_widget =QtGui.QWidget(self)
        self.grid_layout = QtGui.QGridLayout(self.grid_layout_widget)

        self.custom_command_checkbox = QtGui.QCheckBox('Use custom command', parent=self)
        self.grid_layout.addWidget(self.custom_command_checkbox, 0, 0, 2, 1)


        self.load_custom_command_button = QtGui.QPushButton('Select command file',self)
        self.load_custom_command_button.setFixedWidth(150)
        self.load_custom_command_button.setFixedHeight(30)
        self.load_custom_command_button.clicked.connect(self.load_custom_command)
        self.grid_layout.addWidget(self.load_custom_command_button,0, 1, 2, 1)

        self.filename_label = QtGui.QLabel(self.grid_layout_widget)
        self.grid_layout.addWidget(self.filename_label, 2, 0, 1, 2)

        self.species_path_entry = EntryWithLabel(self,'Dft engine path')
        self.grid_layout.addWidget(self.species_path_entry, 3, 0, 1, 2)

        self.verticalLayout = QtGui.QVBoxLayout(self)
        self.verticalLayout.addWidget(self.grid_layout_widget)
        self.verticalLayout.addWidget(self.buttonBox)

    def apply(self):
        self.parent.project_properties['custom command'] = self.filename_label.text()
        self.parent.project_properties['custom command active'] = bool(self.custom_command_checkbox.checkState())
        esc_handler.custom_command = self.filename_label.text()
        esc_handler.custom_command_active = bool(self.custom_command_checkbox.checkState())
        species_path = self.species_path_entry.get_text()
        if len(species_path) > 0:
            self.parent.project_properties['custom dft folder'] = species_path
            esc_handler.exciting_folder = species_path

    def accept_own(self):
        self.apply()
        self.close()

    def reject_own(self):
        self.reject()

    def load_custom_command(self):
        self.custom_command_checkbox.setEnabled(True)
        file_dialog = QtGui.QFileDialog()
        file_dialog.setNameFilters(["sh script (*.sh)", "All (*.*)"])

        if file_dialog.exec_():
            file_name = file_dialog.selectedFiles()
            if type(file_name) == list or type(file_name) is tuple:
                file_name = file_name[0]
            if len(file_name) == 0:
                return
            self.filename_label.setText(file_name)

    def update_all(self):

        if not self.parent.project_properties['custom command']:
            self.custom_command_checkbox.setEnabled(False)
        else:
            if self.parent.project_properties['custom command active']:
                if not self.custom_command_checkbox.checkState():
                    self.custom_command_checkbox.toggle()
        self.species_path_entry.set_text(esc_handler.exciting_folder)
        self.filename_label.setText(self.parent.project_properties['custom command'])


class OptionWithTreeview(PlotWithTreeview):
    def __init__(self,side_panel,data_dictionary,parent=None):
        super(OptionWithTreeview, self).__init__(side_panel,data_dictionary,parent)
        self.add_result_key('None')

    def handle_item_changed(self):
        indexes = self.treeview.selectedIndexes()
        if len(indexes) == 0:
            return
        item = self.treeview.itemFromIndex(indexes[0])
        bs_name = item.text(0)

        plot_options = self.plot_widget.get_options()

        if main.mayavi_widget.visualization.cp is not None:
            main.mayavi_widget.update_plot(keep_view=True)
        if bs_name != 'None':
            main.mayavi_widget.visualization.plot_density((self.data_dictionary[bs_name]),**plot_options)

    def update_tree(self):
        self.treeview.clear()
        for key,value in self.data_dictionary.items():
            self.add_result_key(key)
        self.add_result_key('None')


class SliderWithEntry(QtGui.QWidget):
    def __init__(self,parent=None,label=None,limits=[0,1],value=None):
        super(SliderWithEntry, self).__init__(parent)
        # self.horizontalLayoutWidget.setGeometry(QtCore.QRect(90, 150, 160, 31))
        self.limits = limits
        if value is None:
            self.value = limits[0]
        if value < limits[0] or value > limits[1]:
            raise ValueError('Value must be within bounds')

        self.value = value
        self.horizontalLayout = QtGui.QGridLayout(self)

        if label is not None:
            self.label = QtGui.QLabel(label)
            self.horizontalLayout.addWidget(self.label,0,0)
            counter = 1
        else:
            counter = 0

        limit_range = limits[1]-limits[0]

        self.horizontalSlider = QtGui.QSlider(self)
        self.horizontalSlider.setMinimumWidth(200)
        self.horizontalSlider.setOrientation(QtCore.Qt.Horizontal)
        self.horizontalSlider.setValue((self.value-limits[0])/limit_range*100)
        QtCore.QObject.connect(self.horizontalSlider, QtCore.SIGNAL('valueChanged(int)'), self.change_text)

        self.horizontalLayout.addWidget(self.horizontalSlider,0,counter)

        self.lineEdit = QtGui.QLineEdit(self)
        self.lineEdit.setText("{0:1.1f}".format(self.value))
        self.horizontalLayout.addWidget(self.lineEdit,0,1+counter)
        self.horizontalLayout.setColumnStretch(0+counter, 3)
        self.horizontalLayout.setColumnStretch(1+counter, 1)


    def change_text(self):
        val = self.horizontalSlider.value()*(self.limits[1]-self.limits[0])/100+self.limits[0]
        self.lineEdit.setText("{0:1.1f}".format(val))
        self.value = val

    # def change_slider(self):
    #     try:
    #         val = float(self.lineEdit.text())
    #     except:
    #         return
    #     self.value = val
    #     self.horizontalSlider.setValue(val)

    def get_value(self):
        try:
            val = float(self.lineEdit.text())
        except:
            val = self.value
        return val


class KsStatePlotOptionWidget(QtGui.QWidget):

    def __init__(self,parent):
        super(KsStatePlotOptionWidget, self).__init__(parent)
        self.parent = parent
        self.setSizePolicy(QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Expanding)
        self.verticalLayoutWidget = QtGui.QWidget(self)
        self.verticalLayout = QtGui.QVBoxLayout(self.verticalLayoutWidget)

        self.opacity_slider = SliderWithEntry(self.verticalLayoutWidget,label='Opacity',limits=[0,1],value=0.5)
        self.verticalLayout.addWidget(self.opacity_slider)

        self.contours_entry = EntryWithLabel(self,'Contours:','10')
        self.verticalLayout.addWidget(self.contours_entry)

        self.transparent_checkbox = QtGui.QCheckBox('Transparent')
        self.transparent_checkbox.toggle()
        self.verticalLayout.addWidget(self.transparent_checkbox)


        self.colormap_combobox = QtGui.QComboBox(self)
        self.verticalLayout.addWidget(self.colormap_combobox)
        for el in colormap_list:
            self.colormap_combobox.addItem(el)
        index = self.colormap_combobox.findText('hot', QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.colormap_combobox.setCurrentIndex(index)
        self.colormap_combobox.currentIndexChanged.connect(self.parent.handle_item_changed)


        button_frame = QtGui.QWidget(self)
        self.button_layout = QtGui.QHBoxLayout(button_frame)
        self.verticalLayout.addWidget(button_frame)
        self.button_layout.setAlignment(QtCore.Qt.AlignLeft)

        self.apply_button = QtGui.QPushButton('Apply')
        self.apply_button.setFixedSize(100,50)
        self.apply_button.clicked.connect(self.parent.handle_item_changed)
        self.button_layout.addWidget(self.apply_button)

    def get_options(self):
        opacity = self.opacity_slider.get_value()

        contour_str = self.contours_entry.get_text()
        if ',' in contour_str or '.' in contour_str:
            contours = contour_str.split(',')
            contours = [float(x) for x in contours]
        else:
            contours = int(contour_str)

        transparent = bool(self.transparent_checkbox.checkState())
        colormap = colormap_list[self.colormap_combobox.currentIndex()]
        out_dic = {'opacity':opacity,'contours':contours,'transparent':transparent,'colormap':colormap}


        return out_dic
        # self.test_label = QtGui.QLabel('asdas')
        # self.verticalLayout.addWidget(self.test_label)

        # self.verticalLayoutWidget.show()


class KsStateWindow(QtGui.QDialog):
    def __init__(self,parent):
        super(KsStateWindow, self).__init__(parent)
        self.setFixedSize(700,500)
        self.parent = parent
        self.main_widget = QtGui.QWidget(parent=self)
        self.layout = QtGui.QVBoxLayout(self)
        self.calc_ks_group = QtGui.QGroupBox(parent=self.main_widget)
        self.calc_ks_group.setTitle('Calculate KS state')
        self.layout.addWidget(self.calc_ks_group)

        self.sub_layout = QtGui.QGridLayout(self.calc_ks_group)

        self.k_point_entry = EntryWithLabel(self.calc_ks_group,'k point')
        self.sub_layout.addWidget(self.k_point_entry,0,0)

        self.n_band_entry = EntryWithLabel(self.calc_ks_group,'Band index')
        self.sub_layout.addWidget(self.n_band_entry,0,1)

        button_frame = QtGui.QWidget(self.calc_ks_group)
        self.sub_layout.addWidget(button_frame,2,0,1,0)

        button_layout = QtGui.QHBoxLayout(button_frame)

        self.calculate_button = QtGui.QPushButton('Calculate KS State',button_frame)
        self.calculate_button.setFixedWidth(150)
        self.calculate_button.setFixedHeight(50)
        self.calculate_button.clicked.connect(self.calculate_ks_state)
        button_layout.addWidget(self.calculate_button)

        self.choose_nk_button = QtGui.QPushButton(button_frame)
        self.choose_nk_button.setFixedWidth(150)
        self.choose_nk_button.setFixedHeight(50)
        self.choose_nk_button.clicked.connect(self.choose_nk)
        button_layout.addWidget(self.choose_nk_button)

        self.plot_group = QtGui.QGroupBox(parent=self.main_widget)
        self.plot_group.setTitle('Calculate KS state')
        self.layout.addWidget(self.plot_group)

        self.plot_widget = OptionWithTreeview(KsStatePlotOptionWidget,self.parent.ks_densities,parent=self)

        self.sub_layout2 = QtGui.QVBoxLayout(self.plot_group)
        self.sub_layout2.addWidget(self.plot_widget)

        self.plot_widget.update_tree()



    def calculate_ks_state(self):
        n_band = int(self.n_band_entry.get_text())
        k = int(self.k_point_entry.get_text())


        esc_handler.calculate_ks_density(self.parent.crystal_structure,[k,n_band])

        QtCore.QTimer.singleShot(500, self.check_engine)

    def choose_nk(self):
        pass


    def check_engine(self):
        tasks=['ks density']
        if esc_handler.is_engine_running(tasks=tasks):
            self.parent.status_bar.set_engine_status(True,tasks=tasks)
            QtCore.QTimer.singleShot(500, self.check_engine)
        else:
            self.parent.status_bar.set_engine_status(False)
            message, err = esc_handler.engine_process.communicate()
            if ('error' in message.lower() or len(err)>0):
                error_message = 'DFT calculation finished with an error:<br><br>' + message+'<br>Error:<br>'+err \
                                + '<br><br>Try following:<br>1.Check if the selected dft engine is correctly installed<br>' \
                                  '2. Check if the input file was correctly parsed into the respective folder (e.g. input.xml in exciting_files for exciting)'
                self.parent.error_dialog.showMessage(error_message)

            ks_dens = esc_handler.load_ks_state()
            n_band = int(self.n_band_entry.get_text())
            k = int(self.k_point_entry.get_text())
            key = "k{} n{}".format(k,n_band)
            if ks_dens is not None:
                self.parent.ks_densities[key] = ks_dens
                self.plot_widget.update_tree()


class MainWindow(QtGui.QMainWindow):
    def __init__(self, central_window, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.central_window = central_window

    def closeEvent(self, event):
        self.central_window.close_application()
        event.ignore()


class EditStructureWindow(QtGui.QDialog):
    "TODO: Clean unit cell correctly for new structure. Make the buttons to really set the structure"
    def __init__(self,parent):
        super(EditStructureWindow, self).__init__(parent)
        self.setWindowTitle('Edit Structure')
        self.setFixedSize(650, 700)
        self.parent = parent
        self.anything_changed = False

        self.crystal_structure = None
        self.number_of_atoms = 1

        self.main_layout = QtGui.QHBoxLayout(self)

        self.structure_widget = QtGui.QWidget(self)
        self.main_layout.addWidget(self.structure_widget)

        self.verticalLayout = QtGui.QVBoxLayout(self.structure_widget)
        self.unit_cell_box = QtGui.QGroupBox(self.structure_widget)
        self.unit_cell_box.setTitle('Unit Cell')
        self.verticalLayout.addWidget(self.unit_cell_box)


        self.unit_cell_layout = QtGui.QVBoxLayout(self.unit_cell_box)
        self.unit_cell_layout.setAlignment(QtCore.Qt.AlignTop)

        unit_cell_option_widget = QtGui.QWidget(self.unit_cell_box)
        unit_cell_option_widget.setFixedHeight(50)
        self.unit_cell_option_layout = QtGui.QHBoxLayout(unit_cell_option_widget)
        self.unit_cell_layout.addWidget(unit_cell_option_widget)

        self.scale_entry = EntryWithLabel(self,'Scale')
        self.scale_entry.setFixedHeight(50)
        self.unit_cell_option_layout.addWidget(self.scale_entry)
        self.scale_entry.set_text('1.0')
        self.scale_entry.connect_editFinished(self.handle_change)

        self.unit_cell_table =  QtGui.QTableWidget(self.unit_cell_box)
        self.unit_cell_table.setColumnCount(3)
        self.unit_cell_table.setRowCount(3)
        self.unit_cell_table.setFixedWidth(328)
        self.unit_cell_table.setFixedHeight(128)

        # copy_action_unit = CopySelectedCellsAction(self.unit_cell_table)
        # self.unit_cell_table.addAction(copy_action_unit)

        self.unit_cell_layout.addWidget(self.unit_cell_table)

        item = QtGui.QTableWidgetItem()
        self.unit_cell_table.setHorizontalHeaderItem(0, item)
        item.setText('x')

        item = QtGui.QTableWidgetItem()
        self.unit_cell_table.setHorizontalHeaderItem(1, item)
        item.setText('y')

        item = QtGui.QTableWidgetItem()
        self.unit_cell_table.setHorizontalHeaderItem(2, item)
        item.setText('z')

        for i in range(3):
            for j in range(3):
                item = QtGui.QTableWidgetItem()
                self.unit_cell_table.setItem(i,j,item)

        self.atom_box = QtGui.QGroupBox(self.structure_widget)
        self.atom_box.setTitle('Atoms')
        self.verticalLayout.addWidget(self.atom_box)

        self.atom_layout = QtGui.QVBoxLayout(self.atom_box)

        self.atom_table = QtGui.QTableWidget(self.atom_box)
        copy_action_atoms = CopySelectedCellsAction(self.atom_table)
        self.atom_table.addAction(copy_action_atoms)
        paste_action = PasteIntoTable(self.atom_table,self)
        self.atom_table.addAction(paste_action)

        self.atom_table.setColumnCount(4)
        self.atom_table.setRowCount(1)
        self.atom_table.setFixedWidth(450)
        self.atom_table.setFixedHeight(300)
        self.make_header()
        self.atom_layout.addWidget(self.atom_table)

        self.atom_table_buttons_widget = QtGui.QWidget(self)
        self.atom_layout.addWidget(self.atom_table_buttons_widget)

        self.atom_table_buttons_layout = QtGui.QHBoxLayout(self.atom_table_buttons_widget)
        self.atom_table_buttons_layout.setAlignment(QtCore.Qt.AlignLeft)

        self.add_atom_button = QtGui.QPushButton('Add atom',self)
        self.add_atom_button.setFixedWidth(150)
        self.add_atom_button.clicked.connect(self.add_atom)
        self.atom_table_buttons_layout.addWidget(self.add_atom_button)

        self.remove_atom_button = QtGui.QPushButton('Remove atoms',self)
        self.remove_atom_button.setFixedWidth(150)
        self.remove_atom_button.clicked.connect(self.remove_atoms)
        self.atom_table_buttons_layout.addWidget(self.remove_atom_button)

        self.buttonBox = QtGui.QDialogButtonBox(self)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok|QtGui.QDialogButtonBox.Apply)
        self.verticalLayout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.button(QtGui.QDialogButtonBox.Apply).clicked.connect(self.apply)

        header = self.atom_table.horizontalHeader()
        header.setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        header.setResizeMode(1, QtGui.QHeaderView.Stretch)
        header.setResizeMode(2, QtGui.QHeaderView.Stretch)
        header.setResizeMode(3, QtGui.QHeaderView.Stretch)

        self.unit_cell_table.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)
        self.unit_cell_table.verticalHeader().setResizeMode(QtGui.QHeaderView.Stretch)

        self.atom_table.itemChanged.connect(self.handle_change)
        self.unit_cell_table.itemChanged.connect(self.handle_change)

    def apply(self):
        if self.anything_changed:
            crystal_structure = self.read_tables()
            main.crystal_structure = crystal_structure
            # self.handle_change() # Probably unnecessary
            # self.handle_change() # Probably unnecessary

    def accept(self):
        self.apply()
        super(EditStructureWindow, self).accept()

    def reject(self):
        if self.anything_changed:
            main.mayavi_widget.update_crystal_structure(main.crystal_structure)
            main.mayavi_widget.update_plot()
        super(EditStructureWindow, self).reject()

    def make_header(self):
        item = QtGui.QTableWidgetItem()
        self.atom_table.setHorizontalHeaderItem(0, item)
        item = QtGui.QTableWidgetItem()
        self.atom_table.setHorizontalHeaderItem(1, item)
        item = QtGui.QTableWidgetItem()
        self.atom_table.setHorizontalHeaderItem(2, item)
        item = QtGui.QTableWidgetItem()
        self.atom_table.setHorizontalHeaderItem(3, item)
        item = self.atom_table.horizontalHeaderItem(0)
        item.setText("Species")
        item = self.atom_table.horizontalHeaderItem(1)
        item.setText("x")
        item = self.atom_table.horizontalHeaderItem(2)
        item.setText("y")
        item = self.atom_table.horizontalHeaderItem(3)
        item.setText("z")

    def set_structure(self,structure):
        self.crystal_structure = structure

    def clear_unit_cell_table(self):
        self.unit_cell_table.clearContents()

    def clear_atom_table(self):
        self.atom_table.clearContents()
        # self.make_header()

    def disconnect_tables(self):
        try:
            self.unit_cell_table.itemChanged.disconnect()
            self.atom_table.itemChanged.disconnect()
        except Exception as e:
            print(e)

    def connect_tables(self):
        self.unit_cell_table.itemChanged.connect(self.handle_change)
        self.atom_table.itemChanged.connect(self.handle_change)

    def add_atom(self):
        self.disconnect_tables()

        n_rows = self.atom_table.rowCount()
        self.atom_table.setRowCount(n_rows+1)
        for j in range(4):
            item = QtGui.QTableWidgetItem()
            self.atom_table.setItem(n_rows,j,item)
        self.connect_tables()

    def remove_atoms(self,atoms=None):
        self.disconnect_tables()
        if atoms is None:
           atoms = sorted(set(index.row() for index in self.atom_table.selectedIndexes()))
        for atom in atoms[::-1]:
            self.atom_table.removeRow(atom)
        self.connect_tables()
        self.handle_change()

    def update_fields(self):
        self.disconnect_tables()
        self.scale_entry.set_text('1.0')
        try:
            if self.crystal_structure is None:
                self.clear_atom_table()
                self.clear_unit_cell_table()
                self.set_number_of_atoms(6)
            else:
                unit_cell = self.crystal_structure.lattice_vectors
                scale = self.crystal_structure.scale
                self.scale_entry.set_text('{0:1.6f}'.format(scale))
                for i in range(3):
                    for j in range(3):
                        self.unit_cell_table.item(i,j).setText("{0:1.6f}".format(unit_cell[i,j]/scale))

                n_atoms = self.crystal_structure.atoms.shape[0]
                self.set_number_of_atoms(n_atoms)
                for i,atom in enumerate(self.crystal_structure.atoms):
                    coords = atom[0:3]
                    for j,coord in enumerate(coords):
                        item = self.atom_table.item(i,j+1)
                        item.setText('{0:1.6f}'.format(coord))
                    item = self.atom_table.item(i, 0)
                    item.setText(p_table[atom[3]])
        except Exception as e:
            print(e)

        self.connect_tables()

    def set_number_of_atoms(self,N):
        self.atom_table.setRowCount(N)
        self.number_of_atoms = N
        for i in range(N):
            for j in range(4):
                item = QtGui.QTableWidgetItem()
                self.atom_table.setItem(i,j,item)

    def read_tables(self):
        unit_cell = np.zeros((3,3))
        for i in range(3):
            for j in range(3):
                item = self.unit_cell_table.item(i,j)
                unit_cell[i,j] = float(item.text())

        try:
            scale_string = self.scale_entry.get_text()
            scale = float(scale_string)
        except:
            scale = 1.0
        unit_cell = unit_cell*scale

        n_rows = self.atom_table.rowCount()
        atoms = np.zeros((n_rows,4))
        for i in range(n_rows):
            a_type = self.atom_table.item(i,0).text()
            try:
                a_type = int(a_type)
                a_type_is_number = True
            except:
                a_type_is_number = False
            if a_type not in p_table_rev.keys():
                continue
            coord = np.zeros((1,3))
            skip_bool = False
            for j in range(1,4):
                try:
                    coord[0,j-1] = float(self.atom_table.item(i,j).text())
                except:
                    skip_bool = True
                    break
            if skip_bool:
                continue
            atoms[i,:3] = coord
            if not a_type_is_number:
                a_type = p_table_rev[a_type]
            atoms[i,3] = a_type

        atoms_clean = atoms[atoms[:,3]!=0,:]
        return sst.CrystalStructure(unit_cell,atoms_clean, scale=scale)

    def handle_change(self):
        self.anything_changed = True
        crystal_structure = self.read_tables()
        main.mayavi_widget.update_crystal_structure(crystal_structure)
        main.mayavi_widget.update_plot()


class CentralWindow(QtGui.QWidget):
    def __init__(self,parent=None, *args, **kwargs):
        super(CentralWindow, self).__init__(*args, **kwargs)
        self.project_loaded = False
        self.project_directory = None
        self.parent=parent
        self.crystal_structure = None
        self.band_structures = {}
        self.optical_spectra = {}
        self.ks_densities = {}
        self.project_properties = {'title': '','dft engine':'','custom command':'','custom command active':False,'custom dft folder':''}

        self.error_dialog = QtGui.QErrorMessage(parent=self)
        self.error_dialog.resize(700, 600)

        self.layout = QtGui.QGridLayout(self)
        self.mayavi_widget = MayaviQWidget(self.crystal_structure, parent=self)

        self.band_structure_window = PlotWithTreeview(Visualizer=BandStructureVisualization, data_dictionary=self.band_structures, parent=self)
        self.optical_spectra_window = PlotWithTreeview(Visualizer=OpticalSpectrumVisualization, data_dictionary=self.optical_spectra, parent=self)
        self.dft_engine_window = DftEngineWindow(self)
        self.scf_window = ScfWindow(parent=self)

        self.tabWidget = QtGui.QTabWidget()
        self.tabWidget.currentChanged.connect(self.tab_is_changed)
        self.layout.addWidget(self.tabWidget)

        self.status_bar = StatusBar()
        self.layout.addWidget(self.status_bar)

        self.engine_option_window = EngineOptionsDialog(self)
        self.ks_state_window = KsStateWindow(self)
        self.structure_window = EditStructureWindow(self)

        self.tab_layout = QtGui.QVBoxLayout()
        self.tabWidget.setLayout(self.tab_layout)

        self.list_of_tabs = [self.mayavi_widget,self.dft_engine_window,self.band_structure_window,self.optical_spectra_window,self.scf_window]


        self.tabWidget.addTab(self.list_of_tabs[0], 'Structure')
        self.tabWidget.addTab(self.list_of_tabs[1], 'DFT-Engine')
        self.tabWidget.addTab(self.list_of_tabs[2],'Bandstructure')
        self.tabWidget.addTab(self.list_of_tabs[3],'Optical Spectrum')
        self.tabWidget.addTab(self.list_of_tabs[4], 'Scf')
        self.tabWidget.show()

        self.show()
        self.window = MainWindow(self)
        self.window.setWindowTitle("OpenDFT")
        self.window.setGeometry(50, 50, 1300, 900)
        self.window.setCentralWidget(self)
        self.make_menu_bar()

        self.window.show()

        if DEBUG:
            if sys.platform in ['linux', 'linux2']:
                # project_directory = r"/home/jannick/OpenDFT_projects/diamond/"
                project_directory = r"/home/jannick/OpenDFT_projects/LiBH4"
            else:
                project_directory = r'D:\OpenDFT_projects\test'
            # self.load_saved_results()
            QtCore.QTimer.singleShot(500, lambda: self.load_project(folder_name=project_directory))


    def tab_is_changed(self,i):
        self.list_of_tabs[i].do_select_event()

    def overwrite_handler(self):
        "TODO this is horrible"
        esc_handler_new = Handler()
        for method in dir(esc_handler_new):
            command = 'type(esc_handler_new.'+method+')'
            new_type = eval(command)
            if new_type == dict:
                eval('esc_handler.'+method+'.clear()')
                eval('esc_handler.'+method+'.update(esc_handler_new.'+method+')')
            else:
                pass
                # exec('esc_handler.' + method + ' = esc_handler_new.'+method)
        esc_handler.exciting_folder = esc_handler.find_exciting_folder()

    def make_new_project(self):
        folder_name = QtGui.QFileDialog().getExistingDirectory(parent=self)
        if len(folder_name) > 1:
            if self.project_loaded:
                self.save_results()
                self.reset_results_and_plots()
            self.project_directory = folder_name
            esc_handler.project_directory = self.project_directory
            self.initialize_project()

    def initialize_project(self):
        self.project_properties.update({'title': '','dft engine':'','custom command':'','custom command active':False,'custom dft folder':''})
        self.window.setWindowTitle("OpenDFT - " + self.project_directory)
        os.chdir(self.project_directory)
        self.project_loaded = True

    def reset_results_and_plots(self):
        self.crystal_structure = None
        self.overwrite_handler()
        self.project_properties.clear()
        for key, value in self.band_structures.items():
            del self.band_structures[key]
        for key, value in self.optical_spectra.items():
            del self.optical_spectra[key]
        for key, value in self.ks_densities.items():
            del self.ks_densities[key]
        self.mayavi_widget.visualization.clear_plot()
        self.band_structure_window.plot_widget.clear_plot()
        self.band_structure_window.clear_treeview()
        self.scf_window.scf_widget.clear_plot()
        self.optical_spectra_window.plot_widget.clear_plot()
        self.optical_spectra_window.clear_treeview()
        self.dft_engine_window.update_all()

    def load_project(self,folder_name=None,*args):
        if folder_name is None:
            folder_name = QtGui.QFileDialog().getExistingDirectory(parent=self)
        if len(folder_name) > 1:
            self.reset_results_and_plots()
            self.project_directory = folder_name
            os.chdir(self.project_directory)
            esc_handler.project_directory = self.project_directory
            self.load_saved_results()
            self.dft_engine_window.update_all()
            self.window.setWindowTitle("OpenDFT - "+self.project_directory)
            self.project_loaded = True

    def save_results(self):
        try:
            self.dft_engine_window.read_all_option_widgets()
            a = {'crystal structure': self.crystal_structure, 'band structure': self.band_structures, 'optical spectra':self.optical_spectra,
                 'properties': self.project_properties,'scf_options':esc_handler.scf_options,
                 'dft engine':esc_handler.engine_name,'general options':esc_handler.general_options,'bs options':esc_handler.bs_options,
                 'phonon options':esc_handler.phonons_options,'optical spectrum options':esc_handler.optical_spectrum_options,
                 'gw options':esc_handler.gw_options,'ks densities':self.ks_densities}
            with open(self.project_directory + '/save.pkl', 'wb') as handle:
                pickle.dump(a, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            print(e)

    def load_saved_results(self):
        esc_handler.project_directory = self.project_directory
        try:
            with open(self.project_directory + '/save.pkl', 'rb') as handle:
                b = pickle.load(handle)
                b = no_error_dictionary(b)
                self.crystal_structure = b['crystal structure']
                if self.crystal_structure is not None:
                    self.mayavi_widget.update_crystal_structure(self.crystal_structure)
                    self.mayavi_widget.update_plot()

                loaded_bandstructure_dict = b['band structure']
                if type(loaded_bandstructure_dict) == dict:
                    for key,value in loaded_bandstructure_dict.items():
                        self.band_structures[key] = value

                loaded_optical_spectra_dict = b['optical spectra']
                if type(loaded_optical_spectra_dict) == dict:
                    for key,value in loaded_optical_spectra_dict.items():
                        self.optical_spectra[key] = value

                loaded_ksdens_dict = b['ks densities']
                if type(loaded_ksdens_dict ) == dict:
                    for key,value in loaded_ksdens_dict.items():
                        self.ks_densities[key] = value

                load_scf_options = b['scf_options']
                if load_scf_options is not None and b['dft engine'] == esc_handler.engine_name:
                    for key,value in load_scf_options.items():
                        esc_handler.scf_options[key] = value

                load_general_options = b['general options']
                if load_general_options is not None and b['dft engine'] == esc_handler.engine_name:
                    for key,value in load_general_options.items():
                        esc_handler.general_options[key] = value

                load_bs_options = b['bs options']
                if load_bs_options is not None and b['dft engine'] == esc_handler.engine_name:
                    for key,value in load_bs_options.items():
                        esc_handler.bs_options[key] = value

                load_phonon_options = b['phonon options']
                if load_phonon_options is not None and b['dft engine'] == esc_handler.engine_name:
                    for key,value in load_phonon_options.items():
                        esc_handler.phonons_options[key] = value

                load_gw_options = b['gw options']
                if load_gw_options is not None and b['dft engine'] == esc_handler.engine_name:
                    for key,value in load_gw_options.items():
                        esc_handler.gw_options[key] = value

                load_optical_spectrum_options = b['optical spectrum options']
                if load_optical_spectrum_options is not None and b['dft engine'] == esc_handler.engine_name:
                    for key,value in load_optical_spectrum_options.items():
                        esc_handler.optical_spectrum_options[key] = value

                self.project_properties.update(b['properties'])
                ## Update esc_handler ! DANGER ZONE !
                try:
                    esc_handler.custom_command_active = self.project_properties['custom command active']
                    esc_handler.custom_command = self.project_properties['custom command']
                    if self.project_properties['custom dft folder']:
                        esc_handler.exciting_folder = self.project_properties['custom dft folder']
                except:
                    self.project_properties['custom command active'] = False
                    self.project_properties['custom command'] = ''
                    self.project_properties['custom dft folder'] = ''

        except IOError:
            print('file not found')

    def update_structure_plot(self):
        self.mayavi_widget.update_crystal_structure(self.crystal_structure)
        self.mayavi_widget.update_plot()

        # t = MyQThread(self.mayavi_widget.update_plot)
        # t.start()

    def load_crystal_structure(self,filetype):
        file_dialog = QtGui.QFileDialog()

        if filetype == 'exciting xml':
            file_dialog.setNameFilters(["Exciting (*.xml)", "All (*.*)"])
        elif filetype == 'cif':
            file_dialog.setNameFilters(["Cif (*.cif)", "All (*.*)"])

        if file_dialog.exec_():
            file_name = file_dialog.selectedFiles()
            if type(file_name) == list or type(file_name) is tuple:
                file_name = file_name[0]
            if len(file_name) == 0:
                return

            if filetype == 'exciting xml':
                self.crystal_structure = esc_handler.parse_input_file(file_name)
            elif filetype == 'cif':
                parser = sst.StructureParser()
                self.crystal_structure = parser.parse_cif_file(file_name)

            self.update_structure_plot()

    def make_menu_bar(self):
        self.menu_bar = self.window.menuBar()
        self.menu_bar.setNativeMenuBar(False)
        self.file_menu = self.menu_bar.addMenu('&File')

        new_project_action = QtGui.QAction("New project", self.window)
        new_project_action.setShortcut("Ctrl+n")
        new_project_action.setStatusTip('Start new project')
        new_project_action.triggered.connect(self.make_new_project)
        self.file_menu.addAction(new_project_action)

        load_project_action = QtGui.QAction("Load project", self.window)
        load_project_action.setShortcut("Ctrl+o")
        load_project_action.setStatusTip('Load project')
        load_project_action.triggered.connect(self.load_project)
        self.file_menu.addAction(load_project_action)

        save_project_action = QtGui.QAction("Save project", self.window)
        save_project_action.setShortcut("Ctrl+s")
        save_project_action.setStatusTip('Save project')
        save_project_action.triggered.connect(self.save_results)
        self.file_menu.addAction(save_project_action)

        self.file_menu.addSeparator()

        new_structure_action = QtGui.QAction("New structure", self.window)
        new_structure_action.setShortcut('Ctrl+Shift+n')
        new_structure_action.setStatusTip('Make new structure by hand')
        new_structure_action.triggered.connect(lambda: self.open_structure_window(new=True))
        self.file_menu.addAction(new_structure_action)

        edit_structure_action = QtGui.QAction("Edit structure", self.window)
        edit_structure_action.setShortcut('Ctrl+Shift+e')
        edit_structure_action.setStatusTip('Edit existing structure by hand')
        edit_structure_action.triggered.connect(lambda: self.open_structure_window(new=False))
        self.file_menu.addAction(edit_structure_action)

        import_structure_menu = self.file_menu.addMenu('Import structure from')

        open_structure_action_exciting = QtGui.QAction("exciting xml", self.window)
        open_structure_action_exciting.setStatusTip('Load crystal structure from exciting xml')
        open_structure_action_exciting.triggered.connect(lambda: self.load_crystal_structure('exciting xml'))
        import_structure_menu.addAction(open_structure_action_exciting)

        open_structure_action_cif = QtGui.QAction("cif", self.window)
        open_structure_action_cif.setShortcut('Ctrl+Shift+c')
        open_structure_action_cif.setStatusTip('Load crystal structure from cif file')
        open_structure_action_cif.triggered.connect(lambda: self.load_crystal_structure('cif'))
        import_structure_menu.addAction(open_structure_action_cif)

        self.file_menu.addSeparator()

        close_app_action = QtGui.QAction("Exit", self.window)
        close_app_action.setShortcut("Ctrl+Q")
        close_app_action.setStatusTip('Leave The App')
        close_app_action.triggered.connect(self.close_application)
        self.file_menu.addAction(close_app_action)

        self.vis_menu = self.menu_bar.addMenu('&Visualize')

        ks_vis_action = QtGui.QAction("Visualize KS state", self.window)
        ks_vis_action.setStatusTip('Visualize a Kohn-Sham state in the structure window')
        ks_vis_action.triggered.connect(self.open_state_vis_window)
        self.vis_menu.addAction(ks_vis_action)

        self.dft_menu = self.menu_bar.addMenu('&DFT Engine')

        dft_options_action = QtGui.QAction("Options", self.window)
        dft_options_action.setStatusTip('Options for dft engine')
        dft_options_action.triggered.connect(self.open_engine_option_window)
        self.dft_menu.addAction(dft_options_action)

    def close_application(self):
        if not DEBUG:
            reply = QtGui.QMessageBox.question(self, 'Message',
                                               "Are you sure to quit?", QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        if DEBUG or reply == QtGui.QMessageBox.Yes:
            self.save_results()
            self.parent.quit()
            sys.exit()

    def check_engine(self,tasks):
        def check_relax():
            new_struc = esc_handler.load_relax_structure()
            if new_struc is not None:
                self.crystal_structure = new_struc
                self.update_structure_plot()

        tasks = [x.lower() for x in tasks]
        if self.dft_engine_window.abort_bool:
            self.status_bar.set_engine_status(False)
            self.dft_engine_window.abort_bool = False
            return
        elif esc_handler.is_engine_running(tasks=tasks):
            self.scf_data = esc_handler.read_scf_status()
            if self.scf_data is not None:
                self.scf_window.scf_widget.plot(self.scf_data)
            QtCore.QTimer.singleShot(500,lambda: self.check_engine(tasks))
            self.status_bar.set_engine_status(True,tasks=tasks)
            if 'relax' in tasks:
                check_relax()
        else:
            self.status_bar.set_engine_status(False)
            message, err = esc_handler.engine_process.communicate()
            if ('error' in message.lower() or len(err)>0):
                error_message = 'DFT calculation finished with an error:<br><br>' + message+'<br>Error:<br>'+err \
                                + '<br><br>Try following:<br>1.Check if the selected dft engine is correctly installed<br>' \
                                  '2. Check if the input file was correctly parsed into the respective folder (e.g. input.xml in exciting_files for exciting)'
                self.error_dialog.showMessage(error_message)

            if 'bandstructure' in tasks or 'g0w0' in tasks:
                read_bandstructures = []
                titles = [esc_handler.general_options['title']]
                if 'bandstructure' in tasks:
                    read_bandstructures.append(esc_handler.read_bandstructure())
                if 'g0w0' in tasks:
                    read_bandstructures.append(esc_handler.read_gw_bandstructure())
                if 'bandstructure' in tasks and 'g0w0' in tasks:
                    titles.append(esc_handler.general_options['title']+'_gw')


                for read_bandstructure,title in zip(read_bandstructures,titles):
                    self.band_structures[title] = read_bandstructure
                    self.band_structure_window.update_tree()
                if len(read_bandstructures)!=0 and self.band_structure_window.plot_widget.first_plot_bool:
                    self.band_structure_window.plot_widget.plot(self.band_structures[esc_handler.general_options['title']])
            if 'relax' in tasks:
                check_relax()
            if 'phonons' in tasks:
                read_bandstructure = esc_handler.read_phonon_bandstructure()
                self.band_structures[esc_handler.general_options['title'] + '_phonon'] = read_bandstructure
                self.band_structure_window.update_tree()
            if 'optical spectrum' in tasks:
                read_spectrum = esc_handler.read_optical_spectrum()
                self.optical_spectra[esc_handler.general_options['title']] = read_spectrum
                self.optical_spectra_window.update_tree()

    def open_engine_option_window(self):
        self.engine_option_window.update_all()
        self.engine_option_window.show()

    def open_state_vis_window(self):
        self.ks_state_window.plot_widget.update_tree()
        self.ks_state_window.show( )

    def open_structure_window(self,new=False):
        if new:
            self.structure_window.set_structure(None)
        else:
            self.structure_window.set_structure(self.crystal_structure)

        self.structure_window.anything_changed = False
        self.structure_window.update_fields()
        self.structure_window.show()

if __name__ == "__main__":
    DEBUG = True

    app = QtGui.QApplication.instance()
    main = CentralWindow(parent=app)

    app.exec_()
