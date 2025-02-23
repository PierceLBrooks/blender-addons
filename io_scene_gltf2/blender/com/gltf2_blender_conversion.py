# SPDX-FileCopyrightText: 2018-2021 The glTF-Blender-IO authors
#
# SPDX-License-Identifier: Apache-2.0

from math import sin, cos
import numpy as np
from ...io.com import gltf2_io_constants

PBR_WATTS_TO_LUMENS = 683
# Industry convention, biological peak at 555nm, scientific standard as part of SI candela definition.

def texture_transform_blender_to_gltf(mapping_transform):
    """
    Converts the offset/rotation/scale from a Mapping node applied in Blender's
    UV space to the equivalent KHR_texture_transform.
    """
    offset = mapping_transform.get('offset', [0, 0])
    rotation = mapping_transform.get('rotation', 0)
    scale = mapping_transform.get('scale', [1, 1])
    return {
        'offset': [
            offset[0] - scale[1] * sin(rotation),
            1 - offset[1] - scale[1] * cos(rotation),
        ],
        'rotation': rotation,
        'scale': [scale[0], scale[1]],
    }

def texture_transform_gltf_to_blender(texture_transform):
    """
    Converts a KHR_texture_transform into the equivalent offset/rotation/scale
    for a Mapping node applied in Blender's UV space.
    """
    offset = texture_transform.get('offset', [0, 0])
    rotation = texture_transform.get('rotation', 0)
    scale = texture_transform.get('scale', [1, 1])
    return {
        'offset': [
            offset[0] + scale[1] * sin(rotation),
            1 - offset[1] - scale[1] * cos(rotation),
        ],
        'rotation': rotation,
        'scale': [scale[0], scale[1]],
    }

def get_target(property):
    return {
        "delta_location": "translation",
        "delta_rotation_euler": "rotation",
        "delta_rotation_quaternion": "rotation",
        "delta_scale": "scale",
        "location": "translation",
        "rotation_axis_angle": "rotation",
        "rotation_euler": "rotation",
        "rotation_quaternion": "rotation",
        "scale": "scale",
        "value": "weights"
    }.get(property, None)

def get_component_type(attribute_component_type):
    return {
        "INT8": gltf2_io_constants.ComponentType.Float,
        "BYTE_COLOR": gltf2_io_constants.ComponentType.UnsignedShort,
        "FLOAT2": gltf2_io_constants.ComponentType.Float,
        "FLOAT_COLOR": gltf2_io_constants.ComponentType.Float,
        "FLOAT_VECTOR": gltf2_io_constants.ComponentType.Float,
        "FLOAT_VECTOR_4": gltf2_io_constants.ComponentType.Float,
        "INT": gltf2_io_constants.ComponentType.Float, # No signed Int in glTF accessor
        "FLOAT": gltf2_io_constants.ComponentType.Float,
        "BOOLEAN": gltf2_io_constants.ComponentType.Float
    }.get(attribute_component_type)

def get_channel_from_target(target):
    return {
        "rotation": "rotation_quaternion",
        "translation": "location",
        "scale": "scale"
    }.get(target)

def get_data_type(attribute_component_type):
    return {
        "INT8": gltf2_io_constants.DataType.Scalar,
        "BYTE_COLOR": gltf2_io_constants.DataType.Vec4,
        "FLOAT2": gltf2_io_constants.DataType.Vec2,
        "FLOAT_COLOR": gltf2_io_constants.DataType.Vec4,
        "FLOAT_VECTOR": gltf2_io_constants.DataType.Vec3,
        "FLOAT_VECTOR_4": gltf2_io_constants.DataType.Vec4,
        "INT": gltf2_io_constants.DataType.Scalar,
        "FLOAT": gltf2_io_constants.DataType.Scalar,
        "BOOLEAN": gltf2_io_constants.DataType.Scalar,
    }.get(attribute_component_type)

def get_data_length(attribute_component_type):
    return {
        "INT8": 1,
        "BYTE_COLOR": 4,
        "FLOAT2": 2,
        "FLOAT_COLOR": 4,
        "FLOAT_VECTOR": 3,
        "FLOAT_VECTOR_4": 4,
        "INT": 1,
        "FLOAT": 1,
        "BOOLEAN": 1
    }.get(attribute_component_type)

def get_numpy_type(attribute_component_type):
    return {
        "INT8": np.float32,
        "BYTE_COLOR": np.float32,
        "FLOAT2": np.float32,
        "FLOAT_COLOR": np.float32,
        "FLOAT_VECTOR": np.float32,
        "FLOAT_VECTOR_4": np.float32,
        "INT": np.float32, #signed integer are not supported by glTF
        "FLOAT": np.float32,
        "BOOLEAN": np.float32
    }.get(attribute_component_type)

def get_attribute_type(component_type, data_type):
    if gltf2_io_constants.DataType.num_elements(data_type) == 1:
        return {
            gltf2_io_constants.ComponentType.Float: "FLOAT",
            gltf2_io_constants.ComponentType.UnsignedByte: "INT" # What is the best for compatibility?
        }.get(component_type, None)
    elif gltf2_io_constants.DataType.num_elements(data_type) == 2:
        return {
            gltf2_io_constants.ComponentType.Float: "FLOAT2"
        }.get(component_type, None)
    elif gltf2_io_constants.DataType.num_elements(data_type) == 3:
        return {
            gltf2_io_constants.ComponentType.Float: "FLOAT_VECTOR"
        }.get(component_type, None)
    elif gltf2_io_constants.DataType.num_elements(data_type) == 4:
        return {
            gltf2_io_constants.ComponentType.Float: "FLOAT_COLOR",
            gltf2_io_constants.ComponentType.UnsignedShort: "BYTE_COLOR",
            gltf2_io_constants.ComponentType.UnsignedByte: "BYTE_COLOR" # What is the best for compatibility?
        }.get(component_type, None)
    else:
        pass

def get_gltf_interpolation(interpolation):
        return {
        "BEZIER": "CUBICSPLINE",
        "LINEAR": "LINEAR",
        "CONSTANT": "STEP"
    }.get(interpolation, "LINEAR")

def get_anisotropy_rotation_gltf_to_blender(rotation):
    # glTF rotation is in randian, Blender in 0 to 1
    return rotation / (2 * np.pi)

def get_anisotropy_rotation_blender_to_gltf(rotation):
    # glTF rotation is in randian, Blender in 0 to 1
    return rotation * (2 * np.pi)
