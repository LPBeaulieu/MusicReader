import copy
import cv2
from datetime import datetime
import glob
import json
import math
import mido
from mido import Message, MetaMessage, MidiFile, MidiTrack
import numpy as np
import os
import re
import shutil
import signal
import sys
import tempfile
import textwrap
import time
import traceback


#The "clear_screen()" function will clear the CLI screen
#using the appropriate command depending on the operating system.
def clear_screen():
    #'nt' is for Windows, 'posix is for Linux/Raspberry Pi/macOS (else statement)
    os.system('cls' if os.name == 'nt' else 'clear')

#The Signal Interrupt (SIGINT) handler will
#call the "signal_interrupt_signal_handler()" function 
#when the user presses on CTRL + C to exit the app.

#The function "signal_interrupt_signal_handler()" will call
#"sys.exit(0)" to exit the program normally.
def signal_interrupt_signal_handler(sig, frame):
    sys.exit(0)

#The function "write_entry_in_error_log()" will write 
#the full technical traceback error to the error log.
def write_entry_in_error_log():
    with open("ERROR LOG.txt", "a", encoding="utf-8") as error_log:
        error_log.write(f"\n--- Error at {datetime.now()} ---\n")
        traceback.print_exc(file=error_log)

#The function "display_progress()" will display the progress string in the console
#and return the estimated number of seconds for the code to complete.
def display_progress(current_jpeg_index, first_jpeg_index, last_jpeg_index, start_time, previous_estimated_seconds):
            
    elapsed_seconds = time.perf_counter() - start_time
    #divmod returns (minutes, remaining_seconds)
    mins, secs = divmod(round(elapsed_seconds), 60)
    time_string = f"{mins:02}:{secs:02}"
    eta_string = ""

    #If the MIDI file will only be comprised of one scoresheet 
    #scan, then the "percent_completion" will be 100% after 
    #processing that JPEG file (so as to avoid "Division 
    #by Zero" errors).
    if last_jpeg_index - first_jpeg_index == 0:
        percent_completion = 100
        eta_string = f" ETA: 00:00\n"
    else:
        #The percent completion is calculated by dividing the difference between the current JPEG index
        #and the first JPEG index by the total number of JPEG files to be processed, which is itself
        #calculated by subtracting the first JPEG index from the last JPEG index. The resulting quotient 
        #is multiplied by 100 and then rounded when printed on-screen.
        percent_completion = (current_jpeg_index-first_jpeg_index)/(last_jpeg_index-first_jpeg_index) * 100

    #The previous estimation of the remaining number of seconds is stored in the variable
    #"previous_estimated_seconds" and will be used instead of the current calculation
    #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
    #its estimation.
    estimated_seconds = previous_estimated_seconds
    #A delay of 3 JPEG files is used to be able to gather a somewhat accurate value
    #of the elapsed time for a given percent completion value.
    if (last_jpeg_index > first_jpeg_index + 3 and current_jpeg_index > first_jpeg_index + 3):
        #The estimated number of seconds left is calculated by doing the cross-multiplication between
        #the number of percentage points left to reach completion ("100 - percent_completion") 
        #and the elapsed time for the current percent completion.
        estimated_seconds = round((100 - percent_completion) * elapsed_seconds / percent_completion)
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        if (previous_estimated_seconds != 0 and estimated_seconds > previous_estimated_seconds):
            estimated_seconds = previous_estimated_seconds

        #If the current JPEG index is the last JPEG index,
        #then the remaining time is zero seconds (" ETA: 00:00").
        if (current_jpeg_index == last_jpeg_index):
            percent_completion = 100
            eta_string = f" ETA: 00:00\n"
        #We do not want to display negative times, hence the
        #condition ("elif (estimated_seconds > 0)").
        elif (estimated_seconds > 0):
            eta_mins, eta_secs = divmod(round(estimated_seconds), 60)
            eta_string = f" ETA: {eta_mins:02}:{eta_secs:02}"

    #"\r" resets the line
    sys.stdout.write(f"\rCompleted JPEG file: {current_jpeg_index+1} of {last_jpeg_index+1} ({round(percent_completion)}%) Time: {time_string}{eta_string}")

    return estimated_seconds

#The function "get_terminal_dimensions()" will return the number of columns 
#and rows in the console, to allow to properly format the text and dividers.
def get_terminal_dimensions():
    #Detect columns (width) and lines (height)
    #Returns a named tuple; default fallback is (80, 24)
    size = shutil.get_terminal_size(fallback=(80, 24))
    return int(size.columns * 0.75), int(size.lines)

#The function "is_valid_positive_non_zero_int_or_float" will validate the data 
#stored in the dictionary obtained from the "json_settings.json" file to make 
#sure it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number either an integer or a float and also exclude negative and zero 
#numbers "number <= 0". It will return "True" if the number is a valid
#("else" statement) integer and "False" otherwise ("if" statement).
def is_valid_positive_non_zero_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)) or number <= 0: 
        return False
    else:
        return True
        
#The function "is_valid_positive_int_or_float" will validate the data stored 
#in the dictionary obtained from the "json_settings.json" file to make sure 
#it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number is either a positive integer or a float. It will return 
#"True" if the number is a valid ("else" statement) integer and "False" 
#otherwise ("if" statement).   
def is_valid_positive_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)) or number < 0:
        return False
    else:
        return True

#The function "is_valid_non_negative_int_or_float" will validate the data stored 
#in the dictionary obtained from the "json_settings.json" file to make sure 
#it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number is either an integer or a float and also exclude negative 
#numbers "number < 0". It will return "True" if the number is a valid
#("if" statement) integer and "False" otherwise ("else" statement).   
def is_valid_non_negative_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)) or number < 0:
        return False
    else:
        return True
    
#The function "is_valid_int_or_float" will validate the data stored 
#in the dictionary obtained from the "json_settings.json" file to make sure 
#it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number is either an integer or a float. It will return "True" if 
#the number is a valid ("else" statement) integer and "False" otherwise 
#("if" statement).   
def is_valid_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)):
        return False
    else:
        return True
        
#The function "atomic_save()" will create a temporary JSON file with the updated changes.
#If the files is created successfully, then the files will be swapped. If a problem is 
#encountered, the temp file will be unlinked and an error log will be reported.
def atomic_save(json_settings_dictionary, json_settings_file_path_name):
    #Create a temp file in the same directory
    temp_dir = os.path.dirname(json_settings_file_path_name) or "."
    json_file_descriptor, temp_path = tempfile.mkstemp(dir=temp_dir, text=True)

    try:
        with os.fdopen(json_file_descriptor, "w", encoding="utf-8") as f:
            #Write the default values found in "json_settings_dictionary" in the empty JSON file, 
            #with four space indentations to make it more human-readable.
            json.dump(json_settings_dictionary, f, indent=4)
            #Ensure the data is flushed to hardware.
            f.flush()
            #"os.fsync(f.fileno())" is required to force the OS to physically commit
            #every bit of information to the hardware storage right now, preventing 
            #a situation where an empty file might be created if the computer crashed
            #before the OS finished waiting before committing the file to memory. 
            os.fsync(f.fileno())
        
        #Swap the files only if the temp file was successfully generated (Atomic security)
        os.replace(temp_path, json_settings_file_path_name)
    except Exception as e:
        #Clean up temp file if something goes wrong BEFORE the swap
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        #The function "write_entry_in_error_log()" will write 
        #the full technical traceback error to the error log.
        write_entry_in_error_log()

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
       
        print("\n" + "=" * columns)
        print("CRITICAL ERRROR ENCOUNTERED")
        print("\nDetails:", e)
        print("\n" + "=" * columns)

        #Exit with error code
        sys.exit(1)

#The function "rotate_image()" will rotate the "img"
#numpy array using the "getRotationMatrix2D()" and 
#"warpAffine()" OpenCV methods. 
def rotate_image(img, color_img, rows, cols, angle):
    #Rotate the image according to OpenCV's documentation,
    #where cols-1 and rows-1 are the coordinate limits (zero-indexed)

    #1. Generate the original rotation matrix around the true center
    #We need to invert the specified rotation angle to factor in that 
    #clockwise rotations have a negative angle in mathematics
    M = cv2.getRotationMatrix2D(((cols-1)/2.0, (rows-1)/2.0), -angle, 1.0)
    
    #2. Calculate the absolute values of sine and cosine from the rotation matrix
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    
    #3. Calculate the new bounding dimensions (the new limits for cols and rows)
    new_cols = int((rows * sin) + (cols * cos))
    new_rows = int((rows * cos) + (cols * sin))
    
    #4. Adjust the translation column (the third column of the rotation matrix M).
    #This offsets the center of rotation to the center of the new, larger canvas.
    M[0, 2] += (new_cols / 2.0) - ((cols - 1) / 2.0)
    M[1, 2] += (new_rows / 2.0) - ((rows - 1) / 2.0)
    
    #5. Pass the newly calculated size into warpAffine
    #"BORDER_CONSTANT" will fill newly exposed background area with black (0,0,0).
    #"INTER_CUBIC" will allow better results with floating point rotation angles.
    img = cv2.warpAffine(img, M, (new_cols, new_rows), 
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0),
        flags=cv2.INTER_CUBIC)
    
    color_img = cv2.warpAffine(color_img, M, (new_cols, new_rows), 
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0),
        flags=cv2.INTER_CUBIC)
    
    return img, color_img, new_rows, new_cols

#The function "get_horizontal_projection_profile()" will get the horizontal projection 
#profile by first filtering the "img" array with the "np.where()" method, such that 
#white pixels have a value of zero and non-white pixels have a value of one. This 
#will allow to get the horizontal projection profile by adding up all the rows for 
#each column, thus generating a 1D horizontal array. The left and right edges of 
#the score sheet will be detected, as they will be the first and last elements 
#of the horizontal projection profile where the pixels will not be almost exclusively 
#black. 
def get_horizontal_projection_profile(img, black_pixel_threshold_percentage, rows, undetectable_scoresheet_error_string):
    
    #The non-white pixels will be set to the value of one and white pixels 
    #will have a value of zero, such that adding white pixels does not 
    #impact the count of non-white pixels.
    img_filtered_for_flattening = np.where(img == 255, 0, 1)
    
    #Add up all the rows for each column to get the horizontal projection profile
    #("np.sum" along the "y" axis at index zero).
    horizontal_projection_profile = np.sum(img_filtered_for_flattening, axis=0)
    
    #A column of pixels to the left of or to the right of the scoresheet would be comprised of 
    #entirely black pixels, and so the sum of these pixels in "horizontal_projection_profile"
    #would be almost equal to the height of the rotated image ("rows"). Conversely, any columns 
    #making up the score sheet contain some white pixels and the sum would be much lower than "rows".
    non_black_pixels_horizontal_projection_profile = np.where(horizontal_projection_profile < (black_pixel_threshold_percentage/100)*rows)[0]
    black_pixels_horizontal_projection_profile = np.where(horizontal_projection_profile >= (black_pixel_threshold_percentage/100)*rows)[0]
    
    #If a scoresheet is visible in the form of some non-black pixels
    #then the "if" statement below will run. If that is not the case,
    #then the user has probably set a too stringent value for the 
    #"paper_color_grayscale_filter_threshold" (too high, meaning that 
    #no pixels were lighter than the threshold and consequently all 
    #pixels were set to black).
    if non_black_pixels_horizontal_projection_profile.size != 0:
    
        left_x_scoresheet = non_black_pixels_horizontal_projection_profile[0]
        right_x_scoresheet = non_black_pixels_horizontal_projection_profile[-1]            
        
        scoresheet_width = right_x_scoresheet - left_x_scoresheet
        
    #If a scoresheet is visible in the form of some non-black pixels
    #then the "if" statement below will run. If that is not the case,
    #then the user has probably set a too stringent value for the 
    #"paper_color_grayscale_filter_threshold" (too high, meaning that 
    #no pixels were lighter than the threshold and consequently all 
    #pixels were set to black).
    else:
        print(undetectable_scoresheet_error_string)
        input(press_any_key_string)
        sys.exit(1)
        
    return (img_filtered_for_flattening, 
            horizontal_projection_profile, 
            non_black_pixels_horizontal_projection_profile, 
            black_pixels_horizontal_projection_profile, 
            left_x_scoresheet, 
            right_x_scoresheet,
            scoresheet_width)

#The function "get_file_name_horizontal_vertical_shift_manual_override_strings()"
#will return the horizontal and vertical shift manual override pixel values, that 
#were extracted from the file name and the file name where these have been removed
#(e.g., 5, -2, "track_01" for the file name "track_01+ (v=5, h=-2)"). Should there 
#be no such manual override parenthesized expressions in "file_name_without_extension", 
#then zero will be returned for the horizontal and vertical shift manual override pixel 
#values, along with the original value of "file_name_without_extension".
def get_file_name_horizontal_vertical_shift_manual_override_strings(full_file_name):
    #Returns the final component of the path
    file_name_with_extension = os.path.basename(full_file_name)
    file_name_without_extension, extension = os.path.splitext(file_name_with_extension)
    
    horizontal_vertical_shift_manual_override_strings = (
        #The search pattern queries for a "v" or "h" (uppercased or lowercased), followed by zero or more spaces, 
        #zero or one equal sign, zero or more spaces, zero or one minus sign, one or more digits, zero or more spaces, 
        #a comma, and the same pattern for the second parameter.
        re.findall(r"\([vVhH][ ]*[=]?[ ]*[-]?[\d]+[ ]*,[ ]*[vVhH][ ]*[=]?[ ]*[-]?[\d]+\)", file_name_without_extension))
    #If a horizontal and vertical shift manual override string was found, then the returned list will be indexed 
    #at the first index (zero) to return it and the original file name will have this substring removed using a 
    #"re.sub()" method.    
    if (horizontal_vertical_shift_manual_override_strings != [] and 
        horizontal_vertical_shift_manual_override_strings[0].count(",") == 1):
        file_name_without_extension = re.sub(re.escape(horizontal_vertical_shift_manual_override_strings[0]), "", file_name_without_extension).strip()
        horizontal_vertical_shift_split_strings_at_comma = horizontal_vertical_shift_manual_override_strings[0].split(",")
        
        #The values of "horizontal_shift_pixels_candidate" and "vertical_shift_pixels_candidate",
        #both initialized to "None" will be set to the extracted pixel shifts from the parenthesized 
        #expression, after it was split at the comma character. If no digit patterns were found in the 
        #split strings, then zero will be returned for the horizontal and vertical shift manual override 
        #pixel values
        horizontal_shift_pixels_candidate = None 
        vertical_shift_pixels_candidate = None
        #The digit pattern consists of zero or one minus sign, followed by one or more digits.
        digit_pattern = r"[-]?[\d]+"
        for split_string in horizontal_vertical_shift_split_strings_at_comma:
            #If "h" is in the split string, but  not "v", then it means that this 
            #is the horizontal shift expression.
            if "h" in split_string.lower() and not "v" in split_string.lower():
                horizontal_shift_pixels_candidates = re.findall(digit_pattern, split_string)
                if horizontal_shift_pixels_candidates != []:
                    horizontal_shift_pixels_candidate = int(horizontal_shift_pixels_candidates[0])
            #If "v" is in the split string, but  not "h", then it means that this 
            #is the vertical shift expression.
            elif "v" in split_string.lower() and not "h" in split_string.lower():
                vertical_shift_pixels_candidates = re.findall(digit_pattern, split_string)
                if vertical_shift_pixels_candidates != []:
                    vertical_shift_pixels_candidate = int(vertical_shift_pixels_candidates[0])
        #If both values of the horizontal and vertical shift pixel candidates are 
        #not equal to zero, then they will be returned, along with the value of 
        #"file_name_without_extension".
        if not (horizontal_shift_pixels_candidate == 0 and vertical_shift_pixels_candidate == 0):
            return horizontal_shift_pixels_candidate, vertical_shift_pixels_candidate, file_name_without_extension
        #Otherwise a value of zero for each shift will be returned, 
        #along with the value of "file_name_without_extension".
        else:
            return 0, 0, file_name_without_extension
    #Otherwise a value of zero for each shift will be returned, 
    #along with the value of "file_name_without_extension".
    else:
        return 0, 0, file_name_without_extension

#The function "load_json_data()" will load the JSON data from file
#and store them in the "json_settings_dictionary", or initialize the
#dictionary based on the values of "json_default_settings_dictionary".
def load_json_data(json_settings_file_path_name): 

    json_default_settings_dictionary = {
            "_comment_1" : dpi_setting_comment_string,
            "Scan Resolution in DPI" : 200,
            
            "_comment_2" : page_rotation_angle_comment_string,
            "Page Rotation Angle" : -90.0,

            "_comment_3" : contrast_level_comment_string,
            "Contrast Level" : 5.0,

            "_comment_4" : brightness_level_comment_string,
            "Brightness Level" : 80,

            "_comment_5" : paper_color_grayscale_filter_threshold_comment_string,
            "Paper Color Grayscale Filter Threshold" : 245,

            "_comment_6" : black_pixel_threshold_percentage_comment_string,
            "Black Pixel Threshold Percentage" : 95,

            "_comment_7" : white_pixel_threshold_percentage_comment_string,
            "White Pixel Threshold Percentage" : 99,
            #The value of "white_pixel_threshold_percentage_slice"
            #needs to be lower than that of "white_pixel_threshold_percentage",
            #as there are fewer pixels to flatten in the slices, meaning that it 
            #is much more difficult to reach the 99% threshold for inclusion in 
            #the list of white pixels. By having a lower threshold around 80%,
            #it means that even if there are a few non-white pixels in the slice,
            #that flattened row or column will be detected as a white pixel.
            "_comment_8" : white_pixel_threshold_percentage_slice_comment_string,
            "White Pixel Threshold Percentage for Slices" : 80,

            "_comment_9" : punched_hole_diameter_percentage_threshold_comment_string,
            "Punched Hole Diameter Percentage Threshold" : 80,

            "_comment_10" : punched_hole_percent_overlap_threshold_comment_string,
            "Punched Hole Percentage Overlap Threshold" : 25,

            "_comment_11" : punched_hole_diameter_mm_comment_string,
            "Punched Hole Diameter in Millimeters" : 2.5,

            "_comment_12" : scoresheet_grid_height_mm_comment_string,
            "Scoresheet Grid Height in Millimeters" : 58.0,

            "_comment_13" : number_of_notes_comment_string,
            "Number of Notes" : 30,
    
            "_comment_14" : tempo_bpm_comment_string,
            "Tempo bpm" : 120,

            "_comment_15" : ticks_per_quarter_note_comment_string,
            "Ticks per Quarter Note" : 960,
            
            "_comment_16" : width_of_ten_smallest_measures_mm_comment_string,
            "Width of Ten Successive Smallest Measures in Millimeters" : 40.0,

            "_comment_17" : smallest_measure_duration_denominator_comment_string,
            "Smallest Measure Duration Denominator" : 16,

            "_comment_18" : time_signature_numerator_comment_string,
            "Time Signature Numerator" : 4,

            "_comment_19" : time_signature_denominator_comment_string,
            "Time Signature Denominator" : 4,

            "_comment_20" : leading_silence_milliseconds_comment_string,
            "Leading Silence Duration in Milliseconds" : 250,

            "_comment_21" : trailing_silence_milliseconds_comment_string,
            "Trailing Silence Duration in Milliseconds" : 500,

            "_comment_22" : vertical_shift_pixels_comment_string,
            "Vertical Shift in Pixels" : 0,

            "_comment_23" : horizontal_shift_pixels_comment_string,
            "Horizontal Shift in Pixels" : 0,

            "_comment_24" : midi_velocity_comment_string,
            "Midi Velocity" : 64,

            "_comment_25" : semitone_shift_comment_string,
            "Semitone Shift" : 0,

            "_comment_26" : midi_copyright_string_comment_string,
            "Midi Copyright Metadata String" : "",

            "_comment_27" : midi_comment_comment_string,
            "Midi Comment String" : ""
        }

    need_to_generate_new_json_file = False
    if os.path.isfile(json_settings_file_path_name):
        #A try-except statement is used in case
        #the JSON file is malformed or empty,
        #in which case the Boolean variable
        #"need_to_generate_new_json_file" will
        #be set to "True" and the "if" statement
        #below this one would run.
        try:
            #The "utf-8-sig" encoding handles files with or without a BOM automatically
            with open(json_settings_file_path_name, "r", encoding="utf-8-sig") as f:
                json_settings_dictionary = json.load(f)
        except json.JSONDecodeError:
            need_to_generate_new_json_file = True
    else:
        need_to_generate_new_json_file = True

    if need_to_generate_new_json_file:
        #A deep copy (since it contains a list of deleted pages) of 
        #"json_default_settings_dictionary" is made so as to avoid having
        #both "json_settings_dictionary" and "json_default_settings_dictionary"
        #pointing to the same address.
        json_settings_dictionary = copy.deepcopy(json_default_settings_dictionary)

        #Create a low-level file descriptor (used for atomic saves)
        #The two access flags "os.O_RDWR" and "os.O_CREAT" allow for the file to be 
        #read and written to and created if it doesn't already exist, respectively.
        file_descriptor = os.open(json_settings_file_path_name, os.O_RDWR | os.O_CREAT)
        with os.fdopen(file_descriptor, "w+", encoding="utf-8") as f:
            #Write the default values found in "json_settings_dictionary" in the empty JSON file, 
            #with four space indentations to make it more human-readable.
            json.dump(json_settings_dictionary, f, indent=4)
            #Ensure the data is flushed to hardware.
            f.flush()
            #"os.fsync(f.fileno())" is required to force the OS to physically commit
            #every bit of information to the hardware storage right now, preventing 
            #a situation where an empty file might be created if the computer crashed
            #before the OS finished waiting before committing the file to memory. 
            os.fsync(f.fileno())
    return json_default_settings_dictionary, json_settings_dictionary

#The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
#a menu action dictionary comprised of one character keys and values made up
#of a three-member tuple (action string, function, function arguments).
#The action strings ("value[0]") will be textwrapped and the modified
#dictionary will be returned.
def textwrap_action_strings_in_menu_action_dict(menu_action_dict):
    
    #The function "get_terminal_dimensions()" will return the number of columns 
    #and rows in the console, to allow to properly format the text and dividers.
    columns, lines = get_terminal_dimensions()

    for key, value in menu_action_dict.items():
        value[0] = textwrap.fill(value[0], columns)
    return menu_action_dict

#The function "quit_function()" will call
#"sys.exit()" with the exit code "1" meaning
#"success".
def quit_function():
    sys.exit(1)

#The function "back_to_main_menu_function()"
#will set the Boolean flags "is_in_submenu" and 
#"is_in_sub_submenu" to "False", which will break the submenu
#"while" loops and return to the main menu.
def back_to_main_menu_function(json_settings_dictionary):
    global is_in_submenu 
    global is_in_sub_submenu
    global is_in_sub_sub_submenu
    is_in_submenu = False
    is_in_sub_submenu = False
    is_in_sub_sub_submenu = False    
    return json_settings_dictionary

def back_to_submenu_function(json_settings_dictionary):
    global is_in_sub_submenu
    is_in_sub_submenu = False  
    return json_settings_dictionary

#The "invalid_menu_choice()" function will be called when the
#user enters invalid input in one of the functions called by
#the "run_menu()" function.
def invalid_menu_choice(json_settings_dictionary):
    input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The function "run_menu" will retrieve and call the function
#at the appropriate choice key in the "menu_actions_dict"
def run_menu(menu_actions_dict, json_settings_dictionary):

    for key, (label, _, _) in menu_actions_dict.items():
        print(f"[{key}] {label}")
    
    choice = input("\nSelect an option: ").strip().lower()

    #In case the user just pressed "Enter",
    #"json_settings_dictionary" will be returned
    #(no action, this will avoid an error message).
    if choice == "":
        return json_settings_dictionary
    
    #If you can successfully access the "menu_actions_dict" dictionary
    #with the value of "choice", you then have access to the tuple containing
    #(function label, function, args). Indexing the tuple at the position one
    #gives the function itself, and indexing it at the position 2 gives you the
    #arguments for that function as a list, which must be unpacked with the "*" operator. 
    nested_list = menu_actions_dict.get(choice, [None, invalid_menu_choice, (json_settings_dictionary,)]) 
    return nested_list[1](*nested_list[2])

#The "reset_to_default_setting()" function will reset the setting to its default value
#found while accessing the value of the "json_default_settings_dictionary" dictionary 
#with the key "setting_label_key".
def reset_to_default_setting(setting_label_key, json_settings_dictionary, 
json_default_settings_dictionary, json_settings_file_path_name):
    json_settings_dictionary[setting_label_key] = json_default_settings_dictionary[setting_label_key]
    #The function "atomic_save()" will create a temporary JSON file with the updated changes.
    #If the files is created successfully, then the files will be swapped. If a problem is 
    #encountered, the temp file will be unlinked and an error log will be reported.
    atomic_save(json_settings_dictionary, json_settings_file_path_name)   
    return json_settings_dictionary

#The "set_numeric_setting()" function will set the value of the setting found while accessing
#the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
#value ("setting_value"). 
def set_numeric_setting(setting_value, setting_label_key, json_settings_dictionary, 
json_settings_file_path_name):
    json_settings_dictionary[setting_label_key] = setting_value
    #The function "atomic_save()" will create a temporary JSON file with the updated changes.
    #If the files is created successfully, then the files will be swapped. If a problem is 
    #encountered, the temp file will be unlinked and an error log will be reported.
    atomic_save(json_settings_dictionary, json_settings_file_path_name)   
    return json_settings_dictionary

