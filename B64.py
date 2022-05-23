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



#B64 encodes from and to HP45 controller based B64
#from 0-63: ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
#signs can be used as follows: -L2a, making the L2a number negative

#todo:

def B64ToLookup(temp_input):
    """Takes an integer value between 0 and 63 and returns a character"""
    #constrain values
    if (temp_input < 0):
        temp_input = 0
    if (temp_input > 63):
        temp_input = 63
        
    temp_return = ""
    #make B64 array
    temp_b64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    temp_return += temp_b64[temp_input]
    return temp_return
    
def B64ToSingle(temp_input):
    """Takes an integer value, and turns it to a string containing the value in B64"""
    temp_return_value = ""
    temp_negative = 1
    temp_convert = 0
    temp_input = int(temp_input)
    if (temp_input < 0): #if value is negative
        temp_negative = -1 #add a minus
        temp_input *= -1 #make positive
    
    #add 6 bits at a time to value
    while (True):
        temp_convert = temp_input & 63 #take 6 LSBits
        temp_return_value += B64ToLookup(temp_convert) #add to return
        temp_input = temp_input >> 6 #shift 6 bits
        
        if (temp_input == 0):
            break
    
    if (temp_negative == -1):
        temp_return_value += '-'
        
    temp_return_value = temp_return_value[::-1]
    return temp_return_value


#B64 to array, B64 is  flipped. Somewhere the order seems to be reversed. Don't know where, but this is simpler than 8 hours of digging
#I do not know where (though I suspect in the firmware), but this solution is tested working, and I have stopped caring until I have all other things work
#(I Sure hope future me does not regret refusing to find the real cause, but this is a calculated risk)
def B64ToArray(temp_input): 
    """Takes an array of 1's and 0's and turns it into a string of B64"""
    temp_return_value = ""
    temp_value = 0
    temp_output = 0
    temp_counter = 0
    temp_b6 = 0
    temp_inf = 0
    while (True):
        temp_inf = 5 - temp_b6 #the legendary bodge that inverts the B6 value and magically fixes things
        temp_value = int(temp_input[temp_counter]) #add value to variable
        if (temp_value > 1): #limit value to 1 if higher
            temp_value = 1 #(make 1)
        temp_value = temp_value << temp_inf #shift bits (Was temp_b6, inf is inverted value!!!!!)
        temp_output = temp_output | temp_value #add to output value
        temp_value = 0 #reset value
        temp_b6 = temp_b6 + 1 #add one to b6 counter
        temp_counter = temp_counter + 1 #add one to overal counter
        if (temp_b6 >= 6 or temp_counter >= len(temp_input)): #if value is six, reset to 0, add value
            temp_b6 = 0 
            temp_return_value += B64ToLookup(temp_output) 
            temp_output = 0 #reset output value
            
            if (temp_counter >= len(temp_input)): #if break conditions
                #temp_return_value = temp_return_value [::-1] #reverse value (Needed?)
                return temp_return_value #return value
        
    
    
def B64FromLookup(temp_input):
    """Takes a string of one character B64, and turn it to decimal 0-63"""
    temp_input = ord(temp_input) #convert to ascii value
    if (temp_input >= ord('A') and temp_input <= ord('Z')): return temp_input - ord('A') #0-25
    if (temp_input >= ord('a') and temp_input <= ord('z')): return temp_input - 71 #26-51
    if (temp_input >= ord('0') and temp_input <= ord('9')): return temp_input + 4 #52-61
    if (temp_input == ord('+')): return 62 #62
    if (temp_input == ord('/')): return 63 #63
    return -1 #-1
    
def B64FromSingle(temp_input):
    """takes a string of B64 and turns it into a real value"""
    if (len(temp_input) > 0):
        temp_return_value = 0
        temp_negative = 1
        temp_order = 1
        if (temp_input[0] == '-'):
            temp_negative = -1
            #print("minus found")
            
        if (len(temp_input) == 0): #if after strip no characters are left
            return
            
        temp_input = temp_input[::-1] #reverse string
            
        while (True):
            #print("Parsing: " + str(temp_input[0]))
            temp_val = B64FromLookup(temp_input[0])
            if (temp_val != -1):
                #print("modified to: " + str(temp_val))
                temp_return_value += (temp_val * temp_order)
                #print("Total so far: " + str(temp_return_value))
                temp_order *= 64 #add next order of magnitude
                temp_input = temp_input[1:] #remove first character
            else:
                temp_return_value *= temp_negative
                return temp_return_value
            
            if (len(temp_input) <= 0):
                temp_return_value *= temp_negative
                return temp_return_value
    
    
def B64FromArray(temp_input):
    """Takes a string of B64 and turns it into an array of values from 0 to 64"""
    #temp_return_value[] 

def B64FromTestArray(temp_input):
    """Takes a string of B64 in test format and turns it into an array of of either 1 or 0"""
    temp_input = temp_input[::-1] #flip the array from LSB to MSB
    temp_return_value = []
    while (True):
        #print("Parsing: " + str(temp_input[0]))
        temp_val = B64FromLookup(temp_input[0]) #decode from B64
        if (temp_val != -1):
            #print("modified to: " + str(temp_val))
            temp_input = temp_input[1:] #remove first character
            for b in range(0,6):
                temp_decode = temp_val
                temp_decode = (temp_decode >> b) & 1
                temp_return_value.append(int(temp_decode)) #return bit of value
                #print(temp_decode)
        else:
            return temp_return_value
        
        if (len(temp_input) <= 0): #if array is empty
            return temp_return_value
    
    

if __name__ == '__main__':
    #print(B64ToArray([0,0,0,0,0,0,0,0,0,0,0,1])) #tested working
    #print(B64ToLookup(2)) #tested working
    #print(B64ToSingle(-129)) #tested working
    #print(B64FromLookup('0')) #tested working
    print(B64FromSingle("ZDg"))
    print(B64FromSingle("eOP"))
    #print(B64FromTestArray("////B"))
    print('finished')

