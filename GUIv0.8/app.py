import streamlit as st
import numpy as np
import time
import pandas as pd
from streamlit_echarts import st_echarts
import os
import re
import sys
# custom modules
from utils.target_op import B2900_target_control
from utils.currgen import WaveGen

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))


# Define the function to check if the Current is within ±30% of the Source
def is_current_in_range(row, col1 = 'Source', col2 = 'Current'):
    """
    Checks if the current value is within 70% to 130% of the source value for a given row.

    Parameters:
    - row (pandas.Series): A row from a DataFrame containing the values to be compared.
    - col1 (str): The name of the column containing the source value. Default is 'Source'.
    - col2 (str): The name of the column containing the current value. Default is 'Current'.

    Returns:
    - bool: True if the current value is within the range, False otherwise.
    """
    source = abs(row[col1])
    current = abs(row[col2])
    lower_bound = source * 0.7
    upper_bound = source * 1.3
    return lower_bound <= current <= upper_bound

def remove_anomaly_iqr(measurements):
    # Calculate Q1 (25th percentile) and Q3 (75th percentile)
    # Q1 = np.percentile(measurements, 25)
    # Q3 = np.percentile(measurements, 75)
    Q1 = np.percentile(measurements, 40)
    Q3 = np.percentile(measurements, 60)
    # Calculate IQR
    IQR = Q3 - Q1
    
    # Define the bounds for non-anomalous data
    lower_bound = Q1 - 0.85 * IQR
    upper_bound = Q3 + 0.85 * IQR
    
    # Filter out anomalies
    filtered_measurements = [x for x in measurements if lower_bound <= x <= upper_bound]
    
    return filtered_measurements

def remove_outliers_amd(data, threshold=1.6):
    """
    Remove outliers from the data using AMD (Absolute Median Deviation).

    Parameters:
    data (array-like): Input data.
    threshold (float): Threshold for outlier detection, default is 1.6.

    Returns:
    array-like: Data with outliers removed.
    """
    data = np.array(data)
    median = np.median(data)
    deviations = np.abs(data - median)
    amd = np.median(deviations)
    mask = np.abs(data - median) <= threshold * amd
    return data[mask]

def thickness_correction(thickness, Probe_spacing):
    """
    Calculate thickness correction factor for a given thickness and probe spacing.
    
    Parameters:
    - thickness (float): The thickness of the material.
    - Probe_spacing (float): The distance between the probes.
    
    Returns:
    - f_1 (float): The thickness correction factor.
    """
    t = thickness
    s = Probe_spacing
    ln_2 = np.log(2)
    sinh_t_over_s = np.sinh(t / s)
    sinh_t_over_2s = np.sinh(t / (2 * s))
    ln_ratio = np.log(sinh_t_over_s / sinh_t_over_2s)
    f_1 = ln_2 / ln_ratio
    return f_1

def circle_lateral_correction(diameter, Probe_spacing):
    """
    Calculate lateral correction factor for circular geometries.
    
    Parameters:
    - diameter (float): The diameter of the circular object.
    - Probe_spacing (float): The distance between the probes.
    
    Returns:
    - f_2 (float): The lateral correction factor for a circle.
    """
    d = diameter
    s = Probe_spacing
    ln_2 = np.log(2)
    d_over_s_squared = (d / s) ** 2
    numerator = d_over_s_squared + 3
    denominator = d_over_s_squared - 3
    ln_fraction = np.log(numerator / denominator)
    f_2 = ln_2 / (ln_2 + ln_fraction)
    return f_2

#sub function for square_lateral_correction, a,d will bve standarised to a/s, d/s
def compute_am(m, a, d, s):
    """
    Compute a term used in the series expansion for square lateral correction.
    
    Parameters:
    - m (int): The term index in the series expansion.
    - a (float): The side length of the square normalized by probe spacing.
    - d (float): The distance normalized by probe spacing.
    - s (float): The probe spacing.
    
    Returns:
    - (float): The computed term of the series.
    """
    term1 = np.exp(-2 * np.pi * (a - 2) * m / d)
    term2 = 1 - np.exp(-6 * np.pi * m / d)
    term3 = 1 - np.exp(-2 * np.pi * m / d)
    term4 = 1 + np.exp(-2 * np.pi * m / d)
    return (1 / m) * term1 * (term2 * term3) / term4

def square_lateral_correction(d, a, s, num_terms=50):
    """
    Calculate lateral correction factor for square geometries.
    
    Parameters:
    - d (float): The distance.
    - a (float): The side length of the square.
    - s (float): The probe spacing.
    - num_terms (int, optional): The number of terms to use in the series expansion (default is 50).
    
    Returns:
    - (float): The lateral correction factor for a square.
    """
    a = a/s
    d = d/s
    sum_am = np.sum([compute_am(m, a, d, s) for m in range(1, num_terms+1)])
    term1 = np.pi / d
    term2 = np.log(1 - np.exp(-4 * np.pi / d))
    term3 = -np.log(1 - np.exp(-2 * np.pi / d))
    return np.log(2) / (term1 + term2 + term3 + sum_am)

