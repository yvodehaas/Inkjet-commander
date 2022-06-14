#This file is part of Oasis controller.

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




#image converter handles the loading, and conversion of images to be printed
#it itself has no capabilies of rendering (interface does that) but it does handle all other tasks
#todo:

from PyQt5.QtGui import QPixmap, QColor, QImage
from PyQt5 import QtWidgets
import numpy as np
from PIL import Image, ImageQt
from pathlib import Path
from enum import Enum
import sys

class ImageType(Enum):
    BITMAP = 1
    VECTOR = 2
    NONE = 0


class ImageConverter():
    def __init__(self):
        super().__init__()

        #variables
        self.dpi = 600 #defaults to 600
        self.burst_size = self.dpi/2 #defaults half of dpi
        self.file_type = 0 #type of file, 0 for nothing, 1 for bitmap, 2 for vector
        self.file_path = ''
        self.image_array_width = 0 #the width of the image
        self.image_array_height = 0 #the height of the image
        self.svg_average_layer_thickness = 0 # the layer thickness of the file

        self.svg_layers = 0 #how many layers there are in the file
        self.svg_layer_names = []
        self.svg_layer_height = []
        self.svg_width = 0
        self.svg_height = 0



    def OpenFile(self, temp_file_path):
        """open attempts to open file in path, if successful, return a 1,
        if failed, will return a 0"""
        #print("Attempting to open: " + str(temp_file_path))
        self.file_path = Path(temp_file_path)
        if not self.file_path.exists():
            self.file_type = ImageType.NONE
            return 0
        else:
            #get file type
            file_extension = self.file_path.suffix
            if (file_extension.lower() == '.svg'):
                self.file_type = ImageType.VECTOR #set image type to vector
            else:
                self.file_type = ImageType.BITMAP #set image type to bitmap

            temp_success = 0
            #open bitmap file
            if (self.file_type == ImageType.BITMAP): #attempt opening bitmap file
                try: #try opening file
                    self.pillow_image = Image.open(self.file_path).convert("RGBA")
                    with_white_bg = Image.new("RGBA", self.pillow_image.size, "WHITE")
                    with_white_bg.paste(self.pillow_image, mask=self.pillow_image)
                    self.pillow_image = with_white_bg
                    self.conversion_image = ImageQt.ImageQt(self.pillow_image) #create conversion image
                    self.input_image = QPixmap.fromImage(self.conversion_image) #create input image
                    self.output_image = QPixmap.fromImage(self.conversion_image) #create output image
                    temp_success = 1 #set succesful,
                except:
                    nothing = 0

                if (temp_success == 1):
                    #print("file opened")
                    #make output array the size of the image, filled with 0
                    self.image_array_width = self.pillow_image.width
                    self.image_array_height = self.pillow_image.height
                    return 1

            if (self.file_type == ImageType.VECTOR): #attempt opening vector file
                try: #try opening file
                    with open(self.file_path) as file_object:
                        self.vector_file = file_object.read()
                    temp_success = 1 #set succesful,
                except:
                    nothing = 0

                if (temp_success == 1):
                    #print("file opened")
                    self.svg_usable = self.SVGGetData() #get data from vector file
                    if (self.svg_usable == 1):
                        #Get data automatically filles width, height and layers
                        #make output array the size of the image, filled with 0
                        #print("Image width: " + str(self.image_array_width) + ", Image height: " + str(self.image_array_height))
                        self.image_array = np.zeros( (self.image_array_height, self.image_array_width) )
                        #print(self.image_array)

                        self.SVGLayerToArray(0) #render first layer

                        return 2
                    else:
                        return 0
        return 0

    def Threshold(self, temp_threshold):
        """Takes the input image file and creates a new file that is black and while
        split along the threshold (0-255)"""
        # Grayscale
        img = self.pillow_image.convert('L')
        # Threshold
        img = img.point( lambda p: 255 if p > temp_threshold else 0 )
        # To mono
        bw = img.convert('1')
        self.image_array = np.asarray(bw)

    def SetDPI(self, temp_dpi):
        """Sets the dots per inch for the conversion"""
        self.dpi = temp_dpi
        #print("Setting dpi to: " + str(self.dpi))

    def GetDPI(self):
        """Returns the current DPI setting"""
        return self.dpi

    def ArrayToImage(self):
        """Take the conversion array and map it to a bilevel output image"""
        im = Image.fromarray(self.image_array, mode="L")
        self.output_image = QPixmap.fromImage(ImageQt.ImageQt(im))

    def RGBToImage(self):
        """Takes the only the RGB of an image and writes it to output"""
        self.output_image = QPixmap(self.image_array_width, self.image_array_height)
        self.temp_image = QImage(self.output_image)
        self.temp_color = QColor()
        for w in range(0,self.image_array_width):
            for h in range(0,self.image_array_height):
                self.pixel_color = self.conversion_image.pixelColor(w,h)
                self.qred = self.pixel_color.red()
                self.qgreen = self.pixel_color.green()
                self.qblue = self.pixel_color.blue()
                self.temp_color.setRgb(self.qred,self.qgreen,self.qblue)
                self.temp_image.setPixelColor(w,h,self.temp_color)
        self.output_image = QPixmap(self.temp_image)

    def AlphaMaskToImage(self):
        """Takes the alpha mask of an image and converts it to greyscale"""
        self.output_image = QPixmap(self.image_array_width, self.image_array_height)
        self.temp_image = QImage(self.output_image)
        self.temp_color = QColor()
        for w in range(0,self.image_array_width):
            for h in range(0,self.image_array_height):
                self.pixel_color = self.conversion_image.pixelColor(w,h)
                self.alpha = self.pixel_color.alpha()
                self.temp_color.setRgb(self.alpha,self.alpha,self.alpha)
                self.temp_image.setPixelColor(w,h,self.temp_color)
        self.output_image = QPixmap(self.temp_image)

    def SVGGetData(self):
        """Gets data like image size, image pixel size and layers from the svg, inputed as a path to svg"""
        #print("getting data from svg file")
        #print(str(temp_input_data))

        temp_layer_counter = 0 #clear number of layers counter
        self.svg_layer_names = [] #clear layer array
        self.svg_layer_height = [] #clear height array

        with open(self.file_path) as file_object:
            for L in file_object:
                #print(L.rstrip())
                if (L.startswith('<svg ')): #decode svg data
                    #print("svg data found")
                    temp_decode = L.partition('<svg ') #partition the svg header away
                    temp_decode = temp_decode[2] #set remainder as new string
                    while(True):
                        temp_decode = temp_decode.partition('"') #get next bit of data
                        #print(temp_decode)
                        #check exit requirements
                        if (temp_decode[1] != '"'): #break from while when the partition character is no longer found
                            break

                        if (temp_decode[0].lstrip() == 'width='): #get width data
                            #print("Getting width data")
                            temp_decode = temp_decode[2].partition('"')
                            self.svg_width = float(temp_decode[0])
                            #print(self.svg_width)
                        if (temp_decode[0].lstrip() == 'height='): #get height data
                            #print("Getting height data")
                            temp_decode = temp_decode[2].partition('"')
                            self.svg_height = float(temp_decode[0])
                            #print(self.svg_height)
                        #set to read next part
                        temp_decode = temp_decode[2]

                if (L.startswith('  <g ')): #decode layer data
                    #print("layer data found")
                    temp_decode = L.partition('  <g ') #partition the svg header away
                    temp_decode = temp_decode[2] #set remainder as new string
                    while(True):
                        temp_decode = temp_decode.partition('"') #get next bit of data
                        #print(temp_decode)
                        #check exit requirements
                        if (temp_decode[1] != '"'): #break from while when the partition character is no longer found
                            break

                        if (temp_decode[0].lstrip() == 'id='): #get layer data
                            #print("Getting layer data")
                            temp_decode = temp_decode[2].partition('"')
                            temp_layer_counter += 1
                            temp_layer_name = temp_decode[0]
                            self.svg_layer_names.append(temp_layer_name)
                            #print(temp_layer_name)
                        if (temp_decode[0].lstrip() == 'slic3r:z='): #get layer height
                            #print("Getting layer height")
                            temp_decode = temp_decode[2].partition('"')
                            temp_layer_height = float(temp_decode[0])
                            temp_layer_height *= 1000000.0 #get mm from whatever the hell they are using (it seems km, WHY!)
                            self.svg_layer_height.append(temp_layer_height)
                            #print(temp_layer_height)

                        #set to read next part
                        temp_decode = temp_decode[2]

        #decode svg size to image array size (pixels)
        #width and height are flipped for reasons of me sucking
        self.image_array_height = int(self.svg_width / 25.4 * self.dpi) + 1 #plus 1 pixel fluff
        self.image_array_width = int(self.svg_height / 25.4 * self.dpi) + 1 #pixel fluff only aid stability that should have never been required
        self.svg_layers = int(temp_layer_counter)


        if (self.svg_layers > 0): #if the number of layers is more than 0
            #get average layer height
            self.svg_average_layer_thickness = 0
            temp_last_height = 0.0 #variable to get thickness
            for L in range(len(self.svg_layer_height)):
                self.svg_average_layer_thickness += (float(self.svg_layer_height[L]-temp_last_height))
                temp_last_height = float(self.svg_layer_height[L]) #make history
            self.svg_average_layer_thickness /= self.svg_layers

            print("Image size: " + str(self.image_array_width) + "," + str(self.image_array_height))
            print("Layers = " + str(temp_layer_counter))
            print(f'Layer height: {self.svg_average_layer_thickness:.2f}')
            #print(self.svg_layer_names)
            #print(self.svg_layer_height)
            return 1
        else:
            print("No layers found, file wrong type")
            print("Make sure only tom import SVG files created by Slic3r")
            return 0

    def SVGLayerToArray(self, temp_layer):
        """Reads the layer in the Slic3r SVG file and converts it to array"""
        #Behold the magnificence.
        #Instead of taking an SVG library to handle the parsing of SVG files like a sane person
        #I went out of my way to write one myself. Why you might ask.
        #I have done it before, so I knew how to
        #also, I had a day where I could not do much else, I thought I give it a go
        #It works surprisingly well on slic3r svg's. I do not care much for other svg files
        #proceed with caution.

        if (temp_layer >= self.svg_layers): #if requested layer exceeds available
            return 0

        temp_line_found = 0
        with open(self.file_path) as file_object:
            for L in file_object:
                #print(L.rstrip())

                #look for the right layer, if found, set line to right one
                if (L.startswith('  <g ')): #decode layer data
                    #print("layer data found")
                    temp_decode = L.partition('  <g ') #partition the svg header away
                    temp_decode = temp_decode[2] #set remainder as new string
                    while(True):
                        temp_decode = temp_decode.partition('"') #get next bit of data
                        #print(temp_decode)
                        #check exit requirements
                        if (temp_decode[1] != '"'): #break from while when the partition character is no longer found
                            break

                        if (temp_decode[0].lstrip() == 'id='): #get layer data
                            #print("Getting layer data")
                            temp_decode = temp_decode[2].partition('"')
                            temp_layer_name = temp_decode[0]
                            if (temp_layer_name == self.svg_layer_names[temp_layer]):
                                temp_line_found = 1
                                self.image_array = np.zeros( (self.image_array_height, self.image_array_width) ) #clear image array
                                #print(temp_layer_name)

                        #set to read next part
                        temp_decode = temp_decode[2]

                #start looking for data until end of layer is found
                if (temp_line_found == 1):
                    if (L.startswith('    <polygon ')): #decode polygon data
                        #print("polygon found")
                        temp_decode = L.partition('    <polygon ') #partition the svg header away
                        temp_decode = temp_decode[2] #set remainder as new string
                        while(True):
                            temp_decode = temp_decode.partition('"') #get next bit of data
                            #print(temp_decode)
                            #check exit requirements
                            if (temp_decode[1] != '"'): #break from while when the partition character is no longer found
                                break

                            if (temp_decode[0].lstrip() == 'points='): #get point data
                                #print("Getting point data")
                                temp_decode = temp_decode[2].partition('"')
                                temp_points = temp_decode[0]
                                #print(temp_points)

                                self.ArrayAddPolygon(temp_points)




                            #set to read next part
                            temp_decode = temp_decode[2]

                    if (L.startswith('  </g>')): #decode polygon data
                        #print("polygon end")
                        temp_line_found = 0

                        #convert flip points to image
                        self.ArrayConvert()

    def ArrayAddPolygon(self, temp_input):
        """add a string with coordinates to the toggle point image array"""
        #move from point to point. Wherever the points intersect with the array, frip bit from 1 to 0 or 0 to 1

        #15,35 10,35 10,25 5,25 5,35 0,35 0,20 15,20 #normal output
        temp_input = temp_input + " " #add space at end for final conversion
        temp_x = []
        temp_y = []
        temp_dpi_multiplier = 25.4 / self.dpi  #amount of mm per pixel

        while(True):
            temp_input = temp_input.partition(' ') #partition single coordinate
            if (temp_input[1] != ' '): #if partition is empty, break
                break;

            temp_xy = temp_input[0].partition(',')
            temp_x.append(float(temp_xy[0]))
            temp_y.append(float(temp_xy[2]))

            temp_input = temp_input[2] #set string to remainder

        #print("pos x: " + str(temp_x))
        #print("pos y: " + str(temp_y))

        temp_array_size = len(temp_x)
        for pos in range(temp_array_size):
            #check all intersections with array between pos - 1 and pos
            if (temp_x[pos - 1] < temp_x[pos]): #make sure smallest X is first
                x_start = temp_x[pos - 1]
                x_end = temp_x[pos]
                y_start = temp_y[pos - 1]
                y_end = temp_y[pos]
            else:
                x_start = temp_x[pos]
                x_end = temp_x[pos - 1]
                y_start = temp_y[pos]
                y_end = temp_y[pos - 1]

            #X positions are chosen to guarantee the x line is within bounds
            #later checks exclude values that are impossible
            x_pixel_start = int(x_start / temp_dpi_multiplier)
            x_pixel_end = int(x_end / temp_dpi_multiplier) + 1

            #loop through all pixels, look for intersections
            #print("From X" +str(x_start) + " to " + str(x_end))
            #print("From X" +str(x_pixel_start) + " to " + str(x_pixel_end))
            if (x_start != x_end): #check if x are not the same
                for x in range(x_pixel_start, x_pixel_end):
                    temp_x_pos = float(x * temp_dpi_multiplier) #get actual x_pos for this value
                    if (temp_x_pos >= x_start and temp_x_pos <= x_end): #if x is in bound of the line
                        #print("pos: " + str(x))

                        #calculate y position
                        delta_x = x_end - x_start
                        delta_y = y_end - y_start
                        #print("delta " + str(delta_x) + "," + str(delta_y))

                        calc_x = temp_x_pos - x_start

                        calc_p = calc_x / delta_x #get percentage of moved along x
                        #print("X percentage " + str(calc_p))

                        calc_y = float(delta_y * calc_p) + y_start
                        #print(calc_y)
                        temp_y_pixel = int(calc_y / temp_dpi_multiplier)
                        #print("pos: " + str(temp_x_pos) + "," + str(calc_y))
                        #print("pix: " + str(x) + "," + str(temp_y_pixel))

                        #toggle pixel in array
                        if (x >= 0 and x < self.image_array_height and temp_y_pixel >= 0 and temp_y_pixel < self.image_array_width):
                            if (self.image_array[x][temp_y_pixel] == 0):
                                self.image_array[x][temp_y_pixel] = 1
                            else:
                                self.image_array[x][temp_y_pixel] = 0




    def ArrayConvert(self):
        """take the toggle point array and convert it to an image array"""
        for x in range(self.image_array_height):
            temp_toggle_state = 0 #whether the printhead is 1 or 0
            for y in range(self.image_array_width):
                if (self.image_array[x][y] != 0): #if pixel is high
                    if (temp_toggle_state == 1): #flip toggle state
                        temp_toggle_state = 0
                    else:
                        temp_toggle_state = 1

                self.image_array[x][y] = temp_toggle_state #write toggle state to pixel






if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    imagec = ImageConverter()
    assert (imagec.OpenFile("TestFiles/Random banana.jpg") > 0)
    imagec.Threshold(128)
    imagec.ArrayToImage()