#The function "generate_midi_file()" will generate the 
#MIDI file and the annotated scoresheet JPEG files.
def generate_midi_file(json_settings_dictionary, json_default_settings_dictionary, cwd):
   
    #An empty line is printed on-screen in order to have the progress 
    #bar display one more line below the main menu.
    print("")
    
    dpi = json_settings_dictionary["Scan Resolution in DPI"]
    #Reset dpi to the default value of 200 if 
    #the JSON data is invalid or under 100.
    if not (is_valid_positive_int_or_float(dpi) and dpi >= 100):
        dpi = int(json_default_settings_dictionary["Scan Resolution in DPI"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        dpi = int(dpi)
    
    user_rotation_angle = json_settings_dictionary["Page Rotation Angle"]
    #As the rotation angle may be positive (counterclockwise) or negative 
    #(clockwise), then the validating function needs to allow for both of 
    #these, hence the use of "is_valid_int_or_float()".
    if not is_valid_int_or_float(user_rotation_angle):
       user_rotation_angle = json_default_settings_dictionary["Page Rotation Angle"]
    
    contrast_level = json_settings_dictionary["Contrast Level"]
    #If the value of "contrast_level" is not a valid 
    #positive integer or float, then it will be reset to its 
    #default value.
    if not is_valid_non_negative_int_or_float(contrast_level):
       contrast_level = float(json_default_settings_dictionary["Contrast Level"])
    #The "contrast_level" needs to be a float value for the contrast operation.
    else:
        contrast_level = float(contrast_level)
    
    color_image_brightness = json_settings_dictionary["Brightness Level"]
    #If the value of "color_image_brightness" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(color_image_brightness) and color_image_brightness <= 100):
       color_image_brightness = int(json_default_settings_dictionary["Brightness Level"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        color_image_brightness = int(color_image_brightness)
    
    paper_color_grayscale_filter_threshold = json_settings_dictionary["Paper Color Grayscale Filter Threshold"]
    #If the value of "paper_color_grayscale_filter_threshold" is not a valid 
    #positive integer or float between 0 and 255, inclusively, then it will be reset to 
    #its default value.
    if not (is_valid_non_negative_int_or_float(paper_color_grayscale_filter_threshold) and 
        paper_color_grayscale_filter_threshold <= 255):
       paper_color_grayscale_filter_threshold = int(json_default_settings_dictionary["Paper Color Grayscale Filter Threshold"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        paper_color_grayscale_filter_threshold = int(paper_color_grayscale_filter_threshold)

    black_pixel_threshold_percentage = json_settings_dictionary["Black Pixel Threshold Percentage"]
    #If the value of "black_pixel_threshold_percentage" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(black_pixel_threshold_percentage) and black_pixel_threshold_percentage <= 100):
       black_pixel_threshold_percentage = int(json_default_settings_dictionary["Black Pixel Threshold Percentage"])
    
    white_pixel_threshold_percentage = json_settings_dictionary["White Pixel Threshold Percentage"]
    #If the value of "white_pixel_threshold_percentage" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(white_pixel_threshold_percentage) and white_pixel_threshold_percentage <= 100):
       white_pixel_threshold_percentage = int(json_default_settings_dictionary["White Pixel Threshold Percentage"])
       
    #The value of "white_pixel_threshold_percentage_slice"
    #needs to be lower than that of "white_pixel_threshold_percentage",
    #as there are fewer pixels to flatten in the slices, meaning that it 
    #is much more difficult to reach the 99% threshold for inclusion in 
    #the list of white pixels. By having a lower threshold around 80%,
    #it means that even if there are a few non-white pixels in the slice,
    #that flattened row or column will be detected as a white pixel. 
    white_pixel_threshold_percentage_slice = json_settings_dictionary["White Pixel Threshold Percentage for Slices"]
    #If the value of "white_pixel_threshold_percentage_slice" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(white_pixel_threshold_percentage_slice) and white_pixel_threshold_percentage_slice <= 100):
       white_pixel_threshold_percentage_slice = int(json_default_settings_dictionary["White Pixel Threshold Percentage for Slices"])
    
    punched_hole_diameter_percentage_threshold = json_settings_dictionary["Punched Hole Diameter Percentage Threshold"]
    #If the value of "punched_hole_diameter_percentage_threshold" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(punched_hole_diameter_percentage_threshold) and punched_hole_diameter_percentage_threshold <= 100):
       punched_hole_diameter_percentage_threshold = int(json_default_settings_dictionary["Punched Hole Diameter Percentage Threshold"])
    
    punched_hole_percent_overlap_threshold = json_settings_dictionary["Punched Hole Percentage Overlap Threshold"]
    #If the value of "punched_hole_percent_overlap_threshold" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(punched_hole_percent_overlap_threshold) and punched_hole_percent_overlap_threshold <= 100):
       punched_hole_percent_overlap_threshold = int(json_default_settings_dictionary["Punched Hole Percentage Overlap Threshold"])
    
    punched_hole_diameter_mm = json_settings_dictionary["Punched Hole Diameter in Millimeters"]
    #If the value of "punched_hole_diameter_mm" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(punched_hole_diameter_mm):
       punched_hole_diameter_mm = json_default_settings_dictionary["Punched Hole Diameter in Millimeters"]
       
    scoresheet_grid_height_mm = json_settings_dictionary["Scoresheet Grid Height in Millimeters"]
    #If the value of "scoresheet_grid_height_mm" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(scoresheet_grid_height_mm):
       scoresheet_grid_height_mm = json_default_settings_dictionary["Scoresheet Grid Height in Millimeters"]
    
    width_of_ten_smallest_measures_mm = json_settings_dictionary["Width of Ten Successive Smallest Measures in Millimeters"]
    #If the value of "width_of_ten_smallest_measures_mm" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(width_of_ten_smallest_measures_mm):
       width_of_ten_smallest_measures_mm = json_default_settings_dictionary["Width of Ten Successive Smallest Measures in Millimeters"]        
    
    vertical_shift_pixels = json_settings_dictionary["Vertical Shift in Pixels"]
    #If the value of "vertical_shift_pixels" is not a valid 
    #integer or float, then it will be reset to its default value.
    if not is_valid_int_or_float(vertical_shift_pixels):
       vertical_shift_pixels = int(json_default_settings_dictionary["Vertical Shift in Pixels"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        vertical_shift_pixels = int(vertical_shift_pixels)

    horizontal_shift_pixels = json_settings_dictionary["Horizontal Shift in Pixels"]
    #If the value of "horizontal_shift_pixels" is not a valid 
    #integer or float, then it will be reset to its default value.
    if not is_valid_int_or_float(horizontal_shift_pixels):
       horizontal_shift_pixels = int(json_default_settings_dictionary["Horizontal Shift in Pixels"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        horizontal_shift_pixels = int(horizontal_shift_pixels)
    
    semitone_shift = json_settings_dictionary["Semitone Shift"]
    #If the value of "semitone_shift" is not a valid 
    #integer or float, then it will be reset to its default value.
    if not is_valid_int_or_float(semitone_shift):
       semitone_shift = int(json_default_settings_dictionary["Semitone Shift"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        semitone_shift = int(semitone_shift)

    leading_silence_milliseconds = json_settings_dictionary["Leading Silence Duration in Milliseconds"]
    #If the value of "leading_silence_milliseconds" is not a valid 
    #non-negative integer or float, then it will be reset to its default value.
    if not is_valid_non_negative_int_or_float(leading_silence_milliseconds):
       leading_silence_milliseconds = int(json_default_settings_dictionary["Leading Silence Duration in Milliseconds"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        leading_silence_milliseconds = int(leading_silence_milliseconds)
          
    trailing_silence_milliseconds = json_settings_dictionary["Trailing Silence Duration in Milliseconds"]
    #If the value of "trailing_silence_milliseconds" is not a valid 
    #non-negative integer or float, then it will be reset to its default value.
    if not is_valid_non_negative_int_or_float(trailing_silence_milliseconds):
       trailing_silence_milliseconds = int(json_default_settings_dictionary["Trailing Silence Duration in Milliseconds"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        trailing_silence_milliseconds = int(trailing_silence_milliseconds)
        
    number_of_notes = json_settings_dictionary["Number of Notes"]
    #If the value of "number_of_notes" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(number_of_notes):
       number_of_notes = int(json_default_settings_dictionary["Number of Notes"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        number_of_notes = int(number_of_notes)
    
    tempo_bpm = json_settings_dictionary["Tempo bpm"]
    #If the value of "tempo_bpm" is not a valid 
    #positive integer or float, then it will be reset 
    #to its default value.
    if not is_valid_positive_int_or_float(tempo_bpm):
       tempo_bpm = int(json_default_settings_dictionary["Tempo bpm"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       tempo_bpm = int(tempo_bpm)
        
    ticks_per_quarter_note = json_settings_dictionary["Ticks per Quarter Note"]
    #If the value of "ticks_per_quarter_note" is not a valid 
    #positive integer or float, then it will be reset 
    #to its default value.
    if not is_valid_positive_int_or_float(ticks_per_quarter_note):
       ticks_per_quarter_note = int(json_default_settings_dictionary["Ticks per Quarter Note"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       ticks_per_quarter_note = int(ticks_per_quarter_note)
     
    smallest_measure_duration_denominator = json_settings_dictionary["Smallest Measure Duration Denominator"]
    #If the value of "smallest_measure_duration_denominator" 
    #is not a valid positive integer or float, then it will 
    #be reset to its default value.
    if not is_valid_positive_int_or_float(smallest_measure_duration_denominator):
       smallest_measure_duration_denominator = int(json_default_settings_dictionary["Smallest Measure Duration Denominator"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       smallest_measure_duration_denominator = int(smallest_measure_duration_denominator)

    time_signature_numerator = json_settings_dictionary["Time Signature Numerator"]
    #If the value of "time_signature_numerator" 
    #is not a valid positive integer or float, then it will 
    #be reset to its default value.
    if not is_valid_positive_non_zero_int_or_float(time_signature_numerator):
       time_signature_numerator = int(json_default_settings_dictionary["Time Signature Numerator"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       time_signature_numerator = int(time_signature_numerator)       

    time_signature_denominator = json_settings_dictionary["Time Signature Denominator"]
    #If the value of "time_signature_denominator" 
    #is not a valid positive integer or float, then it will 
    #be reset to its default value.
    if not is_valid_positive_non_zero_int_or_float(time_signature_denominator):
       time_signature_denominator = int(json_default_settings_dictionary["Time Signature Denominator"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       time_signature_denominator = int(time_signature_denominator)
       
    midi_velocity = json_settings_dictionary["Midi Velocity"]
    #If the value of "midi_velocity" is not a valid positive integer 
    #or float equal to or below 127, then it will be reset to its 
    #default value.
    if not (is_valid_positive_non_zero_int_or_float(midi_velocity) and midi_velocity <= 127):
       midi_velocity = int(json_default_settings_dictionary["Midi Velocity"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       midi_velocity = int(midi_velocity)

    midi_copyright_string = json_settings_dictionary["Midi Copyright Metadata String"]
    midi_comment = json_settings_dictionary["Midi Comment String"]

    #Building a dictionary of notes and corresponding enharmonic notes (between octaves -1 and 9 inclusively)
    #and their numeric counterpart (based on the article: Mathematics 2019, 7, 19; doi:10.3390/math7010019)
    notes_midi_dict = {}
    for i in range(-1,10):
        notes_midi_dict["C" + str(i)] = 12 + 12*i
        notes_midi_dict["C#" + str(i)] = 13 + 12*i
        notes_midi_dict["D" + str(i)] = 14 + 12*i
        notes_midi_dict["D#" + str(i)] = 15 + 12*i
        notes_midi_dict["E" + str(i)] = 16 + 12*i
        notes_midi_dict["F" + str(i)] = 17 + 12*i
        notes_midi_dict["F#" + str(i)] = 18 + 12*i
        notes_midi_dict["G" + str(i)] = 19 + 12*i
        notes_midi_dict["G#" + str(i)] = 20 + 12*i
        notes_midi_dict["A" + str(i)] = 21 + 12*i
        notes_midi_dict["A#" + str(i)] = 22 + 12*i
        notes_midi_dict["B" + str(i)] = 23 + 12*i

    #Remove the notes above the Midi note number 127 from the dictionary generated above
    deleted_notes = ["B9", "A#9", "A9", "G#9"]
    for deleted_note in deleted_notes:
        del notes_midi_dict[deleted_note]

    list_notes_midi_dict_keys = list(notes_midi_dict.keys())
    list_notes_midi_dict_values = list(notes_midi_dict.values())
    #The dictionary of midi notes keys to notes in 
    #letter form values is generated.
    midi_notes_dict = {}
    for i in range(len(list_notes_midi_dict_keys)):
        midi_notes_dict[list_notes_midi_dict_values[i]] = list_notes_midi_dict_keys[i]

    #The notes printed out on the 30-note music box scoresheet are actually transposed.
    #Here is a list of the notes as they appear on the  scoresheet paper when the arrow 
    #points to the left, from top to bottom.
    #["E6", "D6", "C6", "B5", "A#5", "A5", "G#5", "G5", "F#5", "F5", "E5", "D#5", 
    # "D5", "C#5", "C5", "B4", "A#4", "A4", "G#4", "G4", "F#4", "F4", "E4", "D4", "C4", "B3", 
    # "A3", "G3", "D3", "C3"]

    #Here are the actual notes played by the 30-note Grand Illusions music box (F scale), 
    #when the arrow points to the left, from top to bottom, according to musicboxmaniacs.com:
    music_box_notes = ["A6", "G6", "F6", "E6", "D#6", "D6", "C#6", "C6", "B5", "A#5", "A5",
    "G#5", "G5", "F#5", "F5", "E5", "D#5", "D5", "C#5", "C5", "B4", "A#4", "A4", "G4", "F4", 
    "E4", "D4", "C4", "G3", "F3"]

    #The list "txt_file_names" will tally the file names 
    #of text files that are not named "license.txt" nor 
    #"readme.txt" nor "error log.txt" (case insensitive).
    txt_file_names = [file_name for file_name in os.listdir(cwd) if (file_name[-4:] == ".txt" and 
        file_name[:-4].lower() != "license" and file_name[:-4].lower() != "readme" and file_name[:-4].lower() != "error log")] 
    #If the list "txt_file_names" isn't empty, then it will be 
    #opened and each stripped and uppercased line will be appended 
    #to the list "music_box_notes_txt_file_path".  
    if txt_file_names != []:
        music_box_notes_txt_file_path = os.path.join(cwd, txt_file_names[0])
        if os.path.exists(music_box_notes_txt_file_path):
            with open(music_box_notes_txt_file_path, "r", encoding="utf-8") as f:
                music_box_note_candidates = f.readlines()
            music_box_note_candidates = [note.strip().upper() for note in music_box_note_candidates]
            #The counter "number_of_valid_notes", initialized to zero,
            #will be incremented every time a music box note candidate 
            #is found within the list of valid midi notes "list_notes_midi_dict_keys".
            #This number should be equal to the specified number of notes of the 
            #music box, which itself should be above zero, for the music box 
            #note candidates to overwrite the default notes.
            number_of_valid_notes = 0
            for note_string in music_box_note_candidates:
                if (note_string in list_notes_midi_dict_keys and 
                music_box_note_candidates.count(note_string) == 1):
                    number_of_valid_notes += 1     
            if number_of_notes > 0 and number_of_valid_notes == number_of_notes:
                music_box_notes = music_box_note_candidates
            elif number_of_notes != len(music_box_note_candidates):      
                #The function "get_terminal_dimensions()" will return the number of columns 
                #and rows in the console, to allow to properly format the text and dividers.
                columns, lines = get_terminal_dimensions()
                
                print("\n" + textwrap.fill(f"The number of notes included in the text file '{txt_file_names[0]}' ({len(music_box_note_candidates)}) does not match the 'Number of Notes' setting ({number_of_notes}). Please adjust accordinly.", width=columns) + "\n")
                input(press_any_key_string)
                return json_settings_dictionary 
            else:
                #The function "get_terminal_dimensions()" will return the number of columns 
                #and rows in the console, to allow to properly format the text and dividers.
                columns, lines = get_terminal_dimensions()
                print("\n" + textwrap.fill(f"Some incorrectly formatted notes were present in the text file '{txt_file_names[0]}' (please only include one note per line in the text file, without any punctuation marks). Here is an example of how the notes should be written (shown here in list format for brevity):", width=columns)+ "\n" + f"{music_box_notes}" + "\n")
                input(press_any_key_string)
                return json_settings_dictionary  

    #These variable depend on user input, so they are 
    #calculated upon starting to process the scans.
    punched_hole_diameter_pixels = punched_hole_diameter_mm / 25.4 * dpi
    scoresheet_grid_height_pixels = scoresheet_grid_height_mm / 25.4 * dpi
    width_of_one_smallest_measure_pixels = width_of_ten_smallest_measures_mm / 10 / 25.4 * dpi
    cell_pixel_height = scoresheet_grid_height_pixels / (number_of_notes - 1)
    #The number of ticks per smallest measure is calculated by multiplying 
    #the number of ticks per quarter notes by the quotient of four over the 
    #value of "smallest_measure_duration_denominator".
    ticks_per_smallest_measure = ticks_per_quarter_note * 4/smallest_measure_duration_denominator
    #The tempo in microseconds per quarter note is determined by calling the "bpm2tempo()"
    #mido method with the time signature numerator and denominator as a tuple additional 
    #argument.
    tempo_us_per_quarter_note = mido.bpm2tempo(tempo_bpm, time_signature = (time_signature_numerator, time_signature_denominator))    
    #The leading silence in ticks is calculated by multiplying the value of "leading_silence_milliseconds"
    #by one million in order to express the silence in microseconds. The result is then divided by 
    #the value of "tempo_us_per_quarter_note" to get the number of quarter notes, which is then 
    #multiplied by "ticks_per_quarter_note" to get the number of ticks.
    leading_silence_ticks = int(leading_silence_milliseconds * 1000 / tempo_us_per_quarter_note * ticks_per_quarter_note)
    trailing_silence_ticks = int(trailing_silence_milliseconds * 1000 / tempo_us_per_quarter_note * ticks_per_quarter_note)
               
    #Get a list of ".jpg" file names in the "Scans" subfolder of the working folder
    jpg_names = [file_name for file_name in sorted(os.listdir(os.path.join(cwd, scans_folder_name))) if file_name[-4:] == ".jpg"]

    if jpg_names != []:
        
        #The function "get_file_name_horizontal_vertical_shift_manual_override_strings()"
        #will return the horizontal and vertical shift manual override pixel values, that 
        #were extracted from the file name and the file name where these have been removed
        #(e.g., 5, -2, "track_01" for the file name "track_01+ (v=5, h=-2)"). Should there 
        #be no such manual override parenthesized expressions in "file_name_without_extension", 
        #then zero will be returned for the horizontal and vertical shift manual override pixel 
        #values, along with the original value of "file_name_without_extension".
        _, _, file_name_without_extension = (
            get_file_name_horizontal_vertical_shift_manual_override_strings(jpg_names[0]))
        
        #Any file number suffix following the required plus sign ("+") at the end of 
        #the scanned file names will be removed to give the string that will be used 
        #for the output, provided that the user hasn't included a CSV naming key.
        file_number_suffix_strings = (re.findall(r"\+[\d]+$", file_name_without_extension))
        if file_number_suffix_strings != []:
            file_name_without_extension = re.sub(file_number_suffix_strings[0], "", file_name_without_extension).strip()
        #If the first file didn't get a file number suffix (e.g., "track_1+.jpg"),
        #then the plus sign will be sliced out, if present at the last character.
        if file_name_without_extension[-1] == "+":
            file_name_without_extension = file_name_without_extension[:-1]

        #The file name will be used to name the output folder and the MIDI file.
        output_file_name = file_name_without_extension
        #The output folder path will be created if it doesn't already exist.
        output_folder_path = os.path.join(cwd, "Output Files", output_file_name)
        if not os.path.exists(output_folder_path):
            try:
                os.makedirs(output_folder_path)
            except:
                #The function "get_terminal_dimensions()" will return the number of columns 
                #and rows in the console, to allow to properly format the text and dividers.
                columns, lines = get_terminal_dimensions()
    
                print("\n" + textwrap.fill(f"Invalid folder name: {output_file_name}. Please enter a file name without special characters.", width=columns) + "\n")
                input(press_any_key_string)
                return json_settings_dictionary    
        
        #If this is the last note of a scoresheet, then the value of 
        #"x_pixel_width_after_last_note_of_previous_scoresheet" will be 
        #set to the difference between the right "x" coordinate of the 
        #scoresheet and the center "x" coordinate of this last note in 
        #order to include the silence after this last note to the silence
        #before the first note of the next scoresheet, as the two scoresheets 
        #were cut and are really contiguous.
        x_pixel_width_after_last_note_of_previous_scoresheet = 0           
        #The data for the "note_on" and "note_off" messages for each punched hole center coordinates 
        #in chronological order will be appended to the list "nested_list_of_note_on_off_midi_cumulative_ticks", 
        #which will be used when procedurally generating the MIDI file, as a tuple of three elements: 
        #("note_on", midi note, cumulative_ticks).
        nested_list_of_note_on_off_midi_cumulative_ticks = []
        cumulative_ticks = 0
        
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        previous_estimated_seconds = 0
        first_jpeg_index = 0
        last_jpeg_index = len(jpg_names)
        start_time = time.perf_counter()
        for i in range(len(jpg_names)):
            #The function "get_file_name_horizontal_vertical_shift_manual_override_strings()"
            #will return the horizontal and vertical shift manual override pixel values, that 
            #were extracted from the file name and the file name where these have been removed
            #(e.g., 5, -2, "track_01" for the file name "track_01+ (v=5, h=-2)"). Should there 
            #be no such manual override parenthesized expressions in "file_name_without_extension", 
            #then zero will be returned for the horizontal and vertical shift manual override pixel 
            #values, along with the original value of "file_name_without_extension".
            horizontal_shift_pixels_current_jpeg, vertical_shift_pixels_current_jpeg, file_name_without_extension = (
                get_file_name_horizontal_vertical_shift_manual_override_strings(jpg_names[i]))
            #If the value of both "horizontal_shift_pixels_current_jpeg" and 
            #"vertical_shift_pixels_current_jpeg" is equal to zero, then it 
            #means that the user has not specified a horizontal nor vertical 
            #shift override string in the file name (e.g., "Track 1+0001 (h=1,v-2).jpg").
            #Therefore, the values that was provided by the user in the CLI menu will be
            #used instead, with the default values of these both being zero pixels.
            if horizontal_shift_pixels_current_jpeg == 0 and vertical_shift_pixels_current_jpeg == 0:
                horizontal_shift_pixels_current_jpeg = horizontal_shift_pixels
                vertical_shift_pixels_current_jpeg = vertical_shift_pixels
            
            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            undetectable_scoresheet_error_string = "\n" + textwrap.fill(f"Please adjust the value of the 'Black Pixel Threshold Percentage' to a higher value (around 95% should be good), as no columns or rows of pixels in your image \"{jpg_names[i]}\" fell below your current threshold of {json_settings_dictionary['Black Pixel Threshold Percentage']}%.", width=columns) + "\n"
            undetectable_notes_error_string = "\n" + textwrap.fill(f"Please decrease the value of the white pixel percentage threshold (current value: {white_pixel_threshold_percentage}), as no horizontal spaces between punched holes were detected in your image \"{jpg_names[i]}\".", width=columns) + "\n"
            
            #The color version of the image will be used to save the final rotated image
            #with the extrapolated notes written on it.
            color_img = cv2.imread(os.path.join(cwd, scans_folder_name, jpg_names[i]), cv2.IMREAD_COLOR_RGB)
            color_img = cv2.flip(src=color_img, dst=color_img, flipCode=1)
            color_img = cv2.convertScaleAbs(color_img, alpha=1, beta=color_image_brightness)
            
            #The grayscale version of the image will be used to calculate the rotation angles 
            #and to perform the NumPy calculations to extrapolate the notes corresponding to 
            #the punched holes.
            img = cv2.imread(os.path.join(cwd, scans_folder_name, jpg_names[i]), cv2.IMREAD_GRAYSCALE)
            img = cv2.flip(src=img, dst=img, flipCode=1)
            
            #The formula for the contrast adjustment was taken from the "Pil.Image.blend()"
            #Pillow method that is used when adjusting the contrast with Pillow's ImageEnhance 
            #module ("Pil.ImageEnhance.Contrast()").
            if contrast_level != 1 and contrast_level >= 0:
                initial_mean_pixel_value = np.mean(img)
                img = img * contrast_level + initial_mean_pixel_value * (1.0 - contrast_level)

            #filter the image to make pixels of the paper color pure white (255),
            #as they are above the threshold "paper_color_grayscale_filter_threshold",
            #with any remaining pixels being black (0)
            img = np.where(img > paper_color_grayscale_filter_threshold, 255, 0)
            
            #In order to get the horizontal and vertical projection profiles,
            #non-white pixels
            rows, cols = img.shape
            
            #The function "rotate_image()" will rotate the "img"
            #numpy array using the "getRotationMatrix2D()" and 
            #"warpAffine()" OpenCV methods. It will only be called 
            #if the rotation angle doesn't result in no rotation
            #(a multiple of 360 degrees, hence the "angle%360 != 0).
            if user_rotation_angle%360 != 0: 
                img, color_img, rows, cols = rotate_image(img.astype(np.uint8), color_img.astype(np.uint8), rows, cols, user_rotation_angle)
             
            #The function "get_horizontal_projection_profile()" will get the horizontal projection 
            #profile by first filtering the "img" array with the "np.where()" method, such that 
            #white pixels have a value of zero and non-white pixels have a value of one. This 
            #will allow to get the horizontal projection profile by adding up all the rows for 
            #each column, thus generating a 1D horizontal array. The left and right edges of 
            #the score sheet will be detected, as they will be the first and last elements 
            #of the horizontal projection profile where the pixels will not be almost exclusively 
            #black.
            (img_filtered_for_flattening, 
            horizontal_projection_profile, 
            non_black_pixels_horizontal_projection_profile, 
            black_pixels_horizontal_projection_profile, 
            left_x_scoresheet, 
            right_x_scoresheet,
            scoresheet_width) = get_horizontal_projection_profile(img, black_pixel_threshold_percentage, 
                rows, undetectable_scoresheet_error_string)
            
            #The following code will detect any tilt in the scoresheet scans and correct it by rotating the image accordingly.
            
            #The vertical projection profile for the first and last 25% of the scoresheet's width 
            #will allow to determine the top "y" coordinate of the scoresheet at these locations,
            #which will in turn allow to determine the tilt angle of the score sheet.
            
            #To get the slice of "img_filtered_for_flattening" corresponding to 
            #the first 25% of the scoresheet's width, all "y" coordinates need to 
            #be included (":,") and the range of the "x" coordinates corresponds to 
            #"left_x_scoresheet: round(left_x_scoresheet + 0.25*scoresheet_width)"
            first_25_width_percent_vertical_projection_profile = np.sum(img_filtered_for_flattening[:, left_x_scoresheet: 
                round(left_x_scoresheet + 0.25*scoresheet_width)], axis=1)
            #A row of pixels above or below the scoresheet would be comprised of 
            #entirely black pixels, and so the sum of these pixels in 
            #"non_black_pixels_first_25_width_percent_vertical_projection_profile"
            #would be almost equal to the width of 25% of the scoresheet width, 
            #which is the width of the slice used when setting the value of 
            #"first_25_width_percent_vertical_projection_profile". Conversely, 
            #any rows making up the score sheet contain some white pixels and 
            #the sum would be much lower than 25% of the scoresheet width.
            non_black_pixels_first_25_width_percent_vertical_projection_profile = ( 
                np.where(first_25_width_percent_vertical_projection_profile < (black_pixel_threshold_percentage/100)*0.25*scoresheet_width)[0])
            #A similar approach is taken for the last 25% of the scoresheet's width.
            last_25_width_percent_vertical_projection_profile = np.sum(img_filtered_for_flattening[:, round(right_x_scoresheet - 
                0.25*scoresheet_width): right_x_scoresheet], axis=1)
            
            non_black_pixels_last_25_width_percent_vertical_projection_profile = (
                np.where(last_25_width_percent_vertical_projection_profile < (black_pixel_threshold_percentage/100)*0.25*scoresheet_width)[0])
            
            #If some non-black pixels were detected in both the first and last 25% of the 
            #scoresheet array slices, then the top "y" coordinate at both these locations
            #is determined by indexing the vertical projection profile arrays at the first 
            #index.
            if (non_black_pixels_first_25_width_percent_vertical_projection_profile.size != 0 and 
            non_black_pixels_last_25_width_percent_vertical_projection_profile.size != 0):
                first_25_width_percent_top_y = non_black_pixels_first_25_width_percent_vertical_projection_profile[0]
                last_25_width_percent_top_y = non_black_pixels_last_25_width_percent_vertical_projection_profile[0]
                
                #If the two top "y" coordinates differ, then the tilt angle will 
                #be calculated by first determining the sine (the difference 
                #between the two top "y" coordinates ("delta_y"), divided by the 
                #scoresheet width. The smallest angle of the right angle triangle, 
                #where the hypothenuse corresponds to the top side of the 
                #scoresheet and the opposite side corresponds to the "delta_y",
                #is obtained by the "np.arcsin()" method of the sine result.
                #As the "cv2.getRotationMatrix2D()" method requires an angle in 
                #degrees, the "np.degrees()" method is used to convert the 
                #radians angle to degrees.
                if first_25_width_percent_top_y != last_25_width_percent_top_y:
                    
                    delta_y = last_25_width_percent_top_y - first_25_width_percent_top_y
                    sine = abs(delta_y) / scoresheet_width
                    rotation_angle = np.degrees(np.arcsin(sine))
                    
                    if delta_y > 0:
                        rotation_angle = - rotation_angle
                    
                    #The function "rotate_image()" will rotate the "img"
                    #numpy array using the "getRotationMatrix2D()" and 
                    #"warpAffine()" OpenCV methods. It will only be called 
                    #if the rotation angle doesn't result in no rotation
                    #(a multiple of 360 degrees, hence the "angle%360 != 0).
                    if rotation_angle%360 != 0: 
                        img, color_img, rows, cols = rotate_image(img.astype(np.uint8), color_img.astype(np.uint8), rows, cols, rotation_angle)
                        
                        #As the image was rotated, some variables need to be updated.
                        
                        #The function "get_horizontal_projection_profile()" will get the horizontal projection 
                        #profile by first filtering the "img" array with the "np.where()" method, such that 
                        #white pixels have a value of zero and non-white pixels have a value of one. This 
                        #will allow to get the horizontal projection profile by adding up all the rows for 
                        #each column, thus generating a 1D horizontal array. The left and right edges of 
                        #the score sheet will be detected, as they will be the first and last elements 
                        #of the horizontal projection profile where the pixels will not be almost exclusively 
                        #black.
                        (img_filtered_for_flattening, 
                        horizontal_projection_profile, 
                        non_black_pixels_horizontal_projection_profile, 
                        black_pixels_horizontal_projection_profile, 
                        left_x_scoresheet, 
                        right_x_scoresheet,
                        scoresheet_width) = get_horizontal_projection_profile(img, black_pixel_threshold_percentage, 
                            rows, undetectable_scoresheet_error_string)
            
            #Add up all the columns for each row to get the vertical projection profile
            #("np.sum" along the "x" axis at index one).
            vertical_projection_profile = np.sum(img_filtered_for_flattening, axis=1)
            
            #A row of pixels above or below the scoresheet would be comprised of 
            #entirely black pixels, and so the sum of these pixels in "vertical_projection_profile"
            #would be almost equal to the width of the rotated image ("cols"). Conversely, any rows making 
            #up the score sheet contain some white pixels and the sum would be much lower than "cols".
            non_black_pixels_vertical_projection_profile = np.where(vertical_projection_profile < (black_pixel_threshold_percentage/100)*cols)[0]
            black_pixels_vertical_projection_profile = np.where(vertical_projection_profile >= (black_pixel_threshold_percentage/100)*cols)[0]
            
            #If a scoresheet is visible in the form of some non-black pixels
            #then the "if" statement below will run. If that is not the case,
            #then the user has probably set a too stringent value for the 
            #"paper_color_grayscale_filter_threshold" (too high, meaning that 
            #no pixels were lighter than the threshold and consequently all 
            #pixels were set to black).
            if non_black_pixels_vertical_projection_profile.size != 0:
            
                #The top "y" coordinate of the scoresheet corresponds to that 
                #of the first pixel in "non_black_pixels_vertical_projection_profile",
                #as it is the first row of pixels that falls under the threshold for inclusion 
                #in the black pixels vertical projection profile, meaning that it contains 
                #a significan amount of non-black pixels denoting the presence of the scoresheet.
                top_y_scoresheet = non_black_pixels_vertical_projection_profile[0]
                #Similarly, the bottom "y" coordinate of the scoresheet corresponds to 
                #that of the last pixel in "non_black_pixels_vertical_projection_profile",
                #as it is the last row of pixels that falls under the threshold for inclusion 
                #in the black pixels vertical projection profile, meaning that it contains 
                #a significan amount of non-black pixels denoting the presence of the scoresheet.
                bottom_y_scoresheet = non_black_pixels_vertical_projection_profile[-1]
                #The scoresheet pixel height corresponds to the difference between 
                #the bottom and top "y" coordinates of the scoresheet.
                scoresheet_height = bottom_y_scoresheet - top_y_scoresheet
                
                #The top "y" coordinate of the first music box scoresheet note 
                #horizontal gridline is calculated by vertically centering the 
                #grid height along the scoresheet height by halving the difference 
                #between the scoresheet height and the grid height.
                y_first_note = (scoresheet_height - scoresheet_grid_height_pixels)/2
                #The dictionary of "float" note horizontal gridline "y" coordinate keys to 
                #values made up of a list of the notes in letter form and corresponding midi 
                #notes "note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict"
                #will allow to tally up the extrapolated notes from the detected punched 
                #hole center "y" coordinates. 
                note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict = {}
                for j in range(len(music_box_notes)):
                    note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[y_first_note + j * cell_pixel_height] = (
                        [music_box_notes[j], notes_midi_dict[music_box_notes[j]]])
                #The list of of "float" note horizontal gridline "y" coordinates
                #"list_of_music_box_note_center_y_coordinates" will be used to draw 
                #the music box gridlines on the scoresheet and a copy of the list 
                #will be used to extrapolate which note corresponds to the center 
                #"y" coordinate of each punched hole. To to this, the center "y"
                #coordinate will be appended to the list copy, which will then 
                #be sorted, and the index of the newly added note will be obtained 
                #with the "index()" method. Then the neighboring note that has the 
                #nearest "y" coordinate will be selected.
                list_of_music_box_note_center_y_coordinates = (
                    list(note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict.keys()))
                
                for j in range(len(list_of_music_box_note_center_y_coordinates)):
                    music_box_note_line_y_coordinate = list_of_music_box_note_center_y_coordinates[j]
                    #The music box note lines corresponding to "C" notes (excluding "C#") will be 
                    #drawn in green to facilitate reading of the annotated JPEG scoresheet files,
                    #provided that the semitone shift is a multiple of 12 semitones (the equivalent 
                    #of an octave, meaning that the notes were either not shifted ("semitone_shift == 0"), 
                    #or they were shifted by whole octaves (-12 or 12, for example).
                    if (semitone_shift%12 == 0 and 
                    note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[music_box_note_line_y_coordinate][0][0] == "C" and 
                    "#" not in note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[music_box_note_line_y_coordinate][0]):
                        music_box_note_line_color = (51, 136, 34)
                    else:
                        music_box_note_line_color = (187, 187, 187)
                    
                    #Some gray horizontal lines spanning 
                    #the entire canvas are drawn for each 
                    #music box note in the list
                    #"list_of_music_box_note_center_y_coordinates". 
                    cv2.line(
                        img=color_img,
                        pt1=(0, int(top_y_scoresheet + music_box_note_line_y_coordinate)), 
                        pt2=(cols, int(top_y_scoresheet + music_box_note_line_y_coordinate)), 
                        color=music_box_note_line_color,                    
                        thickness=1,
                        lineType=cv2.LINE_AA)
               
            #If a scoresheet is visible in the form of some non-black pixels
            #then the "if" statement below will run. If that is not the case,
            #then the user has probably set a too stringent value for the 
            #"paper_color_grayscale_filter_threshold" (too high, meaning that 
            #no pixels were lighter than the threshold and consequently all 
            #pixels were set to black).
            else:
                print(undetectable_scoresheet_error_string)
                input(press_any_key_string)
                sys.exit(1)
            
            #The slice coordinates of the scoresheet are stored 
            #in the variable "scoresheet_img_slice" through the
            #use of the Numpy "np.s_" indexing routine.
            scoresheet_img_slice = np.s_[
                top_y_scoresheet:bottom_y_scoresheet, 
                left_x_scoresheet:right_x_scoresheet
                ]
            
            #The filtered "img" array where white pixels (grayscale value of 255)
            #correspond to ones and non-white pixels are set to zero will allow to 
            #detect columns of punched holes by screening the scoresheet horizontal 
            #projection profile derived from it to retain pixels that fall under the 
            #threshold for columns of white pixels, meaning that these columns contain 
            #some punched holes.
            img_filtered_for_flattening_white_is_one = np.where(img == 255, 1, 0)
            
            #Add up all the rows for each column within the scoresheet area to get the 
            #horizontal projection profile ("np.sum" along the "y" axis at index zero).
            scoresheet_horizontal_projection_profile = np.sum(img_filtered_for_flattening_white_is_one[scoresheet_img_slice], axis=0)
            
            #As only the rows contained within the scoresheet area are flattened to make up 
            #the "scoresheet_horizontal_projection_profile", the threshold below which notes 
            #are considered to be present is calculated by multiplying the height of the 
            #scoresheet by the white pixel threshold percentage.
            non_white_pixels_horizontal_projection_profile = np.where(scoresheet_horizontal_projection_profile < (white_pixel_threshold_percentage/100)*scoresheet_height)[0]
            #If the threshold is met or exceeded, then the column corresponding to the flattened rows
            #at this "x" coordinate will be included in "white_pixels_horizontal_projection_profile"
            #instead.
            white_pixels_horizontal_projection_profile = np.where(scoresheet_horizontal_projection_profile >= (white_pixel_threshold_percentage/100)*scoresheet_height)[0]
            
            #If some notes were detected on the scoresheet in the form of 
            #some non-white pixels, then the "if" statement below will run. 
            #If that is not the case, then the user likely needs decrease 
            #the value of the white pixel percentage threshold
            #("white_pixel_threshold_percentage), as no horizontal 
            #spaces between punched holes were detected in the image.
            if non_white_pixels_horizontal_projection_profile.size != 0:
                
                #The index "non_white_pixels_horizontal_projection_profile_index"
                #will keep track of which element of the "non_white_pixels_horizontal_projection_profile"
                #list is being iterated over. This index will be incremented every time the leftmost or  
                #rightmost "x" coordinates of a punched hole are being screened over, as these need to 
                #be included in the nested list of leftmost and rightmost "x" coordinates for the 
                #punched holes "nested_list_of_left_right_x_of_punched_holes". 
                non_white_pixels_horizontal_projection_profile_index = 0
                len_non_white_pixels_horizontal_projection_profile = non_white_pixels_horizontal_projection_profile.size
                nested_list_of_left_right_x_of_punched_holes = []

                #The Boolean variable "left_x_punched_hole_reached", initialized to "False",
                #will be set to "True" upon reaching the leftmost coordinate of a punched hole,
                #("left_x_candidate") and will be reset to "False" once more upon reaching its 
                #rightmost coordinate ("right_x_candidate").
                #This will allow the "if" statement below to only run if the value of 
                #"left_x_candidate" for the leftmost coordinate of the punched hole 
                #hasn't yet been updated, and the first "elif" statement below to 
                #only run once the leftmost coordinate for the punched hole has 
                #been stored in that variable, during a subsequent iteration of 
                #the "for" loop.
                left_x_punched_hole_reached = False            
                left_x_candidate = 0
                right_x_candidate = 0
                #The "for" loop below iterates over all of the column indices of the image 
                #in order to store a punched hole's leftmost "x" coordinate candidate
                #in the "left_x_candidate" variable in the "if" statement, and the 
                #rightmost "x" coordinate candidate in the "right_x_candidate"
                #variable in the first "elif" statement.
                for j in range(cols):
                    #In order for the "if" statement to run and set the
                    #punched hole's leftmost "x" coordinate candidate
                    #in the "left_x_candidate" variable, the counter 
                    #iterating over all of the "non_white_pixels_horizontal_projection_profile"
                    #elements must have a value below that of the last element of that list, 
                    #in order to avoid indexing errors, the current value of the Boolean 
                    #variable "left_x_punched_hole_reached" must be set to "False" to avoid 
                    #seting the leftmost coordinate more than once for any given punched 
                    #hole, and the corrected coordinate of the element at the index  
                    #"non_white_pixels_horizontal_projection_profile_index" of the 
                    #"non_white_pixels_horizontal_projection_profile" list (calculated 
                    #by adding the value of "left_x_scoresheet", as this list was obtained 
                    #from the slicing of the "img" NumPy array in order to only select the 
                    #pixels of the scoresheet) needs to be equal to the column index "i"
                    #of the "img" array to ensure that the same pixel is under consideration.
                    if (non_white_pixels_horizontal_projection_profile_index < 
                    len_non_white_pixels_horizontal_projection_profile and 
                    non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 
                    left_x_scoresheet == j and not left_x_punched_hole_reached):
                        #The condition "not (j == cols - 1 or 
                        #non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1 in
                        #white_pixels_horizontal_projection_profile" prevents the very last pixel from being detected as a punched 
                        #hole note, and also any black pixels that are immediately followed by a white pixel, as these are merely 
                        #artifacts. In any case, we will increment the value of "non_white_pixels_horizontal_projection_profile_index"
                        #to move on to the next index in the next iteration of the "for" loop.
                        if not (j == cols - 1 or 
                        non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1 in
                        white_pixels_horizontal_projection_profile):
                            left_x_punched_hole_reached = True
                            left_x_candidate = j
                        
                        non_white_pixels_horizontal_projection_profile_index += 1
                    #In order for the "elif" statement below to run, the Boolean variable 
                    #"left_x_punched_hole_reached" must already be set to "True", as we will be detecting 
                    #the rightmost coordinate of the punched hole. The next pixel at the corrected index 
                    #"non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1" 
                    #must be present in "white_pixels_horizontal_projection_profile", as this would indicate that this is 
                    #the last pixel of the punched hole before reaching a column found in the white pixels horizontal profile.
                    elif (non_white_pixels_horizontal_projection_profile_index < 
                    len_non_white_pixels_horizontal_projection_profile and
                    non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 
                    left_x_scoresheet == j and 
                    left_x_punched_hole_reached and (j == cols - 1 or 
                    non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1 in
                    white_pixels_horizontal_projection_profile)):
                        right_x_candidate = j
                        #The Boolean variable "left_x_punched_hole_reached" is 
                        #reset to "False" in order to allow the code to find the 
                        #next punched hole.
                        left_x_punched_hole_reached = False
                        non_white_pixels_horizontal_projection_profile_index += 1
                        if (right_x_candidate - left_x_candidate >= 
                        punched_hole_diameter_pixels * (punched_hole_diameter_percentage_threshold/100)):
                            nested_list_of_left_right_x_of_punched_holes.append([left_x_candidate, right_x_candidate])
                    #If the Boolean variable "left_x_punched_hole_reached" is set to "True",
                    #yet the "elif" statement above didn't run, then it means that we are not 
                    #done traversing the punched hole, and therefore the value of the index 
                    #"non_white_pixels_horizontal_projection_profile_index" needs to be 
                    #incremented.
                    elif left_x_punched_hole_reached:
                        non_white_pixels_horizontal_projection_profile_index += 1
                
                #The nested list "nested_list_of_center_x_y_coordinates_of_punched_holes"
                #will contain lists of center "x, y" coordinates for each punched hole of 
                #the scoresheet and will be sorted along "x" coordinates in ascending order 
                #before extrapolating the notes and ticks corresponding to each punched hole.
                nested_list_of_center_x_y_coordinates_of_punched_holes = []
                #Each slice of the scoresheet corresponding to a column of punched holes will 
                #be used to detect the center "y" coordinates of the punched holes, and then 
                #the center "x" coordinates of each detected punched hole, as these may vary 
                #slightly within a given slice (for example if two notes were so close together 
                #in time that they were detected in the same slice).
                for sublist in nested_list_of_left_right_x_of_punched_holes:
                    
                    sliced_img_filtered_array_for_flattening = img_filtered_for_flattening_white_is_one[top_y_scoresheet:bottom_y_scoresheet, sublist[0]:sublist[1]]
                    width_of_slice = sublist[1] - sublist[0]
                    
                    #The vertical profile of the sliced portion of the filtered array where 
                    #white pixels have the value of one and non-white have a value of zero 
                    #will be used to select pixels that fall short of the threshold for 
                    #rows comprised of white pixels, indicating that these rows contain 
                    #punched holes.
                    sliced_img_filtered_array_vertical_profile = np.sum(sliced_img_filtered_array_for_flattening, axis=1)
                    
                    #As only the columns contained within "sublist[0]" and "sublist[1]" of the 
                    #scoresheet area are flattened to make up the "scoresheet_horizontal_projection_profile", 
                    #the threshold below which notes are considered to be present is calculated by multiplying 
                    #the width of the slice ("width_of_slice") by the white pixel threshold percentage.
                    non_white_pixels_vertical_projection_profile = np.where(sliced_img_filtered_array_vertical_profile < (white_pixel_threshold_percentage_slice/100)*width_of_slice)[0]
                                    
                    #If the threshold is met or exceeded, then the column corresponding to the flattened rows
                    #at this "y" coordinate will be included in "white_pixels_vertical_projection_profile"
                    #instead.
                    white_pixels_vertical_projection_profile = np.where(sliced_img_filtered_array_vertical_profile >= (white_pixel_threshold_percentage_slice/100)*width_of_slice)[0]
                    
                    #The index "non_white_pixels_vertical_projection_profile_index"
                    #will keep track of which element of the "non_white_pixels_vertical_projection_profile"
                    #list is being iterated over. This index will be incremented every time the highest or  
                    #lowest "y" coordinates of a punched hole are being screened over, as these need to 
                    #be used in the calculation of the center "y" coordinates for the punched holes, 
                    #which will be appended to the list "list_of_center_y_coordinates".
                    non_white_pixels_vertical_projection_profile_index = 0
                    len_non_white_pixels_vertical_projection_profile = non_white_pixels_vertical_projection_profile.size               

                    #The Boolean variable "top_y_punched_hole_reached", initialized to "False",
                    #will be set to "True" upon reaching the highest coordinate of a punched hole,
                    #("top_y_candidate") and will be reset to "False" once more upon reaching its 
                    #lowest coordinate ("bottom_y_candidate").
                    #This will allow the "if" statement below to only run if the value of 
                    #"top_y_candidate" for the highest coordinate of the punched hole 
                    #hasn't yet been updated, and the first "elif" statement below to 
                    #only run once the highest coordinate for the punched hole has 
                    #been stored in that variable, during a subsequent iteration of 
                    #the "for" loop.
                    top_y_punched_hole_reached = False            
                    top_y_candidate = 0
                    bottom_y_candidate = 0
                    #The list of center "y" coordinates of successive notes, initialized as an empty
                    #list, will be set to the center "y" coordinate of the first successive note from 
                    #the top, calculated by adding half the punched hole pixel diameter to the top "y"
                    #coordinate of the overlapping successive notes. Then, for each successive note in 
                    #excess of one, the cell pixel height will be added to the previously processed 
                    #successive note punched hole at the last element of the list.
                    list_of_center_y_coordinates_of_successive_notes = []
                    #The list of center "y" coordinates of detected punched holes,
                    #initialized to an empty list, will be populated with each of 
                    #the individual punched holes' center "y" coordinates.
                    list_of_center_y_coordinates = []
                    #The "for" loop below iterates over all of the row indices of the 
                    #scoresheet between "top_y_scoresheet" and "bottom_y_scoresheet"
                    #in order to store a punched hole's highest "y" coordinate candidate
                    #in the "top_y_candidate" variable in the "if" statement, and the 
                    #rightmost "x" coordinate candidate in the "right_x_candidate"
                    #variable in the first "elif" statement.
                    for j in range(scoresheet_height):
                        #The "if" statement below will run if either no successive notes that span contiguous 
                        #"y" pixels were detected (the list "list_of_center_y_coordinates_of_successive_notes" 
                        #is empty, or the current "y" coordinate "i" under investigation at the current 
                        #iteration of the "for" loop is greater than the scoresheet note right below 
                        #that of the last successive note (hence the addition of "cell_pixel_height" 
                        #to move from the central "y" coordinate of the last successive note to 
                        #the next note down.
                        if (list_of_center_y_coordinates_of_successive_notes == [] or 
                            j > list_of_center_y_coordinates_of_successive_notes[-1] + cell_pixel_height):
                            #If the list "list_of_center_y_coordinates_of_successive_notes" isn't 
                            #empty and yet the outer "if" statement is running, then it means that 
                            #all of the successive notes in the list have been fully processed 
                            #and therefore it can be reinitialized to an empty list.
                            if list_of_center_y_coordinates_of_successive_notes != []:
                                list_of_center_y_coordinates_of_successive_notes = []
                            #In order for the "if" statement to run and set the
                            #punched hole's leftmost "x" coordinate candidate
                            #in the "top_y_candidate" variable, the counter 
                            #iterating over all of the "non_white_pixels_vertical_projection_profile"
                            #elements must have a value below that of the last element of that list, 
                            #in order to avoid indexing errors, the current value of the Boolean 
                            #variable "left_x_punched_hole_reached" must be set to "False" to avoid 
                            #seting the leftmost coordinate more than once for any given punched 
                            #hole, and the corrected coordinate of the element at the index  
                            #"non_white_pixels_vertical_projection_profile_index" of the 
                            #"non_white_pixels_vertical_projection_profile" list (calculated 
                            #by adding the value of "left_x_scoresheet", as this list was obtained 
                            #from the slicing of the "img" NumPy array in order to only select the 
                            #pixels of the scoresheet) needs to be equal to the column index "i"
                            #of the "img" array to ensure that the same pixel is under consideration.
                            if (non_white_pixels_vertical_projection_profile_index < 
                            len_non_white_pixels_vertical_projection_profile and 
                            non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] == j and 
                            not top_y_punched_hole_reached):
                                #The condition "not (i == scoresheet_height - 1 or 
                                #non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1 in
                                #white_pixels_vertical_projection_profile" prevents the very last pixel from being detected as a punched 
                                #hole note, and also any black pixels that are immediately followed by a white pixel, as these are merely 
                                #artifacts. In any case, we will increment the value of "non_white_pixels_vertical_projection_profile_index"
                                #to move on to the next index in the next iteration of the "for" loop.
                                if not (j == scoresheet_height - 1 or 
                                non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1 in
                                white_pixels_vertical_projection_profile):
                                    top_y_punched_hole_reached = True
                                    top_y_candidate = j
                                
                                #The index "non_white_pixels_vertical_projection_profile_index"
                                #will keep track of which element of the "non_white_pixels_vertical_projection_profile"
                                #list is being iterated over. This index will be incremented every time the highest or  
                                #lowest "y" coordinates of a punched hole are being screened over, as these need to 
                                #be used in the calculation of the center "y" coordinates for the punched holes, 
                                #which will be appended to the list "list_of_center_y_coordinates".
                                non_white_pixels_vertical_projection_profile_index += 1
                                
                            #In order for the "elif" statement below to run, the Boolean variable 
                            #"top_y_punched_hole_reached" must already be set to "True", as we will be 
                            #detecting the lowest coordinate of the punched hole. The next pixel at the index 
                            #"non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1" 
                            #must be present in "white_pixels_vertical_projection_profile", as this would indicate that this is 
                            #the last pixel of the punched hole before reaching a row found in the white pixels vertical profile.
                            elif (non_white_pixels_vertical_projection_profile_index < 
                            len_non_white_pixels_vertical_projection_profile and
                            non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] == j and 
                            top_y_punched_hole_reached and (j == scoresheet_height - 1 or 
                            non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1 in
                            white_pixels_vertical_projection_profile)):
                                bottom_y_candidate = j
                                #The Boolean variable "top_y_punched_hole_reached" is 
                                #reset to "False" in order to allow the code to find the 
                                #next punched hole.
                                top_y_punched_hole_reached = False
                                
                                #The index "non_white_pixels_vertical_projection_profile_index"
                                #will keep track of which element of the "non_white_pixels_vertical_projection_profile"
                                #list is being iterated over. This index will be incremented every time the highest or  
                                #lowest "y" coordinates of a punched hole are being screened over, as these need to 
                                #be used in the calculation of the center "y" coordinates for the punched holes, 
                                #which will be appended to the list "list_of_center_y_coordinates". 
                                non_white_pixels_vertical_projection_profile_index += 1
                                
                                #The height of the punched hole candidate is calculated by subtracting 
                                #the detected top "y" coordinate from the bottom "y" coordinate, and 
                                #if it exceeds the threshold of the punched hole diameter in pixels 
                                #times the value of "punched_hole_diameter_percentage_threshold",
                                #then it is deemed to be a punched hole and not a smaller artifact.
                                height_of_punched_hole_candidate = bottom_y_candidate - top_y_candidate
                                if height_of_punched_hole_candidate >= punched_hole_diameter_pixels * (punched_hole_diameter_percentage_threshold/100):
                                    
                                    #If the height of the punched hole candidate exceeds the threshold for two or more successive notes, 
                                    #calculated by multiplying the value of one plus the "punched_hole_percent_overlap_threshold" by 
                                    #the punched hole diameter in pixels, then the following "if" statement will split these overlapping 
                                    #successive notes apart.
                                    if (height_of_punched_hole_candidate > (1 + (punched_hole_percent_overlap_threshold/100)) * punched_hole_diameter_pixels):
                                        #The number of successive notes is calculated by dividing the height of the 
                                        #punched hole candidate by the punched hole diameter in pixels, and applying 
                                        #the "math.ceil()" method to the result, as multiple overlapping holes would 
                                        #have a detected height that is inferior to their combined individual heights 
                                        #were they not overlapping.
                                        number_of_consecutive_notes = math.ceil(height_of_punched_hole_candidate/punched_hole_diameter_pixels)
                                        #The list of center "y" coordinates of successive notes, initialized as an empty
                                        #list, will be set to the center "y" coordinate of the first successive note from 
                                        #the top, calculated by adding half the punched hole pixel diameter to the top "y"
                                        #coordinate of the overlapping successive notes. Then, for each successive note in 
                                        #excess of one, the cell pixel height will be added to the previously processed 
                                        #successive note punched hole at the last element of the list.
                                        list_of_center_y_coordinates_of_successive_notes = [top_y_candidate + 0.5 * punched_hole_diameter_pixels]
                                        #The list of center "y" coordinates of detected punched holes,
                                        #initialized to an empty list, will be populated with each of 
                                        #the individual punched holes' center "y" coordinates.
                                        list_of_center_y_coordinates.append(list_of_center_y_coordinates_of_successive_notes[-1])
                                        if number_of_consecutive_notes > 1:
                                            for k in range(1, number_of_consecutive_notes):
                                                list_of_center_y_coordinates_of_successive_notes.append(list_of_center_y_coordinates_of_successive_notes[-1] + k * cell_pixel_height)
                                                #The list of center "y" coordinates of detected punched holes,
                                                #initialized to an empty list, will be populated with each of 
                                                #the individual punched holes' center "y" coordinates.
                                                list_of_center_y_coordinates.append(list_of_center_y_coordinates_of_successive_notes[-1])
                                    #If the height of the punched hole candidate does not exceed the threshold for two or more successive 
                                    #notes, calculated by multiplying the value of one plus the "punched_hole_percent_overlap_threshold" by 
                                    #the punched hole diameter in pixels, then the "else" statement will append the center "y" coordinate 
                                    #of the detected note, calculated by adding half the pixel diameter of a punched hole to the top "y"
                                    #coordinate of the detected punched hole.
                                    else:     
                                        #The list of center "y" coordinates of detected punched holes,
                                        #initialized to an empty list, will be populated with each of 
                                        #the individual punched holes' center "y" coordinates.
                                        list_of_center_y_coordinates.append(top_y_candidate + (bottom_y_candidate - top_y_candidate)/2)
                                    
                            #If the Boolean variable "top_y_punched_hole_reached" is set to "True",
                            #yet the "elif" statement above didn't run, then it means that we are not 
                            #done traversing the punched hole, and therefore the value of the index 
                            #"non_white_pixels_vertical_projection_profile_index" needs to be 
                            #incremented.
                            elif top_y_punched_hole_reached:                        
                                non_white_pixels_vertical_projection_profile_index += 1
                                  
                    #The list of center "y" coordinates of detected punched holes
                    #"current_note_center_y_coordinate" will be iterated over in 
                    #order to get the horizontal projection profile of the slice 
                    #spanning the entire width of the original slice 
                    #(sublist[0]:sublist[1]) and half the punched hole 
                    #diameter above and below the center "y" coordinate.
                    #This will allow to detect the center "x" coordinate 
                    #separately for each punched hole that is present in 
                    #the slice spanning the full height of the scoresheet.
                    for current_note_center_y_coordinate in list_of_center_y_coordinates:
                        
                        punched_hole_sliced_img_filtered_array_for_flattening = (
                            img_filtered_for_flattening_white_is_one[int(current_note_center_y_coordinate - 
                                0.5*punched_hole_diameter_pixels):
                                int(current_note_center_y_coordinate + 
                                0.5*punched_hole_diameter_pixels), sublist[0]:sublist[1]])
                        
                        #The horizontal profile of the sliced portion of the filtered array where 
                        #white pixels have the value of one and non-white have a value of zero 
                        #will be used to select pixels that fall short of the threshold for 
                        #columns comprised of white pixels, indicating that these columns contain 
                        #punched holes.
                        punched_hole_sliced_img_filtered_array_horizontal_profile = (
                            np.sum(punched_hole_sliced_img_filtered_array_for_flattening, axis=0))
                        
                        #As only the rows around the "current_note_center_y_coordinate" are flattened 
                        #to make up the "punched_hole_sliced_img_filtered_array_horizontal_profile", 
                        #the threshold below which notes are considered to be present is calculated by multiplying 
                        #the height of the slice ("punched_hole_diameter_pixels") by the white pixel threshold percentage.
                        punched_hole_non_white_pixels_horizontal_projection_profile = (
                            np.where(punched_hole_sliced_img_filtered_array_horizontal_profile < 
                            (white_pixel_threshold_percentage_slice/100)*punched_hole_diameter_pixels)[0])
                                        
                        #If the threshold is met or exceeded, then the column corresponding to the flattened rows
                        #at this "x" coordinate will be included in "punched_hole_white_pixels_horizontal_projection_profile"
                        #instead.
                        punched_hole_white_pixels_horizontal_projection_profile = (
                            np.where(punched_hole_sliced_img_filtered_array_horizontal_profile >= 
                            (white_pixel_threshold_percentage_slice/100)*punched_hole_diameter_pixels)[0])
                        
                        #If some notes were detected on the scoresheet in the form of 
                        #some non-white pixels, then the "if" statement below will run. 
                        #If that is not the case, then the user likely needs decrease 
                        #the value of the white pixel percentage threshold
                        #("white_pixel_threshold_percentage).
                        if punched_hole_non_white_pixels_horizontal_projection_profile.size != 0:
                            
                            #The index "punched_hole_non_white_pixels_horizontal_projection_profile_index"
                            #will keep track of which element of the "punched_hole_non_white_pixels_horizontal_projection_profile"
                            #list is being iterated over. This index will be incremented every time the leftmost or  
                            #rightmost "x" coordinates of a punched hole are being screened over, as these need to 
                            #be used in the calculation of the center "x" coordinates for the punched holes.
                            punched_hole_non_white_pixels_horizontal_projection_profile_index = 0
                            len_punched_hole_non_white_pixels_horizontal_projection_profile = punched_hole_non_white_pixels_horizontal_projection_profile.size 

                            #The Boolean variable "left_x_punched_hole_reached", initialized to "False",
                            #will be set to "True" upon reaching the leftmost coordinate of a punched hole,
                            #("left_x_candidate") and will be reset to "False" once more upon reaching its 
                            #rightmost coordinate ("right_x_candidate").
                            #This will allow the "if" statement below to only run if the value of 
                            #"left_x_candidate" for the leftmost coordinate of the punched hole 
                            #hasn't yet been updated, and the first "elif" statement below to 
                            #only run once the leftmost coordinate for the punched hole has 
                            #been stored in that variable, during a subsequent iteration of 
                            #the "for" loop.
                            left_x_punched_hole_reached = False            
                            left_x_candidate = 0
                            right_x_candidate = 0
                            #The "for" loop below iterates over all of the column indices of the slice 
                            #in order to store a punched hole's leftmost "x" coordinate candidate
                            #in the "left_x_candidate" variable in the "if" statement, and the 
                            #rightmost "x" coordinate candidate in the "right_x_candidate"
                            #variable in the first "elif" statement.
                            for j in range(width_of_slice):
                                #In order for the "if" statement to run and set the
                                #punched hole's leftmost "x" coordinate candidate
                                #in the "left_x_candidate" variable, the counter 
                                #iterating over all of the "punched_hole_non_white_pixels_horizontal_projection_profile"
                                #elements must have a value below that of the last element of that list, 
                                #in order to avoid indexing errors, the current value of the Boolean 
                                #variable "left_x_punched_hole_reached" must be set to "False" to avoid 
                                #seting the leftmost coordinate more than once for any given punched 
                                #hole, and the corrected coordinate of the element at the index  
                                #"punched_hole_non_white_pixels_horizontal_projection_profile_index" of the 
                                #"punched_hole_non_white_pixels_horizontal_projection_profile" list needs 
                                #to be equal to the column index "j" of the slice array to ensure that 
                                #the same pixel is under consideration.
                                if (punched_hole_non_white_pixels_horizontal_projection_profile_index < 
                                len_punched_hole_non_white_pixels_horizontal_projection_profile and 
                                punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] == j and
                                not left_x_punched_hole_reached):
                                    #The condition "not (j == width_of_slice - 1 or 
                                    #punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + 1 in
                                    #punched_hole_white_pixels_horizontal_projection_profile" prevents the very last pixel from being detected as a punched 
                                    #hole note, and also any black pixels that are immediately followed by a white pixel, as these are merely 
                                    #artifacts. In any case, we will increment the value of "punched_hole_non_white_pixels_horizontal_projection_profile_index"
                                    #to move on to the next index in the next iteration of the "for" loop.
                                    if not (j == width_of_slice - 1 or 
                                    punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + j in
                                    punched_hole_white_pixels_horizontal_projection_profile):
                                        left_x_punched_hole_reached = True
                                        left_x_candidate = j
                                    
                                    punched_hole_non_white_pixels_horizontal_projection_profile_index += 1
                                #In order for the "elif" statement below to run, the Boolean variable 
                                #"left_x_punched_hole_reached" must already be set to "True", as we will be detecting 
                                #the rightmost coordinate of the punched hole. The next pixel at the corrected index 
                                #"punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + 1" 
                                #must be present in "punched_hole_white_pixels_horizontal_projection_profile", as this would indicate that this is 
                                #the last pixel of the punched hole before reaching a column found in the white pixels horizontal profile.
                                elif (punched_hole_non_white_pixels_horizontal_projection_profile_index < 
                                len_punched_hole_non_white_pixels_horizontal_projection_profile and
                                punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] == j and 
                                left_x_punched_hole_reached and (j == width_of_slice - 1 or 
                                punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + 1 in
                                punched_hole_white_pixels_horizontal_projection_profile)):
                                    right_x_candidate = j
                                    #The Boolean variable "left_x_punched_hole_reached" is 
                                    #reset to "False" in order to allow the code to find the 
                                    #next punched hole.
                                    left_x_punched_hole_reached = False
                                    punched_hole_non_white_pixels_horizontal_projection_profile_index += 1
                                     
                                    width_of_punched_hole_candidate = right_x_candidate - left_x_candidate
                                     
                                    if (width_of_punched_hole_candidate >= 
                                    punched_hole_diameter_pixels * (punched_hole_diameter_percentage_threshold/100)):

                                        #The nested list "nested_list_of_center_x_y_coordinates_of_punched_holes"
                                        #will contain lists of center "x, y" coordinates for each punched hole of 
                                        #the scoresheet and will be sorted along "x" coordinates in ascending order 
                                        #before extrapolating the notes and ticks corresponding to each punched hole.
                                        
                                        #The "x" coordinate is calculated by adding the "horizontal_shift_pixels_current_jpeg" 
                                        #(such that a positive shift would shift the notes to the right and a negative shift 
                                        #would bring them to the left) to the value of the left coordinate of the detected 
                                        #punched hole, plus half the punched hole pixel diameter to the left "x" coordinate 
                                        #of the slice ("sublist[0]") to allow to have an "x" coordinate relative to the start 
                                        #of the entire image.
                                        
                                        #The "y" coordinate is calculated by adding the "vertical_shift_pixels_current_jpeg" 
                                        #(such that a positive shift would shift the notes down and a negative shift would 
                                        #bring them upwards) to the value of the top coordinate of the detected punched hole,
                                        #plus half the punched hole pixel diameter ("current_note_center_y_coordinate") 
                                        #to the top "y" coordinate of the scoresheet, to allow to have a "y" coordinate 
                                        #relative to the start of the entire image.                                        
                                        nested_list_of_center_x_y_coordinates_of_punched_holes.append([sublist[0] + 
                                            left_x_candidate + width_of_punched_hole_candidate/2 + horizontal_shift_pixels_current_jpeg, 
                                            top_y_scoresheet + current_note_center_y_coordinate + vertical_shift_pixels_current_jpeg])

                                        #A pink vertical line spanning the 
                                        #punched hole's diameter is drawn.
                                        cv2.line(
                                            img=color_img,
                                            #The line's top "y" coordinate is calculated by subtracting half the
                                            #punched hole diameter from the punched hole's center "y" coordinate.
                                            pt1=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0]), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1] -  
                                            0.5*punched_hole_diameter_pixels)), 
                                            #The line's bottom "y" coordinate is calculated by adding half the
                                            #punched hole diameter to the punched hole's center "y" coordinate.
                                            pt2=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0]), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1] +
                                            0.5*punched_hole_diameter_pixels)), 
                                            #BGR color
                                            #color=(106, 190, 255),
                                            color=(119, 102, 238),
                                            thickness=2,
                                            lineType=cv2.LINE_AA)
                                            
                                        #A blue horizontal line spanning the 
                                        #punched hole's diameter is drawn. 
                                        cv2.line(
                                            img=color_img,
                                            #The line's left "x" coordinate is calculated by subtracting half the
                                            #punched hole diameter from the punched hole's center "x" coordinate.
                                            pt1=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0] -  
                                            0.5*punched_hole_diameter_pixels), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1])), 
                                            #The line's right "x" coordinate is calculated by adding half the
                                            #punched hole diameter to the punched hole's center "x" coordinate.
                                            pt2=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0] +
                                            0.5*punched_hole_diameter_pixels), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1])), 
                                            #BGR color
                                            #color=(166, 176, 64),
                                            color=(238, 204, 102),
                                            thickness=2,
                                            lineType=cv2.LINE_AA)
                                            
                                #If the Boolean variable "left_x_punched_hole_reached" is set to "True",
                                #yet the "elif" statement above didn't run, then it means that we are not 
                                #done traversing the punched hole, and therefore the value of the index 
                                #"punched_hole_non_white_pixels_horizontal_projection_profile_index" needs to be 
                                #incremented.
                                elif left_x_punched_hole_reached:
                                    punched_hole_non_white_pixels_horizontal_projection_profile_index += 1  

                #Once the nested list of punched hole center "[x, y]" coordinate lists
                #has been completely populated, it is sorted in ascending order along 
                #the "x" coordinates at the index zero to sort the notes in chronological 
                #order starting at the beginning of the song (lowest "x").
                nested_list_of_center_x_y_coordinates_of_punched_holes.sort(key=lambda x: x[0])
                #The following "for" loop will cycle over each "[x,y]" center coordinate in 
                #the sorted nested list "nested_list_of_center_x_y_coordinates_of_punched_holes"
                #and calculate the number of ticks between each successive note and extrapolate 
                #the notes from the "y" coordinates. The resulting "[ticks, midi note]" results 
                #for each successive note in chronological order will be appended to the list 
                #"nested_list_of_note_on_off_midi_cumulative_ticks", which will be used when procedurally generating 
                #the MIDI file.
                for j in range(len(nested_list_of_center_x_y_coordinates_of_punched_holes)):  
                    #If this is the first note ("j == 0") of a given scoresheet, then the "if" 
                    #statement below will set the value of "delta_x" to zero if it is also the 
                    #first scoresheet of the music track ("i == 0"). 
                    #For subsequent scoresheets, the difference between the punched hole's 
                    #center "x" coordinate and the left "x" coordinate of the scoresheet (which 
                    #represents the portion of the silence between notes on this scoresheet) will 
                    #be added the value of "x_pixel_width_after_last_note_of_previous_scoresheet" 
                    #to include the silence after the last note of the previous scoresheet as well, 
                    #as the two scoresheets were cut and are really contiguous.
                    if j == 0:
                        if i == 0:
                            delta_x = 0
                        else:
                            delta_x = (x_pixel_width_after_last_note_of_previous_scoresheet +
                            (nested_list_of_center_x_y_coordinates_of_punched_holes[j][0] - left_x_scoresheet))
                    #If this isn't the first note in a given scoresheet, then the value of "delta_x"
                    #is calculated by subtracting the center "x" coordinate of the previous note in 
                    #chronological order (at the index "j-1") from the center "x" coordinate of the 
                    #current note at index "j".
                    else:
                        delta_x = (nested_list_of_center_x_y_coordinates_of_punched_holes[j][0] -
                            nested_list_of_center_x_y_coordinates_of_punched_holes[j-1][0])
                    #If this is the last note of a scoresheet, then the value of 
                    #"x_pixel_width_after_last_note_of_previous_scoresheet" will be 
                    #set to the difference between the right "x" coordinate of the 
                    #scoresheet and the center "x" coordinate of this last note in 
                    #order to include the silence after this last note to the silence
                    #before the first note of the next scoresheet, as the two scoresheets 
                    #were cut and are really contiguous.
                    if j == len(nested_list_of_center_x_y_coordinates_of_punched_holes) - 1:
                        x_pixel_width_after_last_note_of_previous_scoresheet = (right_x_scoresheet - 
                            nested_list_of_center_x_y_coordinates_of_punched_holes[j][0])
                            
                    #If this is the first note ("j == 0") of the first scoresheet ("i == 0")
                    #for a given music track, then the value of "ticks" will be set to that 
                    #of "leading_silence_ticks" to include the requested leading delay.
                    if i == 0 and j == 0:
                        ticks = leading_silence_ticks
                    else:
                        #The number of ticks is calculated by first dividing "delta_x" by the number of 
                        #horizontal pixels per smallest measure ("width_of_one_smallest_measure_pixels") in order 
                        #to get the number of smallest measures between the two successive notes in chronological
                        #order. Then, this result is multiplied by the number of ticks per quarter notes, times 
                        #the quotient of four over the value of "smallest_measure_duration_denominator" to get 
                        #the number of ticks per smallest measure, which yields the number of ticks as the number 
                        #of smallest measures cancel out.
                        ticks = (delta_x/width_of_one_smallest_measure_pixels) * ticks_per_smallest_measure
                    
                    #Increment the value of "cumulative_ticks" by the value of "ticks".
                    cumulative_ticks += ticks
                    
                    #The list of of "float" note horizontal gridline "y" coordinates
                    #"list_of_music_box_note_center_y_coordinates" will be used to draw 
                    #the music box gridlines on the scoresheet and a copy of the list 
                    #will be used to extrapolate which note corresponds to the center 
                    #"y" coordinate of each punched hole. To to this, the center "y"
                    #coordinate will be appended to the list copy, which will then 
                    #be sorted, and the index of the newly added note will be obtained 
                    #with the "index()" method. Then the neighboring note that has the 
                    #nearest "y" coordinate will be selected.
                    temp_list_of_music_box_note_center_y_coordinates = list_of_music_box_note_center_y_coordinates.copy()
                    temp_list_of_music_box_note_center_y_coordinates.append(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1])
                    temp_list_of_music_box_note_center_y_coordinates.sort()
                    index_of_current_note = temp_list_of_music_box_note_center_y_coordinates.index(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1])
                    #If the index of the newly added note in the sorted list is equal to zero,
                    #then it necessarily means that the note is the first note in list of 
                    #music box note "y" coordinates "list_of_music_box_note_center_y_coordinates". 
                    if index_of_current_note == 0:
                        current_note_extrapolated_y = list_of_music_box_note_center_y_coordinates[0]
                    #Alternatively, if the index of the newly added note in the sorted list is equal 
                    #to the last index of the sorted list, then it necessarily means that the note 
                    #is the last note in list of music box note "y" coordinates 
                    #"list_of_music_box_note_center_y_coordinates". 
                    elif index_of_current_note == len(temp_list_of_music_box_note_center_y_coordinates) - 1:
                        current_note_extrapolated_y = list_of_music_box_note_center_y_coordinates[-1]
                    #Otherwise, the absolute value of the difference between the "y" coordinates of 
                    #the newly added note and the notes right before and right after it in the sorted 
                    #list will be used to determine which note corresponds to that punched hole. The 
                    #lowest absolute value result will mean that the punched hole is closest to that 
                    #music box note.
                    else:
                        previous_note_y = temp_list_of_music_box_note_center_y_coordinates[index_of_current_note-1]
                        next_note_y = temp_list_of_music_box_note_center_y_coordinates[index_of_current_note+1]
                        if abs(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1] - previous_note_y) <= abs(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1] - next_note_y):
                            current_note_extrapolated_y = previous_note_y
                        else:
                            current_note_extrapolated_y = next_note_y
                    
                    #The extrapolated MIDI note is obtained by accessing the dictionary of music box 
                    #note center "y" coordinate keys to values made up of lists of notes in letter 
                    #format and MIDI notes ("note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict")
                    #with the extrapolated "y" coordinate ("current_note_extrapolated_y"), and then indexing the 
                    #list at the index 1 to retrieve the corresponding MIDI note.
                    extrapolated_midi_note = note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[current_note_extrapolated_y][1]
                    #If the user has entered a semitone shift other than zero, it will be added to 
                    #the value of the extrapolated MIDI note. The shifted note will only be retained 
                    #if it falls within the MIDI range of 0-127, and the original value of the extrapolated 
                    #MIDI note will be used otherwise.
                    if semitone_shift != 0:
                        semitone_shifted_midi_note_candidate =  extrapolated_midi_note + semitone_shift
                        if semitone_shifted_midi_note_candidate >= 0 and semitone_shifted_midi_note_candidate <= 127:
                            extrapolated_midi_note = semitone_shifted_midi_note_candidate
                    
                    #The data for the "note_on" and "note_off" messages for each punched hole center coordinates 
                    #in chronological order will be appended to the list "nested_list_of_note_on_off_midi_cumulative_ticks", 
                    #which will be used when procedurally generating the MIDI file, as a tuple of three elements: 
                    #("note_on", midi note, cumulative_ticks).
                    nested_list_of_note_on_off_midi_cumulative_ticks.append(("note_on", 
                        extrapolated_midi_note, int(cumulative_ticks)))
                    nested_list_of_note_on_off_midi_cumulative_ticks.append(("note_off", 
                        extrapolated_midi_note, int(cumulative_ticks + ticks_per_smallest_measure)))
                    
                    color_img = cv2.putText(
                        img=color_img, 
                        #The dictionary of "float" note horizontal gridline "y" coordinate keys to 
                        #values made up of a list of the notes in letter form and corresponding midi 
                        #notes "note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict"
                        #will allow to tally up the extrapolated notes from the detected punched 
                        #hole center "y" coordinates. 
                        text=midi_notes_dict[extrapolated_midi_note],
                        org=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[j][0] - 0.5*punched_hole_diameter_pixels + horizontal_shift_pixels_current_jpeg), 
                        int(top_y_scoresheet + nested_list_of_center_x_y_coordinates_of_punched_holes[j][1] + 0.5*punched_hole_diameter_pixels + vertical_shift_pixels_current_jpeg)), 
                        fontFace=cv2.FONT_HERSHEY_PLAIN,
                        fontScale=1,
                        color=(0, 0, 0),
                        thickness=1,
                        lineType=cv2.LINE_AA
                        )
                        
                #The cropped and annotated version of the "color_img" scoresheet array will be saved to 
                #a JPEG file, with the " (Annotated)" file name suffix. As JPEG images only support 
                #8-bit per channel data (CV_8U), we first need to cast the data to "np.uint8" before 
                #writing the image.
                cv2.imwrite(os.path.join(output_folder_path, jpg_names[i] + " (Annotated).jpg"), 
                    color_img[top_y_scoresheet:bottom_y_scoresheet + 1, left_x_scoresheet:right_x_scoresheet + 1].astype(np.uint8))
        
                #The function "display_progress" will display the progress string in the console
                #and return the estimated number of seconds for the code to complete.

                #The previous estimation of the remaining number of seconds is stored in the variable
                #"previous_estimated_seconds" and will be used instead of the current calculation
                #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
                #its estimation.
                
                #The value of "i+1" is passed in for the "current_jpeg_index" argument, as the 
                #JPEG file at the index "i" of the "jpeg_files" list has just finished being 
                #processed.
                previous_estimated_seconds = display_progress(i+1, first_jpeg_index, last_jpeg_index, start_time, previous_estimated_seconds)         
                
            #If some notes were detected on the scoresheet in the form of 
            #some non-white pixels, then the "if" statement below will run. 
            #If that is not the case, then the user likely needs decrease 
            #the value of the white pixel percentage threshold
            #("white_pixel_threshold_percentage), as no horizontal 
            #spaces between punched holes were detected in the image.
            else:
                print(undetectable_notes_error_string)
                input(press_any_key_string)
                sys.exit(1)  
        #The MIDI file is generated by first instantiating a "MidiFile" object,
        #setting the MIDI file type to 1 to allow multiple tracks and setting the 
        #value of the "ticks_per_beat" property to the value of the "ticks_per_quarter_note"
        #variable.
        mid = MidiFile()
        mid.type = 1
        mid.ticks_per_beat = ticks_per_quarter_note
        #The track zero will contain the tempo  and time signature.
        track_0 = MidiTrack()
        #The track zero is appended to the "MidiFile" object "mid".
        mid.tracks.append(track_0)
        track_0.append(MetaMessage("set_tempo", tempo=tempo_us_per_quarter_note, time=0))
        track_0.append(MetaMessage("time_signature", numerator=time_signature_numerator, denominator=time_signature_denominator, time=0))
        track_0.append(MetaMessage("end_of_track", time=0))
        #The track 1 will contain the "track_name", "text" and "copyright" metadata,
        #with the two latter being optional, and will be appended to the "MidiFile" 
        #object "mid".
        track_1 = MidiTrack()
        mid.tracks.append(track_1)
        track_1.append(MetaMessage("track_name", name=output_file_name))
        if midi_comment != "":
            track_1.append(MetaMessage("text", text=midi_comment))
        if midi_copyright_string != "":
            track_1.append(MetaMessage("copyright", text=midi_copyright_string))
                    
        #The data for the "note_on" and "note_off" messages for each punched hole center coordinates 
        #in chronological order was appended to the list "nested_list_of_note_on_off_midi_cumulative_ticks", 
        #which will be used when procedurally generating the MIDI file, as a tuple of three elements: 
        #("note_on", midi note, cumulative_ticks).
        
        #The tuple elements in the nested list "nested_list_of_note_on_off_midi_cumulative_ticks"
        #are sorted in chronological order of "cumulative_ticks", which is the third element in 
        #each tuple at index two. Sorting is once again necessary, even though the "x, y" coordinates 
        #used for extrapolating the notes have already been sorted chronologically, as these only 
        #represented "note_on" events that were played on the music box, and did not include the 
        #"note_off" messages, which are also considered events in the MIDI file, and so the 
        #"note_off" events were inserted right after "note_on" events when populating the list 
        #"nested_list_of_note_on_off_midi_cumulative_ticks". This will allow to calculate
        #the relative ticks between each sorted "note_on" and "note_off" element.
        nested_list_of_note_on_off_midi_cumulative_ticks.sort(key=lambda x:x[2])
        #The elements of the sorted list "nested_list_of_note_on_off_midi_cumulative_ticks",
        #which now represent the "note_on" and "note_off" events in chronological order,
        #will by cycled over and a "Message" will be appended to the track one for each 
        #of these events.
        for i in range(len(nested_list_of_note_on_off_midi_cumulative_ticks)):
            #If this is the first "note_on" event, then the relative ticks will be equal 
            #to the cumulative ticks value at the index two of the list, as the previous 
            #metadata messages for track one are all at time zero.
            if i == 0:
                relative_ticks = nested_list_of_note_on_off_midi_cumulative_ticks[i][2]
            #Subsequent "note_on" and "note_off" messages will have their relative ticks 
            #calculated by subtracting the value of the preceding message's cumulative 
            #ticks from that of the current message.
            else:
                relative_ticks = (nested_list_of_note_on_off_midi_cumulative_ticks[i][2] -
                    nested_list_of_note_on_off_midi_cumulative_ticks[i-1][2])
            #The "note_on" or "note_off" "Message" will be appended to the track one 
            #of the MIDI file, with the "note_on" or "note_off" string being accessed 
            #at the index zero of the tuple, and the note at the index one. The "time"
            #parameter is set to the value of "relative_ticks" calculated above and the 
            #"velocity" parameter is set to the "midi_velocity" user setting.
            track_1.append(Message(nested_list_of_note_on_off_midi_cumulative_ticks[i][0], 
                channel=0, 
                note=nested_list_of_note_on_off_midi_cumulative_ticks[i][1],
                velocity=midi_velocity,
                time=relative_ticks))
            #If this is the last "note_off" message at the last indes of the list 
            #"nested_list_of_note_on_off_midi_cumulative_ticks", then an "end_of_track"
            #"Message" will be appended to track one, with a "time" parameter equal to 
            #that of last "note_off" message, with the addition of "trailing_silence_ticks".
            if i == len(nested_list_of_note_on_off_midi_cumulative_ticks) - 1:
                track_1.append(MetaMessage("end_of_track", time = trailing_silence_ticks))
        #The MIDI file is saved to the output folder path.
        mid.save(os.path.join(output_folder_path, output_file_name + ".mid"))
        
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        input("\n" + textwrap.fill(f"Your MIDI file was successfully generated in the '{output_file_name}' subfolder!", width=columns) + "\n\nPress any key to continue.\n")

    else:
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        input("\n" + textwrap.fill(f"Please include some JPEG scans of the back sides of your scoresheets in the '{scans_folder_name}' subfolder.", width=columns) + "\n\nPress any key to continue.\n")
        
    return json_settings_dictionary  