# Title of the web app
st.set_page_config(layout="wide")
st.title('Automated Test System UI')

################################################
# Pop-up Dialogs
################################################

# Target Connection
####################
@st.experimental_dialog("Connecting to the Device")
def Establish_connection():
    with st.status("Connecting to device...", expanded=True) as status:
        st.write("Searching for device...")
        if 'device' not in st.session_state:
            st.session_state.device = B2900_target_control(resource_name=resource_name)
        time.sleep(1)
        if st.session_state.device.error is None: # return from device is needed
            status.update(label="Connection complete!", state="complete", expanded=False)
            st.session_state.Connected = True
            st.session_state.name_disabled = True
            st.rerun()
        ## for connection failure
        else:
            status.update(label="Connection failed!", state="error", expanded=False)
            st.error(f"Connection failed! Please try again. ErrorMessage: {st.session_state.device.error[0]}{st.session_state.device.error[1]}")
            st.session_state.name_disabled = False
            del st.session_state.device
            # st.rerun()

@st.experimental_dialog("Test Initiated")
def Test_Initiation():
    with st.status("Downloading data...", expanded=True) as status:
        st.write("Searching for data...")
        st.session_state.Measured_result = st.session_state.device.Measure_List(selected_channel = st.session_state.Channel,
                                                                                current_data = square_wave,
                                                                                nplc = st.session_state.test_param["nplc"],
                                                                                curr_range = st.session_state.test_param["curr_range"],
                                                                                mea_volt_range = st.session_state.test_param["Mea_Range"],
                                                                                mea_wait = st.session_state.test_param["wait_time"],
                                                                                compliance_volt= st.session_state.test_param["compliance_volt"]
                                                                                )
        st.write("Found URL.")
        time.sleep(1)
        st.write("Downloading data...")
        time.sleep(1)
        ####################
        # add the test logic here
        ####################
        if type(st.session_state.Measured_result) == str: # return from device is needed
            st.write("Data downloaded.")
            status.update(label="Test failed!", state="error", expanded=False)
            st.error(f"Connection failed! Please try again. ErrorMessage: {st.session_state.Measured_result}")
            st.session_state.Measured_df = None
            st.session_state.test_initiated = False
            st.session_state.safe = None
        else:
            status.update(label="Test complete!", state="complete", expanded=False)
            st.session_state.Measured_df = pd.DataFrame(st.session_state.Measured_result[0], columns=["Voltage", "Current", "Resistance", "Time", "Status", "Source"])
            st.session_state.test_initiated = False
            st.session_state.safe = None
            # st.rerun()

@st.experimental_dialog("Self Calibration")
def Cal_start():
    with st.status("Downloading data...", expanded=True) as status:
        st.write("Searching for data...")
        Calibration_result, error = st.session_state.device.calibrate()
        ####################
        # add the test logic here
        ####################
        if Calibration_result == False: # return from device is needed
            status.update(label="Test failed!", state="error", expanded=False)
            st.error(f"Connection failed! Please try again. ErrorMessage: {error[0]}{error[1]}")
            calibrating = False
        else:
            status.update(label="Test complete!", state="complete", expanded=False)
            st.write("Calibration successful")
            calibrating = False



@st.experimental_dialog("Auto Test Initiated")
def Auto_Test_Initiation():
    with st.status("Downloading data...", expanded=True) as status:
        st.session_state.Measured_df = pd.DataFrame() # initialize session df to an empty dataframe
        wave = WaveGen(magnitude = st.session_state.test_param["magnitude"])
        num_of_curr = len(st.session_state.test_param["curr_value"])
        for i, value in enumerate(st.session_state.test_param["curr_value"]):
            square_wave = wave.generate_square_wave(length      =   st.session_state.test_param["period"] * st.session_state.test_param["repeats"],
                                                    period      =   st.session_state.test_param["period"],
                                                    high_value  =   value,
                                                    low_value   =   -value,
                                                    duty_cycle  =   st.session_state.test_param["duty_cycle"],
                                                    init_time   =   st.session_state.test_param["initial_zero"])
            
            st.session_state.Auto_Measured_result = st.session_state.device.Measure_List(selected_channel = st.session_state.Channel,
                                                                                        current_data = square_wave,
                                                                                        nplc = st.session_state.test_param["nplc"],
                                                                                        curr_range = 5e-4,
                                                                                        mea_volt_range = st.session_state.test_param["Mea_Range"],
                                                                                        mea_wait = st.session_state.test_param["wait_time"],
                                                                                        compliance_volt = st.session_state.test_param["Mea_Range"]
                                                                                        )
            ####################
            # add the test logic here
            ####################
            if type(st.session_state.Auto_Measured_result) == str: # return from device is needed
                st.write("Data downloaded.")
                status.update(label="Test failed!", state="error", expanded=False)
                st.error(f"Connection failed! Please try again. ErrorMessage: {st.session_state.device.Auto_Measured_result}")
                st.session_state.Measured_df = None
                st.session_state.test_initiated = False
            else:
                # status.update(label="Test complete!", state="complete", expanded=False)
                temp_df = pd.DataFrame(st.session_state.Auto_Measured_result[0], columns=[f"Voltage@{value}μA",
                                                                                          f"Current@{value}μA",
                                                                                          f"Resistance@{value}μA",
                                                                                          f"Time@{value}μA",
                                                                                          f"Status@{value}μA",
                                                                                          f"Source@{value}μA"])
                temp_df[f'In_Range@{value}μA'] = temp_df.apply(is_current_in_range, axis=1, col1=f"Source@{value}μA", col2=f"Current@{value}μA")
                st.session_state.Measured_df = pd.concat([st.session_state.Measured_df, temp_df], axis=1)
                st.write(f"completed {i+1} out of {num_of_curr} tests")
                st.session_state.test_initiated = False

