# -*- coding: utf-8 -*-  
"""
Load Cell Plugin
Copyright (C) 2015 Olaf Lüke <olaf@tinkerforge.com>
Copyright (C) 2015 Matthias Bolte <matthias@tinkerforge.com>

load_cell.py: Load Cell Plugin Implementation

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License 
as published by the Free Software Foundation; either version 2 
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QVBoxLayout, QLabel, QHBoxLayout, QSpinBox, \
                        QPushButton, QFrame, QComboBox, QCheckBox, QDialog

from brickv.plugin_system.plugin_base import PluginBase
from brickv.bindings.bricklet_load_cell import BrickletLoadCell
from brickv.plugin_system.plugins.load_cell.ui_calibration import Ui_Calibration
from brickv.plot_widget import PlotWidget
from brickv.async_call import async_call
from brickv.callback_emulator import CallbackEmulator

class WeightLabel(QLabel):
    def setText(self, weight):
        if abs(weight) < 1000:
            text = "Weight: " + str(weight) + " g"
        else:
            text = "Weight: " + "{0:.3f}".format(round(weight/1000.0, 3)) + " kg"
        super(WeightLabel, self).setText(text)

class Calibration(QDialog, Ui_Calibration):
    def __init__(self, parent):
        QDialog.__init__(self, parent)

        self.setupUi(self)

        self.parent = parent
        self.lc = parent.lc

        self.button_zero.clicked.connect(self.button_zero_clicked)
        self.button_weight.clicked.connect(self.button_weight_clicked)
        self.button_weight.setEnabled(False)
        
        self.label_step1.setStyleSheet('QLabel { color : red }')
        self.label_step2.setStyleSheet('')
        self.label_status.setText('Calibration in progress...')

    def button_zero_clicked(self):
        self.lc.calibrate(0)
        self.button_weight.setEnabled(True)

        self.label_step1.setStyleSheet('')
        self.label_step2.setStyleSheet('QLabel { color : red }')

    def button_weight_clicked(self):
        self.lc.calibrate(self.spin_weight.value())

        self.label_step1.setStyleSheet('')
        self.label_step2.setStyleSheet('')
        self.label_status.setText('The new calibration is now saved in the EEPROM.')

    def closeEvent(self, event):
        self.parent.button_calibration.setEnabled(True)
        self.parent.calibration = None
    
class LoadCell(PluginBase):
    def __init__(self, *args):
        PluginBase.__init__(self, BrickletLoadCell, *args)
        
        self.lc = self.device

        self.cbe_weight = CallbackEmulator(self.lc.get_weight,
                                           self.cb_weight,
                                           self.increase_error_count)

        self.weight_label = WeightLabel()
        
        self.gain = 0 # 128x
        self.current_value = None
        self.calibration = None
        
        plot_list = [['', Qt.red, self.get_current_value]]
        self.plot_widget = PlotWidget('Weight [g]', plot_list)

        self.button_calibration = QPushButton("Calibration")
        self.button_calibration.clicked.connect(self.button_calibration_clicked)

        self.button_tare = QPushButton("Tare")
        self.button_tare.clicked.connect(self.button_tare_clicked)
        
        self.enable_led = QCheckBox("LED On")
        self.enable_led.stateChanged.connect(self.enable_led_changed)
        
        self.spin_average = QSpinBox()
        self.spin_average.setMinimum(0)
        self.spin_average.setMaximum(40)
        self.spin_average.setSingleStep(1)
        self.spin_average.setValue(5)
        self.spin_average.editingFinished.connect(self.spin_average_finished)
        self.label_average = QLabel('Length of moving average:')

        layout_h = QHBoxLayout()
        layout_h.addStretch()
        layout_h.addWidget(self.weight_label)
        layout_h.addStretch()
        
        self.rate_label = QLabel('Rate: ')
        self.rate_combo = QComboBox()
        self.rate_combo.addItem("10Hz")
        self.rate_combo.addItem("80Hz")
        self.rate_combo.currentIndexChanged.connect(self.new_config)
        
        layout_avg = QHBoxLayout()
        layout_avg.addWidget(self.label_average)
        layout_avg.addWidget(self.spin_average)
        layout_avg.addWidget(self.rate_label)
        layout_avg.addWidget(self.rate_combo)
        layout_avg.addStretch()
        layout_avg.addWidget(self.button_calibration)
        layout_avg.addWidget(self.button_tare)
        layout_avg.addWidget(self.enable_led)

        layout = QVBoxLayout(self)
        layout.addLayout(layout_h)
        layout.addWidget(self.plot_widget)
        layout.addLayout(layout_avg)

    def start(self):
        async_call(self.lc.is_led_on, None, self.is_led_on_async, self.increase_error_count)
        async_call(self.lc.get_configuration, None, self.get_configuration_async, self.increase_error_count)
        async_call(self.lc.get_moving_average, None, self.get_moving_average_async, self.increase_error_count)
        async_call(self.lc.get_weight, None, self.cb_weight, self.increase_error_count)
        self.cbe_weight.set_period(100)
        
        self.plot_widget.stop = False
        
    def stop(self):
        self.cbe_weight.set_period(0)
        
        self.plot_widget.stop = True

    def destroy(self):
        if self.calibration:
            self.calibration.close()

    def get_url_part(self):
        return 'load_cell'

    @staticmethod
    def has_device_identifier(device_identifier):
        return device_identifier == BrickletLoadCell.DEVICE_IDENTIFIER

    def get_moving_average_async(self, avg):
        self.spin_average.setValue(avg)
        
    def get_configuration_async(self, conf):
        self.gain = conf.gain
        self.rate_combo.setCurrentIndex(conf.rate)
        
    def is_led_on_async(self, value):
        if value:
            self.enable_led.setChecked(True)
        else:
            self.enable_led.setChecked(False)

    def button_calibration_clicked(self):
        if self.calibration is None:
            self.calibration = Calibration(self)

        self.button_calibration.setEnabled(False)
        self.calibration.show()
            
    def button_tare_clicked(self):
        self.lc.tare()
    
    def enable_led_changed(self, state):
        if state == Qt.Checked:
            self.lc.led_on()
        else:
            self.lc.led_off()
    
    def new_config(self, value):
        rate = self.rate_combo.currentIndex()
        self.lc.set_configuration(rate, self.gain)
    
    def spin_average_finished(self):
        self.lc.set_moving_average(self.spin_average.value())

    def get_current_value(self):
        return self.current_value

    def cb_weight(self, weight):
        self.current_value = weight
        self.weight_label.setText(weight)
