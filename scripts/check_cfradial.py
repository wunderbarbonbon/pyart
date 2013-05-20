#!/usr/bin/env python
"""
Script to check the compliance of a file with the CF/Radial 1.2 standard
"""

import time
import argparse

import numpy as np
import netCDF4

# variable types
DOUBLE = np.float64
FLOAT = np.float32
BYTE = np.byte
INT = np.int32
SHORT = np.int16
STRING = unicode
CHAR = np.dtype('S1')


class AttributeTable:
    """
    A class represeting a table of required/optional variable attributes.
    """

    def __init__(self, text, section):
        self.text = text
        self.section = section
        self.attributes = {}
        self.required_attrs = []
        self.optional_attrs = []

    def add_attr(self, attr_name, required, _type=None, value=None):
        """ Add an attribute to the table. """
        self.attributes[attr_name] = Attribute(_type, value)
        if required:
            self.required_attrs.append(attr_name)
        else:
            self.optional_attrs.append(attr_name)

    def req_attr(self, attr_name, _type=None, value=None):
        """ Add a required attribute to the table. """
        self.attributes[attr_name] = Attribute(_type, value)
        self.required_attrs.append(attr_name)

    def opt_attr(self, attr_name, _type=None, value=None):
        """ Add an optional attribute to the table. """
        self.attributes[attr_name] = Attribute(_type, value)
        self.optional_attrs.append(attr_name)

    def check_attr(self, attr_name, required, test_var, verb):
        """ Check an attribute, log errors or notes if detected. """
        if attr_name not in test_var.ncattrs():
            if required:
                t = "Required %s '%s' missing." % (self.text, attr_name)
                log_error(self.section, t)
                return
            if verb:
                t = "Optional %s '%s' missing." % (self.text, attr_name)
                log_note(self.section, t)
            return

        attr_obj = self.attributes[attr_name]
        attr = getattr(test_var, attr_name)

        # check for incorrect type
        if attr_obj.type_bad(type(attr)):
            tup = (self.text, attr_name, type(attr), attr_obj._type)
            t = "%s '%s' has incorrect type: %s should be %s." % tup
            log_error(self.section, t)

        # check for incorrect value
        if attr_obj.value_bad(attr):
            tup = (self.text, attr_name, attr, attr_obj.value)
            t = "%s '%s' has incorrect value: %s should be %s." % tup
            log_error(self.section, t)

    def check(self, test_var, verb=False):
        """ Check all attributes for errror and notes. """
        # check for required attributes
        for attr_name in self.required_attrs:
            self.check_attr(attr_name, True, test_var, verb)
        for attr_name in self.optional_attrs:
            self.check_attr(attr_name, False, test_var, verb)


class Attribute:
    """
    A class for holding and checking netCDF variable attributes.

    Parameters
    ----------
    _type : type or None
        Expected type of the attribute, None for no expected type.
    value : any or None
        Expected value for the attribute, None for no expected value.

    """

    def __init__(self, _type=None, value=None):
        """ initialize the object. """
        self._type = _type
        self.value = value

    def type_bad(self, _type):
        """
        Return True if the provided type does not matches the expected type.
        """
        if self._type is None or self._type == _type:
            return False
        return True

    def value_bad(self, value):
        """
        Return True if the provided value does not match the expected value.
        """
        if self.value is None or self.value == value:
            return False
        return True


class VariableTable:
    """
    A class represeting a table of required/optional variables.
    """
    def __init__(self, text, section):
        """ Initialize the table. """
        self.text = text
        self.section = section
        self.variables = {}
        self.required_vars = []
        self.optional_vars = []

    def add_var(self, var_name, required, dtype=None, dim=None, units=None):
        """ Add an attribute to the table. """
        self.variables[var_name] = Variable(dtype, dim, units)
        if required:
            self.required_vars.append(var_name)
        else:
            self.optional_vars.append(var_name)

    def req_var(self, var_name, dtype=None, dim=None, units=None):
        """ Add a required variable to the table. """
        self.variables[var_name] = Variable(dtype, dim, units)
        self.required_vars.append(var_name)

    def opt_var(self, var_name, dtype=None, dim=None, units=None):
        """ Add an optional variable to the table. """
        self.variables[var_name] = Variable(dtype, dim, units)
        self.optional_vars.append(var_name)

    def check_var(self, var_name, required, dataset, verb):
        """ Check a specific that a variable exists has correct attributes."""
        if var_name not in dataset.variables:
            if required:
                t = "Required %s '%s' missing." % (self.text, var_name)
                log_error(self.section, t)
                return
            if verb:
                t = "Optional %s '%s' missing." % (self.text, var_name)
                log_note(self.section, t)
            return

        # the variable exist, load the variable and variable object
        var_obj = self.variables[var_name]
        var = dataset.variables[var_name]

        # check for incorrect type
        if var_obj.dtype_bad(var.dtype):
            tup = (self.text, var_name, var.dtype, var_obj.dtype)
            t = "%s '%s' has incorrect type: %s should be %s" % tup
            log_error(self.section, t)
        # check for incorrect dim
        if var_obj.dim_bad(var.dimensions):
            tup = (self.text, var_name, var.dimensions, var_obj.dim)
            t = "%s '%s' has incorrect dimensions: %s should be %s" % tup
            log_error(self.section, t)
        # check for bad units
        if 'units' not in var.ncattrs() and var_obj.units is not None:
            t = "%s '%s' is missing a unit attribute." % (self.text, var_name)
            log_error(self.section, t)
            return
        if var_obj.units is not None and var_obj.units_bad(var.units):
            tup = (self.text, var_name, var.units, var_obj.units)
            t = "%s '%s' has incorrect units: %s should be %s" % tup
            log_error(self.section, t)

    def check(self, dataset, verb=False):
        """ Perform all checks on the variables. """
        # check required variables
        for var_name in self.required_vars:
            self.check_var(var_name, True, dataset, verb)
        # check optional variables
        for var_name in self.optional_vars:
            self.check_var(var_name, False, dataset, verb)
        return


