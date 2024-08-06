from datetime import timedelta, datetime
from time import sleep
from numpy import reshape
from numpy import array
import keysight_ktb2900

class B2900_target_control:
    """
    This class is designed to interface with and control a Keysight B2900 series 
    source/measure unit (SMU). It handles initialization, setting up connections, 
    error checking, and provides access to device identity properties.
    """
    def __init__(self,
                 resource_name=None,
                 idQuery=True,
                 reset=True,
                 options="QueryInstrStatus=True, Simulate=False, Trace=False",
                 delta=timedelta(days=0, seconds=100, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0)):
        """
        Initializes the B2900_target_control object.

        Parameters:
        - resource_name (str): The VISA resource name of the instrument.
        - idQuery (bool): Whether to query the instrument's identity during initialization.
        - reset (bool): Whether to reset the instrument during initialization.
        - options (str): Driver options for initialization.
        - delta (timedelta): Timeout value for instrument I/O operations.
        """

        self.resource_name = resource_name
        self.idQuery = idQuery
        self.reset = reset
        self.options = options
        self.delta = delta
        self.driver = None
        self.error = None # reffering to initialisation error only

        try:
            # Call driver constructor with options
            self.driver = keysight_ktb2900.KtB2900(self.resource_name, self.idQuery, self.reset, self.options)
            print("Driver Initialized")

            # Print a few identity properties
            print('  identifier: ', self.driver.identity.identifier)
            print('  revision:   ', self.driver.identity.revision)
            print('  vendor:     ', self.driver.identity.vendor)
            print('  description:', self.driver.identity.description)
            print('  model:      ', self.driver.identity.instrument_model)
            print('  resource:   ', self.driver.driver_operation.io_resource_descriptor)
            print('  options:    ', self.driver.driver_operation.driver_setup)

            # Manually set the IO timeout
            self.driver.system.io_timeout = self.delta

            self.chan_list = [name for name in self.driver.outputs]

            # Check instrument for errors
            self.fetched_error = None
            while True:
                outVal = self.driver.utility.error_query()
                self.fetched_error = outVal
                if outVal[0] == 0:  # 0 = No error, error queue empty
                    break

        except Exception as e:
            print("\n  Exception:", e.__class__.__name__, e.args)
            self.error = (e.__class__.__name__, e.args)
        
        # finally:
        #     if self.driver is not None:  # Skip close() if constructor failed
        #         self.driver.close()

    def channel_model_query(self):
        """
        Query the channel model and fetch errors for the Keysight B2900 instrument.

        Returns:
        - chan_list (list): List of available channel names.
        - ModelNo (str): The model number of the instrument.
        - fetched_error (tuple): The last fetched error code and message from the instrument.

        If an exception occurs, returns:
        - (str, tuple): The exception class name and exception arguments.
        """
        try:
            self.driver.system.io_timeout = self.delta
            # The number of repeated capability instances is returned by the count property
            # It returns 1 for this B2912A_Target, which means Channel 2 is not available here, however, it can be turned on by change the chanlist to "(@1,2)"
            chan_list = []
            for name in self.driver.outputs:
                chan_list.append(name)
            ModelNo = self.driver.identity.instrument_model
            print("ModelNo. :" + ModelNo)
            # Check instrument for errors
            print()
            while True:
                outVal = ()
                outVal = self.driver.utility.error_query()
                print("  error_query: code:", outVal[0], " message:", outVal[1])
                fetched_error = outVal
                if(outVal[0] == 0): # 0 = No error, error queue empty
                    break
            return chan_list, ModelNo, fetched_error
        
        except Exception as e:
            print("\n  Exception:", e.__class__.__name__, e.args)
            return e.__class__.__name__, e.args
        
        # finally:
        #     if self.driver is not None: # Skip close() if constructor failed
        #         self.driver.close()
        
    def Measure_List(self, selected_channel = '1', current_data = None, nplc = 1, curr_range = None, mea_volt_range = None, mea_wait = None, compliance_volt = 2):
        """
        Configure and execute a list-based current measurement on a Keysight B2900 series instrument.

        Parameters:
        - selected_channel (str): The channel number to be selected for measurement.
        - current_data (list or np.array): The list of current values for the transient current measurement.
        - nplc (float): Number of power line cycles (NPLC) for integration time.
        - curr_range (float): The range setting for current measurement (if not using auto-range).
        - mea_volt_range (float): The range setting for voltage measurement (if not using auto-range).
        - mea_wait (float): The wait time offset for the measurement in seconds.
        - compliance_volt (float): The compliance voltage setting.

        Returns:
        - reshaped_result (np.array): A reshaped array of measurement data.
        - fetched_error (tuple): The last fetched error code and message from the instrument.

        If an exception occurs, returns:
        - str_e (str): A string representation of the exception class name and arguments.
        """
        try:
            iNumberOfChannels = self.driver.outputs.count
            # The number of repeated capability instances is returned by the count property
            # It returns 1 for this B2912A_Target, which means Channel 2 is not available here, however, it can be turned on by change the chanlist to "(@1,2)"

            ModelNo = self.driver.identity.instrument_model
            for i in range(iNumberOfChannels):
                print("Channel " + str(i+1) + " enabled")
                self.driver.outputs[i].type = keysight_ktb2900.OutputType.CURRENT # specify output type as current
                if curr_range is not None:
                    self.driver.outputs[i].current.auto_range_enabled = False
                    self.driver.outputs[i].current.range = curr_range
                else:
                    self.driver.outputs[i].current.auto_range_enabled = True

                self.driver.measurements[i].remote_sensing_enabled = True # Enable remote sensing (4-wire measurement)
                ##################
                transient_current = self.driver.transients[i].current
                transient_current.mode = keysight_ktb2900.TransientCurrentVoltageMode.LIST
                # Set the transient current list
                # current_data = np.array([0.02, 0.02, 0.03, 0.04, 0.05], dtype='double') # Testing data for debugging
                transient_current.configure_list(current_data)
                l = transient_current.query_list()
                print("List: ", l)
                ####################
                ####################
                if (ModelNo == "B2901A" or ModelNo == "B2902A" or ModelNo == "B2911A" or ModelNo == "B2912A" or ModelNo == "B2901B" or ModelNo == "B2902B" or ModelNo == "B2911B" or ModelNo == "B2912B"):
                    if mea_volt_range is not None:
                        self.driver.measurements[i].voltage.auto_range_enabled = False
                        self.driver.measurements[i].voltage.range = mea_volt_range
                    else:
                        self.driver.measurements[i].voltage.auto_range_enabled = True; #Supported Models for this property: B2901A|B, B2902A|B, B2911A|B, B2912A|B
                    self.driver.measurements[i].voltage.compliance_value = compliance_volt
                    self.driver.measurements[i].voltage.nplc = nplc
                    ###################
                    self.driver.transients[i].trigger.count = len(current_data)
                    if mea_wait is not None:
                        self.driver.measurements[i].wait_time.enabled = True
                        self.driver.measurements[i].wait_time.offset = mea_wait
                    else:
                        self.driver.measurements[i].wait_time.enabled = False
                    self.driver.measurements[i].trigger.count = len(current_data)
                    self.driver.measurements[i].trigger.trigger_output_enabled = True
                    ###################
                chanlist = "(@"+str(selected_channel)+")"
                print("Channel List: " + chanlist)
                self.driver.trigger.initiate(chanlist)
                dResult = self.driver.measurements.fetch_array_data((keysight_ktb2900.MeasurementFetchType.ALL), chan_list=chanlist) # ALL => Voltage, Current, Resistance, Time, Status, Source
                # dResult = driver.measurements.fetch_array_data((keysight_ktb2900.MeasurementFetchType.CURRENT), chan_list="(@1,2)")
                ##return data needed
                print(f"Number of Fetched Elements: {len(dResult)}")
                print("Measured data:")
                for j in range(len(dResult)):
                    print(f"Item[{j}]: {dResult[j]}")
                for k in range(iNumberOfChannels):
                    self.driver.outputs[k].enabled = False
            # Check instrument for errors
            while True:
                outVal = ()
                outVal = self.driver.utility.error_query()
                print("  error_query: code:", outVal[0], " message:", outVal[1])
                fetched_error = outVal
                if(outVal[0] == 0): # 0 = No error, error queue empty
                    break

            num_sequences = len(dResult) // 6 
            reshaped_result = reshape(dResult, (num_sequences, 6))   # data col in order: Voltage, Current, Resistance, Time, Status, Source
            return reshaped_result, fetched_error
        
        except Exception as e:
            print("\n  Exception:", e.__class__.__name__, e.args)
            str_e = str(e.__class__.__name__) + " " + str(e.args)
            return str_e
    
    def close(self):
        """
        Close the connection to the Keysight B2900 instrument.

        This method ensures that the instrument driver is properly closed,
        releasing any resources or locks associated with the connection.
        """
        if self.driver is not None:
            self.driver.close()

    def calibrate(self):
        """
        Perform a calibration procedure on the Keysight B2900 instrument.

        This method sends a calibration command to the instrument, waits for the process 
        to complete, checks the calibration status, and handles any errors that may occur.

        Returns:
        - CALsuccess (bool): True if calibration was successful, False otherwise.
        - fetched_error (tuple): The last fetched error code and message from the instrument.

        If an exception occurs, it prints the exception details.
        """
        try:
            self.driver.system.write_string("*CAL?")
            sleep(5)
            CALstatus = self.driver.system.read_string()
            print("Calibration status:", CALstatus)
            if CALstatus == "+0":
                print("Calibration successful")
                CALsuccess = True
            else:
                print("Calibration failed")
                CALsuccess = False

            print()
            while True:
                outVal = ()
                outVal = self.driver.utility.error_query()
                print("  error_query: code:", outVal[0], " message:", outVal[1])
                fetched_error = outVal
                if(outVal[0] == 0): # 0 = No error, error queue empty
                    break

            return CALsuccess, fetched_error
        
        except Exception as e:
            print("\n  Exception:", e.__class__.__name__, e.args)