################################################
# mapping dictionaries
################################################

probe_dict = {
    "1.6 mm spacing; co-liner": {"spacing": 1.6, "layout": "coliner"},
    }
equipped_probe = {}
dim_mapping = {
    "2-inch (50.8 mm)": 50.8,
    "3-inch (76.2 mm)": 76.2,
    "4-inch (100 mm)": 100,
    "5-inch (125 mm)": 125,
    "6-inch (150 mm)": 150,
    "8-inch (200 mm)": 200,
    "12-inch (300 mm)": 300
    }

################################################
# Sidebar for General inputs
################################################
st.sidebar.header("Target")
## Sidebar Container 1
Target_selection_group = st.sidebar.container(border=True) 
with Target_selection_group:
    # Target Selection
    if 'name_disabled' not in st.session_state:
        st.session_state.name_disabled = False  #initialization
    if 'Channel' not in st.session_state:
        st.session_state.Channel = None
    genre = st.radio(
        "Determine Target Through:",
        ["Alias Name", "VISA Address"], disabled=st.session_state.name_disabled)

    if genre == "Alias Name":
        resource_name = st.text_input("Enter Alias Name Below:", "B2912A_Target", disabled=st.session_state.name_disabled)
    else:
        ip = st.number_input("Enter Target VISA Address Below:", value=23, format="%d",placeholder="Type a number...",disabled=st.session_state.name_disabled)
        resource_name = f"GPIB0::{ip}::INSTR"
    # test print
    st.write("Current Target is ", resource_name)

    # Connect logic
    if 'Connected' not in st.session_state:
        st.session_state.Connected = False  #initialization
    if not st.session_state.Connected:      # When not Connected
        if st.button("Find Target Device", type="primary", use_container_width=True):
            Establish_connection()
    else:                                   # Connected
        ## 1.initial case 
        if 'device_param' not in st.session_state:
            st.session_state.device_param = st.session_state.device.channel_model_query()
            st.rerun()

        ## 2.Normal case
        elif len(st.session_state.device_param) == 3:
            # device info
            st.write("Targeted Device Model: ", st.session_state.device_param[1])
            st.write("Number of Channels Avaliable: ", len(st.session_state.device_param[0]))
            # Fetched device error display
            if st.session_state.device_param[2][0] > 0:
                st.write(":red[Device Error: ]", st.session_state.device_param[2][1], "Try to reconnect or restart the device.")
            #######Channel Selection (displaced outside the container)##############
            Chan_list = st.session_state.device_param[0]
            # Chan_list = ['channel1','channel2'] # test line
            # extract channel number
            Chan_selection = st.sidebar.selectbox("Select Channel", Chan_list)
            match = re.search(r'\d+$', Chan_selection)
            if match:
                # Channel = int(match.group())
                st.session_state.Channel = match.group()
            else:
                st.session_state.Channel = None
            ########################################################################

        ## 3.Function error case
        else: 
            e = st.session_state.device_param
            st.exception(f"Error: {e[0]} {e[1]}")

        st.success(f"You have been connected with {resource_name}")
        if st.button("Disconnect", type="primary", use_container_width=True): # Disconnect
            if 'device' in st.session_state:
                st.session_state.device.close()
                del st.session_state.device
            del st.session_state.Connected
            del st.session_state.device_param
            del st.session_state.name_disabled
            st.session_state.curr_manual_enabled = False
            st.rerun()
####################

################################################
# Sidebar End
################################################