class Variable:
    """
    A class for holding and checking netCDF variables.

    Parameters
    ----------
    dtype : type or None
        Expected dtype of the variable, None for no expected type.
    dim : tuple of str
        Expected dimensions of the variable, None for no expected dimensions.
    units : str
        Expected units attribute of the variable.  None for no expected units.

    """

    def __init__(self, dtype=None, dim=None, units=None):
        """ initalize the object. """
        self.dtype = dtype
        self.dim = dim
        self.units = units

    def dtype_bad(self, dtype):
        """ True if the provided dtype does not match the expected dtype. """
        if self.dtype is None:
            return False
        elif self.dtype == dtype:
            return False
        else:
            return True

    def dim_bad(self, dim):
        """ True if the provided dim does not match the expected dim. """
        if self.dim is None:
            return False
        elif self.dim == dim:
            return False
        else:
            return True

    def units_bad(self, units):
        """ True is the provided units does not match the expected units. """
        if self.units is None:
            return False
        elif self.units == units:
            return False
        else:
            return True


def log_error(section, text):
    """
    Log an error, print it to standard out.
    """
    print "ERROR: (%s) %s" % (section, text)


def log_note(section, text):
    """
    Log a note (unmet optional part of the standard), print to standard out.
    """
    print "NOTE: (%s) %s" % (section, text)


def check_attribute(section, obj, text, attr_name, valid_choices):
    """ Checks an attribute which has a set number of valid values. """
    if attr_name in obj.ncattrs():
        attr = getattr(obj, attr_name)
        if attr not in valid_choices:
            tup = (text, attr_name, attr, ' '.join(valid_choices))
            t = "%s '%s' has an invalid value: %s must be one of %s" % tup
            log_error(section, t)
    return


def check_char_variable(section, dataset, text, var_name, valid_options):
    """ Check a char variable which has a set number of valid values."""
    if var_name in dataset.variables:
        var = dataset.variables[var_name][:]
        value = var.tostring().strip('\x00').strip()
        if value not in valid_options:
            tup = (text, var_name, value, ' '.join(valid_options))
            t = "%s '%s' has an invalid value: %s must be one of %s" % tup
            log_error(section, t)
    return


def check_chararr_variable(section, dataset, text, var_name, valid_options):
    """
    Check a variable array of chars which has a set number of valid values.
    """
    if var_name in dataset.variables:
        for i, chars in enumerate(dataset.variables[var_name]):

            value = chars.tostring().strip('\x00').strip()
            if value not in valid_options:
                tup = (text, var_name, i, value, ' '.join(valid_options))
                t = ("%s '%s' has an invalid value in position %i: "
                     "%s must be one of %s" % tup)
                log_error(section, t)
    return


def check_valid_time_format(section, dataset, text, var_name):
    """ Check that a variable is a valid UTC time formatted string. """
    if var_name in dataset.variables:
        s = str(netCDF4.chartostring(dataset.variables[var_name][:]))
        try:
            time.strptime(s, '%Y-%m-%dT%H:%M:%SZ')
        except:
            tup = (text, var_name, s, 'yyyy-mm-ddThh:mm:ssZ')
            t = "%s '%s' has an invalid format: %s should be %s" % (tup)
            log_error(section, t)


