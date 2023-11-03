import numpy as np


def gaussian_filter(raw_data, p1_param = 1/2, p2_param = 1/6):
    input_shape = np.shape(raw_data)
    filter_mat = 1
    for dim_size in input_shape:
        p1 = dim_size*p1_param
        p2 = dim_size*p2_param
        filter_vec = np.exp(-(np.square(np.arange(dim_size) - p1)/(p2**2)))
        filter_mat = np.multiply.outer(filter_mat, filter_vec)
    return np.multiply(raw_data, filter_mat)


def sine_bell_squared_filter(raw_data,  filter_strength = 1):
    input_shape = np.shape(raw_data)
    filter_mat = 1
    for dim_size in input_shape:
        p1 = dim_size/2
        axis = np.linspace(-dim_size/2, dim_size/2, dim_size)
        filter_vec = 1-filter_strength*np.square(np.cos(0.5*np.pi*(axis-p1)/(dim_size-p1)))
        filter_mat = np.multiply.outer(filter_mat, filter_vec)
    return np.multiply(raw_data, filter_mat)