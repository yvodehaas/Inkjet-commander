#Oasis controller is the software used to control the HP45 and GRBL driver in Oasis
#Copyright (C) 2018  Yvo de Haas

#Oasis controller is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#Oasis controller is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Oasis controller.  If not, see <https://www.gnu.org/licenses/>.


import sys
import glob

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QMessageBox, QComboBox, QLabel
from PyQt5.QtGui import QPixmap, QColor, QImage
from SerialHP45 import HP45
import os
from ImageConverter import ImageConverter
import B64
from numpy import * 
import threading
import time
import serial

#a small note on threading. It is used so some of the functions update automatically (serial GRBL and inkjet)
#however, it is a bit of a lie. If python is busy in one thread, it will quietly ignore the others
#sleep commands will give enough room that python works on other threads.
#this is the reason why sending inkjet while moving is difficult. Will fix later, with another attempt

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()        
        
        Form, Window = uic.loadUiType("Inkjet commander.ui")
        
        self.ui = Window()
        self.form = Form()
        self.form.setupUi(self.ui)
        self.ui.show()
                
        
        self.inkjet = HP45()
        self.imageconverter = ImageConverter()
        
        self.printing_state = 0 #whether the printer is printing
        self.printing_abort_flag = 0
        self.printing_pause_flag = 0
        
        self.image_x_size = 0 #pixel dimensions of the to be printed image
        self.image_y_size = 0
        self.inkjet_overlap = 1 #overlap of the to be printed image
        
        self.RefreshPorts() #get com ports for the buttons
        
        self.error_counter = 0

        
        self.form.inkjet_refresh.clicked.connect(self.RefreshPorts)
        
        
        #inkjet connect button
        self.inkjet_connection_state = 0 #connected state of inkjet
        self.form.inkjet_connect.clicked.connect(self.InkjetConnect)
        #self.form.inkjet_set_port.returnPressed.connect(self.InkjetConnect)
        #self.form.inkjet_refresh.clicked.connect(self.SetStatus)
        
        #inkjet send command button
        #self.form.inkjet_send_line.clicked.connect(self.InkjetSendCommand)
        #self.form.inkjet_write_line.returnPressed.connect(self.InkjetSendCommand)
        
        #inkjet function buttons
        self.form.inkjet_preheat.clicked.connect(self.InkjetPreheat)
        self.form.inkjet_prime.clicked.connect(self.InkjetPrime)
        #self.form.inkjet_set_dpi.clicked.connect(self.InkjetSetDPI)
        self.form.dpi_combo.currentIndexChanged.connect(self.InkjetSetDPI)
        #self.form.inkjet_dpi.returnPressed.connect(self.InkjetSetDPI)
        self.form.inkjet_set_density.clicked.connect(self.InkjetSetDensity)
        self.form.inkjet_density.valueChanged.connect(self.InkjetSetDensityText)
        self.form.inkjet_test_button.clicked.connect(self.inkjet.TestPrinthead)
        self.form.button_clear_buffer.clicked.connect(self.inkjet.ClearBuffer)
        self.form.button_reset_buffer.clicked.connect(self.inkjet.ResetBuffer)
        self.form.buffer_mode_combo.currentIndexChanged.connect(self.InkjetBufferMode)
        self.form.side_combo.currentIndexChanged.connect(self.InkjetSideMode)
        self.form.overlap_combo.currentIndexChanged.connect(self.SetOverlap)
        self.form.serial_send_button.clicked.connect(self.InkjetSendCommand)
        self.form.serial_send_line.returnPressed.connect(self.InkjetSendCommand)
        
        #print radio mode buttons 
        self.form.mode_radio_encoder.toggled.connect(self.InkjetSetMode)
        self.form.mode_radio_velocity.toggled.connect(self.InkjetSetMode)
        self.printing_mode = 0 #defaults to encoder mode
        
        #position configuration
        self.form.encoder_position_set.clicked.connect(self.InkjetSetPosition)
        self.form.encoder_position.returnPressed.connect(self.InkjetSetPosition)
        self.form.encoder_ppi_set.clicked.connect(self.InkjetSetPPI)
        self.form.encoder_ppi.returnPressed.connect(self.InkjetSetPPI)
        self.form.virtual_velocity_set.clicked.connect(self.InkjetVirtualVelocity)
        self.form.virtual_velocity.returnPressed.connect(self.InkjetVirtualVelocity)
        
        #trigger modes
        self.form.trigger_set_mode.clicked.connect(self.InkjetTriggerMode)
        self.form.virtual_enable.clicked.connect(self.inkjet.VirtualEnable)
        self.form.virtual_disable.clicked.connect(self.inkjet.VirtualDisable)
        self.form.trigger_reset_position_set.clicked.connect(self.InkjetSetTriggerPosition)
        self.form.trigger_reset_position.returnPressed.connect(self.InkjetSetTriggerPosition)
        self.form.virtual_trigger.clicked.connect(self.inkjet.SerialTrigger)
        self.form.virtual_stop.clicked.connect(self.inkjet.SerialStop)
        
        #file buttons
        self.file_loaded = 0
        self.form.file_open_button.clicked.connect(self.OpenFile)
        self.form.file_convert_button.clicked.connect(self.RenderOutput)
        self.form.threshold_slider.valueChanged.connect(self.UpdateThresholdSliderValue) 
        self.form.inkjet_send_image.clicked.connect(self.PrintButtonClicked)
        
        
    
    def RefreshPorts(self):
        """ Lists serial port names
        :raises EnvironmentError:
            On unsupported or unknown platforms
        """
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        #print(result)
        
        #update the com ports for motion and inkjet        
        self.form.inkjet_set_port.clear()
        self.form.inkjet_set_port.addItems(result)
    
    def InkjetConnect(self):
        """Gets the inkjet serial port and attempt to connect to it"""
        if (self.printing_state == 0): #only act on the button if the printer is not printing
            if (self.inkjet_connection_state == 0): #get connection state, if 0 (not connected)
                #print("Attempting connection with HP45")
                temp_port = str(self.form.inkjet_set_port.currentText()) #get text
                temp_succes = self.inkjet.Connect(temp_port) #attempt to connect
                if (temp_succes == 1): #on success, 
                    self.form.inkjet_connect.setText("Disconnect") #rewrite button text
                    self.inkjet_connection_state = 1 #set  state
                    #self.form.inkjet_set_port.clear()
                    #start a thread that will update the serial in and output for HP45
                    self._inkjet_stop_event = threading.Event()
                    self.inkjet_update_thread = threading.Thread(target=self.InkjetUpdate)
                    self.inkjet_update_thread.start()
                    
                else:
                    print("Connection with HP failed")
            else: #on state 1
                #print("disconnecting from HP45")
                self.inkjet.Disconnect() #disconnect
                self.inkjet_connection_state = 0 #set state to disconnected
                self.form.inkjet_connect.setText("Connect") #rewrite button
                self._inkjet_stop_event.set() #close the HP45 serial thread
            
    def InkjetUpdate(self):
        """updates serial in and output for the inkjet window"""
        time.sleep(1)
        self.status_multiplier_counter = 0
        while not self._inkjet_stop_event.is_set():
            
            #update state and coordinates
            self.form.inkjet_temperature_value.setText(f'{self.inkjet.inkjet_temperature:.1f}C')
            self.form.inkjet_position_value.setText(f'{self.inkjet.inkjet_x_pos:.2f}mm')
            self.form.inkjet_virtual_position_value.setText(f'{self.inkjet.inkjet_virtual_pos:.2f}mm')
            self.form.buffer_read_left_label.setText(f'{self.inkjet.inkjet_readleft:.0f}')
            self.form.buffer_write_left_label.setText(f'{self.inkjet.inkjet_writeleft:.0f}')
            self.form.buffer_send_left_label.setText(f'{self.inkjet.BufferLeft():.0f}') #update send left
            
            self.status_multiplier_counter += 1
            if (self.status_multiplier_counter > 5):
                self.status_multiplier_counter = 0
                if (self.inkjet.inkjet_error > 0): #if there errors, display those
                    while (True):
                        #print(self.error_counter)
                        temp_val = 1 << self.error_counter #make comparison bitmask
                        if (self.inkjet.inkjet_error & temp_val == temp_val): #if the checked bit is 1
                            self.form.error_message_value.setText(self.inkjet.inkjet_error_message[self.error_counter])
                            self.error_counter += 1
                            if (self.error_counter > len(self.inkjet.inkjet_error_message)):
                                self.error_counter = 0
                            break
                            
                        self.error_counter += 1
                        if (self.error_counter > len(self.inkjet.inkjet_error_message)):
                            self.error_counter = 0
                            break                    
                elif(self.inkjet.inkjet_warning > 0): #if there are warnings and no errors
                    while (True):
                        #print(self.error_counter)
                        temp_val = 1 << self.error_counter #make comparison bitmask
                        if (self.inkjet.inkjet_warning & temp_val == temp_val): #if the checked bit is 1
                            self.form.error_message_value.setText(self.inkjet.inkjet_warning_message[self.error_counter])
                            self.error_counter += 1
                            if (self.error_counter > len(self.inkjet.inkjet_warning_message)):
                                self.error_counter = 0
                            break
                            
                        self.error_counter += 1
                        if (self.error_counter > len(self.inkjet.inkjet_warning_message)):
                            self.error_counter = 0
                            break                    
                else:
                    self.form.error_message_value.setText("None") #display no errors message
                
            
            #update inkjet test state
            self.form.inkjet_test_state.setText("Nozzles: " + str(self.inkjet.inkjet_working_nozzles) + "/" + str(self.inkjet.inkjet_total_nozzles))
            
            time.sleep(0.2)
    
    def InkjetSendCommand(self):
        """Gets the command from the textedit and prints it to Inkjet"""
        if (self.inkjet_connection_state == 1):
            temp_command = str(self.form.serial_send_line.text())#get line
            temp_command += "\r" #add end of line
            self.inkjet.SerialWriteBufferRaw(temp_command) #write to inkjet
            self.form.serial_send_line.clear() #clear line

    def InkjetSetMode(self):
        """Sets the printhead to encoder mode"""
        #if mode is not yet encoder mode and encoder mode is clicked
        if (self.form.mode_radio_encoder.isChecked() == 1 and self.printing_mode != 0):
            self.printing_mode = 0 #set to encoder mode
            self.inkjet.SetPrintMode(0)
        
        #if mode is not yet virtual mode and virtual mode is clicked
        if (self.form.mode_radio_velocity.isChecked() == 1 and self.printing_mode != 1):
            self.printing_mode = 1 #set to virtual velocity mode
            self.inkjet.SetPrintMode(1)
            
    def InkjetSetPosition(self):
        """Gets the position from the textbox and converts it and sends it to HP45"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            temp_pos = self.form.encoder_position.text() #set pos to variable
            try:
                temp_pos = float(temp_pos)
                print("Setting position to: " + str(temp_pos))
                temp_pos *= 1000.0
                temp_pos = int(temp_pos) #cast to intergers
            except:
                print("Value could not be converted")
                return
            self.form.encoder_position.setText("")
            self.inkjet.SetPosition(temp_pos) #set position
    
    def InkjetSetPPI(self):
        """Gets the position from the textbox and converts it and sends it to HP45"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            temp_pos = self.form.encoder_ppi.text() #set pos to variable
            try:
                temp_pos = int(temp_pos)
                print("Setting PPI to: " + str(temp_pos))
            except:
                print("Value could not be converted")
                return
            self.form.encoder_position.setText("")
            self.inkjet.SetEncoderPPI(temp_pos) #set position
            
    def InkjetVirtualVelocity(self):
        """Set the printhead to the given virtual velocity in mm/s (float)"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            temp_vel = self.form.virtual_velocity.text() #set pos to variable
            try:
                temp_vel = float(temp_vel)
                print("Setting virtual velocity to: " + str(temp_vel))
                #temp_vel *= 1000.0
                temp_vel = int(temp_vel) #cast to intergers
            except:
                print("Value could not be converted")
                return
            #self.form.virtual_velocity.setText("")
            self.inkjet.SetVirtualVelocity(temp_vel) #set position
        
    def InkjetSetTriggerPosition(self):
        """Set the trigger position, the position the printhead moves to when the trigger is given"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            temp_vel = self.form.trigger_reset_position.text() #set pos to variable
            try:
                temp_vel = float(temp_vel)
                print("Setting trigger position to: " + str(temp_vel))
                temp_vel *= 1000.0
                temp_vel = int(temp_vel) #cast to intergers
            except:
                print("Value could not be converted")
                return
            #self.form.trigger_reset_position.setText("")
            self.inkjet.SetTriggerPosition(temp_vel) #set position
    
    def InkjetTriggerMode(self):
        """Take the pin and the mode and write these to the printhead"""
        temp_pin = self.form.trigger_pin.currentIndex ()
        temp_mode = self.form.trigger_mode.currentIndex ()
        temp_resistor = self.form.pin_mode.currentIndex ()
        self.inkjet.SetPinTriggerMode(temp_pin, temp_mode)
        self.inkjet.SetPinTriggerResistor(temp_pin, temp_resistor)
        print("Setting trigger mode")
        #print(temp_pin)
        #print(temp_mode)
    
    def InkjetUpdateTriggerMode(self): 
        """Ask for the trigger mode for the given pin and update the value of the box to the current value"""
    
    
    def InkjetBufferMode(self): #sets what mode the buffer resets at
        temp_mode = self.form.buffer_mode_combo.currentIndex ()
        self.inkjet.BufferMode(temp_mode)
        #print(temp_mode)
        
    def InkjetSideMode(self): #sets what side can and cannot print
        temp_mode = self.form.side_combo.currentIndex ()
        self.inkjet.SetSideMode(temp_mode)
        print(temp_mode)
        
    def SetOverlap(self):
        """Set the overlap of the image printed and change printing density to compensate"""
        #set overlap (read "overlap_combo")
        temp_overlap = self.form.overlap_combo.currentIndex() #get index
        temp_overlap += 1 #add one to make it 1-4
        print("overlap set to: " + str(temp_overlap))
        self.inkjet_overlap = temp_overlap
    
        #reset density to printhead
        self.InkjetSetDensity()
        
        #alter required sweeps
        self.SetSweepData()
        
    def InkjetPrime(self):
        """if possible, sends a priming burst to the printhead"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            self.inkjet.Prime(100)
            
    def InkjetPreheat(self):
        """if possible, sends a preheating burst to the printhead"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            self.inkjet.Preheat(5000)
    
    def InkjetSetDPI(self):
        """Writes the DPI to the printhead and decode function"""
        #temp_dpi = str(self.form.inkjet_dpi.text()) #get text#get dpi
        #print("Setting DPI")
        temp_dpi = str(self.form.dpi_combo.currentText()) #get dpi
        temp_dpi = temp_dpi.partition(' ')
        temp_dpi = temp_dpi[0]
        temp_dpi_val = 0
        #print(temp_dpi)
        temp_success = 0
        try:
            temp_dpi_val = int(temp_dpi)
            temp_success = 1
        except:
            print ("Unable to set dpi")
            nothing = 0

        if (temp_success == 1): #if conversion was successful
            if (self.printing_state == 0): #only set DPI when not printing
                print("DPI to set: " + str(temp_dpi_val))
                if (self.inkjet_connection_state == 1): #only write to printhead when connected
                    self.inkjet.SetDPI(temp_dpi_val) #write to inkjet
                self.imageconverter.SetDPI(temp_dpi_val) #write to image converter
                if (self.file_loaded != 0): #if any file is loaded
                    print("resising image")
                    self.OpenFile(self.input_file_name[0])
                
    def InkjetSetDensity(self):
        """Writes the Density to the printhead"""
        if (self.inkjet_connection_state == 1):
            temp_density = str(self.form.inkjet_density.value()) #get text #get density
            temp_density_val = 0
            temp_success = 0
            try:
                temp_density_val = int(temp_density)
                temp_success = 1
            except:
                #print ("Unable to convert to dpi")
                nothing = 0

            if (temp_success == 1): #if conversion was successful
                #print("Density to set: " + str(temp_density_val))
                temp_density_val = temp_density_val * 10 #multiply by 10 because interface handles this value from 1-100
                temp_density_val /= self.inkjet_overlap #divide by overlap because of possible multiple sweeps per pixel
                temp_density_val = int(temp_density_val) #cast to integer
                print("Setting density to: " + str(temp_density_val))
                
                self.inkjet.SetDensity(temp_density_val) #write to inkjet
                
    def InkjetSetDensityText(self):
        """Rewrited density on GUI"""
        temp_density = str(self.form.inkjet_density.value()) #get text #get density
        temp_density = int(temp_density)
        temp_density *= 10
        self.form.inket_density_value.setText('Density: ' + str(temp_density) + '%')
               
    def UpdateThresholdSliderValue(self):
        """Updates the value next to the threshold slider"""
        temp_threshold = self.form.threshold_slider.value()
        self.form.threshold_slider_value.setText("Threshold: " + str(temp_threshold))
        
    def OpenFile(self, temp_input_file = ""):
        """Opens a file dialog, takes the filepath, and passes it to the image converter"""
        if (temp_input_file):
            temp_response = self.imageconverter.OpenFile(temp_input_file)
        else:
            self.input_file_name = QFileDialog.getOpenFileName(self, 'Open file', 
            '',"Image files (*.jpg *.png *.svg)")
            temp_response = self.imageconverter.OpenFile(self.input_file_name[0])
            
        if (temp_response == 1):
            self.RenderInput()
            self.file_loaded = 1
        if (temp_response == 2):
            self.file_loaded = 2
            self.form.layer_slider.setMaximum(self.imageconverter.svg_layers-1)
            self.RenderOutput()
            
    def UpdateLayer(self):
        if (self.imageconverter.file_type == 2 and self.printing_state == 0): #if file is svg
            temp_layer = self.form.layer_slider.value()
            self.form.layer_slider_value.setText("Layer: " + str(temp_layer))
            self.imageconverter.SVGLayerToArray(temp_layer)
            self.RenderOutput()
            
    def RenderInput(self):
        """Gets an image from the image converter class and renders it to input"""
        self.input_image_display = self.imageconverter.input_image
        if (self.input_image_display.width() > 200 or self.input_image_display.height() > 200):
            self.input_image_display = self.input_image_display.scaled(200,200, QtCore.Qt.KeepAspectRatio)
        self.form.output_window.setPixmap(self.input_image_display)
        #self.form.input_window.setPixmap(self.imageconverter.input_image)
        
    def RenderOutput(self):
        """Gets an image from the image converter class and renders it to output"""
        if (self.file_loaded == 1): #if image file
            temp_threshold = self.form.threshold_slider.value()
            self.imageconverter.Threshold(temp_threshold)
            self.imageconverter.ArrayToImage()
            self.output_image_display = self.imageconverter.output_image
            if (self.output_image_display.width() > 200 or self.output_image_display.height() > 200):
                self.output_image_display = self.output_image_display.scaled(200,200, QtCore.Qt.KeepAspectRatio)
            self.form.output_window.setPixmap(self.output_image_display)
            
        if (self.file_loaded == 2): #if svg file (not currently working)
            self.imageconverter.ArrayToImage()
            self.output_image_display = self.imageconverter.output_image
            if (self.output_image_display.width() > 200 and self.output_image_display.height() > 200):
                self.output_image_display = self.output_image_display.scaled(300,300, QtCore.Qt.KeepAspectRatio)
            self.form.output_window.setPixmap(self.output_image_display)
            
        self.SetSweepData() #update image size and sweeps required
    
    def SetSweepData(self):
        """Updates the values of the sweep data"""
        self.image_y_size = self.imageconverter.image_array_width
        self.image_x_size = self.imageconverter.image_array_height
        temp_required_sweeps = self.imageconverter.GetDPI() #get printing DPI
        temp_required_sweeps /= 2 #divide by 2 to get the sweep size (300 nozzles at 600DPI is half de DPI)
        temp_required_sweeps /= self.inkjet_overlap #divide by the overlap
        
        temp_required_sweeps = int(self.image_x_size / temp_required_sweeps) + (self.image_x_size % temp_required_sweeps > 0) #get the rounded up number of sweeps
        
        #add optional overlap to the number of sweeps
        temp_lead_ins = self.inkjet_overlap - 1 #if there is overlap, lead-in sweeps need to be added
        temp_required_sweeps += temp_lead_ins #add lead ins and outs to the required sweeps
        
        #print("Image size: " + str(self.image_y_size) + "x" + str(self.image_x_size))
        #print("Sweeps: " + str(temp_required_sweeps))
        
        self.form.image_dimensions.setText(str(self.image_y_size) + " x " + str(self.image_x_size))
        self.form.image_required_sweeps.setText(str(temp_required_sweeps))
        
    def RenderAlpha(self):
        """Renders alpha mask (used for troubleshooting)"""
        self.imageconverter.AlphaMaskToImage()
        self.output_image_display = self.imageconverter.output_image
        if (self.output_image_display.width() > 300 and self.output_image_display.height() > 300):
            self.output_image_display = self.output_image_display.scaled(300,300, QtCore.Qt.KeepAspectRatio)
        self.form.output_window.setPixmap(self.output_image_display)
        
    def RenderRGB(self):
        """Renders only RGB, ignoring alpha (used for troubleshooting)"""
        self.imageconverter.RGBToImage()
        self.output_image_display = self.imageconverter.output_image
        if (self.output_image_display.width() > 300 and self.output_image_display.height() > 300):
            self.output_image_display = self.output_image_display.scaled(300,300, QtCore.Qt.KeepAspectRatio)
        self.form.output_window.setPixmap(self.output_image_display)
    
    def RunPrintArray(self):
        """Starts a thread for the print array function"""
        if (self.file_loaded == 1):
            self._printing_stop_event = threading.Event()
            self.printing_thread = threading.Thread(target=self.SendArray)
            self.printing_thread.start()
        if (self.file_loaded == 2):
            self._printing_stop_event = threading.Event()
            self.printing_thread = threading.Thread(target=self.PrintSVG)
            self.printing_thread.start()
       
    def PrintButtonClicked(self):
        """Print button clicked, get variables and print the array"""        
        #get the starting position from the menu
        if (self.inkjet_connection_state == 1): #only act on the button if the printer is not connected
            try:
                temp_pos = self.form.image_start_position.text() #set pos to variable
                temp_pos = float(temp_pos)
                print("Starting position is: " + str(temp_pos))
                temp_pos = int(temp_pos) #cast to intergers
            except:
                print("Value could not be converted, defaulting to 10mm")
                temp_pos = 10.0
            
            #send the print command
            self.SendArray(temp_pos)
    
    def PrintSVG(self):
        """Prints the currently loaded SVG file if present.
        This will not check powder levels, ink levels and if file is much more than theoretically possible
        """
        #Todo: 
        #-Add printhead purge to the start of the print so the first sweep will work properly
        #-Re-add send code while printing. The problem with speed was traced to threading not working
        # while another thread is busy. Now there are sleep command in the While(True) blocks,
        # Giving the other threads time to do stuff.
        
        print("Starting print from SVG")
        
        #start printing if file is svg, inkjet and motion are started
        if (self.file_loaded == 2 and self.inkjet_connection_state == 1 and self.grbl_connection_state == 1):
            self.printing_state = 2 #set printing state
            self.inkjet.ClearBuffer() #clear inkjet buffer on HP45
            self.grbl.Home() #home printer
            
            #make variables
            self.build_center_x = 157.0 #where the center of the build platform is
            self.build_center_y = 111.0 #where the center of the build platform is
            self.print_speed = 2200.0 #how fast to print
            self.travel_speed = 15000.0 #how fast to travel
            self.acceleration_distance = 20.0 #how much to accelerate before printing
            self.printing_dpi = int(self.imageconverter.dpi) #the set DPI
            self.printing_sweep_size = int(self.printing_dpi / 2) #the sweep size
            self.pixel_to_pos_multiplier = 25.4 / self.printing_dpi #the value from pixel to mm 
            self.image_size_x = self.imageconverter.image_array_height #the max size of image, in X-direction
            self.image_size_y = self.imageconverter.image_array_width #the max size of image, in Y-direction
            self.layers = self.imageconverter.svg_layers #how many layers there are
            self.current_layer = 0 #the currently printed layer
            self.current_layer_height = self.imageconverter.svg_layer_height[0]
            print("Starting print at height: " + str(self.current_layer_height))
            
            #set flags
            self.printing_abort_flag = 0
            self.printing_pause_flag = 0
            
            #set inkjet settings
            self.inkjet.SetDPI(self.printing_dpi)
            
            #set motion settings
            
            #check file
            #offsets given above are assumed to be the center of bed
            #calculate offsets for centering file
            #width is Y, height is X
            #self.svg_offset_x = self.imageconverter.svg_height / 2
            #self.svg_offset_y = self.imageconverter.svg_width / 2
            #I flipped these because of a boo-boo somewhere. 
            self.svg_offset_y = self.imageconverter.svg_height / 2
            self.svg_offset_x = self.imageconverter.svg_width / 2
            
            #Wait till homing is done
            if (self.grbl_connection_state == 1): #conditional for testing, only wait for home if there is home to wait on
                while (self.grbl.motion_state != 'idle'):
                    time.sleep(0.1)
                    pass
                    
            time.sleep(0.25) #extra delay so the system can stabilize
            self.InkjetSetPosition() #set position
            time.sleep(0.25) #extra delay so position can be set
            
            #add priming purge here, with motions to start the printhead
            
            #start printing
            while(True):
                
                #load proper layer
                self.imageconverter.SVGLayerToArray(self.current_layer)
                self.form.layer_slider.setValue(self.current_layer) #set layer slider value
                self.form.layer_slider_value.setText("Layer: " + str(self.current_layer))
                self.RenderOutput() #render image
                print("Printing layer: " + str(self.current_layer))
                
                #hold firmware while a new layer is being deposited
                while(self.grbl.nl_state == 0): #hold firmware till layer is done
                    time.sleep(0.1)
                    pass
                    
                #check abort state
                if (self.printing_abort_flag == 1):
                    break
                
                #calculate start and end in gantry direction
                #look for X-min and X-max in image 
                self.sweep_x_min = 0
                self.sweep_x_max = 0
                temp_break_loop = 0
                #loop through image
                for h in range(0,self.image_size_x):
                    for w in range(0,self.image_size_y):
                        if (self.imageconverter.image_array[h][w] != 0):
                            self.sweep_x_min = h
                            temp_break_loop = 1
                            print("X-min on row: " + str(h))
                            break
                    if (temp_break_loop == 1):
                        break
                temp_break_loop = 0
                for h in reversed(range(0,self.image_size_x)):
                    for w in range(0,self.image_size_y):
                        if (self.imageconverter.image_array[h][w] != 0):
                            self.sweep_x_max = h
                            temp_break_loop = 1
                            print("X-max on row: " + str(h))
                            break
                    if (temp_break_loop == 1):
                        break
                        
                #calculate how many sweeps are required
                self.sweep_x_size = self.sweep_x_max - self.sweep_x_min
                print("Sweep size in pixels: " + str(self.sweep_x_size))
                if (self.sweep_x_size % int(self.printing_sweep_size) == 0):
                    temp_round = 1
                else:
                    temp_round = 0
                self.sweeps = int(self.sweep_x_size / self.printing_sweep_size)
                if (temp_round == 0):
                    self.sweeps += 1
                print("Sweeps in layer: " + str(self.sweeps))
                
                #calculate starting position and pixel
                #printer prints from x max to x min because of new layer reasons
                self.sweep_x_pix = self.sweep_x_max - self.printing_sweep_size
                
                #load sweep by sweep
                for L in range(self.sweeps):
                    print("printing sweep" + str(L))
                    
                    #set X position
                    self.sweep_x_pos = (self.sweep_x_pix * self.pixel_to_pos_multiplier) + self.build_center_x - self.svg_offset_x                     
                    
                    #calculate start and end in sweep direction
                    temp_break_loop = 0
                    for w in range(self.image_size_y):
                        for h in range(int(self.sweep_x_pix), int(self.sweep_x_pix + self.printing_sweep_size)): 
                            if (h > 0): #if h is within bounds
                                if (self.imageconverter.image_array[h][w] != 0):
                                    self.sweep_y_min = w
                                    temp_break_loop = 1
                                    break
                        if (temp_break_loop == 1):
                            break
                    #get Y max
                    temp_break_loop = 0
                    for w in reversed(range(self.image_size_y)):
                        for h in range(int(self.sweep_x_pix), int(self.sweep_x_pix + self.printing_sweep_size)):
                            if (h > 0): #if h is within bounds
                                if (self.imageconverter.image_array[h][w] != 0):
                                    self.sweep_y_max = w
                                    temp_break_loop = 1
                                    break
                        if (temp_break_loop == 1):
                            break                    
                    
                    #calculate position
                    self.sweep_y_start_pix = self.sweep_y_min
                    self.sweep_y_end_pix = self.sweep_y_max
                    self.sweep_y_start_pos = (self.sweep_y_start_pix * self.pixel_to_pos_multiplier) + self.build_center_y - self.svg_offset_y - self.acceleration_distance
                    self.sweep_y_end_pos = (self.sweep_y_end_pix * self.pixel_to_pos_multiplier) + self.build_center_y - self.svg_offset_y + self.acceleration_distance
                    print("Sweep from: " + str(self.sweep_y_start_pos) + ", to: " + str(self.sweep_y_end_pos))
                            
                    #fill inkjet buffer ------------------------------------------
                    print("Filling local buffer with inkjet")
                    temp_line_history = ""
                    temp_line_string = ""
                    temp_line_array = zeros(self.printing_sweep_size)
                    temp_line_history = B64.B64ToArray(temp_line_array) #make first history 0
                    temp_line_string = temp_line_history #make string also 0
                    
                    #add all of starter cap at the front
                    temp_pos = ((self.sweep_y_start_pix - 1) * self.pixel_to_pos_multiplier) + self.build_center_y - self.svg_offset_y
                    temp_pos *= 1000 #printhead pos is in microns
                    temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                    self.inkjet.SerialWriteBufferRaw("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                    print("SBR " + str(temp_b64_pos) + " " + str(temp_line_string) + ", real pos: " + str(temp_pos)) 
                        
                    for w in range(self.sweep_y_start_pix,self.sweep_y_end_pix):
                        #print("Parsing line: " + str(w))
                        temp_line_changed = 0 #reset changed
                        temp_counter = 0 
                        for h in range(int(self.sweep_x_pix), int(self.sweep_x_pix + self.printing_sweep_size)):
                            #loop through all pixels to make a new burst
                            #while counting down h will become negative, breaking the array
                            #if h lower than 0, value defaults to 0
                            if (h >= 0): 
                                temp_line_array[temp_counter] = self.imageconverter.image_array[h][w] #write array value to temp
                            else:
                                temp_line_array[temp_counter] = 0
                            temp_counter += 1
                        temp_line_string = B64.B64ToArray(temp_line_array) #convert to string
                        if (temp_line_string != temp_line_history):
                            #print("line changed on pos: " + str(w))
                            temp_line_history = temp_line_string
                            #add line to buffer
                            temp_pos = (w * self.pixel_to_pos_multiplier) + self.build_center_y - self.svg_offset_y
                            temp_pos *= 1000 #printhead pos is in microns
                            temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                            self.inkjet.SerialWriteBufferRaw("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                            print("SBR " + str(temp_b64_pos) + " " + str(temp_line_string) + ", real pos: " + str(temp_pos)) 
                    
                    #add all off cap at the end of the image
                    temp_line_array = zeros(self.printing_sweep_size)
                    temp_line_string = B64.B64ToArray(temp_line_array)
                    temp_pos = ((self.sweep_y_end_pix + 1) * self.pixel_to_pos_multiplier) + self.build_center_y - self.svg_offset_y
                    temp_pos *= 1000 #printhead pos is in microns
                    temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                    self.inkjet.SerialWriteBufferRaw("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                    print("SBR " + str(temp_b64_pos) + " " + str(temp_line_string) + ", real pos: " + str(temp_pos)) 
                        
                    print("Making printing buffer done: ")
                    #end of fill inkjet buffer -----------------------------------
                    #move to start of sweep position
                    self.grbl.SerialGotoXY(self.sweep_x_pos, self.sweep_y_start_pos, self.travel_speed)
                    self.grbl.StatusIndexSet() #set current status index 
                    while (True): #wait till the printhead is at start position
                        time.sleep(0.1)
                        if (self.grbl.StatusIndexChanged() == 1 and self.grbl.motion_state == 'idle'):
                            #print("break conditions for print while loop")
                            break #break if exit conditions met
                    
                    #wait till inkjet is loaded and motion is done
                    while(self.inkjet.BufferLeft() >0):
                        time.sleep(0.1)
                        pass
                    
                    #set current position to inkjet
                    time.sleep(0.2)
                    self.InkjetSetPosition()
                    time.sleep(0.2)
                    
                    #fill motion buffer with end of sweep
                    self.grbl.SerialGotoXY(self.sweep_x_pos, self.sweep_y_end_pos, self.print_speed)
                    self.grbl.StatusIndexSet() #set current status index 
                    while (True): #wait till the printhead is at home
                        time.sleep(0.1)
                        if (self.grbl.StatusIndexChanged() == 1 and self.grbl.motion_state == 'idle'):
                            #print("break conditions for print while loop")
                            break #break if exit conditions met
                    
                    #check pause state
                    #if pause state, go to home pos and wait till restart
                    if (self.printing_pause_flag == 1):
                        #goto home and wait to reach position
                        self.grbl.SerialGotoHome(self.travel_speed)
                        self.grbl.StatusIndexSet() #set current status index 
                        while (True): #wait till the printhead is at home
                            if (self.grbl.StatusIndexChanged() == 1 and self.grbl.motion_state == 'idle' and self.printing_pause_flag == 0):
                                #print("break conditions for print while loop")
                                break #break if exit conditions met
                    
                    #check abort state
                    if (self.printing_abort_flag == 1):
                        break
                    
                    #set next sweep
                    self.sweep_x_pix = self.sweep_x_pix - self.printing_sweep_size
                    
                    #return to load sweep
                
                #return to load layer
                self.current_layer += 1
                if (self.current_layer >= self.layers):
                    print("Last layer printed")
                    break
                    
                #check exit conditions
                if (self.printing_abort_flag == 1):
                    print("Print aborted")
                    break
                    
                #Add next layer
                temp_layer_thickness = self.imageconverter.svg_layer_height[self.current_layer] - self.current_layer_height
                print("Adding new layer, thickness: " + str(temp_layer_thickness))
                self.current_layer_height = self.imageconverter.svg_layer_height[self.current_layer]
                self.grbl.NewLayer(temp_layer_thickness)
                
                
            #if all layers printed or stop button pressed, exit
            if (self.grbl_connection_state == 1): #conditional for testing, only wait for goto home if there is motion to wait on
                self.grbl.SerialGotoHome(self.travel_speed)
                self.grbl.StatusIndexSet() #set current status index 
                while (True): #wait till the printhead is at home
                    if (self.grbl.StatusIndexChanged() == 1 and self.grbl.motion_state == 'idle'):
                        #print("break conditions for print while loop")
                        break #break if exit conditions met
                    
            self.printing_state = 0 #set printing to stopped
    
    def SendArray(self, temp_start_position):
        """Sends the current converted image array"""
        #for this function the following directions apply:
        #y is sweep direction, x is gantry direction
        #Width is Y direction, height is X direction
        
        #make universal variables
        self.inkjet_line_buffer = [] #buffer storing the print lines
        self.inkjet_lines_left = 0 #the number of lines in buffer
        self.inkjet_line_history = "" #the last burst line sent to buffer
        self.sweep = 1 #what sweep is being printed, starts at one for math reasons
        
        #motion variables if applicable
        self.y_acceleration_distance = 25.0
        
        #self.inkjet.ClearBuffer() #clear inkjet buffer on HP45
        self.print_whole_image = 1 #whether the whole image is printed, or just the parts that need ink (this excludes the edges if they are not ink)
        
        #look for X-min and X-max in image (translating direction)
        self.sweep_x_min = 0
        self.sweep_x_max = self.imageconverter.image_array_height - 1
        temp_break_loop = 0
        
        if (self.print_whole_image == 0): #only look for edges if the whole image is not printed
            #loop through image
            for h in range(0,self.imageconverter.image_array_height):
                for w in range(0,self.imageconverter.image_array_width):
                    if (self.imageconverter.image_array[h][w] != 0):
                        self.sweep_x_min = h
                        temp_break_loop = 1
                        print("X-min on row: " + str(h))
                        break
                if (temp_break_loop == 1):
                    break
            temp_break_loop = 0
            for h in reversed(range(0,self.imageconverter.image_array_height)):
                for w in range(0,self.imageconverter.image_array_width):
                    if (self.imageconverter.image_array[h][w] != 0):
                        self.sweep_x_max = h
                        temp_break_loop = 1
                        print("X-max on row: " + str(h))
                        break
                if (temp_break_loop == 1):
                    break
                
        #set X start pixel, X pixel step (using current DPI)
        self.sweep_size = int(self.imageconverter.GetDPI() / 2) #get sweep size (is halve of DPI)
        self.sweep_step = int(self.sweep_size / self.inkjet_overlap) #get sweep step
        print("Sweep size: " + str(self.sweep_size))
        print("Sweep step: " + str(self.sweep_step))
        #determine pixel to position multiplier (in millimeters)
        self.pixel_to_pos_multiplier = 25.4 / self.imageconverter.GetDPI() 
        #determine x and y start position (in millimeters)
        self.y_start_pos = temp_start_position
        self.sweep_x_min_pos = self.sweep_x_min
        
        #printing direction variables, printing direction order (1 for positive, 2 for negative, 3 for PNP, 4 for NPN)
        self.printing_direction = self.form.direction_combo.currentIndex() #get index
        self.printing_direction += 1 #add one to make it 1-4
        print("direction index: " + str(self.printing_direction))
        
        temp_current_direction = 1
        if (self.printing_direction == 1 or self.printing_direction == 3): #if mode starts positive
            temp_current_direction = 1 #start positive
        if (self.printing_direction == 2 or self.printing_direction == 4): #if mode starts negative
            temp_current_direction = -1 #start negative
        
        ###loop through all sweeps
        temp_sweep_stop = 0
        while (temp_sweep_stop == 0): 
            print("Printing sweep: " + str(self.sweep))
            #determine if there still is a sweep left
            #determine X-start and X end of sweep
            #start at negative sweep size to start with only a tiny interlaced strip
            self.sweep_x_min_pos = (0 - self.sweep_size) + (self.sweep * self.sweep_step)  
            self.sweep_x_real_min_pos = self.sweep_x_min_pos #make real position that ignores negative numbers
            #check if end of line is reached
            if (self.sweep_x_min_pos + self.sweep_step <= self.sweep_x_max): #if within range
                self.sweep_x_max_pos = self.sweep_x_min_pos + self.sweep_size
            else: #if outside range
                self.sweep_x_max_pos = self.sweep_x_max #set max of image as max pos
                temp_sweep_stop = 1 #mark last loop
                
            if (self.sweep_x_min_pos <= 0): #limit values
                self.sweep_x_min_pos = 0
            if (self.sweep_x_max_pos >= self.sweep_x_max): #limit values
                self.sweep_x_max_pos = self.sweep_x_max
                
            print("Sweep from: " + str(self.sweep_x_min_pos) + ", to: " + str(self.sweep_x_max_pos))
            
            #Look for Y min and Y max in sweep 
            self.sweep_y_min = 0
            self.sweep_y_max = self.imageconverter.image_array_width - 1
            if (self.print_whole_image == 0): #only look for edges if the whole image is not printed
                #get Y min
                temp_break_loop = 0
                for w in range(self.imageconverter.image_array_width):
                    for h in range(self.sweep_x_min_pos, self.sweep_x_max_pos):
                        if (self.imageconverter.image_array[h][w] != 0):
                            self.sweep_y_min = w
                            temp_break_loop = 1
                            break
                    if (temp_break_loop == 1):
                        break
                #get Y max
                temp_break_loop = 0
                for w in reversed(range(self.imageconverter.image_array_width)):
                    for h in range(self.sweep_x_min_pos, self.sweep_x_max_pos):
                        if (self.imageconverter.image_array[h][w] != 0):
                            self.sweep_y_max = w
                            temp_break_loop = 1
                            break
                    if (temp_break_loop == 1):
                        break
            print("sweep Y min: " + str(self.sweep_y_min) +", Y max: " + str(self.sweep_y_max))
            
            #Set Y at starting and end position
            if (temp_current_direction == 1):
                self.y_printing_start_pos = self.sweep_y_min * self.pixel_to_pos_multiplier
                self.y_printing_start_pos += self.y_start_pos - self.y_acceleration_distance
                self.y_printing_end_pos = self.sweep_y_max * self.pixel_to_pos_multiplier
                self.y_printing_end_pos += self.y_start_pos + self.y_acceleration_distance
                print("Sweep ranges from: " + str(self.y_printing_start_pos) + "mm, to: " + str(self.y_printing_end_pos) + "mm")
            elif (temp_current_direction == -1):
                self.y_printing_start_pos = self.sweep_y_max * self.pixel_to_pos_multiplier
                self.y_printing_start_pos += self.y_start_pos + self.y_acceleration_distance
                self.y_printing_end_pos = self.sweep_y_min * self.pixel_to_pos_multiplier
                self.y_printing_end_pos += self.y_start_pos - self.y_acceleration_distance
                print("Sweep ranges from: " + str(self.y_printing_start_pos) + "mm, to: " + str(self.y_printing_end_pos) + "mm")
            
            #fill local print buffer with lines
            print("Filling local buffer with inkjet")
            temp_line_history = ""
            temp_line_string = ""
            temp_line_array = zeros(self.sweep_size)
            temp_line_history = B64.B64ToArray(temp_line_array) #make first history 0
            temp_line_string = temp_line_history #make string also 0
            temp_y_from = 0
            temp_y_to = 0
            temp_direction = 0
            #add all off starter cap at the front
            if (temp_current_direction == 1):
                temp_pos = ((self.sweep_y_min - 1) * self.pixel_to_pos_multiplier) + self.y_start_pos
                temp_pos *= 1000 #printhead pos is in microns
                temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                self.inkjet_line_buffer.append("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                self.inkjet_lines_left += 1
                temp_y_from = self.sweep_y_min
                temp_y_to = self.sweep_y_max
                temp_direction = 1
            elif (temp_current_direction == -1):
                temp_pos = ((self.sweep_y_max + 1) * self.pixel_to_pos_multiplier) + self.y_start_pos
                temp_pos *= 1000 #printhead pos is in microns
                temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                self.inkjet_line_buffer.append("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                self.inkjet_lines_left += 1
                temp_y_from = self.sweep_y_max
                temp_y_to = self.sweep_y_min
                temp_direction = -1
            
            #get X-offset to compensate for leading sweeps of overlap
            temp_x_offset = self.sweep_x_min_pos - self.sweep_x_real_min_pos #get offset between X-pos and real X-pos
            #print(temp_x_offset)
            
        
            for w in range(temp_y_from,temp_y_to,temp_direction):
                #print("Parsing line: " + str(w))
                temp_line_changed = 0 #reset changed
                temp_counter = 0
                
                for h in range(self.sweep_x_min_pos, self.sweep_x_max_pos):
                    #loop through all pixels to make a new burst
                    temp_line_array[temp_counter+temp_x_offset] = self.imageconverter.image_array[h][w] #write array value to temp
                    
                    temp_counter += 1
                temp_line_string = B64.B64ToArray(temp_line_array) #convert to string
                if (temp_line_string != temp_line_history):
                    #print("line changed on pos: " + str(w))
                    temp_line_history = temp_line_string
                    #add line to buffer
                    temp_pos = (w * self.pixel_to_pos_multiplier) + self.y_start_pos
                    temp_pos *= 1000 #printhead pos is in microns
                    temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                    self.inkjet_line_buffer.append("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                    self.inkjet_lines_left += 1
            
            #add all off cap at the end of the image
            temp_line_array = zeros(self.sweep_size)
            temp_line_string = B64.B64ToArray(temp_line_array)
            if (temp_current_direction == 1):
                temp_pos = ((self.sweep_y_max + 1) * self.pixel_to_pos_multiplier) + self.y_start_pos
                temp_pos *= 1000 #printhead pos is in microns
                temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                self.inkjet_line_buffer.append("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                self.inkjet_lines_left += 1
            elif (temp_current_direction == -1):
                temp_pos = ((self.sweep_y_min - 1) * self.pixel_to_pos_multiplier) + self.y_start_pos
                temp_pos *= 1000 #printhead pos is in microns
                temp_b64_pos = B64.B64ToSingle(temp_pos) #make position value
                self.inkjet_line_buffer.append("SBR " + str(temp_b64_pos) + " " + str(temp_line_string))
                self.inkjet_lines_left += 1
                
                
            #change direction if in alternating mode
            if (self.printing_direction == 3 or self.printing_direction == 4): #if mode is alternating PNP or NPN
                if (temp_current_direction == 1): #swap direction
                    temp_current_direction = -1
                else:
                    temp_current_direction = 1

            print("Making printing buffer done: ")
            #print(self.inkjet_line_buffer)

            #Fill inkjet buffer with with sweep lines
            print("Filling inkjet buffer")
            #start filling the inkjet buffer on the HP45 lines
            temp_lines_sent = 0
            while(True):
                if (self.inkjet_lines_left > 0):
                    self.inkjet.SerialWriteBufferRaw(self.inkjet_line_buffer[0])
                    #time.sleep(0.001) #this is a good replacement for print, but takes forever
                    print(str(self.inkjet_line_buffer[0])) #some sort of delay is required, else the function gets filled up too quickly. Will move to different buffer later
                    del self.inkjet_line_buffer[0] #remove sent line
                    self.inkjet_lines_left -= 1
                    temp_lines_sent += 1
                else:
                    break
            
            self.sweep += 1 #add one to sweep
            
        ###end of loop through sweep
        #repeat loop until all sweeps are finished
        print("Sending data done")
        
    def SavePng(self):
        """Saves current SVG to array of bitmap images, enables camera"""
        if (self.file_loaded == 2): #if a file is present
            if not os.path.exists('demo'):
                os.makedirs('demo')#make demo folder
            
            #run through all layers of the file
            for L in range(self.imageconverter.svg_layers):
                #save each of the files to the demo folder
                print("Layer" + str(L))
                self.imageconverter.SVGLayerToArray(L)
                self.RenderOutput() #render image
                self.imageconverter.output_image.save("demo\Layer" + str(L) + ".png", "PNG") 
                
        
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = MainWindow()
    sys.exit(app.exec_())