def check_metagroup(section, dataset, meta_group_name, valid_meta_group_vars):
    """ Check the meta_group attributes of a meta group. """
    # check that all variable present have a meta_group attribute and it is
    # set correctly.
    for var_name in valid_meta_group_vars:
        if var_name in dataset.variables:
            var = dataset.variables[var_name]
            if 'meta_group' not in var.ncattrs():
                tup = (meta_group_name, var_name)
                text = "%s %s does not have a `meta_group` attribute" % (tup)
                log_error(section, text)
            else:
                if var.meta_group != meta_group_name:
                    tup = (meta_group_name, var_name, var.meta_group,
                           meta_group_name)
                    text = ("%s %s 'meta_group' attribute has incorrect "
                            "value: %s should be %s" % (tup))
                    log_error(section, text)

    # check if other variables have meta_group attribute set to the
    # current meta_group.
    # XXX this might not be considered an error but rather a note
    for var_name in find_all_meta_group_vars(dataset, meta_group_name):
        if var_name not in valid_meta_group_vars:
            text = ('variable %s should not have its meta_group attribute '
                    "set to '%s'" % (var_name, meta_group_name))
            log_error(section, text)


def find_all_meta_group_vars(dataset, meta_group_name):
    """
    Return a list of all variables which are in a given meta_group.
    """
    return [k for k, v in dataset.variables.iteritems() if
            'meta_group' in v.ncattrs() and v.meta_group == meta_group_name]