# """
# Main display for the test
# """
calibrate_container = st.container(border=True)
with calibrate_container:
    # st.write(":red[please <span style='font-size: larger;'>**Remove All the Test Leads**</span> from the device.]")
    st.markdown('<p>Before performing calibration, please <span style="font-size: larger; color: red; font-weight: bold;">REMOVE ALL THE TEST LEADS</span> from the device.</p>', unsafe_allow_html=True)
    st.button("Calibrate", type="primary", use_container_width=True, disabled=not st.session_state.Connected, on_click=Cal_start)


curr_manual = st.toggle("Manual", False, key='curr_manual_enabled', disabled=not st.session_state.Connected)
Parambox = st.container(border=False) 

if "test_param" not in st.session_state:
    st.session_state.test_param = {}
if "manual_mode_enable" not in st.session_state:
    st.session_state.manual_mode_enable = False
if 'safe' not in st.session_state:
    st.session_state.safe = None

param_dict = {} # continuously initialize the parameter dictionary
################################################
# Manual Mode
################################################
if curr_manual:
    # safe stamp for manual is None -- awaiting for check
    st.session_state.safe = None

    curr_param, meas_param = Parambox.columns(2)
    st.session_state.manual_mode_enable = True
    # Current Parameters
    ####################
    with curr_param:
        curr_param.header("Current Parameters")
        curr_col1, curr_col2, curr_col3 = curr_param.container(border=True).columns(3)
        with curr_col1:
            # value = st.number_input("Insert a number for Force Current")
            param_dict["curr_value"] = st.number_input("Insert a number for Force Current")

        with curr_col2:
            unit_mapping = {
                # "A": 1,
                # "mA": 1e-3,
                # "μA": 1e-6,
                # "nA": 1e-9,
                # "pA": 1e-12
                "A": 0,
                "mA": -3,
                "μA": -6,
                "nA": -9,
                "pA": -12
                }
            unit = st.selectbox(
            "Select a magnitude unit",
            list(unit_mapping.keys()),
            index=2,                     # default to μA
            placeholder="Select a magnitude unit...",
            help="Select a magnitude unit for the current input."
            )
            param_dict["magnitude"] = unit_mapping[unit]
            # st.write(f"Selected unit: {param_dict["magnitude"]}")
            # magnitude = unit_mapping[unit]

        with curr_col3:
            curr_adv = st.toggle("Advanced Settings", False)
            if curr_adv:
                st.write("Advanced Settings")
                # period = st.number_input("Period", min_value=0, value=100, step=10, format="%d") 
                # duty_cycle = st.slider("Duty Cycle", 0.0, 1.0, 0.5, 0.05)
                # initial_zero = st.number_input("Initial Zeros", min_value=0, value=0, format="%d")
                # repeats = st.number_input("Number of Period", min_value=0, value=1, format="%d")
                param_dict["period"] = st.number_input("Period", min_value=0, value=100, step=10, format="%d")
                param_dict["duty_cycle"] = st.slider("Duty Cycle", 0.0, 1.0, 0.5, 0.05)
                param_dict["initial_zero"] = st.number_input("Initial Zeros", min_value=0, value=0, format="%d")
                param_dict["repeats"] = st.number_input("Number of Period", min_value=0, value=1, format="%d")
            else:
                # period = 100
                # duty_cycle = 0.5
                # initial_zero = 0
                # repeats = 1
                param_dict["period"] = 100
                param_dict["duty_cycle"] = 0.5
                param_dict["initial_zero"] = 0
                param_dict["repeats"] = 1
    ####################

    # Measurement Parameters
    ####################
        with meas_param:
            meas_param.header("Measurement Parameters")
            meas_col1, meas_col2 = meas_param.container(border=True).columns(2)
            with meas_col1:
                # nplc = st.slider("NPLC", 0.01, 10.0, 1.0, 0.1, help="Number of Power Line Cycles")
                param_dict["nplc"] = st.slider("NPLC", 0.01, 10.0, 1.0, 0.1, help="Number of Power Line Cycles")
                # wait_time = st.number_input("Wait Time offset in μs", min_value=0.0, value=0.05, step=0.05)
                param_dict["wait_time"] = st.number_input("Wait Time offset in seconds", min_value=0.0, value=0.005, step=0.005)
            with meas_col2:
                # add more parameters here
                # st.number_input("anything", min_value=0, value=1, step=1, format="%d")
                curr_range_dict = {
                    "10nA": 10*1e-9,
                    "100nA": 100*1e-9,
                    "1μA": 1e-6,
                    "10μA": 10*1e-6,
                    "100μA": 100*1e-6,
                    "1mA": 1e-3,
                    "10mA": 10*1e-3,
                    "100mA": 100*1e-3,
                    "1A": 1.0,
                    "Auto":None
                }
                vol_range_dict = {
                    "0.2V": 0.2,
                    "2V": 2.0,
                    "20V": 20.0,
                    "200V": 200.0
                }
                param_dict["curr_range"] = curr_range_dict[st.select_slider(label='Current Output Range',options=curr_range_dict.keys(),value="1mA")]
                param_dict["Mea_Range"] = vol_range_dict[st.select_slider(label='Measurement Range',options=vol_range_dict.keys(),value="0.2V")]
                param_dict["compliance_volt"] = st.number_input("Compliance Voltage in V", min_value=0.0, value=param_dict["Mea_Range"], step=0.01)
    ####################