#The "set_number_of_notes()" function will 
#set the number of notes for the music box.
def set_number_of_notes(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Music Box Number of Notes ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(number_of_notes_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the music box's number of notes (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_time_signature_numerator()" function will 
#set the time signature's numerator.
def set_time_signature_numerator(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Time Signature Numerator ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(time_signature_numerator_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the sime signature numerator (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_time_signature_denominator()" function will 
#set the time signature's denominator.
def set_time_signature_denominator(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Time Signature Denominator ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(time_signature_denominator_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the sime signature denominator (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_tempo_bpm()" function will 
#set the tempo in beats per minute (bpm).
def set_tempo_bpm(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Tempo in Beats per Minute (bpm) ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(tempo_bpm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the tempo in beats per minute (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_ticks_per_quarter_note()" function will 
#set the number of ticks per quarter note.
def set_ticks_per_quarter_note(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Ticks per Quarter Note ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(ticks_per_quarter_note_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the number of ticks per quarter note (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_width_of_ten_successive_smallest_measures_in_millimeters()" function will 
#set the number of millimeters for ten successive smallest measures.
def set_width_of_ten_successive_smallest_measures_in_millimeters(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Width of Ten Successive Smallest Measures in Millimeters ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(width_of_ten_smallest_measures_mm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the number millimeters for ten consecutive smallest boxes or measures on the scoresheet (above zero, decimals allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_smallest_measure_duration_denominator()" function will 
#set the denominator of the duration of the smallest measure.
def set_smallest_measure_duration_denominator(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Smallest Measure Duration Denominator ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(smallest_measure_duration_denominator_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the denominator of the duration of the smallest boxes or measures on the scoresheet (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_midi_velocity()" function will 
#set the MIDI velocity of each note.
def set_midi_velocity(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set MIDI Velocity ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(midi_velocity_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the MIDI velocity that will be used for every note (0-127), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 127:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_semitone_shift()" function will 
#set the semitone shift that will be applied 
#to all of the MIDI notes.
def set_semitone_shift(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Semitone Shift ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(semitone_shift_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the semitone shift that will be applied to every note (positive or negative integer), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)

            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_leading_silence_duration_in_milliseconds()" function will 
#set leading silence before the first note of the music track, in 
#milliseconds.
def set_leading_silence_duration_in_milliseconds(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Leading Silence Duration in Milliseconds ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(leading_silence_milliseconds_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the leading silence duration in milliseconds (0 and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_trailing_silence_duration_in_milliseconds()" function will 
#set trailing silence after the last note of the music track, in 
#milliseconds.
def set_trailing_silence_duration_in_milliseconds(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Trailing Silence Duration in Milliseconds ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(trailing_silence_milliseconds_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the trailing silence duration in milliseconds (0 and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "music_metrics_settings_menu()" function will run a "while is_in_submenu"
#loop that will allow the user to navigate the menu, and the loop will 
#be broken out of when they select the "Quit" option.
def music_metrics_settings_menu(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        music_metrics_settings_menu_actions_dict = {
        "1": [f"Music Box Number of Notes ({json_settings_dictionary["Number of Notes"]})", set_number_of_notes, ("Number of Notes", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "2": [f"Time Signature Numerator ({json_settings_dictionary["Time Signature Numerator"]})", set_time_signature_numerator, ("Time Signature Numerator", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "3": [f"Time Signature Denominator ({json_settings_dictionary["Time Signature Denominator"]})", set_time_signature_denominator, ("Time Signature Denominator", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "4": [f"Tempo in Beats per Minute (bpm) ({json_settings_dictionary["Tempo bpm"]})", set_tempo_bpm, ("Tempo bpm", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "5": [f"Ticks per Quarter Note ({json_settings_dictionary["Ticks per Quarter Note"]})", set_ticks_per_quarter_note, ("Ticks per Quarter Note", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "6": [f"Width of Ten Successive Smallest Measures in Millimeters ({json_settings_dictionary["Width of Ten Successive Smallest Measures in Millimeters"]})", set_width_of_ten_successive_smallest_measures_in_millimeters, ("Width of Ten Successive Smallest Measures in Millimeters", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "7": [f"Smallest Measure Duration Denominator ({json_settings_dictionary["Smallest Measure Duration Denominator"]})", set_smallest_measure_duration_denominator, ("Smallest Measure Duration Denominator", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "8": [f"Midi Velocity ({json_settings_dictionary["Midi Velocity"]})", set_midi_velocity, ("Midi Velocity", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "9": [f"Semitone Shift ({json_settings_dictionary["Semitone Shift"]})", set_semitone_shift, ("Semitone Shift", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "10": [f"Leading Silence Duration in Milliseconds ({json_settings_dictionary["Leading Silence Duration in Milliseconds"]})", set_leading_silence_duration_in_milliseconds, ("Leading Silence Duration in Milliseconds", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "11": [f"Trailing Silence Duration in Milliseconds ({json_settings_dictionary["Trailing Silence Duration in Milliseconds"]})", set_trailing_silence_duration_in_milliseconds, ("Trailing Silence Duration in Milliseconds", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "m": ["Main Menu", back_to_main_menu_function, (json_settings_dictionary,)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        music_metrics_settings_menu_actions_dict = textwrap_action_strings_in_menu_action_dict(music_metrics_settings_menu_actions_dict)

        print("=== Music Metrics Settings Menu ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()

        print(textwrap.fill("This menu will allow you to set the settings for the music metrics. Further details are available in the submenu options, or in the 'README.txt' file.", width=columns) + "\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(music_metrics_settings_menu_actions_dict, json_settings_dictionary)
    return json_settings_dictionary   

#The "set_midi_copyright_metadata_string()" function 
#will set the copyright MIDI metadata string.
def set_midi_copyright_metadata_string(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Copyright MIDI Metadata String  ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            #If an empty string is present either as the default or current metadata setting,
            #then the "Metadata not included in MIDI file" string will be printed on-screen.
            #Otherwise, the value of the "json_default_settings_dictionary" or "json_settings_dictionary"
            #will be displayed instead.           
            metadata_not_included_string = "Metadata not included in MIDI file"
            current_setting_string = metadata_not_included_string
            if json_settings_dictionary[json_settings_key].strip() != "":
                current_setting_string = json_settings_dictionary[json_settings_key]
            
            default_setting_string = metadata_not_included_string
            if json_default_settings_dictionary[json_settings_key].strip() != "":
                default_setting_string = json_default_settings_dictionary[json_settings_key]
            
            print(f"Current Setting: {current_setting_string} | Default: {default_setting_string}.\n")

            textwrapped_instructions_string = textwrap.fill(midi_copyright_string_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the copyright text that will be included in the MIDI file's metadata, leave empty to exclude this from the metadata, or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] MIDI File Metadata Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice.lower() == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice.lower() == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice.lower() == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice.lower() == "q":
                quit_function()
            user_input = choice
            
            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_midi_comment_metadata_string()" function 
#will set the comment MIDI metadata string.
def set_midi_comment_metadata_string(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Comment MIDI Metadata String  ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            #If an empty string is present either as the default or current metadata setting,
            #then the "Metadata not included in MIDI file" string will be printed on-screen.
            #Otherwise, the value of the "json_default_settings_dictionary" or "json_settings_dictionary"
            #will be displayed instead.           
            metadata_not_included_string = "Metadata not included in MIDI file"
            current_setting_string = metadata_not_included_string
            if json_settings_dictionary[json_settings_key].strip() != "":
                current_setting_string = json_settings_dictionary[json_settings_key]
            
            default_setting_string = metadata_not_included_string
            if json_default_settings_dictionary[json_settings_key].strip() != "":
                default_setting_string = json_default_settings_dictionary[json_settings_key]
            
            print(f"Current Setting: {current_setting_string} | Default: {default_setting_string}.\n")

            textwrapped_instructions_string = textwrap.fill(midi_comment_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the comment text that will be included in the MIDI file's metadata, leave empty to exclude this from the metadata, or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] MIDI File Metadata Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice.lower() == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice.lower() == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice.lower() == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice.lower() == "q":
                quit_function()
            user_input = choice
            
            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "midi_file_metadata_settings_menu()" function will run a "while is_in_submenu"
#loop that will allow the user to navigate the menu, and the loop will 
#be broken out of when they select the "Quit" option.
def midi_file_metadata_settings_menu(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        midi_file_metadata_settings_menu_actions_dict = {
        "1": [f"Midi Copyright Metadata String", set_midi_copyright_metadata_string, ("Midi Copyright Metadata String", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "2": [f"Midi Comment String", set_midi_comment_metadata_string, ("Midi Comment String", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "m": ["Main Menu", back_to_main_menu_function, (json_settings_dictionary,)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        midi_file_metadata_settings_menu_actions_dict = textwrap_action_strings_in_menu_action_dict(midi_file_metadata_settings_menu_actions_dict)

        print("=== MIDI File Metadata Settings Menu ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()

        print(textwrap.fill("This menu will allow you to set the MIDI file metadata settings. Further details are available in the submenu options, or in the 'README.txt' file.", width=columns) + "\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(midi_file_metadata_settings_menu_actions_dict, json_settings_dictionary)
    return json_settings_dictionary 

#The "set_dpi()" function will set the resolution 
#in dpi of the JPEG scoresheet scans.
def set_dpi(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Scans Resolution in DPI ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(dpi_setting_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the dpi resolution of your scanned scoresheet JPEG files (100 or higher), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_page_rotation_angle()" function will set the  
#rotation angle in degrees of the JPEG scoresheet scans.
def set_page_rotation_angle(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Page Rotation Angle ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(page_rotation_angle_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the rotation angle for your scanned scoresheet JPEG files (0 - 360, positive or negative), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)

            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_contrast_level()" function will set the  
#contrast level for the JPEG scoresheet scans.
def set_contrast_level(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Contrast Level ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(contrast_level_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the contrast level for your scanned scoresheet JPEG files (0 and above, decimal values allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_brightness_level()" function will set the  
#brightness level for the JPEG scoresheet scans.
def set_brightness_level(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Brightness Level ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(brightness_level_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the brightness level for the annotated JPEG files (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_paper_color_grayscale_filter_threshold()" function will set the  
#grayscale value filter threshold for the JPEG scoresheet scans.
def set_paper_color_grayscale_filter_threshold(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Grayscale Filter Threshold Value ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(paper_color_grayscale_filter_threshold_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the grayscale value filter threshold (0 - 255), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 255:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_black_pixel_threshold_percentage()" 
#function will set the black pixel threshold percentage.
def set_black_pixel_threshold_percentage(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Black Pixel Threshold Percentage ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(black_pixel_threshold_percentage_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the black pixel percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_white_pixel_threshold_percentage()" 
#function will set the white pixel threshold percentage.
def set_white_pixel_threshold_percentage(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set White Pixel Threshold Percentage ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(white_pixel_threshold_percentage_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the white pixel percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_white_pixel_threshold_percentage_for_slices()" 
#function will set the white pixel threshold percentage 
#for slices.
def set_white_pixel_threshold_percentage_for_slices(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set White Pixel Threshold Percentage for Slices ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(white_pixel_threshold_percentage_slice_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the white pixel percentage threshold for slices (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_punched_hole_diameter_percentage_threshold()" 
#function will set the punched hole diameter percentage 
#threshold.
def set_punched_hole_diameter_percentage_threshold(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Punched Hole Diameter Percentage Threshold ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(punched_hole_diameter_percentage_threshold_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the punched hole diameter percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_punched_hole_percentage_overlap_threshold()" 
#function will set the punched hole overlap percentage 
#threshold.
def set_punched_hole_percentage_overlap_threshold(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Punched Hole Overlap Percentage Threshold ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(punched_hole_percent_overlap_threshold_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the punched hole overlap percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_punched_hole_diameter_in_millimeters()" 
#function will set the punched hole diameter in 
#millimeters.
def set_punched_hole_diameter_in_millimeters(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Punched Hole Diameter in Millimeters ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(punched_hole_diameter_mm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the punched diameter in millimeters (above zero, decimal values allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_scoresheet_grid_height_in_millimeters()" 
#function will set the height of the scoresheet 
#grid in millimeters.
def set_scoresheet_grid_height_in_millimeters(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Scoresheet Grid Height in Millimeters ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(scoresheet_grid_height_mm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the height of the scoresheet grid in millimeters (above zero, decimal values allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_vertical_shift_in_pixels()" 
#function will set the vertical shift 
#by which all of the punched holes' 
#center "x, y" coordinates will be 
#shifted by.
def set_vertical_shift_in_pixels(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Vertical Shift in Pixels ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(vertical_shift_pixels_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the vertical shift in pixels (zero and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_horizontal_shift_in_pixels()" 
#function will set the horizontal shift 
#by which all of the punched holes' 
#center "x, y" coordinates will be 
#shifted by.
def set_horizontal_shift_in_pixels(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Horizontal Shift in Pixels ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(horizontal_shift_pixels_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the horizontal shift in pixels (zero and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "image_processing_settings_menu()" function will run a "while is_in_submenu"
#loop that will allow the user to navigate the menu, and the loop will 
#be broken out of when they select the "Quit" option.
def image_processing_settings_menu(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        image_processing_settings_menu_actions_dict = {
        "1": [f"Scan Resolution in DPI ({json_settings_dictionary["Scan Resolution in DPI"]})", set_dpi, ("Scan Resolution in DPI", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "2": [f"Page Rotation Angle ({json_settings_dictionary["Page Rotation Angle"]})", set_page_rotation_angle, ("Page Rotation Angle", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "3": [f"Contrast Level ({json_settings_dictionary["Contrast Level"]})", set_contrast_level, ("Contrast Level", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "4": [f"Brightness Level ({json_settings_dictionary["Brightness Level"]})", set_brightness_level, ("Brightness Level", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "5": [f"Paper Color Grayscale Filter Threshold ({json_settings_dictionary["Paper Color Grayscale Filter Threshold"]})", set_paper_color_grayscale_filter_threshold, ("Paper Color Grayscale Filter Threshold", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "6": [f"Black Pixel Threshold Percentage ({json_settings_dictionary["Black Pixel Threshold Percentage"]})", set_black_pixel_threshold_percentage, ("Black Pixel Threshold Percentage", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "7": [f"White Pixel Threshold Percentage ({json_settings_dictionary["White Pixel Threshold Percentage"]})", set_white_pixel_threshold_percentage, ("White Pixel Threshold Percentage", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "8": [f"White Pixel Threshold Percentage for Slices ({json_settings_dictionary["White Pixel Threshold Percentage for Slices"]})", set_white_pixel_threshold_percentage_for_slices, ("White Pixel Threshold Percentage for Slices", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "9": [f"Punched Hole Diameter Percentage Threshold ({json_settings_dictionary["Punched Hole Diameter Percentage Threshold"]})", set_punched_hole_diameter_percentage_threshold, ("Punched Hole Diameter Percentage Threshold", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "10": [f"Punched Hole Percentage Overlap Threshold ({json_settings_dictionary["Punched Hole Percentage Overlap Threshold"]})", set_punched_hole_percentage_overlap_threshold, ("Punched Hole Percentage Overlap Threshold", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "11": [f"Punched Hole Diameter in Millimeters ({json_settings_dictionary["Punched Hole Diameter in Millimeters"]})", set_punched_hole_diameter_in_millimeters, ("Punched Hole Diameter in Millimeters", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "12": [f"Scoresheet Grid Height in Millimeters ({json_settings_dictionary["Scoresheet Grid Height in Millimeters"]})", set_scoresheet_grid_height_in_millimeters, ("Scoresheet Grid Height in Millimeters", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "13": [f"Vertical Shift in Pixels ({json_settings_dictionary["Vertical Shift in Pixels"]})", set_vertical_shift_in_pixels, ("Vertical Shift in Pixels", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "14": [f"Horizontal Shift in Pixels ({json_settings_dictionary["Horizontal Shift in Pixels"]})", set_horizontal_shift_in_pixels, ("Horizontal Shift in Pixels", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "m": ["Main Menu", back_to_main_menu_function, (json_settings_dictionary,)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        image_processing_settings_menu_actions_dict = textwrap_action_strings_in_menu_action_dict(image_processing_settings_menu_actions_dict)

        print("=== Image Processing Settings Menu ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()

        print(textwrap.fill("This menu will allow you to set the settings that will help the code locate the punched holes. Further details are available in the submenu options, or in the 'README.txt' file.", width=columns) + "\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(image_processing_settings_menu_actions_dict, json_settings_dictionary)
    return json_settings_dictionary     

#The "reset_all_settings()" function will set the value "json_settings_dictionary"
#to that of "json_default_settings_dictionary" and save the changes to the JSON file.
def reset_all_settings(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:

        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        print("=== Reset All Settings ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        textwrapped_input_string = textwrap.fill("Are you sure you want to reset all of the settings? Enter (y/n), or select one of the above options: ", width=columns)
        
        print(f"[m] Main Menu\n[q] Quit\n")

        choice = input(textwrapped_input_string + " ").strip().lower()
        if choice in ["", "n"]:
            #A continue needs to be used, as we don't want 
            #the code below the "elif" statements to run,
            #which would cause a ValueError on int("").
            continue
        elif choice == "m":
            #The function "back_to_main_menu_function()"
            #will set the Boolean flags "is_in_submenu" and 
            #"is_in_sub_submenu" to "False", which will break the submenu
            #"while" loops and return to the main menu.
            return json_settings_dictionary
        elif choice == "q":
            quit_function()
        elif choice == "y":           
            #A deep copy (since it contains a list of deleted pages) of 
            #"json_default_settings_dictionary" is made so as to avoid having
            #both "json_settings_dictionary" and "json_default_settings_dictionary"
            #pointing to the same address.
            json_settings_dictionary = copy.deepcopy(json_default_settings_dictionary)
            #The function "atomic_save()" will create a temporary JSON file with the updated changes.
            #If the files is created successfully, then the files will be swapped. If a problem is 
            #encountered, the temp file will be unlinked and an error log will be reported.
            atomic_save(json_settings_dictionary, json_settings_file_path_name)
            print("\nAll settings have successfully been reset to their default values.")
            input("\nPress any key continue.")
        else:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "main_menu()" function will run a "while True"
#loop that will allow the user to navigate the menu, and the
#loop will be broken out of when they select the "Quit" option,
#or when they press Ctrl+C (SIGINT, Signal Interrupt).
def main_menu(json_settings_dictionary, json_default_settings_dictionary, cwd, json_settings_file_path_name):

    while True:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        menu_actions_dict = {
        "1": ["Generate MIDI File with Current Settings", generate_midi_file, (json_settings_dictionary, json_default_settings_dictionary, cwd)],
        "2": ["Music Metrics Settings Menu (Settings regarding the tempo, time signature, etc.)", music_metrics_settings_menu, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "3": ["MIDI File Metadata (Copyright information and comment string that are embedded in the MIDI file)", midi_file_metadata_settings_menu, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "4": ["Image Processing Settings Menu (Settings that help the code locate the punched holes)", image_processing_settings_menu, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "r": ["Reset Defaults", reset_all_settings, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        menu_actions_dict = textwrap_action_strings_in_menu_action_dict(menu_actions_dict)

        print("  MusicReader")
        print("=== Main Menu ===\n\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(menu_actions_dict, json_settings_dictionary)


#The "main()" function will initialize the path variables and the "json_settings_dictionary" and 
#"json_default_settings_dictionary" dictionaries by calling the "load_json_data()" function.
#It will then initiate the main menu loop by calling the "main_menu()" function.
def main():
    #Register the Signal Interrupt (SIGINT) handler that will
    #call the "signal_interrupt_signal_handler()" function 
    #when the user presses on CTRL + C to exit the app.

    #The function "signal_interrupt_signal_handler()" will call
    #"sys.exit(0)" to exit the program normally.
    signal.signal(signal.SIGINT, signal_interrupt_signal_handler)

    cwd = os.getcwd()

    #The function "get_terminal_dimensions()" will return the number of columns 
    #and rows in the console, to allow to properly format the text and dividers.
    columns, lines = get_terminal_dimensions()
    
    #If either the "Scans" subfolder is missing, or if it is empty,
    #it will be created and the code will exit the application while 
    #printing the "missing_scans_string" on-screen.
    missing_scans_string = "\n" + textwrap.fill("Please add the scanned scoresheet JPEG files in the 'Scans' subfolder of the MusicReader folder and launch the application again.", width=columns) + "\n"     
    if not os.path.exists(os.path.join(cwd, scans_folder_name)):
        os.mkdir(os.path.join(cwd, scans_folder_name))
        print(missing_scans_string)
        input(press_any_key_string)
        sys.exit(1)
    else:
        jpeg_path = os.path.join(cwd, scans_folder_name, "*.jpg")
        jpeg_files = glob.glob(jpeg_path)
        if jpeg_files == []:
            print(missing_scans_string)
            input(press_any_key_string)
            sys.exit(1)
     
    json_settings_file_path_name = os.path.join(cwd, "settings.json")

    #The function "load_json_data()" will load the JSON data from file
    #and store them in the "json_settings_dictionary", or initialize the
    #dictionary based on the values of "json_default_settings_dictionary".
    json_default_settings_dictionary, json_settings_dictionary = load_json_data(json_settings_file_path_name)

    #The "main_menu()" function will run a "while True"
    #loop that will allow the user to navigate the menu, and the
    #loop will be broken out of when they select the "Quit" option,
    #or when they press Ctrl+C (SIGINT, Signal Interrupt).
    main_menu(json_settings_dictionary, json_default_settings_dictionary, cwd, json_settings_file_path_name)
 

if __name__ == '__main__':

    README_STRING = """**MusicReader** is an application that generates MIDI files from scanned music box scoresheet JPEG files, complete with features such as tempo adjustment, transposition, and addition of silence to the start and end of the MIDI files, essentially turning your music box into an analog version of a Digital Audio Workstation (DAW)!


Here are a few important pointers for best results:


- You will need to **line the lid of your flatbed scanner with black construction paper** (you may use masking tape to stick the paper, as it should not damage your lid). The application detects the punched holes as black circles when **the underside of the scoresheets are scanned**, meaning that the grid faces up. The underside of the scoresheet are scanned in order to remove any superfluous grid information that might hinder the punched hole detection. The black areas above, below and on either side of the scoresheet will also let the code auto-crop the scoresheet.

- The scoresheets need to be sized to a maximum of around 11 inches in length in order to fit on a standard flatbed scanner **configured to scan in US Legal format (8.5 x 14 inches)** to avoid having information being cut off from your scans. Try to **cut the strips nice and straight at right angles** with the length of the scoresheet, as the code will detect any horizontal spaces left after the last note of a given scoresheet and add it to the horizontal space before the first note on the next image. This way, the timing of your notes should still be fairly accurate even when notes span several scoresheet strips. 

- Make sure to **scan at a resolution of 200 dots per inch (dpi) or higher** for more accurate results (I had great results with 200 dpi, which keeps the file sizes manageable) and output the files as **grayscale or color JPEG images** (grayscale will take up less storage space). You should also select the **lightest scanning setting** on your scanner, as this helps to bleach out any blemishes or shadows that might be present on the scanned underside of your scoresheets. 

- The **scanned JPEG file names should end with a plus sign (“+”)**, such that when your scanner automatically suffixes the JPEG files with a file number, the code will be able to distinguish these from any numbers present at the end of your actual file names (e.g., “Track 1+0001.jpg).

- When placing the scoresheet grid-side up onto your flatbed scanner, **line up the scoresheet strip such that it shows up on the left side of the scan in portrait mode** (the “Page Rotation Angle” setting in the “Image Processing Settings Menu” should then be -90 degrees, which is 90 degrees counterclockwise), and **always have the arrow pointing in the same direction**. See the example JPEG image (“this is what your scans should look like.jpg”) in the working folder to illustrate this. In my case, on an all-in-one printer, I had to place the scoresheet at the very bottom of the flatbed area (grid-side up), with the arrow pointing to the right. This way, it was easier to line up the strip with the lower edge of the scanning area before closing the lid. **Make sure to horizontally center the scoresheet** (the long edge of the scoresheet should be centered with the long edge of the flatbed scanner’s scanning area) to avoid having the edges of the strip being cut off, as this could affect the timing of the song.

- **Place your JPEG scans within the "Scans" subfolder** of the working folder (the folder where the **MusicReader** executable is located is the working folder).

- The default settings should work well in most cases, and every setting is explained in detail in the command-line interface menus of **MusicReader**, with the default values being specified in every case.


Happy (analog) composing with your new AAW (Analog Audio Workstation)!
"""

    LICENSE_STRING = """Copyright (c) 2026 The MusicReader Author

GNU AFFERO GENERAL PUBLIC LICENSE
                       Version 3, 19 November 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU Affero General Public License is a free, copyleft license for
software and other kinds of works, specifically designed to ensure
cooperation with the community in the case of network server software.

  The licenses for most software and other practical works are designed
to take away your freedom to share and change the works.  By contrast,
our General Public Licenses are intended to guarantee your freedom to
share and change all versions of a program--to make sure it remains free
software for all its users.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
them if you wish), that you receive source code or can get it if you
want it, that you can change the software or use pieces of it in new
free programs, and that you know you can do these things.

  Developers that use our General Public Licenses protect your rights
with two steps: (1) assert copyright on the software, and (2) offer
you this License which gives you legal permission to copy, distribute
and/or modify the software.

  A secondary benefit of defending all users' freedom is that
improvements made in alternate versions of the program, if they
receive widespread use, become available for other developers to
incorporate.  Many developers of free software are heartened and
encouraged by the resulting cooperation.  However, in the case of
software used on network servers, this result may fail to come about.
The GNU General Public License permits making a modified version and
letting the public access it on a server without ever releasing its
source code to the public.

  The GNU Affero General Public License is designed specifically to
ensure that, in such cases, the modified source code becomes available
to the community.  It requires the operator of a network server to
provide the source code of the modified version running there to the
users of that server.  Therefore, public use of a modified version, on
a publicly accessible server, gives the public access to the source
code of the modified version.

  An older license, called the Affero General Public License and
published by Affero, was designed to accomplish similar goals.  This is
a different license, not a version of the Affero GPL, but Affero has
released a new version of the Affero GPL which permits relicensing under
this license.

  The precise terms and conditions for copying, distribution and
modification follow.

                       TERMS AND CONDITIONS

  0. Definitions.

  "This License" refers to version 3 of the GNU Affero General Public License.

  "Copyright" also means copyright-like laws that apply to other kinds of
works, such as semiconductor masks.

  "The Program" refers to any copyrightable work licensed under this
License.  Each licensee is addressed as "you".  "Licensees" and
"recipients" may be individuals or organizations.

  To "modify" a work means to copy from or adapt all or part of the work
in a fashion requiring copyright permission, other than the making of an
exact copy.  The resulting work is called a "modified version" of the
earlier work or a work "based on" the earlier work.

  A "covered work" means either the unmodified Program or a work based
on the Program.

  To "propagate" a work means to do anything with it that, without
permission, would make you directly or secondarily liable for
infringement under applicable copyright law, except executing it on a
computer or modifying a private copy.  Propagation includes copying,
distribution (with or without modification), making available to the
public, and in some countries other activities as well.

  To "convey" a work means any kind of propagation that enables other
parties to make or receive copies.  Mere interaction with a user through
a computer network, with no transfer of a copy, is not conveying.

  An interactive user interface displays "Appropriate Legal Notices"
to the extent that it includes a convenient and prominently visible
feature that (1) displays an appropriate copyright notice, and (2)
tells the user that there is no warranty for the work (except to the
extent that warranties are provided), that licensees may convey the
work under this License, and how to view a copy of this License.  If
the interface presents a list of user commands or options, such as a
menu, a prominent item in the list meets this criterion.

  1. Source Code.

  The "source code" for a work means the preferred form of the work
for making modifications to it.  "Object code" means any non-source
form of a work.

  A "Standard Interface" means an interface that either is an official
standard defined by a recognized standards body, or, in the case of
interfaces specified for a particular programming language, one that
is widely used among developers working in that language.

  The "System Libraries" of an executable work include anything, other
than the work as a whole, that (a) is included in the normal form of
packaging a Major Component, but which is not part of that Major
Component, and (b) serves only to enable use of the work with that
Major Component, or to implement a Standard Interface for which an
implementation is available to the public in source code form.  A
"Major Component", in this context, means a major essential component
(kernel, window system, and so on) of the specific operating system
(if any) on which the executable work runs, or a compiler used to
produce the work, or an object code interpreter used to run it.

  The "Corresponding Source" for a work in object code form means all
the source code needed to generate, install, and (for an executable
work) run the object code and to modify the work, including scripts to
control those activities.  However, it does not include the work's
System Libraries, or general-purpose tools or generally available free
programs which are used unmodified in performing those activities but
which are not part of the work.  For example, Corresponding Source
includes interface definition files associated with source files for
the work, and the source code for shared libraries and dynamically
linked subprograms that the work is specifically designed to require,
such as by intimate data communication or control flow between those
subprograms and other parts of the work.

  The Corresponding Source need not include anything that users
can regenerate automatically from other parts of the Corresponding
Source.

  The Corresponding Source for a work in source code form is that
same work.

  2. Basic Permissions.

  All rights granted under this License are granted for the term of
copyright on the Program, and are irrevocable provided the stated
conditions are met.  This License explicitly affirms your unlimited
permission to run the unmodified Program.  The output from running a
covered work is covered by this License only if the output, given its
content, constitutes a covered work.  This License acknowledges your
rights of fair use or other equivalent, as provided by copyright law.

  You may make, run and propagate covered works that you do not
convey, without conditions so long as your license otherwise remains
in force.  You may convey covered works to others for the sole purpose
of having them make modifications exclusively for you, or provide you
with facilities for running those works, provided that you comply with
the terms of this License in conveying all material for which you do
not control copyright.  Those thus making or running the covered works
for you must do so exclusively on your behalf, under your direction
and control, on terms that prohibit them from making any copies of
your copyrighted material outside their relationship with you.

  Conveying under any other circumstances is permitted solely under
the conditions stated below.  Sublicensing is not allowed; section 10
makes it unnecessary.

  3. Protecting Users' Legal Rights From Anti-Circumvention Law.

  No covered work shall be deemed part of an effective technological
measure under any applicable law fulfilling obligations under article
11 of the WIPO copyright treaty adopted on 20 December 1996, or
similar laws prohibiting or restricting circumvention of such
measures.

  When you convey a covered work, you waive any legal power to forbid
circumvention of technological measures to the extent such circumvention
is effected by exercising rights under this License with respect to
the covered work, and you disclaim any intention to limit operation or
modification of the work as a means of enforcing, against the work's
users, your or third parties' legal rights to forbid circumvention of
technological measures.

  4. Conveying Verbatim Copies.

  You may convey verbatim copies of the Program's source code as you
receive it, in any medium, provided that you conspicuously and
appropriately publish on each copy an appropriate copyright notice;
keep intact all notices stating that this License and any
non-permissive terms added in accord with section 7 apply to the code;
keep intact all notices of the absence of any warranty; and give all
recipients a copy of this License along with the Program.

  You may charge any price or no price for each copy that you convey,
and you may offer support or warranty protection for a fee.

  5. Conveying Modified Source Versions.

  You may convey a work based on the Program, or the modifications to
produce it from the Program, in the form of source code under the
terms of section 4, provided that you also meet all of these conditions:

    a) The work must carry prominent notices stating that you modified
    it, and giving a relevant date.

    b) The work must carry prominent notices stating that it is
    released under this License and any conditions added under section
    7.  This requirement modifies the requirement in section 4 to
    "keep intact all notices".

    c) You must license the entire work, as a whole, under this
    License to anyone who comes into possession of a copy.  This
    License will therefore apply, along with any applicable section 7
    additional terms, to the whole of the work, and all its parts,
    regardless of how they are packaged.  This License gives no
    permission to license the work in any other way, but it does not
    invalidate such permission if you have separately received it.

    d) If the work has interactive user interfaces, each must display
    Appropriate Legal Notices; however, if the Program has interactive
    interfaces that do not display Appropriate Legal Notices, your
    work need not make them do so.

  A compilation of a covered work with other separate and independent
works, which are not by their nature extensions of the covered work,
and which are not combined with it such as to form a larger program,
in or on a volume of a storage or distribution medium, is called an
"aggregate" if the compilation and its resulting copyright are not
used to limit the access or legal rights of the compilation's users
beyond what the individual works permit.  Inclusion of a covered work
in an aggregate does not cause this License to apply to the other
parts of the aggregate.

  6. Conveying Non-Source Forms.

  You may convey a covered work in object code form under the terms
of sections 4 and 5, provided that you also convey the
machine-readable Corresponding Source under the terms of this License,
in one of these ways:

    a) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by the
    Corresponding Source fixed on a durable physical medium
    customarily used for software interchange.

    b) Convey the object code in, or embodied in, a physical product
    (including a physical distribution medium), accompanied by a
    written offer, valid for at least three years and valid for as
    long as you offer spare parts or customer support for that product
    model, to give anyone who possesses the object code either (1) a
    copy of the Corresponding Source for all the software in the
    product that is covered by this License, on a durable physical
    medium customarily used for software interchange, for a price no
    more than your reasonable cost of physically performing this
    conveying of source, or (2) access to copy the
    Corresponding Source from a network server at no charge.

    c) Convey individual copies of the object code with a copy of the
    written offer to provide the Corresponding Source.  This
    alternative is allowed only occasionally and noncommercially, and
    only if you received the object code with such an offer, in accord
    with subsection 6b.

    d) Convey the object code by offering access from a designated
    place (gratis or for a charge), and offer equivalent access to the
    Corresponding Source in the same way through the same place at no
    further charge.  You need not require recipients to copy the
    Corresponding Source along with the object code.  If the place to
    copy the object code is a network server, the Corresponding Source
    may be on a different server (operated by you or a third party)
    that supports equivalent copying facilities, provided you maintain
    clear directions next to the object code saying where to find the
    Corresponding Source.  Regardless of what server hosts the
    Corresponding Source, you remain obligated to ensure that it is
    available for as long as needed to satisfy these requirements.

    e) Convey the object code using peer-to-peer transmission, provided
    you inform other peers where the object code and Corresponding
    Source of the work are being offered to the general public at no
    charge under subsection 6d.

  A separable portion of the object code, whose source code is excluded
from the Corresponding Source as a System Library, need not be
included in conveying the object code work.

  A "User Product" is either (1) a "consumer product", which means any
tangible personal property which is normally used for personal, family,
or household purposes, or (2) anything designed or sold for incorporation
into a dwelling.  In determining whether a product is a consumer product,
doubtful cases shall be resolved in favor of coverage.  For a particular
product received by a particular user, "normally used" refers to a
typical or common use of that class of product, regardless of the status
of the particular user or of the way in which the particular user
actually uses, or expects or is expected to use, the product.  A product
is a consumer product regardless of whether the product has substantial
commercial, industrial or non-consumer uses, unless such uses represent
the only significant mode of use of the product.

  "Installation Information" for a User Product means any methods,
procedures, authorization keys, or other information required to install
and execute modified versions of a covered work in that User Product from
a modified version of its Corresponding Source.  The information must
suffice to ensure that the continued functioning of the modified object
code is in no case prevented or interfered with solely because
modification has been made.

  If you convey an object code work under this section in, or with, or
specifically for use in, a User Product, and the conveying occurs as
part of a transaction in which the right of possession and use of the
User Product is transferred to the recipient in perpetuity or for a
fixed term (regardless of how the transaction is characterized), the
Corresponding Source conveyed under this section must be accompanied
by the Installation Information.  But this requirement does not apply
if neither you nor any third party retains the ability to install
modified object code on the User Product (for example, the work has
been installed in ROM).

  The requirement to provide Installation Information does not include a
requirement to continue to provide support service, warranty, or updates
for a work that has been modified or installed by the recipient, or for
the User Product in which it has been modified or installed.  Access to a
network may be denied when the modification itself materially and
adversely affects the operation of the network or violates the rules and
protocols for communication across the network.

  Corresponding Source conveyed, and Installation Information provided,
in accord with this section must be in a format that is publicly
documented (and with an implementation available to the public in
source code form), and must require no special password or key for
unpacking, reading or copying.

  7. Additional Terms.

  "Additional permissions" are terms that supplement the terms of this
License by making exceptions from one or more of its conditions.
Additional permissions that are applicable to the entire Program shall
be treated as though they were included in this License, to the extent
that they are valid under applicable law.  If additional permissions
apply only to part of the Program, that part may be used separately
under those permissions, but the entire Program remains governed by
this License without regard to the additional permissions.

  When you convey a copy of a covered work, you may at your option
remove any additional permissions from that copy, or from any part of
it.  (Additional permissions may be written to require their own
removal in certain cases when you modify the work.)  You may place
additional permissions on material, added by you to a covered work,
for which you have or can give appropriate copyright permission.

  Notwithstanding any other provision of this License, for material you
add to a covered work, you may (if authorized by the copyright holders of
that material) supplement the terms of this License with terms:

    a) Disclaiming warranty or limiting liability differently from the
    terms of sections 15 and 16 of this License; or

    b) Requiring preservation of specified reasonable legal notices or
    author attributions in that material or in the Appropriate Legal
    Notices displayed by works containing it; or

    c) Prohibiting misrepresentation of the origin of that material, or
    requiring that modified versions of such material be marked in
    reasonable ways as different from the original version; or

    d) Limiting the use for publicity purposes of names of licensors or
    authors of the material; or

    e) Declining to grant rights under trademark law for use of some
    trade names, trademarks, or service marks; or

    f) Requiring indemnification of licensors and authors of that
    material by anyone who conveys the material (or modified versions of
    it) with contractual assumptions of liability to the recipient, for
    any liability that these contractual assumptions directly impose on
    those licensors and authors.

  All other non-permissive additional terms are considered "further
restrictions" within the meaning of section 10.  If the Program as you
received it, or any part of it, contains a notice stating that it is
governed by this License along with a term that is a further
restriction, you may remove that term.  If a license document contains
a further restriction but permits relicensing or conveying under this
License, you may add to a covered work material governed by the terms
of that license document, provided that the further restriction does
not survive such relicensing or conveying.

  If you add terms to a covered work in accord with this section, you
must place, in the relevant source files, a statement of the
additional terms that apply to those files, or a notice indicating
where to find the applicable terms.

  Additional terms, permissive or non-permissive, may be stated in the
form of a separately written license, or stated as exceptions;
the above requirements apply either way.

  8. Termination.

  You may not propagate or modify a covered work except as expressly
provided under this License.  Any attempt otherwise to propagate or
modify it is void, and will automatically terminate your rights under
this License (including any patent licenses granted under the third
paragraph of section 11).

  However, if you cease all violation of this License, then your
license from a particular copyright holder is reinstated (a)
provisionally, unless and until the copyright holder explicitly and
finally terminates your license, and (b) permanently, if the copyright
holder fails to notify you of the violation by some reasonable means
prior to 60 days after the cessation.

  Moreover, your license from a particular copyright holder is
reinstated permanently if the copyright holder notifies you of the
violation by some reasonable means, this is the first time you have
received notice of violation of this License (for any work) from that
copyright holder, and you cure the violation prior to 30 days after
your receipt of the notice.

  Termination of your rights under this section does not terminate the
licenses of parties who have received copies or rights from you under
this License.  If your rights have been terminated and not permanently
reinstated, you do not qualify to receive new licenses for the same
material under section 10.

  9. Acceptance Not Required for Having Copies.

  You are not required to accept this License in order to receive or
run a copy of the Program.  Ancillary propagation of a covered work
occurring solely as a consequence of using peer-to-peer transmission
to receive a copy likewise does not require acceptance.  However,
nothing other than this License grants you permission to propagate or
modify any covered work.  These actions infringe copyright if you do
not accept this License.  Therefore, by modifying or propagating a
covered work, you indicate your acceptance of this License to do so.

  10. Automatic Licensing of Downstream Recipients.

  Each time you convey a covered work, the recipient automatically
receives a license from the original licensors, to run, modify and
propagate that work, subject to this License.  You are not responsible
for enforcing compliance by third parties with this License.

  An "entity transaction" is a transaction transferring control of an
organization, or substantially all assets of one, or subdividing an
organization, or merging organizations.  If propagation of a covered
work results from an entity transaction, each party to that
transaction who receives a copy of the work also receives whatever
licenses to the work the party's predecessor in interest had or could
give under the previous paragraph, plus a right to possession of the
Corresponding Source of the work from the predecessor in interest, if
the predecessor has it or can get it with reasonable efforts.

  You may not impose any further restrictions on the exercise of the
rights granted or affirmed under this License.  For example, you may
not impose a license fee, royalty, or other charge for exercise of
rights granted under this License, and you may not initiate litigation
(including a cross-claim or counterclaim in a lawsuit) alleging that
any patent claim is infringed by making, using, selling, offering for
sale, or importing the Program or any portion of it.

  11. Patents.

  A "contributor" is a copyright holder who authorizes use under this
License of the Program or a work on which the Program is based.  The
work thus licensed is called the contributor's "contributor version".

  A contributor's "essential patent claims" are all patent claims
owned or controlled by the contributor, whether already acquired or
hereafter acquired, that would be infringed by some manner, permitted
by this License, of making, using, or selling its contributor version,
but do not include claims that would be infringed only as a
consequence of further modification of the contributor version.  For
purposes of this definition, "control" includes the right to grant
patent sublicenses in a manner consistent with the requirements of
this License.

  Each contributor grants you a non-exclusive, worldwide, royalty-free
patent license under the contributor's essential patent claims, to
make, use, sell, offer for sale, import and otherwise run, modify and
propagate the contents of its contributor version.

  In the following three paragraphs, a "patent license" is any express
agreement or commitment, however denominated, not to enforce a patent
(such as an express permission to practice a patent or covenant not to
sue for patent infringement).  To "grant" such a patent license to a
party means to make such an agreement or commitment not to enforce a
patent against the party.

  If you convey a covered work, knowingly relying on a patent license,
and the Corresponding Source of the work is not available for anyone
to copy, free of charge and under the terms of this License, through a
publicly available network server or other readily accessible means,
then you must either (1) cause the Corresponding Source to be so
available, or (2) arrange to deprive yourself of the benefit of the
patent license for this particular work, or (3) arrange, in a manner
consistent with the requirements of this License, to extend the patent
license to downstream recipients.  "Knowingly relying" means you have
actual knowledge that, but for the patent license, your conveying the
covered work in a country, or your recipient's use of the covered work
in a country, would infringe one or more identifiable patents in that
country that you have reason to believe are valid.

  If, pursuant to or in connection with a single transaction or
arrangement, you convey, or propagate by procuring conveyance of, a
covered work, and grant a patent license to some of the parties
receiving the covered work authorizing them to use, propagate, modify
or convey a specific copy of the covered work, then the patent license
you grant is automatically extended to all recipients of the covered
work and works based on it.

  A patent license is "discriminatory" if it does not include within
the scope of its coverage, prohibits the exercise of, or is
conditioned on the non-exercise of one or more of the rights that are
specifically granted under this License.  You may not convey a covered
work if you are a party to an arrangement with a third party that is
in the business of distributing software, under which you make payment
to the third party based on the extent of your activity of conveying
the work, and under which the third party grants, to any of the
parties who would receive the covered work from you, a discriminatory
patent license (a) in connection with copies of the covered work
conveyed by you (or copies made from those copies), or (b) primarily
for and in connection with specific products or compilations that
contain the covered work, unless you entered into that arrangement,
or that patent license was granted, prior to 28 March 2007.

  Nothing in this License shall be construed as excluding or limiting
any implied license or other defenses to infringement that may
otherwise be available to you under applicable patent law.

  12. No Surrender of Others' Freedom.

  If conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot convey a
covered work so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you may
not convey it at all.  For example, if you agree to terms that obligate you
to collect a royalty for further conveying from those to whom you convey
the Program, the only way you could satisfy both those terms and this
License would be to refrain entirely from conveying the Program.

  13. Remote Network Interaction; Use with the GNU General Public License.

  Notwithstanding any other provision of this License, if you modify the
Program, your modified version must prominently offer all users
interacting with it remotely through a computer network (if your version
supports such interaction) an opportunity to receive the Corresponding
Source of your version by providing access to the Corresponding Source
from a network server at no charge, through some standard or customary
means of facilitating copying of software.  This Corresponding Source
shall include the Corresponding Source for any work covered by version 3
of the GNU General Public License that is incorporated pursuant to the
following paragraph.

  Notwithstanding any other provision of this License, you have
permission to link or combine any covered work with a work licensed
under version 3 of the GNU General Public License into a single
combined work, and to convey the resulting work.  The terms of this
License will continue to apply to the part which is the covered work,
but the work with which it is combined will remain governed by version
3 of the GNU General Public License.

  14. Revised Versions of this License.

  The Free Software Foundation may publish revised and/or new versions of
the GNU Affero General Public License from time to time.  Such new versions
will be similar in spirit to the present version, but may differ in detail to
address new problems or concerns.

  Each version is given a distinguishing version number.  If the
Program specifies that a certain numbered version of the GNU Affero General
Public License "or any later version" applies to it, you have the
option of following the terms and conditions either of that numbered
version or of any later version published by the Free Software
Foundation.  If the Program does not specify a version number of the
GNU Affero General Public License, you may choose any version ever published
by the Free Software Foundation.

  If the Program specifies that a proxy can decide which future
versions of the GNU Affero General Public License can be used, that proxy's
public statement of acceptance of a version permanently authorizes you
to choose that version for the Program.

  Later license versions may give you additional or different
permissions.  However, no additional obligations are imposed on any
author or copyright holder as a result of your choosing to follow a
later version.

  15. Disclaimer of Warranty.

  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY
OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM
IS WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

  16. Limitation of Liability.

  IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING
WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MODIFIES AND/OR CONVEYS
THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES, INCLUDING ANY
GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF THE
USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF
DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD
PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS),
EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF
SUCH DAMAGES.

  17. Interpretation of Sections 15 and 16.

  If the disclaimer of warranty and limitation of liability provided
above cannot be given local legal effect according to their terms,
reviewing courts shall apply local law that most closely approximates
an absolute waiver of all civil liability in connection with the
Program, unless a warranty or assumption of liability accompanies a
copy of the Program in return for a fee.

                     END OF TERMS AND CONDITIONS

            How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
state the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

Also add information on how to contact you by electronic and paper mail.

  If your software can interact with users remotely through a computer
network, you should also make sure that it provides a way for users to
get its source.  For example, if your program is a web application, its
interface could display a "Source" link that leads users to an archive
of the code.  There are many ways you could offer source, and different
solutions will be better for different programs; see section 13 for the
specific requirements.

  You should also get your employer (if you work as a programmer) or school,
if any, to sign a "copyright disclaimer" for the program, if necessary.
For more information on this, and how to apply and follow the GNU AGPL, see
<https://www.gnu.org/licenses/>.
"""

    #Delete any mention of "README_STRING" or "LICENSE_STRING"
    #and "SOURCE_CODE_STRING" from "SOURCE_CODE_STRING", as you 
    #only want the Python code in there. Also, make sure to use
    #a raw string (r""" """) in order to avoid interpreting 
    #backslashes ("\") as escape characters.
    SOURCE_CODE_STRING = textwrap.dedent(r"""import copy
import cv2
from datetime import datetime
import glob
import json
import math
import mido
from mido import Message, MetaMessage, MidiFile, MidiTrack
import numpy as np
import os
import re
import shutil
import signal
import sys
import tempfile
import textwrap
import time
import traceback


#The "clear_screen()" function will clear the CLI screen
#using the appropriate command depending on the operating system.
def clear_screen():
    #'nt' is for Windows, 'posix is for Linux/Raspberry Pi/macOS (else statement)
    os.system('cls' if os.name == 'nt' else 'clear')

#The Signal Interrupt (SIGINT) handler will
#call the "signal_interrupt_signal_handler()" function 
#when the user presses on CTRL + C to exit the app.

#The function "signal_interrupt_signal_handler()" will call
#"sys.exit(0)" to exit the program normally.
def signal_interrupt_signal_handler(sig, frame):
    sys.exit(0)

#The function "write_entry_in_error_log()" will write 
#the full technical traceback error to the error log.
def write_entry_in_error_log():
    with open("ERROR LOG.txt", "a", encoding="utf-8") as error_log:
        error_log.write(f"\n--- Error at {datetime.now()} ---\n")
        traceback.print_exc(file=error_log)

#The function "display_progress()" will display the progress string in the console
#and return the estimated number of seconds for the code to complete.
def display_progress(current_jpeg_index, first_jpeg_index, last_jpeg_index, start_time, previous_estimated_seconds):
            
    elapsed_seconds = time.perf_counter() - start_time
    #divmod returns (minutes, remaining_seconds)
    mins, secs = divmod(round(elapsed_seconds), 60)
    time_string = f"{mins:02}:{secs:02}"
    eta_string = ""

    #If the MIDI file will only be comprised of one scoresheet 
    #scan, then the "percent_completion" will be 100% after 
    #processing that JPEG file (so as to avoid "Division 
    #by Zero" errors).
    if last_jpeg_index - first_jpeg_index == 0:
        percent_completion = 100
        eta_string = f" ETA: 00:00\n"
    else:
        #The percent completion is calculated by dividing the difference between the current JPEG index
        #and the first JPEG index by the total number of JPEG files to be processed, which is itself
        #calculated by subtracting the first JPEG index from the last JPEG index. The resulting quotient 
        #is multiplied by 100 and then rounded when printed on-screen.
        percent_completion = (current_jpeg_index-first_jpeg_index)/(last_jpeg_index-first_jpeg_index) * 100

    #The previous estimation of the remaining number of seconds is stored in the variable
    #"previous_estimated_seconds" and will be used instead of the current calculation
    #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
    #its estimation.
    estimated_seconds = previous_estimated_seconds
    #A delay of 3 JPEG files is used to be able to gather a somewhat accurate value
    #of the elapsed time for a given percent completion value.
    if (last_jpeg_index > first_jpeg_index + 3 and current_jpeg_index > first_jpeg_index + 3):
        #The estimated number of seconds left is calculated by doing the cross-multiplication between
        #the number of percentage points left to reach completion ("100 - percent_completion") 
        #and the elapsed time for the current percent completion.
        estimated_seconds = round((100 - percent_completion) * elapsed_seconds / percent_completion)
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        if (previous_estimated_seconds != 0 and estimated_seconds > previous_estimated_seconds):
            estimated_seconds = previous_estimated_seconds

        #If the current JPEG index is the last JPEG index,
        #then the remaining time is zero seconds (" ETA: 00:00").
        if (current_jpeg_index == last_jpeg_index):
            percent_completion = 100
            eta_string = f" ETA: 00:00\n"
        #We do not want to display negative times, hence the
        #condition ("elif (estimated_seconds > 0)").
        elif (estimated_seconds > 0):
            eta_mins, eta_secs = divmod(round(estimated_seconds), 60)
            eta_string = f" ETA: {eta_mins:02}:{eta_secs:02}"

    #"\r" resets the line
    sys.stdout.write(f"\rCompleted JPEG file: {current_jpeg_index+1} of {last_jpeg_index+1} ({round(percent_completion)}%) Time: {time_string}{eta_string}")

    return estimated_seconds

#The function "get_terminal_dimensions()" will return the number of columns 
#and rows in the console, to allow to properly format the text and dividers.
def get_terminal_dimensions():
    #Detect columns (width) and lines (height)
    #Returns a named tuple; default fallback is (80, 24)
    size = shutil.get_terminal_size(fallback=(80, 24))
    return int(size.columns * 0.75), int(size.lines)

#The function "is_valid_positive_non_zero_int_or_float" will validate the data 
#stored in the dictionary obtained from the "json_settings.json" file to make 
#sure it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number either an integer or a float and also exclude negative and zero 
#numbers "number <= 0". It will return "True" if the number is a valid
#("else" statement) integer and "False" otherwise ("if" statement).
def is_valid_positive_non_zero_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)) or number <= 0: 
        return False
    else:
        return True
        
#The function "is_valid_positive_int_or_float" will validate the data stored 
#in the dictionary obtained from the "json_settings.json" file to make sure 
#it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number is either a positive integer or a float. It will return 
#"True" if the number is a valid ("else" statement) integer and "False" 
#otherwise ("if" statement).   
def is_valid_positive_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)) or number < 0:
        return False
    else:
        return True

#The function "is_valid_non_negative_int_or_float" will validate the data stored 
#in the dictionary obtained from the "json_settings.json" file to make sure 
#it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number is either an integer or a float and also exclude negative 
#numbers "number < 0". It will return "True" if the number is a valid
#("if" statement) integer and "False" otherwise ("else" statement).   
def is_valid_non_negative_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)) or number < 0:
        return False
    else:
        return True
    
#The function "is_valid_int_or_float" will validate the data stored 
#in the dictionary obtained from the "json_settings.json" file to make sure 
#it is not "NaN" or "Infinity" (not "math.isfinite(number)") and make sure 
#that the number is either an integer or a float. It will return "True" if 
#the number is a valid ("else" statement) integer and "False" otherwise 
#("if" statement).   
def is_valid_int_or_float(number):
    if not math.isfinite(number) or not isinstance(number, (int, float)):
        return False
    else:
        return True
        
#The function "atomic_save()" will create a temporary JSON file with the updated changes.
#If the files is created successfully, then the files will be swapped. If a problem is 
#encountered, the temp file will be unlinked and an error log will be reported.
def atomic_save(json_settings_dictionary, json_settings_file_path_name):
    #Create a temp file in the same directory
    temp_dir = os.path.dirname(json_settings_file_path_name) or "."
    json_file_descriptor, temp_path = tempfile.mkstemp(dir=temp_dir, text=True)

    try:
        with os.fdopen(json_file_descriptor, "w", encoding="utf-8") as f:
            #Write the default values found in "json_settings_dictionary" in the empty JSON file, 
            #with four space indentations to make it more human-readable.
            json.dump(json_settings_dictionary, f, indent=4)
            #Ensure the data is flushed to hardware.
            f.flush()
            #"os.fsync(f.fileno())" is required to force the OS to physically commit
            #every bit of information to the hardware storage right now, preventing 
            #a situation where an empty file might be created if the computer crashed
            #before the OS finished waiting before committing the file to memory. 
            os.fsync(f.fileno())
        
        #Swap the files only if the temp file was successfully generated (Atomic security)
        os.replace(temp_path, json_settings_file_path_name)
    except Exception as e:
        #Clean up temp file if something goes wrong BEFORE the swap
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        #The function "write_entry_in_error_log()" will write 
        #the full technical traceback error to the error log.
        write_entry_in_error_log()

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
       
        print("\n" + "=" * columns)
        print("CRITICAL ERRROR ENCOUNTERED")
        print("\nDetails:", e)
        print("\n" + "=" * columns)

        #Exit with error code
        sys.exit(1)

#The function "rotate_image()" will rotate the "img"
#numpy array using the "getRotationMatrix2D()" and 
#"warpAffine()" OpenCV methods. 
def rotate_image(img, color_img, rows, cols, angle):
    #Rotate the image according to OpenCV's documentation,
    #where cols-1 and rows-1 are the coordinate limits (zero-indexed)

    #1. Generate the original rotation matrix around the true center
    #We need to invert the specified rotation angle to factor in that 
    #clockwise rotations have a negative angle in mathematics
    M = cv2.getRotationMatrix2D(((cols-1)/2.0, (rows-1)/2.0), -angle, 1.0)
    
    #2. Calculate the absolute values of sine and cosine from the rotation matrix
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    
    #3. Calculate the new bounding dimensions (the new limits for cols and rows)
    new_cols = int((rows * sin) + (cols * cos))
    new_rows = int((rows * cos) + (cols * sin))
    
    #4. Adjust the translation column (the third column of the rotation matrix M).
    #This offsets the center of rotation to the center of the new, larger canvas.
    M[0, 2] += (new_cols / 2.0) - ((cols - 1) / 2.0)
    M[1, 2] += (new_rows / 2.0) - ((rows - 1) / 2.0)
    
    #5. Pass the newly calculated size into warpAffine
    #"BORDER_CONSTANT" will fill newly exposed background area with black (0,0,0).
    #"INTER_CUBIC" will allow better results with floating point rotation angles.
    img = cv2.warpAffine(img, M, (new_cols, new_rows), 
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0),
        flags=cv2.INTER_CUBIC)
    
    color_img = cv2.warpAffine(color_img, M, (new_cols, new_rows), 
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0),
        flags=cv2.INTER_CUBIC)
    
    return img, color_img, new_rows, new_cols

#The function "get_horizontal_projection_profile()" will get the horizontal projection 
#profile by first filtering the "img" array with the "np.where()" method, such that 
#white pixels have a value of zero and non-white pixels have a value of one. This 
#will allow to get the horizontal projection profile by adding up all the rows for 
#each column, thus generating a 1D horizontal array. The left and right edges of 
#the score sheet will be detected, as they will be the first and last elements 
#of the horizontal projection profile where the pixels will not be almost exclusively 
#black. 
def get_horizontal_projection_profile(img, black_pixel_threshold_percentage, rows, undetectable_scoresheet_error_string):
    
    #The non-white pixels will be set to the value of one and white pixels 
    #will have a value of zero, such that adding white pixels does not 
    #impact the count of non-white pixels.
    img_filtered_for_flattening = np.where(img == 255, 0, 1)
    
    #Add up all the rows for each column to get the horizontal projection profile
    #("np.sum" along the "y" axis at index zero).
    horizontal_projection_profile = np.sum(img_filtered_for_flattening, axis=0)
    
    #A column of pixels to the left of or to the right of the scoresheet would be comprised of 
    #entirely black pixels, and so the sum of these pixels in "horizontal_projection_profile"
    #would be almost equal to the height of the rotated image ("rows"). Conversely, any columns 
    #making up the score sheet contain some white pixels and the sum would be much lower than "rows".
    non_black_pixels_horizontal_projection_profile = np.where(horizontal_projection_profile < (black_pixel_threshold_percentage/100)*rows)[0]
    black_pixels_horizontal_projection_profile = np.where(horizontal_projection_profile >= (black_pixel_threshold_percentage/100)*rows)[0]
    
    #If a scoresheet is visible in the form of some non-black pixels
    #then the "if" statement below will run. If that is not the case,
    #then the user has probably set a too stringent value for the 
    #"paper_color_grayscale_filter_threshold" (too high, meaning that 
    #no pixels were lighter than the threshold and consequently all 
    #pixels were set to black).
    if non_black_pixels_horizontal_projection_profile.size != 0:
    
        left_x_scoresheet = non_black_pixels_horizontal_projection_profile[0]
        right_x_scoresheet = non_black_pixels_horizontal_projection_profile[-1]            
        
        scoresheet_width = right_x_scoresheet - left_x_scoresheet
        
    #If a scoresheet is visible in the form of some non-black pixels
    #then the "if" statement below will run. If that is not the case,
    #then the user has probably set a too stringent value for the 
    #"paper_color_grayscale_filter_threshold" (too high, meaning that 
    #no pixels were lighter than the threshold and consequently all 
    #pixels were set to black).
    else:
        print(undetectable_scoresheet_error_string)
        input(press_any_key_string)
        sys.exit(1)
        
    return (img_filtered_for_flattening, 
            horizontal_projection_profile, 
            non_black_pixels_horizontal_projection_profile, 
            black_pixels_horizontal_projection_profile, 
            left_x_scoresheet, 
            right_x_scoresheet,
            scoresheet_width)

#The function "get_file_name_horizontal_vertical_shift_manual_override_strings()"
#will return the horizontal and vertical shift manual override pixel values, that 
#were extracted from the file name and the file name where these have been removed
#(e.g., 5, -2, "track_01" for the file name "track_01+ (v=5, h=-2)"). Should there 
#be no such manual override parenthesized expressions in "file_name_without_extension", 
#then zero will be returned for the horizontal and vertical shift manual override pixel 
#values, along with the original value of "file_name_without_extension".
def get_file_name_horizontal_vertical_shift_manual_override_strings(full_file_name):
    #Returns the final component of the path
    file_name_with_extension = os.path.basename(full_file_name)
    file_name_without_extension, extension = os.path.splitext(file_name_with_extension)
    
    horizontal_vertical_shift_manual_override_strings = (
        #The search pattern queries for a "v" or "h" (uppercased or lowercased), followed by zero or more spaces, 
        #zero or one equal sign, zero or more spaces, zero or one minus sign, one or more digits, zero or more spaces, 
        #a comma, and the same pattern for the second parameter.
        re.findall(r"\([vVhH][ ]*[=]?[ ]*[-]?[\d]+[ ]*,[ ]*[vVhH][ ]*[=]?[ ]*[-]?[\d]+\)", file_name_without_extension))
    #If a horizontal and vertical shift manual override string was found, then the returned list will be indexed 
    #at the first index (zero) to return it and the original file name will have this substring removed using a 
    #"re.sub()" method.    
    if (horizontal_vertical_shift_manual_override_strings != [] and 
        horizontal_vertical_shift_manual_override_strings[0].count(",") == 1):
        file_name_without_extension = re.sub(re.escape(horizontal_vertical_shift_manual_override_strings[0]), "", file_name_without_extension).strip()
        horizontal_vertical_shift_split_strings_at_comma = horizontal_vertical_shift_manual_override_strings[0].split(",")
        
        #The values of "horizontal_shift_pixels_candidate" and "vertical_shift_pixels_candidate",
        #both initialized to "None" will be set to the extracted pixel shifts from the parenthesized 
        #expression, after it was split at the comma character. If no digit patterns were found in the 
        #split strings, then zero will be returned for the horizontal and vertical shift manual override 
        #pixel values
        horizontal_shift_pixels_candidate = None 
        vertical_shift_pixels_candidate = None
        #The digit pattern consists of zero or one minus sign, followed by one or more digits.
        digit_pattern = r"[-]?[\d]+"
        for split_string in horizontal_vertical_shift_split_strings_at_comma:
            #If "h" is in the split string, but  not "v", then it means that this 
            #is the horizontal shift expression.
            if "h" in split_string.lower() and not "v" in split_string.lower():
                horizontal_shift_pixels_candidates = re.findall(digit_pattern, split_string)
                if horizontal_shift_pixels_candidates != []:
                    horizontal_shift_pixels_candidate = int(horizontal_shift_pixels_candidates[0])
            #If "v" is in the split string, but  not "h", then it means that this 
            #is the vertical shift expression.
            elif "v" in split_string.lower() and not "h" in split_string.lower():
                vertical_shift_pixels_candidates = re.findall(digit_pattern, split_string)
                if vertical_shift_pixels_candidates != []:
                    vertical_shift_pixels_candidate = int(vertical_shift_pixels_candidates[0])
        #If both values of the horizontal and vertical shift pixel candidates are 
        #not equal to zero, then they will be returned, along with the value of 
        #"file_name_without_extension".
        if not (horizontal_shift_pixels_candidate == 0 and vertical_shift_pixels_candidate == 0):
            return horizontal_shift_pixels_candidate, vertical_shift_pixels_candidate, file_name_without_extension
        #Otherwise a value of zero for each shift will be returned, 
        #along with the value of "file_name_without_extension".
        else:
            return 0, 0, file_name_without_extension
    #Otherwise a value of zero for each shift will be returned, 
    #along with the value of "file_name_without_extension".
    else:
        return 0, 0, file_name_without_extension

#The function "load_json_data()" will load the JSON data from file
#and store them in the "json_settings_dictionary", or initialize the
#dictionary based on the values of "json_default_settings_dictionary".
def load_json_data(json_settings_file_path_name): 

    json_default_settings_dictionary = {
            "_comment_1" : dpi_setting_comment_string,
            "Scan Resolution in DPI" : 200,
            
            "_comment_2" : page_rotation_angle_comment_string,
            "Page Rotation Angle" : -90.0,

            "_comment_3" : contrast_level_comment_string,
            "Contrast Level" : 5.0,

            "_comment_4" : brightness_level_comment_string,
            "Brightness Level" : 80,

            "_comment_5" : paper_color_grayscale_filter_threshold_comment_string,
            "Paper Color Grayscale Filter Threshold" : 245,

            "_comment_6" : black_pixel_threshold_percentage_comment_string,
            "Black Pixel Threshold Percentage" : 95,

            "_comment_7" : white_pixel_threshold_percentage_comment_string,
            "White Pixel Threshold Percentage" : 99,
            #The value of "white_pixel_threshold_percentage_slice"
            #needs to be lower than that of "white_pixel_threshold_percentage",
            #as there are fewer pixels to flatten in the slices, meaning that it 
            #is much more difficult to reach the 99% threshold for inclusion in 
            #the list of white pixels. By having a lower threshold around 80%,
            #it means that even if there are a few non-white pixels in the slice,
            #that flattened row or column will be detected as a white pixel.
            "_comment_8" : white_pixel_threshold_percentage_slice_comment_string,
            "White Pixel Threshold Percentage for Slices" : 80,

            "_comment_9" : punched_hole_diameter_percentage_threshold_comment_string,
            "Punched Hole Diameter Percentage Threshold" : 80,

            "_comment_10" : punched_hole_percent_overlap_threshold_comment_string,
            "Punched Hole Percentage Overlap Threshold" : 25,

            "_comment_11" : punched_hole_diameter_mm_comment_string,
            "Punched Hole Diameter in Millimeters" : 2.5,

            "_comment_12" : scoresheet_grid_height_mm_comment_string,
            "Scoresheet Grid Height in Millimeters" : 58.0,

            "_comment_13" : number_of_notes_comment_string,
            "Number of Notes" : 30,
    
            "_comment_14" : tempo_bpm_comment_string,
            "Tempo bpm" : 120,

            "_comment_15" : ticks_per_quarter_note_comment_string,
            "Ticks per Quarter Note" : 960,
            
            "_comment_16" : width_of_ten_smallest_measures_mm_comment_string,
            "Width of Ten Successive Smallest Measures in Millimeters" : 40.0,

            "_comment_17" : smallest_measure_duration_denominator_comment_string,
            "Smallest Measure Duration Denominator" : 16,

            "_comment_18" : time_signature_numerator_comment_string,
            "Time Signature Numerator" : 4,

            "_comment_19" : time_signature_denominator_comment_string,
            "Time Signature Denominator" : 4,

            "_comment_20" : leading_silence_milliseconds_comment_string,
            "Leading Silence Duration in Milliseconds" : 250,

            "_comment_21" : trailing_silence_milliseconds_comment_string,
            "Trailing Silence Duration in Milliseconds" : 500,

            "_comment_22" : vertical_shift_pixels_comment_string,
            "Vertical Shift in Pixels" : 0,

            "_comment_23" : horizontal_shift_pixels_comment_string,
            "Horizontal Shift in Pixels" : 0,

            "_comment_24" : midi_velocity_comment_string,
            "Midi Velocity" : 64,

            "_comment_25" : semitone_shift_comment_string,
            "Semitone Shift" : 0,

            "_comment_26" : midi_copyright_string_comment_string,
            "Midi Copyright Metadata String" : "",

            "_comment_27" : midi_comment_comment_string,
            "Midi Comment String" : ""
        }

    need_to_generate_new_json_file = False
    if os.path.isfile(json_settings_file_path_name):
        #A try-except statement is used in case
        #the JSON file is malformed or empty,
        #in which case the Boolean variable
        #"need_to_generate_new_json_file" will
        #be set to "True" and the "if" statement
        #below this one would run.
        try:
            #The "utf-8-sig" encoding handles files with or without a BOM automatically
            with open(json_settings_file_path_name, "r", encoding="utf-8-sig") as f:
                json_settings_dictionary = json.load(f)
        except json.JSONDecodeError:
            need_to_generate_new_json_file = True
    else:
        need_to_generate_new_json_file = True

    if need_to_generate_new_json_file:
        #A deep copy (since it contains a list of deleted pages) of 
        #"json_default_settings_dictionary" is made so as to avoid having
        #both "json_settings_dictionary" and "json_default_settings_dictionary"
        #pointing to the same address.
        json_settings_dictionary = copy.deepcopy(json_default_settings_dictionary)

        #Create a low-level file descriptor (used for atomic saves)
        #The two access flags "os.O_RDWR" and "os.O_CREAT" allow for the file to be 
        #read and written to and created if it doesn't already exist, respectively.
        file_descriptor = os.open(json_settings_file_path_name, os.O_RDWR | os.O_CREAT)
        with os.fdopen(file_descriptor, "w+", encoding="utf-8") as f:
            #Write the default values found in "json_settings_dictionary" in the empty JSON file, 
            #with four space indentations to make it more human-readable.
            json.dump(json_settings_dictionary, f, indent=4)
            #Ensure the data is flushed to hardware.
            f.flush()
            #"os.fsync(f.fileno())" is required to force the OS to physically commit
            #every bit of information to the hardware storage right now, preventing 
            #a situation where an empty file might be created if the computer crashed
            #before the OS finished waiting before committing the file to memory. 
            os.fsync(f.fileno())
    return json_default_settings_dictionary, json_settings_dictionary

#The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
#a menu action dictionary comprised of one character keys and values made up
#of a three-member tuple (action string, function, function arguments).
#The action strings ("value[0]") will be textwrapped and the modified
#dictionary will be returned.
def textwrap_action_strings_in_menu_action_dict(menu_action_dict):
    
    #The function "get_terminal_dimensions()" will return the number of columns 
    #and rows in the console, to allow to properly format the text and dividers.
    columns, lines = get_terminal_dimensions()

    for key, value in menu_action_dict.items():
        value[0] = textwrap.fill(value[0], columns)
    return menu_action_dict

#The function "quit_function()" will call
#"sys.exit()" with the exit code "1" meaning
#"success".
def quit_function():
    sys.exit(1)

#The function "back_to_main_menu_function()"
#will set the Boolean flags "is_in_submenu" and 
#"is_in_sub_submenu" to "False", which will break the submenu
#"while" loops and return to the main menu.
def back_to_main_menu_function(json_settings_dictionary):
    global is_in_submenu 
    global is_in_sub_submenu
    global is_in_sub_sub_submenu
    is_in_submenu = False
    is_in_sub_submenu = False
    is_in_sub_sub_submenu = False    
    return json_settings_dictionary

def back_to_submenu_function(json_settings_dictionary):
    global is_in_sub_submenu
    is_in_sub_submenu = False  
    return json_settings_dictionary

#The "invalid_menu_choice()" function will be called when the
#user enters invalid input in one of the functions called by
#the "run_menu()" function.
def invalid_menu_choice(json_settings_dictionary):
    input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The function "run_menu" will retrieve and call the function
#at the appropriate choice key in the "menu_actions_dict"
def run_menu(menu_actions_dict, json_settings_dictionary):

    for key, (label, _, _) in menu_actions_dict.items():
        print(f"[{key}] {label}")
    
    choice = input("\nSelect an option: ").strip().lower()

    #In case the user just pressed "Enter",
    #"json_settings_dictionary" will be returned
    #(no action, this will avoid an error message).
    if choice == "":
        return json_settings_dictionary
    
    #If you can successfully access the "menu_actions_dict" dictionary
    #with the value of "choice", you then have access to the tuple containing
    #(function label, function, args). Indexing the tuple at the position one
    #gives the function itself, and indexing it at the position 2 gives you the
    #arguments for that function as a list, which must be unpacked with the "*" operator. 
    nested_list = menu_actions_dict.get(choice, [None, invalid_menu_choice, (json_settings_dictionary,)]) 
    return nested_list[1](*nested_list[2])

#The "reset_to_default_setting()" function will reset the setting to its default value
#found while accessing the value of the "json_default_settings_dictionary" dictionary 
#with the key "setting_label_key".
def reset_to_default_setting(setting_label_key, json_settings_dictionary, 
json_default_settings_dictionary, json_settings_file_path_name):
    json_settings_dictionary[setting_label_key] = json_default_settings_dictionary[setting_label_key]
    #The function "atomic_save()" will create a temporary JSON file with the updated changes.
    #If the files is created successfully, then the files will be swapped. If a problem is 
    #encountered, the temp file will be unlinked and an error log will be reported.
    atomic_save(json_settings_dictionary, json_settings_file_path_name)   
    return json_settings_dictionary

#The "set_numeric_setting()" function will set the value of the setting found while accessing
#the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
#value ("setting_value"). 
def set_numeric_setting(setting_value, setting_label_key, json_settings_dictionary, 
json_settings_file_path_name):
    json_settings_dictionary[setting_label_key] = setting_value
    #The function "atomic_save()" will create a temporary JSON file with the updated changes.
    #If the files is created successfully, then the files will be swapped. If a problem is 
    #encountered, the temp file will be unlinked and an error log will be reported.
    atomic_save(json_settings_dictionary, json_settings_file_path_name)   
    return json_settings_dictionary

#The function "generate_midi_file()" will generate the 
#MIDI file and the annotated scoresheet JPEG files.
def generate_midi_file(json_settings_dictionary, json_default_settings_dictionary, cwd):
   
    #An empty line is printed on-screen in order to have the progress 
    #bar display one more line below the main menu.
    print("")
    
    dpi = json_settings_dictionary["Scan Resolution in DPI"]
    #Reset dpi to the default value of 200 if 
    #the JSON data is invalid or under 100.
    if not (is_valid_positive_int_or_float(dpi) and dpi >= 100):
        dpi = int(json_default_settings_dictionary["Scan Resolution in DPI"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        dpi = int(dpi)
    
    user_rotation_angle = json_settings_dictionary["Page Rotation Angle"]
    #As the rotation angle may be positive (counterclockwise) or negative 
    #(clockwise), then the validating function needs to allow for both of 
    #these, hence the use of "is_valid_int_or_float()".
    if not is_valid_int_or_float(user_rotation_angle):
       user_rotation_angle = json_default_settings_dictionary["Page Rotation Angle"]
    
    contrast_level = json_settings_dictionary["Contrast Level"]
    #If the value of "contrast_level" is not a valid 
    #positive integer or float, then it will be reset to its 
    #default value.
    if not is_valid_non_negative_int_or_float(contrast_level):
       contrast_level = float(json_default_settings_dictionary["Contrast Level"])
    #The "contrast_level" needs to be a float value for the contrast operation.
    else:
        contrast_level = float(contrast_level)
    
    color_image_brightness = json_settings_dictionary["Brightness Level"]
    #If the value of "color_image_brightness" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(color_image_brightness) and color_image_brightness <= 100):
       color_image_brightness = int(json_default_settings_dictionary["Brightness Level"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        color_image_brightness = int(color_image_brightness)
    
    paper_color_grayscale_filter_threshold = json_settings_dictionary["Paper Color Grayscale Filter Threshold"]
    #If the value of "paper_color_grayscale_filter_threshold" is not a valid 
    #positive integer or float between 0 and 255, inclusively, then it will be reset to 
    #its default value.
    if not (is_valid_non_negative_int_or_float(paper_color_grayscale_filter_threshold) and 
        paper_color_grayscale_filter_threshold <= 255):
       paper_color_grayscale_filter_threshold = int(json_default_settings_dictionary["Paper Color Grayscale Filter Threshold"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        paper_color_grayscale_filter_threshold = int(paper_color_grayscale_filter_threshold)

    black_pixel_threshold_percentage = json_settings_dictionary["Black Pixel Threshold Percentage"]
    #If the value of "black_pixel_threshold_percentage" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(black_pixel_threshold_percentage) and black_pixel_threshold_percentage <= 100):
       black_pixel_threshold_percentage = int(json_default_settings_dictionary["Black Pixel Threshold Percentage"])
    
    white_pixel_threshold_percentage = json_settings_dictionary["White Pixel Threshold Percentage"]
    #If the value of "white_pixel_threshold_percentage" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(white_pixel_threshold_percentage) and white_pixel_threshold_percentage <= 100):
       white_pixel_threshold_percentage = int(json_default_settings_dictionary["White Pixel Threshold Percentage"])
       
    #The value of "white_pixel_threshold_percentage_slice"
    #needs to be lower than that of "white_pixel_threshold_percentage",
    #as there are fewer pixels to flatten in the slices, meaning that it 
    #is much more difficult to reach the 99% threshold for inclusion in 
    #the list of white pixels. By having a lower threshold around 80%,
    #it means that even if there are a few non-white pixels in the slice,
    #that flattened row or column will be detected as a white pixel. 
    white_pixel_threshold_percentage_slice = json_settings_dictionary["White Pixel Threshold Percentage for Slices"]
    #If the value of "white_pixel_threshold_percentage_slice" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(white_pixel_threshold_percentage_slice) and white_pixel_threshold_percentage_slice <= 100):
       white_pixel_threshold_percentage_slice = int(json_default_settings_dictionary["White Pixel Threshold Percentage for Slices"])
    
    punched_hole_diameter_percentage_threshold = json_settings_dictionary["Punched Hole Diameter Percentage Threshold"]
    #If the value of "punched_hole_diameter_percentage_threshold" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(punched_hole_diameter_percentage_threshold) and punched_hole_diameter_percentage_threshold <= 100):
       punched_hole_diameter_percentage_threshold = int(json_default_settings_dictionary["Punched Hole Diameter Percentage Threshold"])
    
    punched_hole_percent_overlap_threshold = json_settings_dictionary["Punched Hole Percentage Overlap Threshold"]
    #If the value of "punched_hole_percent_overlap_threshold" is not a valid 
    #positive integer or float between 0 and 100, inclusively, 
    #then it will be reset to its default value.
    if not (is_valid_non_negative_int_or_float(punched_hole_percent_overlap_threshold) and punched_hole_percent_overlap_threshold <= 100):
       punched_hole_percent_overlap_threshold = int(json_default_settings_dictionary["Punched Hole Percentage Overlap Threshold"])
    
    punched_hole_diameter_mm = json_settings_dictionary["Punched Hole Diameter in Millimeters"]
    #If the value of "punched_hole_diameter_mm" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(punched_hole_diameter_mm):
       punched_hole_diameter_mm = json_default_settings_dictionary["Punched Hole Diameter in Millimeters"]
       
    scoresheet_grid_height_mm = json_settings_dictionary["Scoresheet Grid Height in Millimeters"]
    #If the value of "scoresheet_grid_height_mm" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(scoresheet_grid_height_mm):
       scoresheet_grid_height_mm = json_default_settings_dictionary["Scoresheet Grid Height in Millimeters"]
    
    width_of_ten_smallest_measures_mm = json_settings_dictionary["Width of Ten Successive Smallest Measures in Millimeters"]
    #If the value of "width_of_ten_smallest_measures_mm" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(width_of_ten_smallest_measures_mm):
       width_of_ten_smallest_measures_mm = json_default_settings_dictionary["Width of Ten Successive Smallest Measures in Millimeters"]        
    
    vertical_shift_pixels = json_settings_dictionary["Vertical Shift in Pixels"]
    #If the value of "vertical_shift_pixels" is not a valid 
    #integer or float, then it will be reset to its default value.
    if not is_valid_int_or_float(vertical_shift_pixels):
       vertical_shift_pixels = int(json_default_settings_dictionary["Vertical Shift in Pixels"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        vertical_shift_pixels = int(vertical_shift_pixels)

    horizontal_shift_pixels = json_settings_dictionary["Horizontal Shift in Pixels"]
    #If the value of "horizontal_shift_pixels" is not a valid 
    #integer or float, then it will be reset to its default value.
    if not is_valid_int_or_float(horizontal_shift_pixels):
       horizontal_shift_pixels = int(json_default_settings_dictionary["Horizontal Shift in Pixels"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        horizontal_shift_pixels = int(horizontal_shift_pixels)
    
    semitone_shift = json_settings_dictionary["Semitone Shift"]
    #If the value of "semitone_shift" is not a valid 
    #integer or float, then it will be reset to its default value.
    if not is_valid_int_or_float(semitone_shift):
       semitone_shift = int(json_default_settings_dictionary["Semitone Shift"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        semitone_shift = int(semitone_shift)

    leading_silence_milliseconds = json_settings_dictionary["Leading Silence Duration in Milliseconds"]
    #If the value of "leading_silence_milliseconds" is not a valid 
    #non-negative integer or float, then it will be reset to its default value.
    if not is_valid_non_negative_int_or_float(leading_silence_milliseconds):
       leading_silence_milliseconds = int(json_default_settings_dictionary["Leading Silence Duration in Milliseconds"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        leading_silence_milliseconds = int(leading_silence_milliseconds)
          
    trailing_silence_milliseconds = json_settings_dictionary["Trailing Silence Duration in Milliseconds"]
    #If the value of "trailing_silence_milliseconds" is not a valid 
    #non-negative integer or float, then it will be reset to its default value.
    if not is_valid_non_negative_int_or_float(trailing_silence_milliseconds):
       trailing_silence_milliseconds = int(json_default_settings_dictionary["Trailing Silence Duration in Milliseconds"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        trailing_silence_milliseconds = int(trailing_silence_milliseconds)
        
    number_of_notes = json_settings_dictionary["Number of Notes"]
    #If the value of "number_of_notes" is not a valid 
    #positive integer, then it will be reset to its default value.
    if not is_valid_positive_int_or_float(number_of_notes):
       number_of_notes = int(json_default_settings_dictionary["Number of Notes"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
        number_of_notes = int(number_of_notes)
    
    tempo_bpm = json_settings_dictionary["Tempo bpm"]
    #If the value of "tempo_bpm" is not a valid 
    #positive integer or float, then it will be reset 
    #to its default value.
    if not is_valid_positive_int_or_float(tempo_bpm):
       tempo_bpm = int(json_default_settings_dictionary["Tempo bpm"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       tempo_bpm = int(tempo_bpm)
        
    ticks_per_quarter_note = json_settings_dictionary["Ticks per Quarter Note"]
    #If the value of "ticks_per_quarter_note" is not a valid 
    #positive integer or float, then it will be reset 
    #to its default value.
    if not is_valid_positive_int_or_float(ticks_per_quarter_note):
       ticks_per_quarter_note = int(json_default_settings_dictionary["Ticks per Quarter Note"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       ticks_per_quarter_note = int(ticks_per_quarter_note)
     
    smallest_measure_duration_denominator = json_settings_dictionary["Smallest Measure Duration Denominator"]
    #If the value of "smallest_measure_duration_denominator" 
    #is not a valid positive integer or float, then it will 
    #be reset to its default value.
    if not is_valid_positive_int_or_float(smallest_measure_duration_denominator):
       smallest_measure_duration_denominator = int(json_default_settings_dictionary["Smallest Measure Duration Denominator"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       smallest_measure_duration_denominator = int(smallest_measure_duration_denominator)

    time_signature_numerator = json_settings_dictionary["Time Signature Numerator"]
    #If the value of "time_signature_numerator" 
    #is not a valid positive integer or float, then it will 
    #be reset to its default value.
    if not is_valid_positive_non_zero_int_or_float(time_signature_numerator):
       time_signature_numerator = int(json_default_settings_dictionary["Time Signature Numerator"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       time_signature_numerator = int(time_signature_numerator)       

    time_signature_denominator = json_settings_dictionary["Time Signature Denominator"]
    #If the value of "time_signature_denominator" 
    #is not a valid positive integer or float, then it will 
    #be reset to its default value.
    if not is_valid_positive_non_zero_int_or_float(time_signature_denominator):
       time_signature_denominator = int(json_default_settings_dictionary["Time Signature Denominator"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       time_signature_denominator = int(time_signature_denominator)
       
    midi_velocity = json_settings_dictionary["Midi Velocity"]
    #If the value of "midi_velocity" is not a valid positive integer 
    #or float equal to or below 127, then it will be reset to its 
    #default value.
    if not (is_valid_positive_non_zero_int_or_float(midi_velocity) and midi_velocity <= 127):
       midi_velocity = int(json_default_settings_dictionary["Midi Velocity"])
    #Otherwise its value will be casted to an integer in case it was a float value.
    else:
       midi_velocity = int(midi_velocity)

    midi_copyright_string = json_settings_dictionary["Midi Copyright Metadata String"]
    midi_comment = json_settings_dictionary["Midi Comment String"]

    #Building a dictionary of notes and corresponding enharmonic notes (between octaves -1 and 9 inclusively)
    #and their numeric counterpart (based on the article: Mathematics 2019, 7, 19; doi:10.3390/math7010019)
    notes_midi_dict = {}
    for i in range(-1,10):
        notes_midi_dict["C" + str(i)] = 12 + 12*i
        notes_midi_dict["C#" + str(i)] = 13 + 12*i
        notes_midi_dict["D" + str(i)] = 14 + 12*i
        notes_midi_dict["D#" + str(i)] = 15 + 12*i
        notes_midi_dict["E" + str(i)] = 16 + 12*i
        notes_midi_dict["F" + str(i)] = 17 + 12*i
        notes_midi_dict["F#" + str(i)] = 18 + 12*i
        notes_midi_dict["G" + str(i)] = 19 + 12*i
        notes_midi_dict["G#" + str(i)] = 20 + 12*i
        notes_midi_dict["A" + str(i)] = 21 + 12*i
        notes_midi_dict["A#" + str(i)] = 22 + 12*i
        notes_midi_dict["B" + str(i)] = 23 + 12*i

    #Remove the notes above the Midi note number 127 from the dictionary generated above
    deleted_notes = ["B9", "A#9", "A9", "G#9"]
    for deleted_note in deleted_notes:
        del notes_midi_dict[deleted_note]

    list_notes_midi_dict_keys = list(notes_midi_dict.keys())
    list_notes_midi_dict_values = list(notes_midi_dict.values())
    #The dictionary of midi notes keys to notes in 
    #letter form values is generated.
    midi_notes_dict = {}
    for i in range(len(list_notes_midi_dict_keys)):
        midi_notes_dict[list_notes_midi_dict_values[i]] = list_notes_midi_dict_keys[i]

    #The notes printed out on the 30-note music box scoresheet are actually transposed.
    #Here is a list of the notes as they appear on the  scoresheet paper when the arrow 
    #points to the left, from top to bottom.
    #["E6", "D6", "C6", "B5", "A#5", "A5", "G#5", "G5", "F#5", "F5", "E5", "D#5", 
    # "D5", "C#5", "C5", "B4", "A#4", "A4", "G#4", "G4", "F#4", "F4", "E4", "D4", "C4", "B3", 
    # "A3", "G3", "D3", "C3"]

    #Here are the actual notes played by the 30-note Grand Illusions music box (F scale), 
    #when the arrow points to the left, from top to bottom, according to musicboxmaniacs.com:
    music_box_notes = ["A6", "G6", "F6", "E6", "D#6", "D6", "C#6", "C6", "B5", "A#5", "A5",
    "G#5", "G5", "F#5", "F5", "E5", "D#5", "D5", "C#5", "C5", "B4", "A#4", "A4", "G4", "F4", 
    "E4", "D4", "C4", "G3", "F3"]

    #The list "txt_file_names" will tally the file names 
    #of text files that are not named "license.txt" nor 
    #"readme.txt" nor "error log.txt" (case insensitive).
    txt_file_names = [file_name for file_name in os.listdir(cwd) if (file_name[-4:] == ".txt" and 
        file_name[:-4].lower() != "license" and file_name[:-4].lower() != "readme" and file_name[:-4].lower() != "error log")] 
    #If the list "txt_file_names" isn't empty, then it will be 
    #opened and each stripped and uppercased line will be appended 
    #to the list "music_box_notes_txt_file_path".  
    if txt_file_names != []:
        music_box_notes_txt_file_path = os.path.join(cwd, txt_file_names[0])
        if os.path.exists(music_box_notes_txt_file_path):
            with open(music_box_notes_txt_file_path, "r", encoding="utf-8") as f:
                music_box_note_candidates = f.readlines()
            music_box_note_candidates = [note.strip().upper() for note in music_box_note_candidates]
            #The counter "number_of_valid_notes", initialized to zero,
            #will be incremented every time a music box note candidate 
            #is found within the list of valid midi notes "list_notes_midi_dict_keys".
            #This number should be equal to the specified number of notes of the 
            #music box, which itself should be above zero, for the music box 
            #note candidates to overwrite the default notes.
            number_of_valid_notes = 0
            for note_string in music_box_note_candidates:
                if (note_string in list_notes_midi_dict_keys and 
                music_box_note_candidates.count(note_string) == 1):
                    number_of_valid_notes += 1     
            if number_of_notes > 0 and number_of_valid_notes == number_of_notes:
                music_box_notes = music_box_note_candidates
            elif number_of_notes != len(music_box_note_candidates):      
                #The function "get_terminal_dimensions()" will return the number of columns 
                #and rows in the console, to allow to properly format the text and dividers.
                columns, lines = get_terminal_dimensions()
                
                print("\n" + textwrap.fill(f"The number of notes included in the text file '{txt_file_names[0]}' ({len(music_box_note_candidates)}) does not match the 'Number of Notes' setting ({number_of_notes}). Please adjust accordinly.", width=columns) + "\n")
                input(press_any_key_string)
                return json_settings_dictionary 
            else:
                #The function "get_terminal_dimensions()" will return the number of columns 
                #and rows in the console, to allow to properly format the text and dividers.
                columns, lines = get_terminal_dimensions()
                print("\n" + textwrap.fill(f"Some incorrectly formatted notes were present in the text file '{txt_file_names[0]}' (please only include one note per line in the text file, without any punctuation marks). Here is an example of how the notes should be written (shown here in list format for brevity):", width=columns)+ "\n" + f"{music_box_notes}" + "\n")
                input(press_any_key_string)
                return json_settings_dictionary  

    #These variable depend on user input, so they are 
    #calculated upon starting to process the scans.
    punched_hole_diameter_pixels = punched_hole_diameter_mm / 25.4 * dpi
    scoresheet_grid_height_pixels = scoresheet_grid_height_mm / 25.4 * dpi
    width_of_one_smallest_measure_pixels = width_of_ten_smallest_measures_mm / 10 / 25.4 * dpi
    cell_pixel_height = scoresheet_grid_height_pixels / (number_of_notes - 1)
    #The number of ticks per smallest measure is calculated by multiplying 
    #the number of ticks per quarter notes by the quotient of four over the 
    #value of "smallest_measure_duration_denominator".
    ticks_per_smallest_measure = ticks_per_quarter_note * 4/smallest_measure_duration_denominator
    #The tempo in microseconds per quarter note is determined by calling the "bpm2tempo()"
    #mido method with the time signature numerator and denominator as a tuple additional 
    #argument.
    tempo_us_per_quarter_note = mido.bpm2tempo(tempo_bpm, time_signature = (time_signature_numerator, time_signature_denominator))    
    #The leading silence in ticks is calculated by multiplying the value of "leading_silence_milliseconds"
    #by one million in order to express the silence in microseconds. The result is then divided by 
    #the value of "tempo_us_per_quarter_note" to get the number of quarter notes, which is then 
    #multiplied by "ticks_per_quarter_note" to get the number of ticks.
    leading_silence_ticks = int(leading_silence_milliseconds * 1000 / tempo_us_per_quarter_note * ticks_per_quarter_note)
    trailing_silence_ticks = int(trailing_silence_milliseconds * 1000 / tempo_us_per_quarter_note * ticks_per_quarter_note)
               
    #Get a list of ".jpg" file names in the "Scans" subfolder of the working folder
    jpg_names = [file_name for file_name in sorted(os.listdir(os.path.join(cwd, scans_folder_name))) if file_name[-4:] == ".jpg"]

    if jpg_names != []:
        
        #The function "get_file_name_horizontal_vertical_shift_manual_override_strings()"
        #will return the horizontal and vertical shift manual override pixel values, that 
        #were extracted from the file name and the file name where these have been removed
        #(e.g., 5, -2, "track_01" for the file name "track_01+ (v=5, h=-2)"). Should there 
        #be no such manual override parenthesized expressions in "file_name_without_extension", 
        #then zero will be returned for the horizontal and vertical shift manual override pixel 
        #values, along with the original value of "file_name_without_extension".
        _, _, file_name_without_extension = (
            get_file_name_horizontal_vertical_shift_manual_override_strings(jpg_names[0]))
        
        #Any file number suffix following the required plus sign ("+") at the end of 
        #the scanned file names will be removed to give the string that will be used 
        #for the output, provided that the user hasn't included a CSV naming key.
        file_number_suffix_strings = (re.findall(r"\+[\d]+$", file_name_without_extension))
        if file_number_suffix_strings != []:
            file_name_without_extension = re.sub(file_number_suffix_strings[0], "", file_name_without_extension).strip()
        #If the first file didn't get a file number suffix (e.g., "track_1+.jpg"),
        #then the plus sign will be sliced out, if present at the last character.
        if file_name_without_extension[-1] == "+":
            file_name_without_extension = file_name_without_extension[:-1]

        #The file name will be used to name the output folder and the MIDI file.
        output_file_name = file_name_without_extension
        #The output folder path will be created if it doesn't already exist.
        output_folder_path = os.path.join(cwd, "Output Files", output_file_name)
        if not os.path.exists(output_folder_path):
            try:
                os.makedirs(output_folder_path)
            except:
                #The function "get_terminal_dimensions()" will return the number of columns 
                #and rows in the console, to allow to properly format the text and dividers.
                columns, lines = get_terminal_dimensions()
    
                print("\n" + textwrap.fill(f"Invalid folder name: {output_file_name}. Please enter a file name without special characters.", width=columns) + "\n")
                input(press_any_key_string)
                return json_settings_dictionary    
        
        #If this is the last note of a scoresheet, then the value of 
        #"x_pixel_width_after_last_note_of_previous_scoresheet" will be 
        #set to the difference between the right "x" coordinate of the 
        #scoresheet and the center "x" coordinate of this last note in 
        #order to include the silence after this last note to the silence
        #before the first note of the next scoresheet, as the two scoresheets 
        #were cut and are really contiguous.
        x_pixel_width_after_last_note_of_previous_scoresheet = 0           
        #The data for the "note_on" and "note_off" messages for each punched hole center coordinates 
        #in chronological order will be appended to the list "nested_list_of_note_on_off_midi_cumulative_ticks", 
        #which will be used when procedurally generating the MIDI file, as a tuple of three elements: 
        #("note_on", midi note, cumulative_ticks).
        nested_list_of_note_on_off_midi_cumulative_ticks = []
        cumulative_ticks = 0
        
        #The previous estimation of the remaining number of seconds is stored in the variable
        #"previous_estimated_seconds" and will be used instead of the current calculation
        #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
        #its estimation.
        previous_estimated_seconds = 0
        first_jpeg_index = 0
        last_jpeg_index = len(jpg_names)
        start_time = time.perf_counter()
        for i in range(len(jpg_names)):
            #The function "get_file_name_horizontal_vertical_shift_manual_override_strings()"
            #will return the horizontal and vertical shift manual override pixel values, that 
            #were extracted from the file name and the file name where these have been removed
            #(e.g., 5, -2, "track_01" for the file name "track_01+ (v=5, h=-2)"). Should there 
            #be no such manual override parenthesized expressions in "file_name_without_extension", 
            #then zero will be returned for the horizontal and vertical shift manual override pixel 
            #values, along with the original value of "file_name_without_extension".
            horizontal_shift_pixels_current_jpeg, vertical_shift_pixels_current_jpeg, file_name_without_extension = (
                get_file_name_horizontal_vertical_shift_manual_override_strings(jpg_names[i]))
            #If the value of both "horizontal_shift_pixels_current_jpeg" and 
            #"vertical_shift_pixels_current_jpeg" is equal to zero, then it 
            #means that the user has not specified a horizontal nor vertical 
            #shift override string in the file name (e.g., "Track 1+0001 (h=1,v-2).jpg").
            #Therefore, the values that was provided by the user in the CLI menu will be
            #used instead, with the default values of these both being zero pixels.
            if horizontal_shift_pixels_current_jpeg == 0 and vertical_shift_pixels_current_jpeg == 0:
                horizontal_shift_pixels_current_jpeg = horizontal_shift_pixels
                vertical_shift_pixels_current_jpeg = vertical_shift_pixels
            
            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            undetectable_scoresheet_error_string = "\n" + textwrap.fill(f"Please adjust the value of the 'Black Pixel Threshold Percentage' to a higher value (around 95% should be good), as no columns or rows of pixels in your image \"{jpg_names[i]}\" fell below your current threshold of {json_settings_dictionary['Black Pixel Threshold Percentage']}%.", width=columns) + "\n"
            undetectable_notes_error_string = "\n" + textwrap.fill(f"Please decrease the value of the white pixel percentage threshold (current value: {white_pixel_threshold_percentage}), as no horizontal spaces between punched holes were detected in your image \"{jpg_names[i]}\".", width=columns) + "\n"
            
            #The color version of the image will be used to save the final rotated image
            #with the extrapolated notes written on it.
            color_img = cv2.imread(os.path.join(cwd, scans_folder_name, jpg_names[i]), cv2.IMREAD_COLOR_RGB)
            color_img = cv2.flip(src=color_img, dst=color_img, flipCode=1)
            color_img = cv2.convertScaleAbs(color_img, alpha=1, beta=color_image_brightness)
            
            #The grayscale version of the image will be used to calculate the rotation angles 
            #and to perform the NumPy calculations to extrapolate the notes corresponding to 
            #the punched holes.
            img = cv2.imread(os.path.join(cwd, scans_folder_name, jpg_names[i]), cv2.IMREAD_GRAYSCALE)
            img = cv2.flip(src=img, dst=img, flipCode=1)
            
            #The formula for the contrast adjustment was taken from the "Pil.Image.blend()"
            #Pillow method that is used when adjusting the contrast with Pillow's ImageEnhance 
            #module ("Pil.ImageEnhance.Contrast()").
            if contrast_level != 1 and contrast_level >= 0:
                initial_mean_pixel_value = np.mean(img)
                img = img * contrast_level + initial_mean_pixel_value * (1.0 - contrast_level)

            #filter the image to make pixels of the paper color pure white (255),
            #as they are above the threshold "paper_color_grayscale_filter_threshold",
            #with any remaining pixels being black (0)
            img = np.where(img > paper_color_grayscale_filter_threshold, 255, 0)
            
            #In order to get the horizontal and vertical projection profiles,
            #non-white pixels
            rows, cols = img.shape
            
            #The function "rotate_image()" will rotate the "img"
            #numpy array using the "getRotationMatrix2D()" and 
            #"warpAffine()" OpenCV methods. It will only be called 
            #if the rotation angle doesn't result in no rotation
            #(a multiple of 360 degrees, hence the "angle%360 != 0).
            if user_rotation_angle%360 != 0: 
                img, color_img, rows, cols = rotate_image(img.astype(np.uint8), color_img.astype(np.uint8), rows, cols, user_rotation_angle)
             
            #The function "get_horizontal_projection_profile()" will get the horizontal projection 
            #profile by first filtering the "img" array with the "np.where()" method, such that 
            #white pixels have a value of zero and non-white pixels have a value of one. This 
            #will allow to get the horizontal projection profile by adding up all the rows for 
            #each column, thus generating a 1D horizontal array. The left and right edges of 
            #the score sheet will be detected, as they will be the first and last elements 
            #of the horizontal projection profile where the pixels will not be almost exclusively 
            #black.
            (img_filtered_for_flattening, 
            horizontal_projection_profile, 
            non_black_pixels_horizontal_projection_profile, 
            black_pixels_horizontal_projection_profile, 
            left_x_scoresheet, 
            right_x_scoresheet,
            scoresheet_width) = get_horizontal_projection_profile(img, black_pixel_threshold_percentage, 
                rows, undetectable_scoresheet_error_string)
            
            #The following code will detect any tilt in the scoresheet scans and correct it by rotating the image accordingly.
            
            #The vertical projection profile for the first and last 25% of the scoresheet's width 
            #will allow to determine the top "y" coordinate of the scoresheet at these locations,
            #which will in turn allow to determine the tilt angle of the score sheet.
            
            #To get the slice of "img_filtered_for_flattening" corresponding to 
            #the first 25% of the scoresheet's width, all "y" coordinates need to 
            #be included (":,") and the range of the "x" coordinates corresponds to 
            #"left_x_scoresheet: round(left_x_scoresheet + 0.25*scoresheet_width)"
            first_25_width_percent_vertical_projection_profile = np.sum(img_filtered_for_flattening[:, left_x_scoresheet: 
                round(left_x_scoresheet + 0.25*scoresheet_width)], axis=1)
            #A row of pixels above or below the scoresheet would be comprised of 
            #entirely black pixels, and so the sum of these pixels in 
            #"non_black_pixels_first_25_width_percent_vertical_projection_profile"
            #would be almost equal to the width of 25% of the scoresheet width, 
            #which is the width of the slice used when setting the value of 
            #"first_25_width_percent_vertical_projection_profile". Conversely, 
            #any rows making up the score sheet contain some white pixels and 
            #the sum would be much lower than 25% of the scoresheet width.
            non_black_pixels_first_25_width_percent_vertical_projection_profile = ( 
                np.where(first_25_width_percent_vertical_projection_profile < (black_pixel_threshold_percentage/100)*0.25*scoresheet_width)[0])
            #A similar approach is taken for the last 25% of the scoresheet's width.
            last_25_width_percent_vertical_projection_profile = np.sum(img_filtered_for_flattening[:, round(right_x_scoresheet - 
                0.25*scoresheet_width): right_x_scoresheet], axis=1)
            
            non_black_pixels_last_25_width_percent_vertical_projection_profile = (
                np.where(last_25_width_percent_vertical_projection_profile < (black_pixel_threshold_percentage/100)*0.25*scoresheet_width)[0])
            
            #If some non-black pixels were detected in both the first and last 25% of the 
            #scoresheet array slices, then the top "y" coordinate at both these locations
            #is determined by indexing the vertical projection profile arrays at the first 
            #index.
            if (non_black_pixels_first_25_width_percent_vertical_projection_profile.size != 0 and 
            non_black_pixels_last_25_width_percent_vertical_projection_profile.size != 0):
                first_25_width_percent_top_y = non_black_pixels_first_25_width_percent_vertical_projection_profile[0]
                last_25_width_percent_top_y = non_black_pixels_last_25_width_percent_vertical_projection_profile[0]
                
                #If the two top "y" coordinates differ, then the tilt angle will 
                #be calculated by first determining the sine (the difference 
                #between the two top "y" coordinates ("delta_y"), divided by the 
                #scoresheet width. The smallest angle of the right angle triangle, 
                #where the hypothenuse corresponds to the top side of the 
                #scoresheet and the opposite side corresponds to the "delta_y",
                #is obtained by the "np.arcsin()" method of the sine result.
                #As the "cv2.getRotationMatrix2D()" method requires an angle in 
                #degrees, the "np.degrees()" method is used to convert the 
                #radians angle to degrees.
                if first_25_width_percent_top_y != last_25_width_percent_top_y:
                    
                    delta_y = last_25_width_percent_top_y - first_25_width_percent_top_y
                    sine = abs(delta_y) / scoresheet_width
                    rotation_angle = np.degrees(np.arcsin(sine))
                    
                    if delta_y > 0:
                        rotation_angle = - rotation_angle
                    
                    #The function "rotate_image()" will rotate the "img"
                    #numpy array using the "getRotationMatrix2D()" and 
                    #"warpAffine()" OpenCV methods. It will only be called 
                    #if the rotation angle doesn't result in no rotation
                    #(a multiple of 360 degrees, hence the "angle%360 != 0).
                    if rotation_angle%360 != 0: 
                        img, color_img, rows, cols = rotate_image(img.astype(np.uint8), color_img.astype(np.uint8), rows, cols, rotation_angle)
                        
                        #As the image was rotated, some variables need to be updated.
                        
                        #The function "get_horizontal_projection_profile()" will get the horizontal projection 
                        #profile by first filtering the "img" array with the "np.where()" method, such that 
                        #white pixels have a value of zero and non-white pixels have a value of one. This 
                        #will allow to get the horizontal projection profile by adding up all the rows for 
                        #each column, thus generating a 1D horizontal array. The left and right edges of 
                        #the score sheet will be detected, as they will be the first and last elements 
                        #of the horizontal projection profile where the pixels will not be almost exclusively 
                        #black.
                        (img_filtered_for_flattening, 
                        horizontal_projection_profile, 
                        non_black_pixels_horizontal_projection_profile, 
                        black_pixels_horizontal_projection_profile, 
                        left_x_scoresheet, 
                        right_x_scoresheet,
                        scoresheet_width) = get_horizontal_projection_profile(img, black_pixel_threshold_percentage, 
                            rows, undetectable_scoresheet_error_string)
            
            #Add up all the columns for each row to get the vertical projection profile
            #("np.sum" along the "x" axis at index one).
            vertical_projection_profile = np.sum(img_filtered_for_flattening, axis=1)
            
            #A row of pixels above or below the scoresheet would be comprised of 
            #entirely black pixels, and so the sum of these pixels in "vertical_projection_profile"
            #would be almost equal to the width of the rotated image ("cols"). Conversely, any rows making 
            #up the score sheet contain some white pixels and the sum would be much lower than "cols".
            non_black_pixels_vertical_projection_profile = np.where(vertical_projection_profile < (black_pixel_threshold_percentage/100)*cols)[0]
            black_pixels_vertical_projection_profile = np.where(vertical_projection_profile >= (black_pixel_threshold_percentage/100)*cols)[0]
            
            #If a scoresheet is visible in the form of some non-black pixels
            #then the "if" statement below will run. If that is not the case,
            #then the user has probably set a too stringent value for the 
            #"paper_color_grayscale_filter_threshold" (too high, meaning that 
            #no pixels were lighter than the threshold and consequently all 
            #pixels were set to black).
            if non_black_pixels_vertical_projection_profile.size != 0:
            
                #The top "y" coordinate of the scoresheet corresponds to that 
                #of the first pixel in "non_black_pixels_vertical_projection_profile",
                #as it is the first row of pixels that falls under the threshold for inclusion 
                #in the black pixels vertical projection profile, meaning that it contains 
                #a significan amount of non-black pixels denoting the presence of the scoresheet.
                top_y_scoresheet = non_black_pixels_vertical_projection_profile[0]
                #Similarly, the bottom "y" coordinate of the scoresheet corresponds to 
                #that of the last pixel in "non_black_pixels_vertical_projection_profile",
                #as it is the last row of pixels that falls under the threshold for inclusion 
                #in the black pixels vertical projection profile, meaning that it contains 
                #a significan amount of non-black pixels denoting the presence of the scoresheet.
                bottom_y_scoresheet = non_black_pixels_vertical_projection_profile[-1]
                #The scoresheet pixel height corresponds to the difference between 
                #the bottom and top "y" coordinates of the scoresheet.
                scoresheet_height = bottom_y_scoresheet - top_y_scoresheet
                
                #The top "y" coordinate of the first music box scoresheet note 
                #horizontal gridline is calculated by vertically centering the 
                #grid height along the scoresheet height by halving the difference 
                #between the scoresheet height and the grid height.
                y_first_note = (scoresheet_height - scoresheet_grid_height_pixels)/2
                #The dictionary of "float" note horizontal gridline "y" coordinate keys to 
                #values made up of a list of the notes in letter form and corresponding midi 
                #notes "note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict"
                #will allow to tally up the extrapolated notes from the detected punched 
                #hole center "y" coordinates. 
                note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict = {}
                for j in range(len(music_box_notes)):
                    note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[y_first_note + j * cell_pixel_height] = (
                        [music_box_notes[j], notes_midi_dict[music_box_notes[j]]])
                #The list of of "float" note horizontal gridline "y" coordinates
                #"list_of_music_box_note_center_y_coordinates" will be used to draw 
                #the music box gridlines on the scoresheet and a copy of the list 
                #will be used to extrapolate which note corresponds to the center 
                #"y" coordinate of each punched hole. To to this, the center "y"
                #coordinate will be appended to the list copy, which will then 
                #be sorted, and the index of the newly added note will be obtained 
                #with the "index()" method. Then the neighboring note that has the 
                #nearest "y" coordinate will be selected.
                list_of_music_box_note_center_y_coordinates = (
                    list(note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict.keys()))
                
                for j in range(len(list_of_music_box_note_center_y_coordinates)):
                    music_box_note_line_y_coordinate = list_of_music_box_note_center_y_coordinates[j]
                    #The music box note lines corresponding to "C" notes (excluding "C#") will be 
                    #drawn in green to facilitate reading of the annotated JPEG scoresheet files,
                    #provided that the semitone shift is a multiple of 12 semitones (the equivalent 
                    #of an octave, meaning that the notes were either not shifted ("semitone_shift == 0"), 
                    #or they were shifted by whole octaves (-12 or 12, for example).
                    if (semitone_shift%12 == 0 and 
                    note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[music_box_note_line_y_coordinate][0][0] == "C" and 
                    "#" not in note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[music_box_note_line_y_coordinate][0]):
                        music_box_note_line_color = (51, 136, 34)
                    else:
                        music_box_note_line_color = (187, 187, 187)
                    
                    #Some gray horizontal lines spanning 
                    #the entire canvas are drawn for each 
                    #music box note in the list
                    #"list_of_music_box_note_center_y_coordinates". 
                    cv2.line(
                        img=color_img,
                        pt1=(0, int(top_y_scoresheet + music_box_note_line_y_coordinate)), 
                        pt2=(cols, int(top_y_scoresheet + music_box_note_line_y_coordinate)), 
                        color=music_box_note_line_color,                    
                        thickness=1,
                        lineType=cv2.LINE_AA)
               
            #If a scoresheet is visible in the form of some non-black pixels
            #then the "if" statement below will run. If that is not the case,
            #then the user has probably set a too stringent value for the 
            #"paper_color_grayscale_filter_threshold" (too high, meaning that 
            #no pixels were lighter than the threshold and consequently all 
            #pixels were set to black).
            else:
                print(undetectable_scoresheet_error_string)
                input(press_any_key_string)
                sys.exit(1)
            
            #The slice coordinates of the scoresheet are stored 
            #in the variable "scoresheet_img_slice" through the
            #use of the Numpy "np.s_" indexing routine.
            scoresheet_img_slice = np.s_[
                top_y_scoresheet:bottom_y_scoresheet, 
                left_x_scoresheet:right_x_scoresheet
                ]
            
            #The filtered "img" array where white pixels (grayscale value of 255)
            #correspond to ones and non-white pixels are set to zero will allow to 
            #detect columns of punched holes by screening the scoresheet horizontal 
            #projection profile derived from it to retain pixels that fall under the 
            #threshold for columns of white pixels, meaning that these columns contain 
            #some punched holes.
            img_filtered_for_flattening_white_is_one = np.where(img == 255, 1, 0)
            
            #Add up all the rows for each column within the scoresheet area to get the 
            #horizontal projection profile ("np.sum" along the "y" axis at index zero).
            scoresheet_horizontal_projection_profile = np.sum(img_filtered_for_flattening_white_is_one[scoresheet_img_slice], axis=0)
            
            #As only the rows contained within the scoresheet area are flattened to make up 
            #the "scoresheet_horizontal_projection_profile", the threshold below which notes 
            #are considered to be present is calculated by multiplying the height of the 
            #scoresheet by the white pixel threshold percentage.
            non_white_pixels_horizontal_projection_profile = np.where(scoresheet_horizontal_projection_profile < (white_pixel_threshold_percentage/100)*scoresheet_height)[0]
            #If the threshold is met or exceeded, then the column corresponding to the flattened rows
            #at this "x" coordinate will be included in "white_pixels_horizontal_projection_profile"
            #instead.
            white_pixels_horizontal_projection_profile = np.where(scoresheet_horizontal_projection_profile >= (white_pixel_threshold_percentage/100)*scoresheet_height)[0]
            
            #If some notes were detected on the scoresheet in the form of 
            #some non-white pixels, then the "if" statement below will run. 
            #If that is not the case, then the user likely needs decrease 
            #the value of the white pixel percentage threshold
            #("white_pixel_threshold_percentage), as no horizontal 
            #spaces between punched holes were detected in the image.
            if non_white_pixels_horizontal_projection_profile.size != 0:
                
                #The index "non_white_pixels_horizontal_projection_profile_index"
                #will keep track of which element of the "non_white_pixels_horizontal_projection_profile"
                #list is being iterated over. This index will be incremented every time the leftmost or  
                #rightmost "x" coordinates of a punched hole are being screened over, as these need to 
                #be included in the nested list of leftmost and rightmost "x" coordinates for the 
                #punched holes "nested_list_of_left_right_x_of_punched_holes". 
                non_white_pixels_horizontal_projection_profile_index = 0
                len_non_white_pixels_horizontal_projection_profile = non_white_pixels_horizontal_projection_profile.size
                nested_list_of_left_right_x_of_punched_holes = []

                #The Boolean variable "left_x_punched_hole_reached", initialized to "False",
                #will be set to "True" upon reaching the leftmost coordinate of a punched hole,
                #("left_x_candidate") and will be reset to "False" once more upon reaching its 
                #rightmost coordinate ("right_x_candidate").
                #This will allow the "if" statement below to only run if the value of 
                #"left_x_candidate" for the leftmost coordinate of the punched hole 
                #hasn't yet been updated, and the first "elif" statement below to 
                #only run once the leftmost coordinate for the punched hole has 
                #been stored in that variable, during a subsequent iteration of 
                #the "for" loop.
                left_x_punched_hole_reached = False            
                left_x_candidate = 0
                right_x_candidate = 0
                #The "for" loop below iterates over all of the column indices of the image 
                #in order to store a punched hole's leftmost "x" coordinate candidate
                #in the "left_x_candidate" variable in the "if" statement, and the 
                #rightmost "x" coordinate candidate in the "right_x_candidate"
                #variable in the first "elif" statement.
                for j in range(cols):
                    #In order for the "if" statement to run and set the
                    #punched hole's leftmost "x" coordinate candidate
                    #in the "left_x_candidate" variable, the counter 
                    #iterating over all of the "non_white_pixels_horizontal_projection_profile"
                    #elements must have a value below that of the last element of that list, 
                    #in order to avoid indexing errors, the current value of the Boolean 
                    #variable "left_x_punched_hole_reached" must be set to "False" to avoid 
                    #seting the leftmost coordinate more than once for any given punched 
                    #hole, and the corrected coordinate of the element at the index  
                    #"non_white_pixels_horizontal_projection_profile_index" of the 
                    #"non_white_pixels_horizontal_projection_profile" list (calculated 
                    #by adding the value of "left_x_scoresheet", as this list was obtained 
                    #from the slicing of the "img" NumPy array in order to only select the 
                    #pixels of the scoresheet) needs to be equal to the column index "i"
                    #of the "img" array to ensure that the same pixel is under consideration.
                    if (non_white_pixels_horizontal_projection_profile_index < 
                    len_non_white_pixels_horizontal_projection_profile and 
                    non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 
                    left_x_scoresheet == j and not left_x_punched_hole_reached):
                        #The condition "not (j == cols - 1 or 
                        #non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1 in
                        #white_pixels_horizontal_projection_profile" prevents the very last pixel from being detected as a punched 
                        #hole note, and also any black pixels that are immediately followed by a white pixel, as these are merely 
                        #artifacts. In any case, we will increment the value of "non_white_pixels_horizontal_projection_profile_index"
                        #to move on to the next index in the next iteration of the "for" loop.
                        if not (j == cols - 1 or 
                        non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1 in
                        white_pixels_horizontal_projection_profile):
                            left_x_punched_hole_reached = True
                            left_x_candidate = j
                        
                        non_white_pixels_horizontal_projection_profile_index += 1
                    #In order for the "elif" statement below to run, the Boolean variable 
                    #"left_x_punched_hole_reached" must already be set to "True", as we will be detecting 
                    #the rightmost coordinate of the punched hole. The next pixel at the corrected index 
                    #"non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1" 
                    #must be present in "white_pixels_horizontal_projection_profile", as this would indicate that this is 
                    #the last pixel of the punched hole before reaching a column found in the white pixels horizontal profile.
                    elif (non_white_pixels_horizontal_projection_profile_index < 
                    len_non_white_pixels_horizontal_projection_profile and
                    non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 
                    left_x_scoresheet == j and 
                    left_x_punched_hole_reached and (j == cols - 1 or 
                    non_white_pixels_horizontal_projection_profile[non_white_pixels_horizontal_projection_profile_index] + 1 in
                    white_pixels_horizontal_projection_profile)):
                        right_x_candidate = j
                        #The Boolean variable "left_x_punched_hole_reached" is 
                        #reset to "False" in order to allow the code to find the 
                        #next punched hole.
                        left_x_punched_hole_reached = False
                        non_white_pixels_horizontal_projection_profile_index += 1
                        if (right_x_candidate - left_x_candidate >= 
                        punched_hole_diameter_pixels * (punched_hole_diameter_percentage_threshold/100)):
                            nested_list_of_left_right_x_of_punched_holes.append([left_x_candidate, right_x_candidate])
                    #If the Boolean variable "left_x_punched_hole_reached" is set to "True",
                    #yet the "elif" statement above didn't run, then it means that we are not 
                    #done traversing the punched hole, and therefore the value of the index 
                    #"non_white_pixels_horizontal_projection_profile_index" needs to be 
                    #incremented.
                    elif left_x_punched_hole_reached:
                        non_white_pixels_horizontal_projection_profile_index += 1
                
                #The nested list "nested_list_of_center_x_y_coordinates_of_punched_holes"
                #will contain lists of center "x, y" coordinates for each punched hole of 
                #the scoresheet and will be sorted along "x" coordinates in ascending order 
                #before extrapolating the notes and ticks corresponding to each punched hole.
                nested_list_of_center_x_y_coordinates_of_punched_holes = []
                #Each slice of the scoresheet corresponding to a column of punched holes will 
                #be used to detect the center "y" coordinates of the punched holes, and then 
                #the center "x" coordinates of each detected punched hole, as these may vary 
                #slightly within a given slice (for example if two notes were so close together 
                #in time that they were detected in the same slice).
                for sublist in nested_list_of_left_right_x_of_punched_holes:
                    
                    sliced_img_filtered_array_for_flattening = img_filtered_for_flattening_white_is_one[top_y_scoresheet:bottom_y_scoresheet, sublist[0]:sublist[1]]
                    width_of_slice = sublist[1] - sublist[0]
                    
                    #The vertical profile of the sliced portion of the filtered array where 
                    #white pixels have the value of one and non-white have a value of zero 
                    #will be used to select pixels that fall short of the threshold for 
                    #rows comprised of white pixels, indicating that these rows contain 
                    #punched holes.
                    sliced_img_filtered_array_vertical_profile = np.sum(sliced_img_filtered_array_for_flattening, axis=1)
                    
                    #As only the columns contained within "sublist[0]" and "sublist[1]" of the 
                    #scoresheet area are flattened to make up the "scoresheet_horizontal_projection_profile", 
                    #the threshold below which notes are considered to be present is calculated by multiplying 
                    #the width of the slice ("width_of_slice") by the white pixel threshold percentage.
                    non_white_pixels_vertical_projection_profile = np.where(sliced_img_filtered_array_vertical_profile < (white_pixel_threshold_percentage_slice/100)*width_of_slice)[0]
                                    
                    #If the threshold is met or exceeded, then the column corresponding to the flattened rows
                    #at this "y" coordinate will be included in "white_pixels_vertical_projection_profile"
                    #instead.
                    white_pixels_vertical_projection_profile = np.where(sliced_img_filtered_array_vertical_profile >= (white_pixel_threshold_percentage_slice/100)*width_of_slice)[0]
                    
                    #The index "non_white_pixels_vertical_projection_profile_index"
                    #will keep track of which element of the "non_white_pixels_vertical_projection_profile"
                    #list is being iterated over. This index will be incremented every time the highest or  
                    #lowest "y" coordinates of a punched hole are being screened over, as these need to 
                    #be used in the calculation of the center "y" coordinates for the punched holes, 
                    #which will be appended to the list "list_of_center_y_coordinates".
                    non_white_pixels_vertical_projection_profile_index = 0
                    len_non_white_pixels_vertical_projection_profile = non_white_pixels_vertical_projection_profile.size               

                    #The Boolean variable "top_y_punched_hole_reached", initialized to "False",
                    #will be set to "True" upon reaching the highest coordinate of a punched hole,
                    #("top_y_candidate") and will be reset to "False" once more upon reaching its 
                    #lowest coordinate ("bottom_y_candidate").
                    #This will allow the "if" statement below to only run if the value of 
                    #"top_y_candidate" for the highest coordinate of the punched hole 
                    #hasn't yet been updated, and the first "elif" statement below to 
                    #only run once the highest coordinate for the punched hole has 
                    #been stored in that variable, during a subsequent iteration of 
                    #the "for" loop.
                    top_y_punched_hole_reached = False            
                    top_y_candidate = 0
                    bottom_y_candidate = 0
                    #The list of center "y" coordinates of successive notes, initialized as an empty
                    #list, will be set to the center "y" coordinate of the first successive note from 
                    #the top, calculated by adding half the punched hole pixel diameter to the top "y"
                    #coordinate of the overlapping successive notes. Then, for each successive note in 
                    #excess of one, the cell pixel height will be added to the previously processed 
                    #successive note punched hole at the last element of the list.
                    list_of_center_y_coordinates_of_successive_notes = []
                    #The list of center "y" coordinates of detected punched holes,
                    #initialized to an empty list, will be populated with each of 
                    #the individual punched holes' center "y" coordinates.
                    list_of_center_y_coordinates = []
                    #The "for" loop below iterates over all of the row indices of the 
                    #scoresheet between "top_y_scoresheet" and "bottom_y_scoresheet"
                    #in order to store a punched hole's highest "y" coordinate candidate
                    #in the "top_y_candidate" variable in the "if" statement, and the 
                    #rightmost "x" coordinate candidate in the "right_x_candidate"
                    #variable in the first "elif" statement.
                    for j in range(scoresheet_height):
                        #The "if" statement below will run if either no successive notes that span contiguous 
                        #"y" pixels were detected (the list "list_of_center_y_coordinates_of_successive_notes" 
                        #is empty, or the current "y" coordinate "i" under investigation at the current 
                        #iteration of the "for" loop is greater than the scoresheet note right below 
                        #that of the last successive note (hence the addition of "cell_pixel_height" 
                        #to move from the central "y" coordinate of the last successive note to 
                        #the next note down.
                        if (list_of_center_y_coordinates_of_successive_notes == [] or 
                            j > list_of_center_y_coordinates_of_successive_notes[-1] + cell_pixel_height):
                            #If the list "list_of_center_y_coordinates_of_successive_notes" isn't 
                            #empty and yet the outer "if" statement is running, then it means that 
                            #all of the successive notes in the list have been fully processed 
                            #and therefore it can be reinitialized to an empty list.
                            if list_of_center_y_coordinates_of_successive_notes != []:
                                list_of_center_y_coordinates_of_successive_notes = []
                            #In order for the "if" statement to run and set the
                            #punched hole's leftmost "x" coordinate candidate
                            #in the "top_y_candidate" variable, the counter 
                            #iterating over all of the "non_white_pixels_vertical_projection_profile"
                            #elements must have a value below that of the last element of that list, 
                            #in order to avoid indexing errors, the current value of the Boolean 
                            #variable "left_x_punched_hole_reached" must be set to "False" to avoid 
                            #seting the leftmost coordinate more than once for any given punched 
                            #hole, and the corrected coordinate of the element at the index  
                            #"non_white_pixels_vertical_projection_profile_index" of the 
                            #"non_white_pixels_vertical_projection_profile" list (calculated 
                            #by adding the value of "left_x_scoresheet", as this list was obtained 
                            #from the slicing of the "img" NumPy array in order to only select the 
                            #pixels of the scoresheet) needs to be equal to the column index "i"
                            #of the "img" array to ensure that the same pixel is under consideration.
                            if (non_white_pixels_vertical_projection_profile_index < 
                            len_non_white_pixels_vertical_projection_profile and 
                            non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] == j and 
                            not top_y_punched_hole_reached):
                                #The condition "not (i == scoresheet_height - 1 or 
                                #non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1 in
                                #white_pixels_vertical_projection_profile" prevents the very last pixel from being detected as a punched 
                                #hole note, and also any black pixels that are immediately followed by a white pixel, as these are merely 
                                #artifacts. In any case, we will increment the value of "non_white_pixels_vertical_projection_profile_index"
                                #to move on to the next index in the next iteration of the "for" loop.
                                if not (j == scoresheet_height - 1 or 
                                non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1 in
                                white_pixels_vertical_projection_profile):
                                    top_y_punched_hole_reached = True
                                    top_y_candidate = j
                                
                                #The index "non_white_pixels_vertical_projection_profile_index"
                                #will keep track of which element of the "non_white_pixels_vertical_projection_profile"
                                #list is being iterated over. This index will be incremented every time the highest or  
                                #lowest "y" coordinates of a punched hole are being screened over, as these need to 
                                #be used in the calculation of the center "y" coordinates for the punched holes, 
                                #which will be appended to the list "list_of_center_y_coordinates".
                                non_white_pixels_vertical_projection_profile_index += 1
                                
                            #In order for the "elif" statement below to run, the Boolean variable 
                            #"top_y_punched_hole_reached" must already be set to "True", as we will be 
                            #detecting the lowest coordinate of the punched hole. The next pixel at the index 
                            #"non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1" 
                            #must be present in "white_pixels_vertical_projection_profile", as this would indicate that this is 
                            #the last pixel of the punched hole before reaching a row found in the white pixels vertical profile.
                            elif (non_white_pixels_vertical_projection_profile_index < 
                            len_non_white_pixels_vertical_projection_profile and
                            non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] == j and 
                            top_y_punched_hole_reached and (j == scoresheet_height - 1 or 
                            non_white_pixels_vertical_projection_profile[non_white_pixels_vertical_projection_profile_index] + 1 in
                            white_pixels_vertical_projection_profile)):
                                bottom_y_candidate = j
                                #The Boolean variable "top_y_punched_hole_reached" is 
                                #reset to "False" in order to allow the code to find the 
                                #next punched hole.
                                top_y_punched_hole_reached = False
                                
                                #The index "non_white_pixels_vertical_projection_profile_index"
                                #will keep track of which element of the "non_white_pixels_vertical_projection_profile"
                                #list is being iterated over. This index will be incremented every time the highest or  
                                #lowest "y" coordinates of a punched hole are being screened over, as these need to 
                                #be used in the calculation of the center "y" coordinates for the punched holes, 
                                #which will be appended to the list "list_of_center_y_coordinates". 
                                non_white_pixels_vertical_projection_profile_index += 1
                                
                                #The height of the punched hole candidate is calculated by subtracting 
                                #the detected top "y" coordinate from the bottom "y" coordinate, and 
                                #if it exceeds the threshold of the punched hole diameter in pixels 
                                #times the value of "punched_hole_diameter_percentage_threshold",
                                #then it is deemed to be a punched hole and not a smaller artifact.
                                height_of_punched_hole_candidate = bottom_y_candidate - top_y_candidate
                                if height_of_punched_hole_candidate >= punched_hole_diameter_pixels * (punched_hole_diameter_percentage_threshold/100):
                                    
                                    #If the height of the punched hole candidate exceeds the threshold for two or more successive notes, 
                                    #calculated by multiplying the value of one plus the "punched_hole_percent_overlap_threshold" by 
                                    #the punched hole diameter in pixels, then the following "if" statement will split these overlapping 
                                    #successive notes apart.
                                    if (height_of_punched_hole_candidate > (1 + (punched_hole_percent_overlap_threshold/100)) * punched_hole_diameter_pixels):
                                        #The number of successive notes is calculated by dividing the height of the 
                                        #punched hole candidate by the punched hole diameter in pixels, and applying 
                                        #the "math.ceil()" method to the result, as multiple overlapping holes would 
                                        #have a detected height that is inferior to their combined individual heights 
                                        #were they not overlapping.
                                        number_of_consecutive_notes = math.ceil(height_of_punched_hole_candidate/punched_hole_diameter_pixels)
                                        #The list of center "y" coordinates of successive notes, initialized as an empty
                                        #list, will be set to the center "y" coordinate of the first successive note from 
                                        #the top, calculated by adding half the punched hole pixel diameter to the top "y"
                                        #coordinate of the overlapping successive notes. Then, for each successive note in 
                                        #excess of one, the cell pixel height will be added to the previously processed 
                                        #successive note punched hole at the last element of the list.
                                        list_of_center_y_coordinates_of_successive_notes = [top_y_candidate + 0.5 * punched_hole_diameter_pixels]
                                        #The list of center "y" coordinates of detected punched holes,
                                        #initialized to an empty list, will be populated with each of 
                                        #the individual punched holes' center "y" coordinates.
                                        list_of_center_y_coordinates.append(list_of_center_y_coordinates_of_successive_notes[-1])
                                        if number_of_consecutive_notes > 1:
                                            for k in range(1, number_of_consecutive_notes):
                                                list_of_center_y_coordinates_of_successive_notes.append(list_of_center_y_coordinates_of_successive_notes[-1] + k * cell_pixel_height)
                                                #The list of center "y" coordinates of detected punched holes,
                                                #initialized to an empty list, will be populated with each of 
                                                #the individual punched holes' center "y" coordinates.
                                                list_of_center_y_coordinates.append(list_of_center_y_coordinates_of_successive_notes[-1])
                                    #If the height of the punched hole candidate does not exceed the threshold for two or more successive 
                                    #notes, calculated by multiplying the value of one plus the "punched_hole_percent_overlap_threshold" by 
                                    #the punched hole diameter in pixels, then the "else" statement will append the center "y" coordinate 
                                    #of the detected note, calculated by adding half the pixel diameter of a punched hole to the top "y"
                                    #coordinate of the detected punched hole.
                                    else:     
                                        #The list of center "y" coordinates of detected punched holes,
                                        #initialized to an empty list, will be populated with each of 
                                        #the individual punched holes' center "y" coordinates.
                                        list_of_center_y_coordinates.append(top_y_candidate + (bottom_y_candidate - top_y_candidate)/2)
                                    
                            #If the Boolean variable "top_y_punched_hole_reached" is set to "True",
                            #yet the "elif" statement above didn't run, then it means that we are not 
                            #done traversing the punched hole, and therefore the value of the index 
                            #"non_white_pixels_vertical_projection_profile_index" needs to be 
                            #incremented.
                            elif top_y_punched_hole_reached:                        
                                non_white_pixels_vertical_projection_profile_index += 1
                                  
                    #The list of center "y" coordinates of detected punched holes
                    #"current_note_center_y_coordinate" will be iterated over in 
                    #order to get the horizontal projection profile of the slice 
                    #spanning the entire width of the original slice 
                    #(sublist[0]:sublist[1]) and half the punched hole 
                    #diameter above and below the center "y" coordinate.
                    #This will allow to detect the center "x" coordinate 
                    #separately for each punched hole that is present in 
                    #the slice spanning the full height of the scoresheet.
                    for current_note_center_y_coordinate in list_of_center_y_coordinates:
                        
                        punched_hole_sliced_img_filtered_array_for_flattening = (
                            img_filtered_for_flattening_white_is_one[int(current_note_center_y_coordinate - 
                                0.5*punched_hole_diameter_pixels):
                                int(current_note_center_y_coordinate + 
                                0.5*punched_hole_diameter_pixels), sublist[0]:sublist[1]])
                        
                        #The horizontal profile of the sliced portion of the filtered array where 
                        #white pixels have the value of one and non-white have a value of zero 
                        #will be used to select pixels that fall short of the threshold for 
                        #columns comprised of white pixels, indicating that these columns contain 
                        #punched holes.
                        punched_hole_sliced_img_filtered_array_horizontal_profile = (
                            np.sum(punched_hole_sliced_img_filtered_array_for_flattening, axis=0))
                        
                        #As only the rows around the "current_note_center_y_coordinate" are flattened 
                        #to make up the "punched_hole_sliced_img_filtered_array_horizontal_profile", 
                        #the threshold below which notes are considered to be present is calculated by multiplying 
                        #the height of the slice ("punched_hole_diameter_pixels") by the white pixel threshold percentage.
                        punched_hole_non_white_pixels_horizontal_projection_profile = (
                            np.where(punched_hole_sliced_img_filtered_array_horizontal_profile < 
                            (white_pixel_threshold_percentage_slice/100)*punched_hole_diameter_pixels)[0])
                                        
                        #If the threshold is met or exceeded, then the column corresponding to the flattened rows
                        #at this "x" coordinate will be included in "punched_hole_white_pixels_horizontal_projection_profile"
                        #instead.
                        punched_hole_white_pixels_horizontal_projection_profile = (
                            np.where(punched_hole_sliced_img_filtered_array_horizontal_profile >= 
                            (white_pixel_threshold_percentage_slice/100)*punched_hole_diameter_pixels)[0])
                        
                        #If some notes were detected on the scoresheet in the form of 
                        #some non-white pixels, then the "if" statement below will run. 
                        #If that is not the case, then the user likely needs decrease 
                        #the value of the white pixel percentage threshold
                        #("white_pixel_threshold_percentage).
                        if punched_hole_non_white_pixels_horizontal_projection_profile.size != 0:
                            
                            #The index "punched_hole_non_white_pixels_horizontal_projection_profile_index"
                            #will keep track of which element of the "punched_hole_non_white_pixels_horizontal_projection_profile"
                            #list is being iterated over. This index will be incremented every time the leftmost or  
                            #rightmost "x" coordinates of a punched hole are being screened over, as these need to 
                            #be used in the calculation of the center "x" coordinates for the punched holes.
                            punched_hole_non_white_pixels_horizontal_projection_profile_index = 0
                            len_punched_hole_non_white_pixels_horizontal_projection_profile = punched_hole_non_white_pixels_horizontal_projection_profile.size 

                            #The Boolean variable "left_x_punched_hole_reached", initialized to "False",
                            #will be set to "True" upon reaching the leftmost coordinate of a punched hole,
                            #("left_x_candidate") and will be reset to "False" once more upon reaching its 
                            #rightmost coordinate ("right_x_candidate").
                            #This will allow the "if" statement below to only run if the value of 
                            #"left_x_candidate" for the leftmost coordinate of the punched hole 
                            #hasn't yet been updated, and the first "elif" statement below to 
                            #only run once the leftmost coordinate for the punched hole has 
                            #been stored in that variable, during a subsequent iteration of 
                            #the "for" loop.
                            left_x_punched_hole_reached = False            
                            left_x_candidate = 0
                            right_x_candidate = 0
                            #The "for" loop below iterates over all of the column indices of the slice 
                            #in order to store a punched hole's leftmost "x" coordinate candidate
                            #in the "left_x_candidate" variable in the "if" statement, and the 
                            #rightmost "x" coordinate candidate in the "right_x_candidate"
                            #variable in the first "elif" statement.
                            for j in range(width_of_slice):
                                #In order for the "if" statement to run and set the
                                #punched hole's leftmost "x" coordinate candidate
                                #in the "left_x_candidate" variable, the counter 
                                #iterating over all of the "punched_hole_non_white_pixels_horizontal_projection_profile"
                                #elements must have a value below that of the last element of that list, 
                                #in order to avoid indexing errors, the current value of the Boolean 
                                #variable "left_x_punched_hole_reached" must be set to "False" to avoid 
                                #seting the leftmost coordinate more than once for any given punched 
                                #hole, and the corrected coordinate of the element at the index  
                                #"punched_hole_non_white_pixels_horizontal_projection_profile_index" of the 
                                #"punched_hole_non_white_pixels_horizontal_projection_profile" list needs 
                                #to be equal to the column index "j" of the slice array to ensure that 
                                #the same pixel is under consideration.
                                if (punched_hole_non_white_pixels_horizontal_projection_profile_index < 
                                len_punched_hole_non_white_pixels_horizontal_projection_profile and 
                                punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] == j and
                                not left_x_punched_hole_reached):
                                    #The condition "not (j == width_of_slice - 1 or 
                                    #punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + 1 in
                                    #punched_hole_white_pixels_horizontal_projection_profile" prevents the very last pixel from being detected as a punched 
                                    #hole note, and also any black pixels that are immediately followed by a white pixel, as these are merely 
                                    #artifacts. In any case, we will increment the value of "punched_hole_non_white_pixels_horizontal_projection_profile_index"
                                    #to move on to the next index in the next iteration of the "for" loop.
                                    if not (j == width_of_slice - 1 or 
                                    punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + j in
                                    punched_hole_white_pixels_horizontal_projection_profile):
                                        left_x_punched_hole_reached = True
                                        left_x_candidate = j
                                    
                                    punched_hole_non_white_pixels_horizontal_projection_profile_index += 1
                                #In order for the "elif" statement below to run, the Boolean variable 
                                #"left_x_punched_hole_reached" must already be set to "True", as we will be detecting 
                                #the rightmost coordinate of the punched hole. The next pixel at the corrected index 
                                #"punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + 1" 
                                #must be present in "punched_hole_white_pixels_horizontal_projection_profile", as this would indicate that this is 
                                #the last pixel of the punched hole before reaching a column found in the white pixels horizontal profile.
                                elif (punched_hole_non_white_pixels_horizontal_projection_profile_index < 
                                len_punched_hole_non_white_pixels_horizontal_projection_profile and
                                punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] == j and 
                                left_x_punched_hole_reached and (j == width_of_slice - 1 or 
                                punched_hole_non_white_pixels_horizontal_projection_profile[punched_hole_non_white_pixels_horizontal_projection_profile_index] + 1 in
                                punched_hole_white_pixels_horizontal_projection_profile)):
                                    right_x_candidate = j
                                    #The Boolean variable "left_x_punched_hole_reached" is 
                                    #reset to "False" in order to allow the code to find the 
                                    #next punched hole.
                                    left_x_punched_hole_reached = False
                                    punched_hole_non_white_pixels_horizontal_projection_profile_index += 1
                                     
                                    width_of_punched_hole_candidate = right_x_candidate - left_x_candidate
                                     
                                    if (width_of_punched_hole_candidate >= 
                                    punched_hole_diameter_pixels * (punched_hole_diameter_percentage_threshold/100)):

                                        #The nested list "nested_list_of_center_x_y_coordinates_of_punched_holes"
                                        #will contain lists of center "x, y" coordinates for each punched hole of 
                                        #the scoresheet and will be sorted along "x" coordinates in ascending order 
                                        #before extrapolating the notes and ticks corresponding to each punched hole.
                                        
                                        #The "x" coordinate is calculated by adding the "horizontal_shift_pixels_current_jpeg" 
                                        #(such that a positive shift would shift the notes to the right and a negative shift 
                                        #would bring them to the left) to the value of the left coordinate of the detected 
                                        #punched hole, plus half the punched hole pixel diameter to the left "x" coordinate 
                                        #of the slice ("sublist[0]") to allow to have an "x" coordinate relative to the start 
                                        #of the entire image.
                                        
                                        #The "y" coordinate is calculated by adding the "vertical_shift_pixels_current_jpeg" 
                                        #(such that a positive shift would shift the notes down and a negative shift would 
                                        #bring them upwards) to the value of the top coordinate of the detected punched hole,
                                        #plus half the punched hole pixel diameter ("current_note_center_y_coordinate") 
                                        #to the top "y" coordinate of the scoresheet, to allow to have a "y" coordinate 
                                        #relative to the start of the entire image.                                        
                                        nested_list_of_center_x_y_coordinates_of_punched_holes.append([sublist[0] + 
                                            left_x_candidate + width_of_punched_hole_candidate/2 + horizontal_shift_pixels_current_jpeg, 
                                            top_y_scoresheet + current_note_center_y_coordinate + vertical_shift_pixels_current_jpeg])

                                        #A pink vertical line spanning the 
                                        #punched hole's diameter is drawn.
                                        cv2.line(
                                            img=color_img,
                                            #The line's top "y" coordinate is calculated by subtracting half the
                                            #punched hole diameter from the punched hole's center "y" coordinate.
                                            pt1=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0]), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1] -  
                                            0.5*punched_hole_diameter_pixels)), 
                                            #The line's bottom "y" coordinate is calculated by adding half the
                                            #punched hole diameter to the punched hole's center "y" coordinate.
                                            pt2=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0]), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1] +
                                            0.5*punched_hole_diameter_pixels)), 
                                            #BGR color
                                            #color=(106, 190, 255),
                                            color=(119, 102, 238),
                                            thickness=2,
                                            lineType=cv2.LINE_AA)
                                            
                                        #A blue horizontal line spanning the 
                                        #punched hole's diameter is drawn. 
                                        cv2.line(
                                            img=color_img,
                                            #The line's left "x" coordinate is calculated by subtracting half the
                                            #punched hole diameter from the punched hole's center "x" coordinate.
                                            pt1=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0] -  
                                            0.5*punched_hole_diameter_pixels), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1])), 
                                            #The line's right "x" coordinate is calculated by adding half the
                                            #punched hole diameter to the punched hole's center "x" coordinate.
                                            pt2=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][0] +
                                            0.5*punched_hole_diameter_pixels), 
                                            int(nested_list_of_center_x_y_coordinates_of_punched_holes[-1][1])), 
                                            #BGR color
                                            #color=(166, 176, 64),
                                            color=(238, 204, 102),
                                            thickness=2,
                                            lineType=cv2.LINE_AA)
                                            
                                #If the Boolean variable "left_x_punched_hole_reached" is set to "True",
                                #yet the "elif" statement above didn't run, then it means that we are not 
                                #done traversing the punched hole, and therefore the value of the index 
                                #"punched_hole_non_white_pixels_horizontal_projection_profile_index" needs to be 
                                #incremented.
                                elif left_x_punched_hole_reached:
                                    punched_hole_non_white_pixels_horizontal_projection_profile_index += 1  

                #Once the nested list of punched hole center "[x, y]" coordinate lists
                #has been completely populated, it is sorted in ascending order along 
                #the "x" coordinates at the index zero to sort the notes in chronological 
                #order starting at the beginning of the song (lowest "x").
                nested_list_of_center_x_y_coordinates_of_punched_holes.sort(key=lambda x: x[0])
                #The following "for" loop will cycle over each "[x,y]" center coordinate in 
                #the sorted nested list "nested_list_of_center_x_y_coordinates_of_punched_holes"
                #and calculate the number of ticks between each successive note and extrapolate 
                #the notes from the "y" coordinates. The resulting "[ticks, midi note]" results 
                #for each successive note in chronological order will be appended to the list 
                #"nested_list_of_note_on_off_midi_cumulative_ticks", which will be used when procedurally generating 
                #the MIDI file.
                for j in range(len(nested_list_of_center_x_y_coordinates_of_punched_holes)):  
                    #If this is the first note ("j == 0") of a given scoresheet, then the "if" 
                    #statement below will set the value of "delta_x" to zero if it is also the 
                    #first scoresheet of the music track ("i == 0"). 
                    #For subsequent scoresheets, the difference between the punched hole's 
                    #center "x" coordinate and the left "x" coordinate of the scoresheet (which 
                    #represents the portion of the silence between notes on this scoresheet) will 
                    #be added the value of "x_pixel_width_after_last_note_of_previous_scoresheet" 
                    #to include the silence after the last note of the previous scoresheet as well, 
                    #as the two scoresheets were cut and are really contiguous.
                    if j == 0:
                        if i == 0:
                            delta_x = 0
                        else:
                            delta_x = (x_pixel_width_after_last_note_of_previous_scoresheet +
                            (nested_list_of_center_x_y_coordinates_of_punched_holes[j][0] - left_x_scoresheet))
                    #If this isn't the first note in a given scoresheet, then the value of "delta_x"
                    #is calculated by subtracting the center "x" coordinate of the previous note in 
                    #chronological order (at the index "j-1") from the center "x" coordinate of the 
                    #current note at index "j".
                    else:
                        delta_x = (nested_list_of_center_x_y_coordinates_of_punched_holes[j][0] -
                            nested_list_of_center_x_y_coordinates_of_punched_holes[j-1][0])
                    #If this is the last note of a scoresheet, then the value of 
                    #"x_pixel_width_after_last_note_of_previous_scoresheet" will be 
                    #set to the difference between the right "x" coordinate of the 
                    #scoresheet and the center "x" coordinate of this last note in 
                    #order to include the silence after this last note to the silence
                    #before the first note of the next scoresheet, as the two scoresheets 
                    #were cut and are really contiguous.
                    if j == len(nested_list_of_center_x_y_coordinates_of_punched_holes) - 1:
                        x_pixel_width_after_last_note_of_previous_scoresheet = (right_x_scoresheet - 
                            nested_list_of_center_x_y_coordinates_of_punched_holes[j][0])
                            
                    #If this is the first note ("j == 0") of the first scoresheet ("i == 0")
                    #for a given music track, then the value of "ticks" will be set to that 
                    #of "leading_silence_ticks" to include the requested leading delay.
                    if i == 0 and j == 0:
                        ticks = leading_silence_ticks
                    else:
                        #The number of ticks is calculated by first dividing "delta_x" by the number of 
                        #horizontal pixels per smallest measure ("width_of_one_smallest_measure_pixels") in order 
                        #to get the number of smallest measures between the two successive notes in chronological
                        #order. Then, this result is multiplied by the number of ticks per quarter notes, times 
                        #the quotient of four over the value of "smallest_measure_duration_denominator" to get 
                        #the number of ticks per smallest measure, which yields the number of ticks as the number 
                        #of smallest measures cancel out.
                        ticks = (delta_x/width_of_one_smallest_measure_pixels) * ticks_per_smallest_measure
                    
                    #Increment the value of "cumulative_ticks" by the value of "ticks".
                    cumulative_ticks += ticks
                    
                    #The list of of "float" note horizontal gridline "y" coordinates
                    #"list_of_music_box_note_center_y_coordinates" will be used to draw 
                    #the music box gridlines on the scoresheet and a copy of the list 
                    #will be used to extrapolate which note corresponds to the center 
                    #"y" coordinate of each punched hole. To to this, the center "y"
                    #coordinate will be appended to the list copy, which will then 
                    #be sorted, and the index of the newly added note will be obtained 
                    #with the "index()" method. Then the neighboring note that has the 
                    #nearest "y" coordinate will be selected.
                    temp_list_of_music_box_note_center_y_coordinates = list_of_music_box_note_center_y_coordinates.copy()
                    temp_list_of_music_box_note_center_y_coordinates.append(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1])
                    temp_list_of_music_box_note_center_y_coordinates.sort()
                    index_of_current_note = temp_list_of_music_box_note_center_y_coordinates.index(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1])
                    #If the index of the newly added note in the sorted list is equal to zero,
                    #then it necessarily means that the note is the first note in list of 
                    #music box note "y" coordinates "list_of_music_box_note_center_y_coordinates". 
                    if index_of_current_note == 0:
                        current_note_extrapolated_y = list_of_music_box_note_center_y_coordinates[0]
                    #Alternatively, if the index of the newly added note in the sorted list is equal 
                    #to the last index of the sorted list, then it necessarily means that the note 
                    #is the last note in list of music box note "y" coordinates 
                    #"list_of_music_box_note_center_y_coordinates". 
                    elif index_of_current_note == len(temp_list_of_music_box_note_center_y_coordinates) - 1:
                        current_note_extrapolated_y = list_of_music_box_note_center_y_coordinates[-1]
                    #Otherwise, the absolute value of the difference between the "y" coordinates of 
                    #the newly added note and the notes right before and right after it in the sorted 
                    #list will be used to determine which note corresponds to that punched hole. The 
                    #lowest absolute value result will mean that the punched hole is closest to that 
                    #music box note.
                    else:
                        previous_note_y = temp_list_of_music_box_note_center_y_coordinates[index_of_current_note-1]
                        next_note_y = temp_list_of_music_box_note_center_y_coordinates[index_of_current_note+1]
                        if abs(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1] - previous_note_y) <= abs(nested_list_of_center_x_y_coordinates_of_punched_holes[j][1] - next_note_y):
                            current_note_extrapolated_y = previous_note_y
                        else:
                            current_note_extrapolated_y = next_note_y
                    
                    #The extrapolated MIDI note is obtained by accessing the dictionary of music box 
                    #note center "y" coordinate keys to values made up of lists of notes in letter 
                    #format and MIDI notes ("note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict")
                    #with the extrapolated "y" coordinate ("current_note_extrapolated_y"), and then indexing the 
                    #list at the index 1 to retrieve the corresponding MIDI note.
                    extrapolated_midi_note = note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict[current_note_extrapolated_y][1]
                    #If the user has entered a semitone shift other than zero, it will be added to 
                    #the value of the extrapolated MIDI note. The shifted note will only be retained 
                    #if it falls within the MIDI range of 0-127, and the original value of the extrapolated 
                    #MIDI note will be used otherwise.
                    if semitone_shift != 0:
                        semitone_shifted_midi_note_candidate =  extrapolated_midi_note + semitone_shift
                        if semitone_shifted_midi_note_candidate >= 0 and semitone_shifted_midi_note_candidate <= 127:
                            extrapolated_midi_note = semitone_shifted_midi_note_candidate
                    
                    #The data for the "note_on" and "note_off" messages for each punched hole center coordinates 
                    #in chronological order will be appended to the list "nested_list_of_note_on_off_midi_cumulative_ticks", 
                    #which will be used when procedurally generating the MIDI file, as a tuple of three elements: 
                    #("note_on", midi note, cumulative_ticks).
                    nested_list_of_note_on_off_midi_cumulative_ticks.append(("note_on", 
                        extrapolated_midi_note, int(cumulative_ticks)))
                    nested_list_of_note_on_off_midi_cumulative_ticks.append(("note_off", 
                        extrapolated_midi_note, int(cumulative_ticks + ticks_per_smallest_measure)))
                    
                    color_img = cv2.putText(
                        img=color_img, 
                        #The dictionary of "float" note horizontal gridline "y" coordinate keys to 
                        #values made up of a list of the notes in letter form and corresponding midi 
                        #notes "note_center_y_coordinate_keys_to_list_of_note_and_midi_values_dict"
                        #will allow to tally up the extrapolated notes from the detected punched 
                        #hole center "y" coordinates. 
                        text=midi_notes_dict[extrapolated_midi_note],
                        org=(int(nested_list_of_center_x_y_coordinates_of_punched_holes[j][0] - 0.5*punched_hole_diameter_pixels + horizontal_shift_pixels_current_jpeg), 
                        int(top_y_scoresheet + nested_list_of_center_x_y_coordinates_of_punched_holes[j][1] + 0.5*punched_hole_diameter_pixels + vertical_shift_pixels_current_jpeg)), 
                        fontFace=cv2.FONT_HERSHEY_PLAIN,
                        fontScale=1,
                        color=(0, 0, 0),
                        thickness=1,
                        lineType=cv2.LINE_AA
                        )
                        
                #The cropped and annotated version of the "color_img" scoresheet array will be saved to 
                #a JPEG file, with the " (Annotated)" file name suffix. As JPEG images only support 
                #8-bit per channel data (CV_8U), we first need to cast the data to "np.uint8" before 
                #writing the image.
                cv2.imwrite(os.path.join(output_folder_path, jpg_names[i] + " (Annotated).jpg"), 
                    color_img[top_y_scoresheet:bottom_y_scoresheet + 1, left_x_scoresheet:right_x_scoresheet + 1].astype(np.uint8))
        
                #The function "display_progress" will display the progress string in the console
                #and return the estimated number of seconds for the code to complete.

                #The previous estimation of the remaining number of seconds is stored in the variable
                #"previous_estimated_seconds" and will be used instead of the current calculation
                #if it exceeds the previous estimation, so as to avoid the ETA timer increasing 
                #its estimation.
                
                #The value of "i+1" is passed in for the "current_jpeg_index" argument, as the 
                #JPEG file at the index "i" of the "jpeg_files" list has just finished being 
                #processed.
                previous_estimated_seconds = display_progress(i+1, first_jpeg_index, last_jpeg_index, start_time, previous_estimated_seconds)         
                
            #If some notes were detected on the scoresheet in the form of 
            #some non-white pixels, then the "if" statement below will run. 
            #If that is not the case, then the user likely needs decrease 
            #the value of the white pixel percentage threshold
            #("white_pixel_threshold_percentage), as no horizontal 
            #spaces between punched holes were detected in the image.
            else:
                print(undetectable_notes_error_string)
                input(press_any_key_string)
                sys.exit(1)  
        #The MIDI file is generated by first instantiating a "MidiFile" object,
        #setting the MIDI file type to 1 to allow multiple tracks and setting the 
        #value of the "ticks_per_beat" property to the value of the "ticks_per_quarter_note"
        #variable.
        mid = MidiFile()
        mid.type = 1
        mid.ticks_per_beat = ticks_per_quarter_note
        #The track zero will contain the tempo  and time signature.
        track_0 = MidiTrack()
        #The track zero is appended to the "MidiFile" object "mid".
        mid.tracks.append(track_0)
        track_0.append(MetaMessage("set_tempo", tempo=tempo_us_per_quarter_note, time=0))
        track_0.append(MetaMessage("time_signature", numerator=time_signature_numerator, denominator=time_signature_denominator, time=0))
        track_0.append(MetaMessage("end_of_track", time=0))
        #The track 1 will contain the "track_name", "text" and "copyright" metadata,
        #with the two latter being optional, and will be appended to the "MidiFile" 
        #object "mid".
        track_1 = MidiTrack()
        mid.tracks.append(track_1)
        track_1.append(MetaMessage("track_name", name=output_file_name))
        if midi_comment != "":
            track_1.append(MetaMessage("text", text=midi_comment))
        if midi_copyright_string != "":
            track_1.append(MetaMessage("copyright", text=midi_copyright_string))
                    
        #The data for the "note_on" and "note_off" messages for each punched hole center coordinates 
        #in chronological order was appended to the list "nested_list_of_note_on_off_midi_cumulative_ticks", 
        #which will be used when procedurally generating the MIDI file, as a tuple of three elements: 
        #("note_on", midi note, cumulative_ticks).
        
        #The tuple elements in the nested list "nested_list_of_note_on_off_midi_cumulative_ticks"
        #are sorted in chronological order of "cumulative_ticks", which is the third element in 
        #each tuple at index two. Sorting is once again necessary, even though the "x, y" coordinates 
        #used for extrapolating the notes have already been sorted chronologically, as these only 
        #represented "note_on" events that were played on the music box, and did not include the 
        #"note_off" messages, which are also considered events in the MIDI file, and so the 
        #"note_off" events were inserted right after "note_on" events when populating the list 
        #"nested_list_of_note_on_off_midi_cumulative_ticks". This will allow to calculate
        #the relative ticks between each sorted "note_on" and "note_off" element.
        nested_list_of_note_on_off_midi_cumulative_ticks.sort(key=lambda x:x[2])
        #The elements of the sorted list "nested_list_of_note_on_off_midi_cumulative_ticks",
        #which now represent the "note_on" and "note_off" events in chronological order,
        #will by cycled over and a "Message" will be appended to the track one for each 
        #of these events.
        for i in range(len(nested_list_of_note_on_off_midi_cumulative_ticks)):
            #If this is the first "note_on" event, then the relative ticks will be equal 
            #to the cumulative ticks value at the index two of the list, as the previous 
            #metadata messages for track one are all at time zero.
            if i == 0:
                relative_ticks = nested_list_of_note_on_off_midi_cumulative_ticks[i][2]
            #Subsequent "note_on" and "note_off" messages will have their relative ticks 
            #calculated by subtracting the value of the preceding message's cumulative 
            #ticks from that of the current message.
            else:
                relative_ticks = (nested_list_of_note_on_off_midi_cumulative_ticks[i][2] -
                    nested_list_of_note_on_off_midi_cumulative_ticks[i-1][2])
            #The "note_on" or "note_off" "Message" will be appended to the track one 
            #of the MIDI file, with the "note_on" or "note_off" string being accessed 
            #at the index zero of the tuple, and the note at the index one. The "time"
            #parameter is set to the value of "relative_ticks" calculated above and the 
            #"velocity" parameter is set to the "midi_velocity" user setting.
            track_1.append(Message(nested_list_of_note_on_off_midi_cumulative_ticks[i][0], 
                channel=0, 
                note=nested_list_of_note_on_off_midi_cumulative_ticks[i][1],
                velocity=midi_velocity,
                time=relative_ticks))
            #If this is the last "note_off" message at the last indes of the list 
            #"nested_list_of_note_on_off_midi_cumulative_ticks", then an "end_of_track"
            #"Message" will be appended to track one, with a "time" parameter equal to 
            #that of last "note_off" message, with the addition of "trailing_silence_ticks".
            if i == len(nested_list_of_note_on_off_midi_cumulative_ticks) - 1:
                track_1.append(MetaMessage("end_of_track", time = trailing_silence_ticks))
        #The MIDI file is saved to the output folder path.
        mid.save(os.path.join(output_folder_path, output_file_name + ".mid"))
        
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        input("\n" + textwrap.fill(f"Your MIDI file was successfully generated in the '{output_file_name}' subfolder!", width=columns) + "\n\nPress any key to continue.\n")

    else:
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        input("\n" + textwrap.fill(f"Please include some JPEG scans of the back sides of your scoresheets in the '{scans_folder_name}' subfolder.", width=columns) + "\n\nPress any key to continue.\n")
        
    return json_settings_dictionary  

#The "set_number_of_notes()" function will 
#set the number of notes for the music box.
def set_number_of_notes(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Music Box Number of Notes ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(number_of_notes_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the music box's number of notes (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_time_signature_numerator()" function will 
#set the time signature's numerator.
def set_time_signature_numerator(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Time Signature Numerator ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(time_signature_numerator_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the sime signature numerator (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_time_signature_denominator()" function will 
#set the time signature's denominator.
def set_time_signature_denominator(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Time Signature Denominator ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(time_signature_denominator_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the sime signature denominator (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_tempo_bpm()" function will 
#set the tempo in beats per minute (bpm).
def set_tempo_bpm(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Tempo in Beats per Minute (bpm) ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(tempo_bpm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the tempo in beats per minute (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_ticks_per_quarter_note()" function will 
#set the number of ticks per quarter note.
def set_ticks_per_quarter_note(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Ticks per Quarter Note ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(ticks_per_quarter_note_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the number of ticks per quarter note (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_width_of_ten_successive_smallest_measures_in_millimeters()" function will 
#set the number of millimeters for ten successive smallest measures.
def set_width_of_ten_successive_smallest_measures_in_millimeters(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Width of Ten Successive Smallest Measures in Millimeters ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(width_of_ten_smallest_measures_mm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the number millimeters for ten consecutive smallest boxes or measures on the scoresheet (above zero, decimals allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_smallest_measure_duration_denominator()" function will 
#set the denominator of the duration of the smallest measure.
def set_smallest_measure_duration_denominator(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Smallest Measure Duration Denominator ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(smallest_measure_duration_denominator_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the denominator of the duration of the smallest boxes or measures on the scoresheet (above zero), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_midi_velocity()" function will 
#set the MIDI velocity of each note.
def set_midi_velocity(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set MIDI Velocity ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(midi_velocity_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the MIDI velocity that will be used for every note (0-127), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 127:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_semitone_shift()" function will 
#set the semitone shift that will be applied 
#to all of the MIDI notes.
def set_semitone_shift(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Semitone Shift ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(semitone_shift_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the semitone shift that will be applied to every note (positive or negative integer), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)

            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_leading_silence_duration_in_milliseconds()" function will 
#set leading silence before the first note of the music track, in 
#milliseconds.
def set_leading_silence_duration_in_milliseconds(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Leading Silence Duration in Milliseconds ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(leading_silence_milliseconds_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the leading silence duration in milliseconds (0 and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_trailing_silence_duration_in_milliseconds()" function will 
#set trailing silence after the last note of the music track, in 
#milliseconds.
def set_trailing_silence_duration_in_milliseconds(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Trailing Silence Duration in Milliseconds ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(trailing_silence_milliseconds_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the trailing silence duration in milliseconds (0 and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Music Metrics Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "music_metrics_settings_menu()" function will run a "while is_in_submenu"
#loop that will allow the user to navigate the menu, and the loop will 
#be broken out of when they select the "Quit" option.
def music_metrics_settings_menu(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        music_metrics_settings_menu_actions_dict = {
        "1": [f"Music Box Number of Notes ({json_settings_dictionary["Number of Notes"]})", set_number_of_notes, ("Number of Notes", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "2": [f"Time Signature Numerator ({json_settings_dictionary["Time Signature Numerator"]})", set_time_signature_numerator, ("Time Signature Numerator", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "3": [f"Time Signature Denominator ({json_settings_dictionary["Time Signature Denominator"]})", set_time_signature_denominator, ("Time Signature Denominator", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "4": [f"Tempo in Beats per Minute (bpm) ({json_settings_dictionary["Tempo bpm"]})", set_tempo_bpm, ("Tempo bpm", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "5": [f"Ticks per Quarter Note ({json_settings_dictionary["Ticks per Quarter Note"]})", set_ticks_per_quarter_note, ("Ticks per Quarter Note", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "6": [f"Width of Ten Successive Smallest Measures in Millimeters ({json_settings_dictionary["Width of Ten Successive Smallest Measures in Millimeters"]})", set_width_of_ten_successive_smallest_measures_in_millimeters, ("Width of Ten Successive Smallest Measures in Millimeters", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "7": [f"Smallest Measure Duration Denominator ({json_settings_dictionary["Smallest Measure Duration Denominator"]})", set_smallest_measure_duration_denominator, ("Smallest Measure Duration Denominator", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "8": [f"Midi Velocity ({json_settings_dictionary["Midi Velocity"]})", set_midi_velocity, ("Midi Velocity", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "9": [f"Semitone Shift ({json_settings_dictionary["Semitone Shift"]})", set_semitone_shift, ("Semitone Shift", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "10": [f"Leading Silence Duration in Milliseconds ({json_settings_dictionary["Leading Silence Duration in Milliseconds"]})", set_leading_silence_duration_in_milliseconds, ("Leading Silence Duration in Milliseconds", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "11": [f"Trailing Silence Duration in Milliseconds ({json_settings_dictionary["Trailing Silence Duration in Milliseconds"]})", set_trailing_silence_duration_in_milliseconds, ("Trailing Silence Duration in Milliseconds", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "m": ["Main Menu", back_to_main_menu_function, (json_settings_dictionary,)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        music_metrics_settings_menu_actions_dict = textwrap_action_strings_in_menu_action_dict(music_metrics_settings_menu_actions_dict)

        print("=== Music Metrics Settings Menu ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()

        print(textwrap.fill("This menu will allow you to set the settings for the music metrics. Further details are available in the submenu options, or in the 'README.txt' file.", width=columns) + "\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(music_metrics_settings_menu_actions_dict, json_settings_dictionary)
    return json_settings_dictionary   

#The "set_midi_copyright_metadata_string()" function 
#will set the copyright MIDI metadata string.
def set_midi_copyright_metadata_string(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Copyright MIDI Metadata String  ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            #If an empty string is present either as the default or current metadata setting,
            #then the "Metadata not included in MIDI file" string will be printed on-screen.
            #Otherwise, the value of the "json_default_settings_dictionary" or "json_settings_dictionary"
            #will be displayed instead.           
            metadata_not_included_string = "Metadata not included in MIDI file"
            current_setting_string = metadata_not_included_string
            if json_settings_dictionary[json_settings_key].strip() != "":
                current_setting_string = json_settings_dictionary[json_settings_key]
            
            default_setting_string = metadata_not_included_string
            if json_default_settings_dictionary[json_settings_key].strip() != "":
                default_setting_string = json_default_settings_dictionary[json_settings_key]
            
            print(f"Current Setting: {current_setting_string} | Default: {default_setting_string}.\n")

            textwrapped_instructions_string = textwrap.fill(midi_copyright_string_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the copyright text that will be included in the MIDI file's metadata, leave empty to exclude this from the metadata, or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] MIDI File Metadata Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice.lower() == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice.lower() == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice.lower() == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice.lower() == "q":
                quit_function()
            user_input = choice
            
            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_midi_comment_metadata_string()" function 
#will set the comment MIDI metadata string.
def set_midi_comment_metadata_string(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set the Comment MIDI Metadata String  ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            #If an empty string is present either as the default or current metadata setting,
            #then the "Metadata not included in MIDI file" string will be printed on-screen.
            #Otherwise, the value of the "json_default_settings_dictionary" or "json_settings_dictionary"
            #will be displayed instead.           
            metadata_not_included_string = "Metadata not included in MIDI file"
            current_setting_string = metadata_not_included_string
            if json_settings_dictionary[json_settings_key].strip() != "":
                current_setting_string = json_settings_dictionary[json_settings_key]
            
            default_setting_string = metadata_not_included_string
            if json_default_settings_dictionary[json_settings_key].strip() != "":
                default_setting_string = json_default_settings_dictionary[json_settings_key]
            
            print(f"Current Setting: {current_setting_string} | Default: {default_setting_string}.\n")

            textwrapped_instructions_string = textwrap.fill(midi_comment_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the comment text that will be included in the MIDI file's metadata, leave empty to exclude this from the metadata, or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] MIDI File Metadata Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice.lower() == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice.lower() == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice.lower() == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice.lower() == "q":
                quit_function()
            user_input = choice
            
            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "midi_file_metadata_settings_menu()" function will run a "while is_in_submenu"
#loop that will allow the user to navigate the menu, and the loop will 
#be broken out of when they select the "Quit" option.
def midi_file_metadata_settings_menu(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        midi_file_metadata_settings_menu_actions_dict = {
        "1": [f"Midi Copyright Metadata String", set_midi_copyright_metadata_string, ("Midi Copyright Metadata String", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "2": [f"Midi Comment String", set_midi_comment_metadata_string, ("Midi Comment String", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "m": ["Main Menu", back_to_main_menu_function, (json_settings_dictionary,)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        midi_file_metadata_settings_menu_actions_dict = textwrap_action_strings_in_menu_action_dict(midi_file_metadata_settings_menu_actions_dict)

        print("=== MIDI File Metadata Settings Menu ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()

        print(textwrap.fill("This menu will allow you to set the MIDI file metadata settings. Further details are available in the submenu options, or in the 'README.txt' file.", width=columns) + "\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(midi_file_metadata_settings_menu_actions_dict, json_settings_dictionary)
    return json_settings_dictionary 

#The "set_dpi()" function will set the resolution 
#in dpi of the JPEG scoresheet scans.
def set_dpi(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Scans Resolution in DPI ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(dpi_setting_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the dpi resolution of your scanned scoresheet JPEG files (100 or higher), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_page_rotation_angle()" function will set the  
#rotation angle in degrees of the JPEG scoresheet scans.
def set_page_rotation_angle(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Page Rotation Angle ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(page_rotation_angle_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the rotation angle for your scanned scoresheet JPEG files (0 - 360, positive or negative), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)

            #The "set_numeric_setting()" function will set the value of the setting found while accessing
            #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
            #value ("setting_value"). 
            json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
            json_settings_file_path_name)

        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_contrast_level()" function will set the  
#contrast level for the JPEG scoresheet scans.
def set_contrast_level(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Contrast Level ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(contrast_level_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the contrast level for your scanned scoresheet JPEG files (0 and above, decimal values allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_brightness_level()" function will set the  
#brightness level for the JPEG scoresheet scans.
def set_brightness_level(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Brightness Level ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(brightness_level_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the brightness level for the annotated JPEG files (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_paper_color_grayscale_filter_threshold()" function will set the  
#grayscale value filter threshold for the JPEG scoresheet scans.
def set_paper_color_grayscale_filter_threshold(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Grayscale Filter Threshold Value ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(paper_color_grayscale_filter_threshold_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the grayscale value filter threshold (0 - 255), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 255:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_black_pixel_threshold_percentage()" 
#function will set the black pixel threshold percentage.
def set_black_pixel_threshold_percentage(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Black Pixel Threshold Percentage ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(black_pixel_threshold_percentage_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the black pixel percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_white_pixel_threshold_percentage()" 
#function will set the white pixel threshold percentage.
def set_white_pixel_threshold_percentage(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set White Pixel Threshold Percentage ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(white_pixel_threshold_percentage_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the white pixel percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_white_pixel_threshold_percentage_for_slices()" 
#function will set the white pixel threshold percentage 
#for slices.
def set_white_pixel_threshold_percentage_for_slices(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set White Pixel Threshold Percentage for Slices ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(white_pixel_threshold_percentage_slice_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the white pixel percentage threshold for slices (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_punched_hole_diameter_percentage_threshold()" 
#function will set the punched hole diameter percentage 
#threshold.
def set_punched_hole_diameter_percentage_threshold(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Punched Hole Diameter Percentage Threshold ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(punched_hole_diameter_percentage_threshold_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the punched hole diameter percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_punched_hole_percentage_overlap_threshold()" 
#function will set the punched hole overlap percentage 
#threshold.
def set_punched_hole_percentage_overlap_threshold(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Punched Hole Overlap Percentage Threshold ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(punched_hole_percent_overlap_threshold_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the punched hole overlap percentage threshold (0 - 100), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0 and user_input <= 100:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_punched_hole_diameter_in_millimeters()" 
#function will set the punched hole diameter in 
#millimeters.
def set_punched_hole_diameter_in_millimeters(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Punched Hole Diameter in Millimeters ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(punched_hole_diameter_mm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the punched diameter in millimeters (above zero, decimal values allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_scoresheet_grid_height_in_millimeters()" 
#function will set the height of the scoresheet 
#grid in millimeters.
def set_scoresheet_grid_height_in_millimeters(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Scoresheet Grid Height in Millimeters ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(scoresheet_grid_height_mm_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the height of the scoresheet grid in millimeters (above zero, decimal values allowed), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = float(choice)
            if user_input > 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_vertical_shift_in_pixels()" 
#function will set the vertical shift 
#by which all of the punched holes' 
#center "x, y" coordinates will be 
#shifted by.
def set_vertical_shift_in_pixels(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Vertical Shift in Pixels ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(vertical_shift_pixels_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the vertical shift in pixels (zero and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "set_horizontal_shift_in_pixels()" 
#function will set the horizontal shift 
#by which all of the punched holes' 
#center "x, y" coordinates will be 
#shifted by.
def set_horizontal_shift_in_pixels(json_settings_key, json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_sub_submenu
    is_in_sub_submenu = True

    while is_in_sub_submenu:
        try:
            #The "clear_screen()" function will clear the CLI screen
            #using the appropriate command depending on the operating system.
            clear_screen()

            print("=== Set Horizontal Shift in Pixels ===\n\n")

            #The function "get_terminal_dimensions()" will return the number of columns 
            #and rows in the console, to allow to properly format the text and dividers.
            columns, lines = get_terminal_dimensions()
            
            print(f"Current Setting: {json_settings_dictionary[json_settings_key]} | Default: {json_default_settings_dictionary[json_settings_key]}.\n")

            textwrapped_instructions_string = textwrap.fill(horizontal_shift_pixels_comment_string, width=columns)
            textwrapped_input_string = textwrap.fill("Enter the horizontal shift in pixels (zero and above), or select one of the above options:", width=columns)

            print(textwrapped_instructions_string + " ")
            print(f"\n[r] Reset to the Default Setting\n[b] Image Processing Settings Menu\n[m] Main Menu\n[q] Quit\n")
            choice = input(textwrapped_input_string + " ").strip().lower()

            if choice == "":
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("").
                continue
            elif choice == "m":
                #The function "back_to_main_menu_function()"
                #will set the Boolean flags "is_in_submenu" and 
                #"is_in_sub_submenu" to "False", which will break the submenu
                #"while" loops and return to the main menu.
                back_to_main_menu_function(json_settings_dictionary)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("m").
                continue
            elif choice == "b":
                is_in_sub_submenu = False
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("b").
                continue
            elif choice == "r":
                #The "reset_to_default_setting()" function will reset the setting to its default value
                #found while accessing the value of the "json_default_settings_dictionary" dictionary 
                #with the key "setting_label_key". 
                #The "True" return value (if used) will break the submenu
                #loop and allow to return to the main menu or
                #the nested menu.
                json_settings_dictionary = reset_to_default_setting(json_settings_key, json_settings_dictionary, 
                    json_default_settings_dictionary, json_settings_file_path_name)
                #A continue needs to be used, as we don't want 
                #the code below the "elif" statements to run,
                #which would cause a ValueError on int("r").
                continue
            elif choice == "q":
                quit_function()
            user_input = int(choice)
            if user_input >= 0:
                #The "set_numeric_setting()" function will set the value of the setting found while accessing
                #the "json_settings_dictionary" dictionary with the key "setting_label_key" to the provided
                #value ("setting_value"). 
                json_settings_dictionary = set_numeric_setting(user_input, json_settings_key, json_settings_dictionary, 
                json_settings_file_path_name)
            else:
                input("\nInvalid choice, press any key to continue.") 
        except ValueError:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "image_processing_settings_menu()" function will run a "while is_in_submenu"
#loop that will allow the user to navigate the menu, and the loop will 
#be broken out of when they select the "Quit" option.
def image_processing_settings_menu(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        image_processing_settings_menu_actions_dict = {
        "1": [f"Scan Resolution in DPI ({json_settings_dictionary["Scan Resolution in DPI"]})", set_dpi, ("Scan Resolution in DPI", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "2": [f"Page Rotation Angle ({json_settings_dictionary["Page Rotation Angle"]})", set_page_rotation_angle, ("Page Rotation Angle", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "3": [f"Contrast Level ({json_settings_dictionary["Contrast Level"]})", set_contrast_level, ("Contrast Level", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "4": [f"Brightness Level ({json_settings_dictionary["Brightness Level"]})", set_brightness_level, ("Brightness Level", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "5": [f"Paper Color Grayscale Filter Threshold ({json_settings_dictionary["Paper Color Grayscale Filter Threshold"]})", set_paper_color_grayscale_filter_threshold, ("Paper Color Grayscale Filter Threshold", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "6": [f"Black Pixel Threshold Percentage ({json_settings_dictionary["Black Pixel Threshold Percentage"]})", set_black_pixel_threshold_percentage, ("Black Pixel Threshold Percentage", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "7": [f"White Pixel Threshold Percentage ({json_settings_dictionary["White Pixel Threshold Percentage"]})", set_white_pixel_threshold_percentage, ("White Pixel Threshold Percentage", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "8": [f"White Pixel Threshold Percentage for Slices ({json_settings_dictionary["White Pixel Threshold Percentage for Slices"]})", set_white_pixel_threshold_percentage_for_slices, ("White Pixel Threshold Percentage for Slices", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "9": [f"Punched Hole Diameter Percentage Threshold ({json_settings_dictionary["Punched Hole Diameter Percentage Threshold"]})", set_punched_hole_diameter_percentage_threshold, ("Punched Hole Diameter Percentage Threshold", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "10": [f"Punched Hole Percentage Overlap Threshold ({json_settings_dictionary["Punched Hole Percentage Overlap Threshold"]})", set_punched_hole_percentage_overlap_threshold, ("Punched Hole Percentage Overlap Threshold", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "11": [f"Punched Hole Diameter in Millimeters ({json_settings_dictionary["Punched Hole Diameter in Millimeters"]})", set_punched_hole_diameter_in_millimeters, ("Punched Hole Diameter in Millimeters", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "12": [f"Scoresheet Grid Height in Millimeters ({json_settings_dictionary["Scoresheet Grid Height in Millimeters"]})", set_scoresheet_grid_height_in_millimeters, ("Scoresheet Grid Height in Millimeters", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "13": [f"Vertical Shift in Pixels ({json_settings_dictionary["Vertical Shift in Pixels"]})", set_vertical_shift_in_pixels, ("Vertical Shift in Pixels", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "14": [f"Horizontal Shift in Pixels ({json_settings_dictionary["Horizontal Shift in Pixels"]})", set_horizontal_shift_in_pixels, ("Horizontal Shift in Pixels", json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "m": ["Main Menu", back_to_main_menu_function, (json_settings_dictionary,)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        image_processing_settings_menu_actions_dict = textwrap_action_strings_in_menu_action_dict(image_processing_settings_menu_actions_dict)

        print("=== Image Processing Settings Menu ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()

        print(textwrap.fill("This menu will allow you to set the settings that will help the code locate the punched holes. Further details are available in the submenu options, or in the 'README.txt' file.", width=columns) + "\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(image_processing_settings_menu_actions_dict, json_settings_dictionary)
    return json_settings_dictionary     

#The "reset_all_settings()" function will set the value "json_settings_dictionary"
#to that of "json_default_settings_dictionary" and save the changes to the JSON file.
def reset_all_settings(json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name):

    global is_in_submenu
    is_in_submenu = True

    while is_in_submenu:

        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        print("=== Reset All Settings ===\n\n")

        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        textwrapped_input_string = textwrap.fill("Are you sure you want to reset all of the settings? Enter (y/n), or select one of the above options: ", width=columns)
        
        print(f"[m] Main Menu\n[q] Quit\n")

        choice = input(textwrapped_input_string + " ").strip().lower()
        if choice in ["", "n"]:
            #A continue needs to be used, as we don't want 
            #the code below the "elif" statements to run,
            #which would cause a ValueError on int("").
            continue
        elif choice == "m":
            #The function "back_to_main_menu_function()"
            #will set the Boolean flags "is_in_submenu" and 
            #"is_in_sub_submenu" to "False", which will break the submenu
            #"while" loops and return to the main menu.
            return json_settings_dictionary
        elif choice == "q":
            quit_function()
        elif choice == "y":           
            #A deep copy (since it contains a list of deleted pages) of 
            #"json_default_settings_dictionary" is made so as to avoid having
            #both "json_settings_dictionary" and "json_default_settings_dictionary"
            #pointing to the same address.
            json_settings_dictionary = copy.deepcopy(json_default_settings_dictionary)
            #The function "atomic_save()" will create a temporary JSON file with the updated changes.
            #If the files is created successfully, then the files will be swapped. If a problem is 
            #encountered, the temp file will be unlinked and an error log will be reported.
            atomic_save(json_settings_dictionary, json_settings_file_path_name)
            print("\nAll settings have successfully been reset to their default values.")
            input("\nPress any key continue.")
        else:
            input("\nInvalid choice, press any key to continue.")
    return json_settings_dictionary

#The "main_menu()" function will run a "while True"
#loop that will allow the user to navigate the menu, and the
#loop will be broken out of when they select the "Quit" option,
#or when they press Ctrl+C (SIGINT, Signal Interrupt).
def main_menu(json_settings_dictionary, json_default_settings_dictionary, cwd, json_settings_file_path_name):

    while True:
        #The "clear_screen()" function will clear the CLI screen
        #using the appropriate command depending on the operating system.
        clear_screen()

        menu_actions_dict = {
        "1": ["Generate MIDI File with Current Settings", generate_midi_file, (json_settings_dictionary, json_default_settings_dictionary, cwd)],
        "2": ["Music Metrics Settings Menu (Settings regarding the tempo, time signature, etc.)", music_metrics_settings_menu, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "3": ["MIDI File Metadata (Copyright information and comment string that are embedded in the MIDI file)", midi_file_metadata_settings_menu, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "4": ["Image Processing Settings Menu (Settings that help the code locate the punched holes)", image_processing_settings_menu, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "r": ["Reset Defaults", reset_all_settings, (json_settings_dictionary, json_default_settings_dictionary, json_settings_file_path_name)],
        "q": ["Quit", quit_function, ()]}

        #The function "textwrap_action_strings_in_menu_action_dict()", which takes in 
        #a menu action dictionary comprised of one character keys and values made up
        #of a three-member tuple (action string, function, function arguments).
        #The action strings ("value[0]") will be textwrapped and the modified
        #dictionary will be returned.
        menu_actions_dict = textwrap_action_strings_in_menu_action_dict(menu_actions_dict)

        print("  MusicReader")
        print("=== Main Menu ===\n\n")

        #The function "run_menu" will retrieve and call the function
        #at the appropriate choice key in the "menu_actions_dict"
        json_settings_dictionary = run_menu(menu_actions_dict, json_settings_dictionary)


#The "main()" function will initialize the path variables and the "json_settings_dictionary" and 
#"json_default_settings_dictionary" dictionaries by calling the "load_json_data()" function.
#It will then initiate the main menu loop by calling the "main_menu()" function.
def main():
    #Register the Signal Interrupt (SIGINT) handler that will
    #call the "signal_interrupt_signal_handler()" function 
    #when the user presses on CTRL + C to exit the app.

    #The function "signal_interrupt_signal_handler()" will call
    #"sys.exit(0)" to exit the program normally.
    signal.signal(signal.SIGINT, signal_interrupt_signal_handler)

    cwd = os.getcwd()

    #The function "get_terminal_dimensions()" will return the number of columns 
    #and rows in the console, to allow to properly format the text and dividers.
    columns, lines = get_terminal_dimensions()
    
    #If either the "Scans" subfolder is missing, or if it is empty,
    #it will be created and the code will exit the application while 
    #printing the "missing_scans_string" on-screen.
    missing_scans_string = "\n" + textwrap.fill("Please add the scanned scoresheet JPEG files in the 'Scans' subfolder of the MusicReader folder and launch the application again.", width=columns) + "\n"     
    if not os.path.exists(os.path.join(cwd, scans_folder_name)):
        os.mkdir(os.path.join(cwd, scans_folder_name))
        print(missing_scans_string)
        input(press_any_key_string)
        sys.exit(1)
    else:
        jpeg_path = os.path.join(cwd, scans_folder_name, "*.jpg")
        jpeg_files = glob.glob(jpeg_path)
        if jpeg_files == []:
            print(missing_scans_string)
            input(press_any_key_string)
            sys.exit(1)
     
    json_settings_file_path_name = os.path.join(cwd, "settings.json")

    #The function "load_json_data()" will load the JSON data from file
    #and store them in the "json_settings_dictionary", or initialize the
    #dictionary based on the values of "json_default_settings_dictionary".
    json_default_settings_dictionary, json_settings_dictionary = load_json_data(json_settings_file_path_name)

    #The "main_menu()" function will run a "while True"
    #loop that will allow the user to navigate the menu, and the
    #loop will be broken out of when they select the "Quit" option,
    #or when they press Ctrl+C (SIGINT, Signal Interrupt).
    main_menu(json_settings_dictionary, json_default_settings_dictionary, cwd, json_settings_file_path_name)
 

if __name__ == '__main__':

    try:
        scans_folder_name = "Scans"
        press_any_key_string = "Press any key to continue." 

        #The strings below will be used as comments in the JSON file
        #and in the menus, so they are instantiated as global variables.
        dpi_setting_comment_string = f"The 'Scan Resolution in DPI' corresponds to the resolution, in dots per inch (DPI), of the scanned scoresheet JPEG files located in the '{scans_folder_name}' subfolder (default setting: 200)."
        page_rotation_angle_comment_string = "The 'Page Rotation Angle' corresponds to the angle, in degrees, that the JPEG scan needs to be rotated by in order for the bottom of the long end of the scoresheet to line up with the bottom of the screen, with positive angle values rotating clockwise and negative angle values rotating counterclockwise (default setting: -90)."
        contrast_level_comment_string = "The 'Contrast Level' setting will adjust the contrast level of the JPEG scan images, with a contrast level of one resulting in no changes, a value less than one and greater than zero decreasing the contrast, and a value above one increasing the contrast. Increasing the contrast will darken the pixels of the punched holes and the pixels outside of the scoresheet (remember to line the lid of your flatbed scanner with black construction paper), while bleaching out any blemishes or shadows on the backside of the scoresheet that was scanned, thus making it easier for the code to locate the punched holes. (default setting: 5.0)."
        brightness_level_comment_string = "The 'Brightness Level', with possible values spanning from 0 to 100, inclusively, will determine to what extent the generated cropped JPEG images will be brightened before annotating them (as the punched holes can be very dark, which would make the written notes difficult to read), with a value of 100 leading to an entirely white image and a value of zero to a black image. If you have scanned your scoresheets using the lightest setting and with a black sheet of construction paper lining the flatbed scanner's lid, then a setting of about 80 should work well (default setting: 80)."
        paper_color_grayscale_filter_threshold_comment_string = "The 'Paper Color Grayscale Filter Threshold', with possible values spanning from 0 to 255, inclusively, will determine the grayscale value cutoff point above which pixels on the contrast-adjusted image will be set to white, with the other pixels being set to black. For example, a threshold of 245 would set all the pixels lighter than it (greater than 245) to 255 (white) and the other pixels to 0 (black) (default setting: 245)."
        black_pixel_threshold_percentage_comment_string = "The 'Black Pixel Threshold Percentage', with possible values spanning from 0 to 100, inclusively, will determine the proportion of black pixels above which a column or row of pixels is considered to be outside of the scoresheet, as the scanner lid was lined with black construction paper to make the punched holes and edges of the scoresheet appear black. This value will be used when auto-cropping the scoresheet (default setting: 95)."
        white_pixel_threshold_percentage_comment_string = "The 'White Pixel Threshold Percentage', with possible values spanning from 0 to 100, inclusively, will determine which columns of pixels spanning the height of the cropped scoresheet are almost exclusively comprised of white pixels (the percentage of white pixels will be greater than or equal to that percentage threshold), with other columns of pixels falling short of the threshold containing some black punched holes (default value: 99)."
        white_pixel_threshold_percentage_slice_comment_string = "The 'White Pixel Threshold Percentage for Slices', with possible values spanning from 0 to 100, inclusively, will determine which pixels, when pinpointing the exact coordinates of the punched holes in smaller subsections of the JPEG images, correspond to the black punched holes. As there are fewer pixels being considered, the threshold needs to be in the order of magnitude of 80%, as opposed to the 99% threshold ('White Pixel Threshold Percentage') that was used to detect black pixels across the entire height of the scoresheet, which is mostly comprised of the white paper color (default value 80)."
        punched_hole_diameter_percentage_threshold_comment_string = "The 'Punched Hole Diameter Percentage Threshold', with possible values spanning from 0 to 100, will determine which group of black pixels are wide or tall enough to be punched holes. A value of about 80% of the pixel value of 'Punched Hole Diameter in Millimeters' works well (default value: 80)."
        punched_hole_percent_overlap_threshold_comment_string = "The 'Punched Hole Percentage Overlap Threshold', with possible values spanning from 0 to 100, inclusively, will determine when overlapping punched holes on successive note lines (e.g., C#5 and C5) will be considered to be distinct punched holes. The percentage represents the height percentage in excess of 100% of the punched hole pixel diameter (so a setting of 25% means 125% of the diameter) needed for the detected black pixels to be split up into two or more successive notes (default setting 25)."          
        punched_hole_diameter_mm_comment_string = "The 'Punched Hole Diameter in Millimeters' represents the measured diameter of the punched holes on your scoresheets, in millimeters (mm). This will be used by the code to determine when a sufficient amount of successive black pixels have been detected for them to belong to a punched hole (default setting: 2.5)."         
        scoresheet_grid_height_mm_comment_string = "The 'Scoresheet Grid Height in Millimeters' is the measured height of the grid on the front side of your scoresheet, in millimeters (mm). This, along with the resolution of your scan in dots per inches ('Scan Resolution in DPI') and the number of notes of your music box ('Number of Notes') will be used to locate the exact position of the horizontal note lines on the scanned backside of your scoresheets (default setting: 58.0)."
        number_of_notes_comment_string = "The 'Number of Notes' is the number of notes on your music box (default setting: 30)."
        tempo_bpm_comment_string = "The 'Tempo bpm' is your music track's tempo expressed as the number of beats per minute (bpm) (default setting: 120)."
        ticks_per_quarter_note_comment_string = "The 'Ticks per Quarter Note' represents the number of ticks (the MIDI time measure) per quarter note. A high value such as 960 allows for higher resolution when determining the exact timing of the punched holes, so that it better reflects the results you have obtained on your music box (default setting: 960)."
        width_of_ten_smallest_measures_mm_comment_string = "The 'Width of Ten Successive Smallest Measures in Millimeters' is the width of ten consecutive smallest boxes or measures on your scoresheet, in millimeters (mm). This measurement, along with the resolution of your scan in dots per inches ('Scan Resolution in DPI') will be used to convert the number of horizontal pixels between the center of punched holes to ticks, which are the MIDI time unit (default setting: 40.0)."
        smallest_measure_duration_denominator_comment_string = "The 'Smallest Measure Duration Denominator' represents the duration of the smallest box or measure on your music box score sheet. For example if the duration of the smallest measure is 1/16th of a note, the setting's value would be 16 (default value: 16)."        
        time_signature_numerator_comment_string = "The 'Time Signature Numerator' is the numerator of the time signature, e.g., 3 for a 3/4 time signature (default setting: 4)."
        time_signature_denominator_comment_string = "The 'Time Signature Denominator' represents the denominator of the time signature, e.g., 4 for a 3/4 time signature (default setting: 4)."        
        leading_silence_milliseconds_comment_string = "The 'Leading Silence Duration in Milliseconds' is the duration of the silence that will be inserted right before the first note of your music track, in milliseconds (ms) (default value: 250)."
        trailing_silence_milliseconds_comment_string = "The 'Trailing Silence Duration in Milliseconds' represents the duration of the silence that will be inserted right after the last note of your music track, in milliseconds (ms) (default value: 500)."
        vertical_shift_pixels_comment_string = "The 'Vertical Shift in Pixels' is the vertical shift in pixels that will be applied to all of your detected punched holes' center 'x,y' coordinates. This can come in handy for example if your scoresheet has a top margin that is larger than the bottom margin. In such a case, simply pass in the number of pixels for the vertical shift (a positive value shifts down and a negative value shifts up) (default value: 0)."
        horizontal_shift_pixels_comment_string = "The 'Horizontal Shift in Pixels' represents the horizontal shift in pixels that will be applied to all of your detected punched holes' center 'x,y' coordinates. Simply pass in the number of pixels for the horizontal shift (a positive value shifts to the right and a negative value shifts leftwards) (default value: 0)."
        midi_velocity_comment_string = "The 'Midi Velocity', with possible values between 0 (no sound) and 127 (full velocity or fff), represents the output level or loudness of the note (default value 64)."
        semitone_shift_comment_string = "The 'Semitone Shift' is the number of semitones by which all of your notes will be shifted up (positive value) or down (negative value) (default value: 0)."     
        midi_copyright_string_comment_string = "The 'Midi Copyright Metadata String' represents the copyright text that will show up in the MIDI file's metadata information (default value: \"\" or empty string)."
        midi_comment_comment_string = "The 'Midi Comment String' is the comment text that will show up in the MIDI file's metadata information (default value: \"\" or empty string)."
 
        main()
        
    except Exception as e:
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        troubleshooting_step_1_string = textwrap.fill("1. Please manually back up 'settings.json' if you need to salvage your user settings.", width=columns)
        troubleshooting_step_2_string = textwrap.fill("2. Once backed up, you can delete the original copy of 'settings.json' in the root folder to reset to the default settings and launch the app again.", width=columns)

        print("\n" + "=" * columns)
        print("CRITICAL ERRROR ENCOUNTERED")
        print("\nDetails:", e)
        print("\n" + "=" * columns)

        print("\nTroubleshooting Steps:\n")
        print(troubleshooting_step_1_string)
        print(troubleshooting_step_2_string)

        #The function "write_entry_in_error_log()" will write 
        #the full technical traceback error to the error log.
        write_entry_in_error_log()

        #Exit with error code
        sys.exit(1)""")

    with open("README.txt", "w", encoding="utf-8") as f:
        f.write(README_STRING)

    with open("LICENSE.txt", "w", encoding="utf-8") as f:
        f.write(LICENSE_STRING)

    with open("source_code.py", "w", encoding="utf-8") as f:
        f.write(SOURCE_CODE_STRING)

    try:
        scans_folder_name = "Scans"
        press_any_key_string = "Press any key to continue." 

        #The strings below will be used as comments in the JSON file
        #and in the menus, so they are instantiated as global variables.
        dpi_setting_comment_string = f"The 'Scan Resolution in DPI' corresponds to the resolution, in dots per inch (DPI), of the scanned scoresheet JPEG files located in the '{scans_folder_name}' subfolder (default setting: 200)."
        page_rotation_angle_comment_string = "The 'Page Rotation Angle' corresponds to the angle, in degrees, that the JPEG scan needs to be rotated by in order for the bottom of the long end of the scoresheet to line up with the bottom of the screen, with positive angle values rotating clockwise and negative angle values rotating counterclockwise (default setting: -90)."
        contrast_level_comment_string = "The 'Contrast Level' setting will adjust the contrast level of the JPEG scan images, with a contrast level of one resulting in no changes, a value less than one and greater than zero decreasing the contrast, and a value above one increasing the contrast. Increasing the contrast will darken the pixels of the punched holes and the pixels outside of the scoresheet (remember to line the lid of your flatbed scanner with black construction paper), while bleaching out any blemishes or shadows on the backside of the scoresheet that was scanned, thus making it easier for the code to locate the punched holes. (default setting: 5.0)."
        brightness_level_comment_string = "The 'Brightness Level', with possible values spanning from 0 to 100, inclusively, will determine to what extent the generated cropped JPEG images will be brightened before annotating them (as the punched holes can be very dark, which would make the written notes difficult to read), with a value of 100 leading to an entirely white image and a value of zero to a black image. If you have scanned your scoresheets using the lightest setting and with a black sheet of construction paper lining the flatbed scanner's lid, then a setting of about 80 should work well (default setting: 80)."
        paper_color_grayscale_filter_threshold_comment_string = "The 'Paper Color Grayscale Filter Threshold', with possible values spanning from 0 to 255, inclusively, will determine the grayscale value cutoff point above which pixels on the contrast-adjusted image will be set to white, with the other pixels being set to black. For example, a threshold of 245 would set all the pixels lighter than it (greater than 245) to 255 (white) and the other pixels to 0 (black) (default setting: 245)."
        black_pixel_threshold_percentage_comment_string = "The 'Black Pixel Threshold Percentage', with possible values spanning from 0 to 100, inclusively, will determine the proportion of black pixels above which a column or row of pixels is considered to be outside of the scoresheet, as the scanner lid was lined with black construction paper to make the punched holes and edges of the scoresheet appear black. This value will be used when auto-cropping the scoresheet (default setting: 95)."
        white_pixel_threshold_percentage_comment_string = "The 'White Pixel Threshold Percentage', with possible values spanning from 0 to 100, inclusively, will determine which columns of pixels spanning the height of the cropped scoresheet are almost exclusively comprised of white pixels (the percentage of white pixels will be greater than or equal to that percentage threshold), with other columns of pixels falling short of the threshold containing some black punched holes (default value: 99)."
        white_pixel_threshold_percentage_slice_comment_string = "The 'White Pixel Threshold Percentage for Slices', with possible values spanning from 0 to 100, inclusively, will determine which pixels, when pinpointing the exact coordinates of the punched holes in smaller subsections of the JPEG images, correspond to the black punched holes. As there are fewer pixels being considered, the threshold needs to be in the order of magnitude of 80%, as opposed to the 99% threshold ('White Pixel Threshold Percentage') that was used to detect black pixels across the entire height of the scoresheet, which is mostly comprised of the white paper color (default value 80)."
        punched_hole_diameter_percentage_threshold_comment_string = "The 'Punched Hole Diameter Percentage Threshold', with possible values spanning from 0 to 100, will determine which group of black pixels are wide or tall enough to be punched holes. A value of about 80% of the pixel value of 'Punched Hole Diameter in Millimeters' works well (default value: 80)."
        punched_hole_percent_overlap_threshold_comment_string = "The 'Punched Hole Percentage Overlap Threshold', with possible values spanning from 0 to 100, inclusively, will determine when overlapping punched holes on successive note lines (e.g., C#5 and C5) will be considered to be distinct punched holes. The percentage represents the height percentage in excess of 100% of the punched hole pixel diameter (so a setting of 25% means 125% of the diameter) needed for the detected black pixels to be split up into two or more successive notes (default setting 25)."          
        punched_hole_diameter_mm_comment_string = "The 'Punched Hole Diameter in Millimeters' represents the measured diameter of the punched holes on your scoresheets, in millimeters (mm). This will be used by the code to determine when a sufficient amount of successive black pixels have been detected for them to belong to a punched hole (default setting: 2.5)."         
        scoresheet_grid_height_mm_comment_string = "The 'Scoresheet Grid Height in Millimeters' is the measured height of the grid on the front side of your scoresheet, in millimeters (mm). This, along with the resolution of your scan in dots per inches ('Scan Resolution in DPI') and the number of notes of your music box ('Number of Notes') will be used to locate the exact position of the horizontal note lines on the scanned backside of your scoresheets (default setting: 58.0)."
        number_of_notes_comment_string = "The 'Number of Notes' is the number of notes on your music box (default setting: 30)."
        tempo_bpm_comment_string = "The 'Tempo bpm' is your music track's tempo expressed as the number of beats per minute (bpm) (default setting: 120)."
        ticks_per_quarter_note_comment_string = "The 'Ticks per Quarter Note' represents the number of ticks (the MIDI time measure) per quarter note. A high value such as 960 allows for higher resolution when determining the exact timing of the punched holes, so that it better reflects the results you have obtained on your music box (default setting: 960)."
        width_of_ten_smallest_measures_mm_comment_string = "The 'Width of Ten Successive Smallest Measures in Millimeters' is the width of ten consecutive smallest boxes or measures on your scoresheet, in millimeters (mm). This measurement, along with the resolution of your scan in dots per inches ('Scan Resolution in DPI') will be used to convert the number of horizontal pixels between the center of punched holes to ticks, which are the MIDI time unit (default setting: 40.0)."
        smallest_measure_duration_denominator_comment_string = "The 'Smallest Measure Duration Denominator' represents the duration of the smallest box or measure on your music box score sheet. For example if the duration of the smallest measure is 1/16th of a note, the setting's value would be 16 (default value: 16)."        
        time_signature_numerator_comment_string = "The 'Time Signature Numerator' is the numerator of the time signature, e.g., 3 for a 3/4 time signature (default setting: 4)."
        time_signature_denominator_comment_string = "The 'Time Signature Denominator' represents the denominator of the time signature, e.g., 4 for a 3/4 time signature (default setting: 4)."        
        leading_silence_milliseconds_comment_string = "The 'Leading Silence Duration in Milliseconds' is the duration of the silence that will be inserted right before the first note of your music track, in milliseconds (ms) (default value: 250)."
        trailing_silence_milliseconds_comment_string = "The 'Trailing Silence Duration in Milliseconds' represents the duration of the silence that will be inserted right after the last note of your music track, in milliseconds (ms) (default value: 500)."
        vertical_shift_pixels_comment_string = "The 'Vertical Shift in Pixels' is the vertical shift in pixels that will be applied to all of your detected punched holes' center 'x,y' coordinates. This can come in handy for example if your scoresheet has a top margin that is larger than the bottom margin. In such a case, simply pass in the number of pixels for the vertical shift (a positive value shifts down and a negative value shifts up) (default value: 0)."
        horizontal_shift_pixels_comment_string = "The 'Horizontal Shift in Pixels' represents the horizontal shift in pixels that will be applied to all of your detected punched holes' center 'x,y' coordinates. Simply pass in the number of pixels for the horizontal shift (a positive value shifts to the right and a negative value shifts leftwards) (default value: 0)."
        midi_velocity_comment_string = "The 'Midi Velocity', with possible values between 0 (no sound) and 127 (full velocity or fff), represents the output level or loudness of the note (default value 64)."
        semitone_shift_comment_string = "The 'Semitone Shift' is the number of semitones by which all of your notes will be shifted up (positive value) or down (negative value) (default value: 0)."     
        midi_copyright_string_comment_string = "The 'Midi Copyright Metadata String' represents the copyright text that will show up in the MIDI file's metadata information (default value: \"\" or empty string)."
        midi_comment_comment_string = "The 'Midi Comment String' is the comment text that will show up in the MIDI file's metadata information (default value: \"\" or empty string)."
 
        main()
        
    except Exception as e:
        #The function "get_terminal_dimensions()" will return the number of columns 
        #and rows in the console, to allow to properly format the text and dividers.
        columns, lines = get_terminal_dimensions()
        troubleshooting_step_1_string = textwrap.fill("1. Please manually back up 'settings.json' if you need to salvage your user settings.", width=columns)
        troubleshooting_step_2_string = textwrap.fill("2. Once backed up, you can delete the original copy of 'settings.json' in the root folder to reset to the default settings and launch the app again.", width=columns)

        print("\n" + "=" * columns)
        print("CRITICAL ERRROR ENCOUNTERED")
        print("\nDetails:", e)
        print("\n" + "=" * columns)

        print("\nTroubleshooting Steps:\n")
        print(troubleshooting_step_1_string)
        print(troubleshooting_step_2_string)

        #The function "write_entry_in_error_log()" will write 
        #the full technical traceback error to the error log.
        write_entry_in_error_log()

        #Exit with error code
        sys.exit(1)