def check_cfradial_compliance(dataset, verb=False):
    """
    Check a netcdf dataset for CF/Radial compliance.

    Parameters
    ----------
    dataset : Dataset
        NetCDF Dataset to check against CF/Radial version 1.2 standard
    verb : bool
        True to turn on verbose messages (Notes on missing optional
        variables/attributes).  False (default) to suppress

    """
    ##########################
    # 3 Convention hierarchy #
    ##########################
    if 'Conventions' in dataset.ncattrs():
        if 'CF/Radial' not in dataset.Conventions:
            text = "Convention attribute does not contain 'CF/Radial'"
            log_error('3', text)

    #################################
    # 4: CF/Radial base conventions #
    #################################

    # 4.1 Global attributes
    global_attrs = AttributeTable('global attribute', '4.1')
    global_attrs.req_attr('Conventions', STRING)
    global_attrs.opt_attr('version', STRING)
    global_attrs.req_attr('title', STRING)
    global_attrs.req_attr('institution', STRING)
    global_attrs.req_attr('references', STRING)
    global_attrs.req_attr('source', STRING)
    global_attrs.req_attr('history', STRING)
    global_attrs.req_attr('comment', STRING)
    global_attrs.req_attr('instrument_name', STRING)
    global_attrs.opt_attr('site_name', STRING)
    global_attrs.opt_attr('scan_name', STRING)
    global_attrs.opt_attr('scan_id', INT)
    global_attrs.opt_attr('platform_is_mobile', STRING)
    global_attrs.opt_attr('n_gates_vary', STRING)
    global_attrs.check(dataset, verb)

    check_attribute('4.1', dataset, 'global attribute', 'platform_is_mobile',
                    ['true', 'false'])

    check_attribute('4.1', dataset, 'global attribute', 'n_gates_vary',
                    ['true', 'false'])

    n_gates_vary_flag = False
    if 'n_gates_vary' in dataset.ncattrs()and dataset.n_gates_vary == 'true':
        n_gates_vary_flag = True

    mobile_platform = False
    if 'platform_is_mobile' in dataset.ncattrs():
        if dataset.platform_is_mobile == 'true':
            mobile_platform = True

    # 4.2 Dimensions
    section = '4.2'

    if 'time' not in dataset.dimensions:
        log_error(section, "Required dimension 'time' missing.")
    if 'range' not in dataset.dimensions:
        log_error(section, "Required dimension 'range' missing.")
    if 'sweep' not in dataset.dimensions:
        log_error(section, "Required dimension 'sweep' missing.")
    if n_gates_vary_flag and 'n_points' not in dataset.dimensions:
        text = "Dimension 'n_points' is required and missing."
        log_error(section, text)
    if n_gates_vary_flag is False and 'n_points' in dataset.dimensions:
        text = "Dimension 'n_points must not be included."
        log_error(section, text)
    if verb:
        if 'frequency' not in dataset.dimensions:
            log_note(section, "Optional dimension 'frequency' missing")

    # 4.3 Global variables
    global_vars = VariableTable('global variable', '4.3')
    global_vars.req_var('volume_number', INT)
    global_vars.opt_var('platform_type', CHAR)
    global_vars.opt_var('instrument_type', CHAR)
    global_vars.opt_var('primary_axis', CHAR)
    global_vars.req_var('time_coverage_start', CHAR)
    global_vars.req_var('time_coverage_end', CHAR)
    global_vars.opt_var('time_reference', CHAR)
    global_vars.check(dataset, verb)

    valid_platform_types = [
        'fixed', 'vehicle', 'ship', 'aircraft', 'aircraft_fore',
        'aircraft_aft', 'aircraft_tail', 'aircraft_belly', 'aircraft_roof',
        'aircraft_nose', 'satellite_orbit', 'satellite_geostat']
    check_char_variable('4.3', dataset, 'global variable', 'platform_type',
                        valid_platform_types)

    check_char_variable('4.3', dataset, 'global variable', 'instrument_type',
                        ['radar', 'lidar'])

    check_char_variable('4.3', dataset, 'global variable', 'primary_axis',
                        ['axis_z', 'axis_y', 'axis_x'])

    check_valid_time_format('4.3', dataset, 'global_variable',
                            'time_coverage_start')

    check_valid_time_format('4.3', dataset, 'global_variable',
                            'time_coverage_end')

    check_valid_time_format('4.3', dataset, 'global_variable',
                            'time_reference')

    # 4.4 Coordinate variables
    coordinate_vars = VariableTable('coordinate variable', '4.4')
    coordinate_vars.req_var('time', DOUBLE, ('time', ))
    coordinate_vars.req_var('range', FLOAT, ('range', ), 'meters')
    coordinate_vars.check(dataset, verb)

    # 4.4.1 Attributes for time coordinate variable
    time_attrs = AttributeTable('time attribute', '4.4.1')
    time_attrs.req_attr('standard_name', STRING, 'time')
    time_attrs.req_attr('long_name', STRING,
                        'time_in_seconds_since_volume_start')
    time_attrs.req_attr('units', STRING)
    if 'time' in dataset.variables:
        time_attrs.check(dataset.variables['time'], verb)

    # time unit must be 'seconds since yyyy-mm-ddThh:mm:ssZ'
    if 'time' in dataset.variables:
        if 'units' in dataset.variables['time'].ncattrs():
            time_units = dataset.variables['time'].units

            # begins with 'seconds since '
            if not time_units.startswith('seconds since '):
                t = ("time attribute 'units' has an invalid format: " +
                     str(time_units) + "should begin with 'seconds since '")
                log_error('4.4.1', t)

            # end with yyy-mm-ddThh:mm:ssZ
            time_str = time_units[-20:]
            try:
                time.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
            except:
                tup = (time_str, 'yyyy-mm-ddThh:mm:ssZ')
                t = ("'time' attribute 'units' has an invalid formatted time"
                     "value: %s should be %s" % (tup))
                log_error('4.4.1', t)

            # and must match time_reference or time_coverage_start
            if 'time_reference' in dataset.variables:
                v = dataset.variables['time_reference']
                s = str(netCDF4.chartostring(v[:]))
                if s != time_str:
                    tup = (time_str, s)
                    t = ("time attribute 'units' does not match time in "
                         "time_reference variable: %s verses %s" % (tup))
                    log_error('4.4.1', t)
            elif 'time_coverage_start' in dataset.variables:
                v = dataset.variables['time_coverage_start']
                s = str(netCDF4.chartostring(v[:]))
                if s != time_str:
                    tup = (time_str, s)
                    t = ("time attribute 'units' does not match time in "
                         "time_coverage_start variable: %s verses %s" % (tup))
                    log_error('4.4.1', t)

    # 4.4.2 Attribute for range coordinate variables
    range_attrs = AttributeTable('range attribute', '4.4.2')
    range_attrs.req_attr('standard_name', STRING,
                         'projection_range_coordinate')
    range_attrs.req_attr('long_name', STRING, 'range_to_measurement_volume')
    range_attrs.req_attr('units', STRING, 'meters')
    range_attrs.req_attr('spacing_is_constant', STRING)
    range_attrs.req_attr('meters_to_center_of_first_gate', FLOAT)
    range_attrs.opt_attr('meters_between_gates', FLOAT)
    range_attrs.req_attr('axis', STRING, 'radial_range_coordinate')
    if 'range' in dataset.variables:
        range_var = dataset.variables['range']
        range_attrs.check(range_var, verb)
        check_attribute('4.4.2', range_var, 'range attribute',
                        'spacing_is_constant', ['true', 'false'])

    # 4.5 Ray dimension variables
    raydim_vars = VariableTable('ray dimension variable', '4.5')
    raydim_vars.req_var('ray_n_gates', INT, ('time', ))
    raydim_vars.req_var('ray_start_index', INT, ('time', ))

    if n_gates_vary_flag:
        raydim_vars.check(dataset)
    else:
        if 'ray_n_gates' in dataset.variables:
            t = "ray dimension variable 'ray_n_gates' must be exist."
            log_error('4.5', t)
        if 'ray_start_index' in dataset.variables:
            t = "ray dimension variable 'ray_start_index' must be exist."
            log_error('4.5', t)

    # 4.6 Location variables
    dim = ()
    if 'platform_is_mobile' in dataset.ncattrs():
        if dataset.platform_is_mobile == 'true':
            dim = ('time', )
    location_vars = VariableTable('location variable', '4.6')
    location_vars.req_var('latitude', DOUBLE, dim, 'degrees_north')
    location_vars.req_var('longitude', DOUBLE, dim, 'degrees_east')
    location_vars.req_var('altitude', DOUBLE, dim, 'meters')
    location_vars.opt_var('altitude_agl', DOUBLE, dim, 'meters')
    location_vars.check(dataset, verb)

    # 4.7 Sweep variables
    sweep_vars = VariableTable('sweep variable', '4.7')
    sweep_vars.req_var('sweep_number', INT, ('sweep', ))
    sweep_vars.req_var('sweep_mode', CHAR)
    sweep_vars.req_var('fixed_angle', FLOAT, ('sweep', ), 'degrees')
    sweep_vars.req_var('sweep_start_ray_index', INT, ('sweep', ))
    sweep_vars.req_var('sweep_end_ray_index', INT, ('sweep', ))
    sweep_vars.opt_var('target_scan_rate', FLOAT, ('sweep', ),
                       'degrees_per_second')
    sweep_vars.check(dataset, verb)

    valid_sweep_modes = [
        'sector', 'coplane', 'rhi', 'vertical_pointing', 'idle',
        'azimuth_surveillance', 'elevation_surveillance', 'sunscan',
        'pointing', 'manual_ppi', 'manual_rhi']
    check_chararr_variable('4.7', dataset, 'sweep variable', 'sweep_mode',
                           valid_sweep_modes)

    # 4.8 Sensor pointing variables
    sensor_vars = VariableTable('sensor pointing variable', '4.8')
    sensor_vars.req_var('azimuth', FLOAT, ('time', ), 'degrees')
    sensor_vars.req_var('elevation', FLOAT, ('time', ), 'degrees')
    sensor_vars.opt_var('scan_rate', FLOAT, ('time', ), 'degrees_per_second')
    sensor_vars.opt_var('antenna_transition', BYTE, ('time', ))
    sensor_vars.check(dataset, verb)

    # 4.8.1 Attributes for azimuth(time) variable
    azimuth_attrs = AttributeTable('azimuth attribute', '4.8.1')
    azimuth_attrs.req_attr('standard_name', STRING, 'beam_azimuth_angle')
    azimuth_attrs.req_attr('long_name', STRING,
                           'azimuth_angle_from_true_north')
    azimuth_attrs.req_attr('units', STRING, 'degrees')
    azimuth_attrs.req_attr('axis', STRING, 'radial_azimuth_coordinate')
    if 'azimuth' in dataset.variables:
        azimuth_attrs.check(dataset.variables['azimuth'], verb)

    # 4.8.2 Attributes for elevation(time) variable
    elev_attrs = AttributeTable('elevation attribute', '4.8.2')
    elev_attrs.req_attr('standard_name', STRING, 'beam_elevation_angle')
    elev_attrs.req_attr('long_name', STRING,
                        'elevation_angle_from_horizontal_plane')
    elev_attrs.req_attr('units', STRING, 'degrees')
    elev_attrs.req_attr('axis', STRING, 'radial_elevation_coordinate')
    if 'elevation' in dataset.variables:
        elev_attrs.check(dataset.variables['elevation'], verb)

    # 4.9 Moving platform geo-reference variables
    georef_vars = VariableTable('moving platform geo-reference variable',
                                '4.9')
    georef_vars.req_var('heading', FLOAT, ('time', ), 'degrees')
    georef_vars.req_var('roll', FLOAT, ('time', ), 'degrees')
    georef_vars.req_var('pitch', FLOAT, ('time', ), 'degrees')
    georef_vars.req_var('drift', FLOAT, ('time', ), 'degrees')
    georef_vars.req_var('rotation', FLOAT, ('time', ), 'degrees')
    georef_vars.req_var('tilt', FLOAT, ('time', ), 'degrees')
    if mobile_platform:
        georef_vars.check(dataset, verb)
    else:  # fixed platfrom
        for v in ['heading', 'roll', 'pitch', 'drift', 'rotation', 'tilt']:
            if v in dataset.variables:
                t = "variable '%s' must be omitted for fixed platforms" % (v)
                log_error('4.9', t)

    # 4.10 Moments field data variables

    # assume all variables with dimensions ('time', 'range') are field data
    # XXX a better way to do this might be to check against section 6.2
    for var_name, var in dataset.variables.iteritems():
        if var.dimensions == ('time', 'range'):

            # check the data type
            if var.dtype not in [BYTE, SHORT, INT, FLOAT, DOUBLE]:
                tup = (var_name, var.dtype)
                t = "field variable '%s' has invalid type: %s" % (tup)
                log_error('4.10', t)

            # check attributes
            if mobile_platform:
                coordinates_value = ('elevation azimuth range heading roll '
                                     'pitch rotation tilt')
            else:
                coordinates_value = 'elevation azimuth range'

            # TODO check standard_name, against variable name
            # TODO check units correct for given standard_name
            text = "field variable %s" % var_name
            field_attrs = AttributeTable(text, '4.10')
            field_attrs.opt_attr('long_name', STRING)
            field_attrs.req_attr('standard_name', STRING)
            field_attrs.req_attr('units', STRING)
            field_attrs.req_attr('_FillValue')
            if var.dtype in [BYTE, SHORT, INT]:
                field_attrs.req_attr('scale_factor', FLOAT)
                field_attrs.req_attr('add_offset', FLOAT)
            field_attrs.req_attr('coordinates', STRING, coordinates_value)
            field_attrs.check(var, verb)

    #####################
    # 5 Sub-conventions #
    #####################

    # 5.1 The instrument_parameters sub-convention
    ip_vars = VariableTable('instrument_parameters variable', '5.1')
    ip_vars.opt_var('frequency', FLOAT, ('frequency', ), 's-1')
    ip_vars.opt_var('follow_mode', CHAR)
    ip_vars.opt_var('pulse_width', FLOAT, ('time', ), 'seconds')
    ip_vars.opt_var('prt_mode', CHAR)
    ip_vars.opt_var('prt', FLOAT, ('time', ), 'seconds')
    ip_vars.opt_var('prt_ratio', FLOAT, ('time', ))
    ip_vars.opt_var('polarization_mode', CHAR)
    ip_vars.opt_var('nyquist_velocity', FLOAT, ('time', ), 'meters_per_second')
    ip_vars.opt_var('unambiguous_range', FLOAT, ('time', ), 'meters')
    ip_vars.opt_var('n_samples', INT, ('time', ))
    ip_vars.opt_var('sampling_ratio', FLOAT, ('time'))
    ip_vars.check(dataset, verb)

    # first dimension should be sweep for _modes variables
    for v in ['follow_mode', 'prt_mode', 'polarization_mode']:
        if v in dataset.variables:
            dim_0 = dataset.variables[v].dimensions[0]
            if dim_0 != 'sweep':
                text = ("instrument_parameters %s must have a first "
                        "dimension of sweep, not %s" % (v, dim_0))
                log_error('5.1', text)

    # check valid options for _modes variables
    valid_follow_modes = [
        'none', 'sun', 'vehicle', 'aircraft', 'target', 'manual']
    check_chararr_variable('5.1', dataset, 'instrument_parameters',
                           'follow_mode', valid_follow_modes)

    valid_prt_modes = ['fixed', 'staggered', 'dual']
    check_chararr_variable('5.1', dataset, 'instrument_parameters',
                           'prt_mode', valid_prt_modes)

    valid_polarization_modes = [
        'horizontal', 'vertical', 'hv_alt', 'hv_sim', 'circular']
    check_chararr_variable('5.1', dataset, 'instrument_parameters',
                           'polarization_mode', valid_polarization_modes)

    # check that meta_group attribute is correctly set.
    valid_ip_vars = [
        'frequency', 'follow_mode', 'pulse_width', 'prt_mode', 'prt',
        'prt_ratio', 'polarization_mode', 'nyquist_velocity',
        'unambiguous_range', 'n_samples', 'sampling_ratio']
    check_metagroup('5.1', dataset, 'instrument_parameters', valid_ip_vars)

    # 5.2 The radar_parameters sub-convention
    rp_vars = VariableTable('radar_parameters', '5.2')
    rp_vars.opt_var('radar_antenna_gain_h', FLOAT, (), 'dB')
    rp_vars.opt_var('radar_antenna_gain_v', FLOAT, (), 'dB')
    rp_vars.opt_var('radar_beam_width_h', FLOAT, (), 'degrees')
    rp_vars.opt_var('radar_beam_width_v', FLOAT, (), 'degrees')
    rp_vars.opt_var('radar_reciever_bandwidth', FLOAT, (), 's-1')
    rp_vars.opt_var('radar_measured_transmit_power_h', FLOAT, ('time', ),
                    'dBm')
    rp_vars.opt_var('radar_measured_transmit_power_b', FLOAT, ('time', ),
                    'dBm')
    rp_vars.check(dataset, verb)

    valid_rp_vars = [
        'radar_antenna_gain_h', 'radar_antenna_gain_v',
        'radar_beam_width_h', 'radar_beam_width_v',
        'radar_reciever_bandwidth',
        'radar_measured_transmit_power_h', 'radar_measured_transmit_power_b']
    check_metagroup('5.2', dataset, 'radar_parameters', valid_rp_vars)

    # 5.3 The lidar_parameter sub-convention
    lp_vars = VariableTable('lidar_parameters', '5.3')
    lp_vars.opt_var('lidar_beam_divergence', FLOAT, (), 'milliradians')
    lp_vars.opt_var('lidar_field_of_view', FLOAT, (), 'milliradians')
    lp_vars.opt_var('lidar_aperature_diameter', FLOAT, (), 'cm')
    lp_vars.opt_var('lidar_aperture_efficiency', FLOAT, (), 'percent')
    lp_vars.opt_var('lidar_peak_power', FLOAT, (), 'watts')
    lp_vars.opt_var('lidar_pulse_energy', FLOAT, (), 'joules')
    lp_vars.check(dataset, verb)

    valid_lp_vars = [
        'lidar_beam_divergence', 'lidar_field_of_view',
        'lidar_aperature_diameter', 'lidar_aperture_efficiency'
        'lidar_peak_power', 'lidar_pulse_energy']
    check_metagroup('5.3', dataset, 'lidar_parameters', valid_lp_vars)

    # 5.4 The radar_calibration sub-convention
    valid_rc_vars = [
        'r_calib_index',
        'r_calib_time',
        'r_calib_pulse_width',
        'r_calib_ant_gain_h',
        'r_calib_ant_gain_v',
        'r_calib_xmit_power_h',
        'r_calib_xmit_power_v',
        'r_calib_two_way_waveguide_loss_h',
        'r_calib_two_way_waveguide_loss_v',
        'r_calib_two_way_radome_loss_h',
        'r_calib_two_way_radome_loss_v',
        'r_calib_receiver_mismatch_loss',
        'r_calib_radar_constant_h',
        'r_calib_radar_constant_v',
        'r_calib_noise_hc',
        'r_calib_noise_vc',
        'r_calib_noise_hx',
        'r_calib_noise_vx',
        'r_calib_receiver_gain_hc',
        'r_calib_receiver_gain_vc',
        'r_calib_receiver_gain_hx',
        'r_calib_receiver_gain_vx',
        'r_calib_base_dbz_1km_hc',
        'r_calib_base_dbz_1km_vc',
        'r_calib_base_dbz_1km_hx',
        'r_calib_base_dbz_1km_vx',
        'r_calib_sun_power_hc',
        'r_calib_sun_power_vc',
        'r_calib_sun_power_hx',
        'r_calib_sun_power_vx',
        'r_calib_noise_source_power_h',
        'r_calib_noise_source_power_v',
        'r_calib_power_measure_loss_h',
        'r_calib_power_measure_loss_v',
        'r_calib_coupler_forward_loss_h',
        'r_calib_coupler_forward_loss_v',
        'r_calib_zdr_correction',
        'r_calib_ldr_correction_h',
        'r_calib_ldr_correction_v',
        'r_calib_system_phidp',
        'r_calib_test_power_h',
        'r_calib_test_power_v',
        'r_calib_receiver_slope_hc',
        'r_calib_receiver_slope_vc',
        'r_calib_receiver_slope_hx',
        'r_calib_receiver_slope_vx', ]
    check_metagroup('5.4', dataset, 'radar_calibration', valid_rc_vars)

    # 5.4.1 Dimensions

    # 5.4.2 Variables
    d = ('r_calib', )
    rc_vars = VariableTable('radar_calibration', '5.4.2')
    rc_vars.opt_var('r_calib_index', BYTE, ('time', ))
    rc_vars.opt_var('r_calib_time', CHAR)
    rc_vars.opt_var('r_calib_pulse_width', FLOAT, d, 'seconds')
    rc_vars.opt_var('r_calib_ant_gain_h', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_ant_gain_v', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_xmit_power_h', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_xmit_power_v', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_two_way_waveguide_loss_h', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_two_way_waveguide_loss_v', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_two_way_radome_loss_h', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_two_way_radome_loss_v', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_receiver_mismatch_loss', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_radar_constant_h', FLOAT, d, 'dB')  # m/mW
    rc_vars.opt_var('r_calib_radar_constant_v', FLOAT, d, 'dB')  # m/mW
    rc_vars.opt_var('r_calib_noise_hc', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_noise_vc', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_noise_hx', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_noise_vx', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_receiver_gain_hc', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_receiver_gain_vc', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_receiver_gain_hx', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_receiver_gain_vx', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_base_dbz_1km_hc', FLOAT, d, 'dBZ')
    rc_vars.opt_var('r_calib_base_dbz_1km_vc', FLOAT, d, 'dBZ')
    rc_vars.opt_var('r_calib_base_dbz_1km_hx', FLOAT, d, 'dBZ')
    rc_vars.opt_var('r_calib_base_dbz_1km_vx', FLOAT, d, 'dBZ')
    rc_vars.opt_var('r_calib_sun_power_hc', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_sun_power_vc', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_sun_power_hx', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_sun_power_vx', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_noise_source_power_h', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_noise_source_power_v', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_power_measure_loss_h', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_power_measure_loss_v', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_coupler_forward_loss_h', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_coupler_forward_loss_v', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_zdr_correction', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_ldr_correction_h', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_ldr_correction_v', FLOAT, d, 'dB')
    rc_vars.opt_var('r_calib_system_phidp', FLOAT, d, 'degrees')
    rc_vars.opt_var('r_calib_test_power_h', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_test_power_v', FLOAT, d, 'dBm')
    rc_vars.opt_var('r_calib_receiver_slope_hc', FLOAT, d)
    rc_vars.opt_var('r_calib_receiver_slope_vc', FLOAT, d)
    rc_vars.opt_var('r_calib_receiver_slope_hx', FLOAT, d)
    rc_vars.opt_var('r_calib_receiver_slope_vx', FLOAT, d)
    rc_vars.check(dataset, verb)

    if 'r_calib_time' in dataset.variables:
        r_calib_time = dataset.variables['r_calib_time']
        dim_0 = r_calib_time.dimensions[0]
        if dim_0 != 'r_calib':
            text = ('radar_calibration r_calib_time must have first '
                    "dimension of 'r_calib' not '%s'" % (dim_0))
            log_error('5.4.2', text)
        else:
            for i, time_arr in enumerate(r_calib_time):
                s = time_arr.tostring().strip('\x00').strip()
                try:
                    time.strptime(s, '%Y-%m-%dT%H:%M:%SZ')
                except:
                    tup = (i, s, 'yyyy-mm-ddThh:mm:ssZ')
                    t = ("radar_calibration r_calib_time has an invalid time "
                         "format in position %i: %s must be %s" % (tup))
                    log_error('5.4.2', t)

    # 5.5 The lidar_calibration sub-convention
    # Not yet defined in the standard

    # 5.6 The platform_velocity sub-convention
    d = ('time', )
    pv_vars = VariableTable('platform_velocity', '5.6')
    pv_vars.req_var('eastward_velocity', FLOAT, d, 'meters_per_second')
    pv_vars.req_var('northward_velocity', FLOAT, d, 'meters_per_second')
    pv_vars.req_var('vertical_velocity', FLOAT, d, 'meters_per_second')
    pv_vars.req_var('eastward_wind', FLOAT, d, 'meters_per_second')
    pv_vars.req_var('northward_wind', FLOAT, d, 'meters_per_second')
    pv_vars.req_var('vertical_wind', FLOAT, d, 'meters_per_second')
    pv_vars.req_var('heading_rate', FLOAT, d, 'degrees_per_second')
    pv_vars.req_var('roll_rate', FLOAT, d, 'degrees_per_second')
    pv_vars.req_var('pitch_rate', FLOAT, d, 'degrees_per_second')

    valid_pv_vars = [
        'eastward_velocity', 'northward_velocity', 'vertical_velocity',
        'eastward_wind', 'northward_wind', 'vertical_wind',
        'heading_rate', 'roll_rate',  'pitch_rate']

    if mobile_platform:
        pv_vars.check(dataset, verb)
        check_metagroup('5.6', dataset, 'platform_velocity', valid_pv_vars)
    else:
        for var_name in valid_pv_vars:
            if var_name in dataset.variables:
                t = ('variable %s should not exist as the platform is'
                     'stationary' % (var_name))
                log_error('5.6', t)

    # 5.7 The geometry_correction sub-convention
    gc_vars = VariableTable('geometry_correction', '5.7')
    gc_vars.opt_var('azimuth_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('elevation_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('range_correction', FLOAT, (), 'meters')
    gc_vars.opt_var('longitude_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('latitude_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('pressure_altitude_correction', FLOAT, (), 'meters')
    gc_vars.opt_var('radar_altitude_correction', FLOAT, (), 'meters')
    gc_vars.opt_var('eastward_ground_speed_correction', FLOAT, (),
                    'meter_per_second')
    gc_vars.opt_var('northward_ground_speed_correction', FLOAT, (),
                    'meter_per_second')
    gc_vars.opt_var('vertical_velocity_correction', FLOAT, (),
                    'meter_per_second')
    gc_vars.opt_var('heading_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('roll_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('pitch_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('drift_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('rotation_correction', FLOAT, (), 'degrees')
    gc_vars.opt_var('tilt_correction', FLOAT, (), 'degrees')
    gc_vars.check(dataset, verb)

    valid_gc_vars = [
        'azimuth_correction',
        'elevation_correction',
        'range_correction',
        'longitude_correction',
        'latitude_correction',
        'pressure_altitude_correction',
        'radar_altitude_correction',
        'eastward_ground_speed_correction',
        'northward_ground_speed_correction',
        'vertical_velocity_correction',
        'heading_correction',
        'roll_correction',
        'pitch_correction',
        'drift_correction',
        'rotation_correction',
        'tilt_correction']
    check_metagroup('5.7', dataset, 'geometry_correction', valid_gc_vars)

    ####################
    # 6 Standard Names #
    ####################

    # 6.1 Proposed standard names for metadata variables

    # 6.2 Standard names for moments variables
    return


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Check a file for CF/Radial version 1.2 compliance.')
    parser.add_argument('filename', type=str, help='netcdf file to check')
    parser.add_argument('--verb', '-v', dest='verb', action='store_true',
                        default=False, help='turn on verbose messages')
    args = parser.parse_args()

    dataset = netCDF4.Dataset(args.filename, 'r')
    check_cfradial_compliance(dataset, args.verb)