################################################
# Auto Mode
################################################
else:
    st.session_state.manual_mode_enable = False
    # safety stamp for auto is True -- no need for check
    st.session_state.safe = True

    with Parambox.container(border=True):
        surf = st.radio(
            "Surface Material:",
            ["Semiconductor", "Metal", "Unknown"],
            index=2,
            disabled=not st.session_state.Connected,
            captions = ["", "(or other low resistivity material)", ""]
        )
        if surf == "Semiconductor": # Typicallly 10-10^5 Ohm/sq => 2-2000ohm =>
            hir_semi = st.toggle("High Resistance Semiconductor", False, disabled=not st.session_state.Connected)
            param_dict["curr_value"] = [5, 10, 30, 50, 70, 90, 100]
            param_dict["Mea_Range"] = 0.2
            if hir_semi:
                param_dict["curr_value"] = [0.1, 0.5, 0.7, 1, 3, 5, 7]
                param_dict["Mea_Range"] = 2
        elif surf == "Metal": # Typically 10^-1 or 10^-2 Ohm/sq => 0.002 - 0.02ohm
            # st.write("Metal")
            param_dict["curr_value"] = [150, 200, 250, 300, 350, 400]
            param_dict["Mea_Range"] = 0.2
        else:
            # st.write("Unknown")
            param_dict["curr_value"] = [5, 30, 50, 70, 100, 200, 400]
            param_dict["Mea_Range"] = 2
        # common parameters
        param_dict["magnitude"] = -6
        param_dict["period"] = 50
        param_dict["duty_cycle"] = 0.5
        param_dict["initial_zero"] = 0
        param_dict["repeats"] = 1

        param_dict["nplc"] = 1.0   
        param_dict["wait_time"] = 0.005 # 5ms
        

################################################
# sample size
################################################
# param_dict["probe_spacing"] = st.number_input("Probe Spacing in mm", min_value=0.001, value=1.6, step=0.1)


sample_info = st.container(border=True) 

with sample_info:
    st.subheader("Sample Information")
    
    equipped_probe = st.selectbox("Probe Spacing (in mm)", probe_dict.keys(), disabled=not st.session_state.Connected)
    param_dict["probe_spacing"] = probe_dict[equipped_probe]["spacing"]
    prob_lim = param_dict["probe_spacing"]*3

    param_dict["est_thickness"] = st.number_input("Enter the estimation of the sample thickness in μm", min_value=0.0, value=None, step=0.1, placeholder="Leave blank if unknown", disabled=not st.session_state.Connected)

    sample_shape = st.selectbox("Select Sample Shape", ["Square", "Circular"], 1, disabled=not st.session_state.Connected)
    if sample_shape == "Square":
        st.image("./utils/pic/Sqr_sample.png", width=400)
        # st.image(os.path.abspath(os.path.join("utils/pic/Sqr_sample.png", os.path.pardir)), width=400)
        param_dict["square_a"] = st.number_input("Enter the side 'a' length of the sample in mm", min_value=prob_lim, value=76.0, step=0.01, disabled=not st.session_state.Connected)
        param_dict["square_d"] = st.number_input("Enter the side 'd' length of the sample in mm", min_value=prob_lim, value=76.0, step=0.01, disabled=not st.session_state.Connected)
    if sample_shape == "Circular":
        st.image("./utils/pic/Cir_sample.png", width=400)
        param_dict["circular_diameter"] = dim_mapping[st.selectbox("WAFER DIMENSION:", dim_mapping.keys(), disabled=not st.session_state.Connected)]
    # param_dict["probe_spacing"] = st.selectbox("Probe Spacing (in mm)", [1.6,])
    # st.toggle("Thick", False, key='curr_manual_enabled', disabled=not st.session_state.Connected)

    
    
################################################
# Test Start
################################################
if 'test_invalid' not in st.session_state:
    st.session_state.test_invalid = None
if 'test_initiated' not in st.session_state:
    st.session_state.test_initiated = False
# st.write(f"{st.session_state.test_param}") # test line

# start test button
if st.button("Start Test",
             type="primary",
             use_container_width=True,
             disabled=not st.session_state.Connected):
    # clear the previous test data
    if 'Measured_df' in st.session_state:
        del st.session_state.Measured_df
    # session state take the value of param_dict
    st.session_state.test_param = param_dict
    st.session_state.test_initiated = True
    
if st.session_state.test_initiated and st.session_state.safe == None:
    #### wavegen block ####
    wave = WaveGen(magnitude = st.session_state.test_param["magnitude"])
    # safety check
    checksafety = wave._check_safety(st.session_state.test_param["curr_value"])
    if not checksafety:
        st.warning(f"Danger! High current input (value: {wave.magnitude*st.session_state.test_param['curr_value']} A). Human confirmation required.")
        # wait for safety override input
        safety_override = st.text_input("Enter 'Y' to continue, 'N' to abort: ", None)
        if safety_override !=None:
            if safety_override.lower() == 'y':
                st.session_state.safe = True
                square_wave = wave.generate_square_wave(length      =   st.session_state.test_param["period"] * st.session_state.test_param["repeats"],
                                                        period      =   st.session_state.test_param["period"],
                                                        high_value  =   st.session_state.test_param["curr_value"],
                                                        low_value   =   -st.session_state.test_param["curr_value"],
                                                        duty_cycle  =   st.session_state.test_param["duty_cycle"],
                                                        init_time   =   st.session_state.test_param["initial_zero"])
            else:
                st.session_state.safe = False
                st.session_state.test_initiated = False
                st.warning("Operation stopped by human intervention.")
                time.sleep(1)
                st.rerun()
            
    else:
        st.session_state.safe = True
        square_wave = wave.generate_square_wave(length      =   st.session_state.test_param["period"] * st.session_state.test_param["repeats"],
                                                period      =   st.session_state.test_param["period"],
                                                high_value  =   st.session_state.test_param["curr_value"],
                                                low_value   =   -st.session_state.test_param["curr_value"],
                                                duty_cycle  =   st.session_state.test_param["duty_cycle"],
                                                init_time   =   st.session_state.test_param["initial_zero"])
    # st.write(square_wave)# test line

#### (popup window) wait for the test to finish ####
if st.session_state.test_initiated:
    if st.session_state.safe == True:
        # manual mode
        if st.session_state.manual_mode_enable:
            Test_Initiation()
            # if 'Measured_df' in st.session_state:
            if st.session_state.Measured_df is not None:
                # st.write("Test Completed")
                st.write(st.session_state.Measured_df)
                # Apply the function to each row and create a new column 'In_Range'
                df = st.session_state.Measured_df # create dummy df to avoid changing the original session df
                df['In_Range'] = df.apply(is_current_in_range, axis=1)

                # Check if 20% of the rows have Current values out of the ±20% range of Source
                out_of_range_count = (df['In_Range'] == False).sum()
                total_rows = len(df)
                if out_of_range_count / total_rows >= 0.2:
                    st.session_state.test_invalid = True
                else:
                    st.session_state.test_invalid = None
        
                reverse_p = st.session_state.test_param["initial_zero"]+int(st.session_state.test_param["period"]*st.session_state.test_param["duty_cycle"])
                st.session_state.test_param['Volt_corrected'] = (df['Voltage'][st.session_state.test_param["initial_zero"]:reverse_p].mean()
                                                                -
                                                                df['Voltage'][reverse_p:st.session_state.test_param["initial_zero"]+st.session_state.test_param["period"]].mean())/2
                st.session_state.test_param['Avg_curr'] = abs(df['Current']).mean()
                st.session_state.test_param['Cal_V/I'] = st.session_state.test_param['Volt_corrected'] / st.session_state.test_param['Avg_curr']
                                # thickness and lateral correction
                if curr_adv != True:
                    if st.session_state.test_param["est_thickness"] != None:
                        st.session_state.test_param['thicknessComp'] = thickness_correction(st.session_state.test_param["est_thickness"]*1e-3, st.session_state.test_param["probe_spacing"])
                    else:
                        st.session_state.test_param['thicknessComp'] = 1
                    if sample_shape == "Square":
                        st.session_state.test_param['lateralComp'] = square_lateral_correction(st.session_state.test_param["square_d"],
                                                                                            st.session_state.test_param["square_a"],
                                                                                            st.session_state.test_param["probe_spacing"])
                    elif sample_shape == "Circular":
                        st.session_state.test_param['lateralComp'] = circle_lateral_correction(st.session_state.test_param["circular_diameter"],
                                                                                            st.session_state.test_param["probe_spacing"])

                    
                    st.session_state.test_param['Corr_Rsheet'] = st.session_state.test_param['Cal_V/I'] * np.pi/np.log(2) * st.session_state.test_param['thicknessComp'] * st.session_state.test_param['lateralComp']

                    st.session_state.auto_result = False # toggle to avoid plot display warning

                st.rerun()

        # auto mode
        else:
            # Call Auto test logic
            Auto_Test_Initiation()
            if st.session_state.Measured_df is not None:
                out_of_range_count = 0
                CorrectedVlist = []
                Avgcurrlist = []
                df = st.session_state.Measured_df
                for i in st.session_state.test_param["curr_value"]:
                    out_of_range_count += (df[f'In_Range@{i}μA'] == False).sum() # calculate the total number of out of range current values
                    reverse_p = st.session_state.test_param["initial_zero"]+int(st.session_state.test_param["period"]*st.session_state.test_param["duty_cycle"])
                    CorrectedVlist.append((df[f'Voltage@{i}μA'][st.session_state.test_param["initial_zero"]:reverse_p].mean()
                                           -
                                           df[f'Voltage@{i}μA'][reverse_p:st.session_state.test_param["initial_zero"]+st.session_state.test_param["period"]].mean())/2)
                    Avgcurrlist.append(abs(df[f'Current@{i}μA']).mean())
                # calculate V/I
                st.session_state.test_param['Cal_V/I'] = [CorrectedVlist[i] / Avgcurrlist[i] for i in range(len(CorrectedVlist))]
                # filter out the anomalies
                # st.session_state.test_param['Cal_V/I_filtered'] = remove_anomaly_iqr(st.session_state.test_param['Cal_V/I'])
                st.session_state.test_param['Cal_V/I_filtered'] = remove_outliers_amd(st.session_state.test_param['Cal_V/I'])
                st.session_state.test_param['Avg_V/I_filtered'] = np.mean(st.session_state.test_param['Cal_V/I_filtered'])

                # thickness and lateral correction
                if st.session_state.test_param["est_thickness"] != None:
                    st.session_state.test_param['thicknessComp'] = thickness_correction(st.session_state.test_param["est_thickness"]*1e-3, st.session_state.test_param["probe_spacing"])
                else:
                    st.session_state.test_param['thicknessComp'] = 1
                if sample_shape == "Square":
                    st.session_state.test_param['lateralComp'] = square_lateral_correction(st.session_state.test_param["square_d"],
                                                                                           st.session_state.test_param["square_a"],
                                                                                           st.session_state.test_param["probe_spacing"])
                elif sample_shape == "Circular":
                    st.session_state.test_param['lateralComp'] = circle_lateral_correction(st.session_state.test_param["circular_diameter"],
                                                                                           st.session_state.test_param["probe_spacing"])
                
                st.session_state.test_param['Corr_Rsheet'] = st.session_state.test_param['Avg_V/I_filtered'] * np.pi/np.log(2) * st.session_state.test_param['thicknessComp'] * st.session_state.test_param['lateralComp']
                # st.session_state.test_param['Corr_Rsheet'] = st.session_state.test_param['Avg_V/I_filtered'] * st.session_state.test_param['thicknessComp'] * st.session_state.test_param['lateralComp']
                st.session_state.auto_result = True # toggle to avoid plot display warning

                total_rows = len(df)*len(st.session_state.test_param["curr_value"])
                if out_of_range_count / total_rows >= 0.2:
                    st.session_state.test_invalid = True
                else:
                    st.session_state.test_invalid = None
                
        
        
if st.session_state.test_invalid != None:
    st.warning("The measurement just done might be invalid, this could be caused by the insulated surface material, bad contact, or voltage measurement out of range. Please check the test setup and try again.")
# if 'Cal_V/I' in st.session_state.test_param:     
#     st.metric("Average Forced Current", "A")   
#     col1, col2, col3 = st.columns(3)
#     col1.metric("Average Forced Current", f"{st.session_state.test_param['Avg_curr']} A")
#     col2.metric("Corrected Voltage", f"{st.session_state.test_param['Volt_corrected']} V")
#     col3.metric("R", f"{st.session_state.test_param['Cal_V/I']}")
if 'Measured_df' in st.session_state:
    st.write(st.session_state.Measured_df)



if 'Cal_V/I' in st.session_state.test_param:
    result_container = st.container(border=True)    
    with result_container:
        st.header("Testing Results :", divider="grey")
    col1, col2, col3 = result_container.columns([1.5,1,2])
    with col1:
        st.metric("$\Large {Corrected\space Sheet\space Resistance}$", f"{st.session_state.test_param['Corr_Rsheet'].round(5)} Ω/sq")
        if st.session_state.auto_result == True:
            if surf == "Unknown":
                if st.session_state.test_param['Corr_Rsheet'] < 5:
                    # st.subheader("The sample surface is likely to be metal.")
                    st.markdown('<p>The sample surface is likely to be <span style="font-size: larger; color: red; font-weight: bold;">Metal</span>.</p>', unsafe_allow_html=True)
                elif st.session_state.test_param['Corr_Rsheet'] >= 5 and st.session_state.test_param['Corr_Rsheet'] <= 10**6:
                    # st.subheader("The sample surface is likely to be semiconductor.")
                    st.markdown('<p>The sample surface is likely to be <span style="font-size: larger; color: red; font-weight: bold;">Semiconductor</span>.</p>', unsafe_allow_html=True)
                elif st.session_state.test_invalid != None or st.session_state.test_param['Corr_Rsheet'] >= 10**6:
                    # st.subheader("The sample surface is likely to be insulator.")
                    st.markdown('<p>The sample surface is likely to be <span style="font-size: larger; color: red; font-weight: bold;">Insulator</span>.</p>', unsafe_allow_html=True)

    with col2:
        if  st.session_state.test_param["est_thickness"] != None:
            st.metric("Thickness Correction Factor", f"{st.session_state.test_param['thicknessComp'].round(5)}")
        else:
            st.metric("Thickness Correction Factor", "1")
        st.metric("Lateral Correction Factor", f"{st.session_state.test_param['lateralComp'].round(5)}")
        # st.write(st.session_state.test_param['thicknessComp'])
        # st.write(st.session_state.test_param['lateralComp'])
    with col3:
        c1, c2 = st.columns(2)
        with c1:
            st.write("Calculated V/I (Ω) :")
            st.write(st.session_state.test_param['Cal_V/I'])
        with c2:
            if st.session_state.auto_result == True:
                st.write("Filtered V/I (Ω) :")
                st.write(st.session_state.test_param['Cal_V/I_filtered'])
                st.write("Average Filtered V/I (Ω) :")
                st.write(st.session_state.test_param['Avg_V/I_filtered'])
    # st.write(st.session_state.test_param['Corr_Rsheet'])

## display remote test
# current_dir = os.getcwd()
# data_file_path = os.path.join(current_dir, 'data')
# csv_file_path = data_file_path + '/500u.csv'
# # if csv_file_path is not None:
# #     df = pd.read_csv(csv_file_path)

if 'Measured_df' in st.session_state and st.session_state.Measured_df is not None:
# if st.session_state.Measured_df is not None:
    # if st.session_state.manual_mode_enable == True:
    if st.session_state.auto_result == False:
        df = st.session_state.Measured_df
        # tab1, tab2 = st.tabs(["Chart", "Data"])

        # original credict: https://echarts.apache.org/examples/en/editor.html?c=line-simple
        options = {
            "title": {"text": "Measured Data", "left": "center"},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["Voltage", "Current"], "right": 10},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            # "toolbox": {"feature": {"saveAsImage": {"type:'png'": None}}},
            "xAxis": {
                "name": "Time",
                "type": "category",
                "boundaryGap": False,
                "data": df["Time"].tolist(),
            },
            # "yAxis": {"type": "value"},
            "yAxis": [
                {
                "name": 'Current (A)\n\nVoltage (V)',
                "type": 'value'
                },
                # {
                # "name": 'Voltage(V)',
                # "nameLocation": 'start',
                # "alignTicks": "true",
                # "type": 'value',
                # "inverse": "true"
                # }
            ],
            "series": [
                {
                    "name": "Voltage",
                    "type": "line",
                    "data": df["Voltage"].tolist(),
                },
                {
                    # "yAxisIndex": 1,
                    "name": "Current",
                    "type": "line",
                    "data": df["Current"].tolist(),
                },
            ],
        }
        st_echarts(options=options, height="400px") 



################################################
# download data
################################################
save_container = st.container(border=True)
with save_container:
    st.header("Save Data")
    file_name = st.text_input("Enter the file name (leave blank for default): ", placeholder="default in format: YYYY-MM-DD_HH-MM-SS")
    file_path = st.text_input("Enter the file path to save the CSV file: ", placeholder="default: 'data' under current working directory")

    if st.button("Save Data", type="primary", use_container_width=True, disabled=('Measured_df' not in st.session_state)):
        current_dir = os.getcwd()
        # st.write(f"Current working directory: {current_dir}")
        # Enter file name
        if not file_name:
            file_name = pd.Timestamp.now().strftime("%Y-%m-%d_%H-%M-%S")
        else:
            file_name = file_name.replace(" ", "_")

        # Enter file path
        if not file_path:
            file_path = os.path.join(current_dir, 'data')
        else:
            file_path = os.path.abspath(file_path)

        # Ensure directory exists
        if not os.path.exists(file_path):
            try:
                os.makedirs(file_path)
            except OSError as e:
                st.error(f"Error creating directory: {e}")
                st.stop()

        # Construct the full file path
        full_file_path = os.path.join(file_path, f"{file_name}.csv")

        # Display file save path
        st.write(f"CSV file will be saved to: {full_file_path}")

        try:
            # df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})   # Test line
            df = st.session_state.Measured_df

            df['Test Param'] = [st.session_state.test_param] + [None] * (len(df) - 1)

            df.to_csv(full_file_path, index=False)
            st.success(f"File saved successfully at {full_file_path}")
        except Exception as e:
            st.error(f"Error saving file: {e}")