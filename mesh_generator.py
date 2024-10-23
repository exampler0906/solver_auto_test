#!/usr/bin/python3
import sys
import numpy as np
from itertools import chain
import json
import logging

out_put_path = ""

def generate_block(dim, domain_offset, grid_size, steps, name):
    """
    Generates grid files based on dimensions and grid properties.

    :param dim: Dimension of the grid (1-3)
    :param grid_size: Number of cells in each grid direction (int)
    :param steps: Step sizes for each dimension
    :param name: Name for the generated files
    """
    global out_put_path

    # Validate the dimension
    if dim not in [1, 2, 3]:
        raise ValueError("Dimension must be 1, 2, or 3")

    for i in range(dim):
        s = np.concatenate(([domain_offset[i]], np.cumsum(steps[i]) + domain_offset[i]))
    
    # Create the grid points
    vertex_coords = np.meshgrid(*[np.concatenate(([domain_offset[i]], np.cumsum(steps[i]) + domain_offset[i])) for i in range(dim)], indexing="ij")

    vertex_shape = grid_size + 1

    shape_string = " ".join(str(item) for item in vertex_shape)

    # Write to the plot3d file
    plot3d_filename = out_put_path +  f"{name}.x"
    with open(plot3d_filename, "w") as f:
        f.write("1\n")
        f.write(f"{shape_string}\n")

        for d in range(dim):
            f.write(" ".join(("%.18lf" % item)
                    for item in np.transpose(vertex_coords[d], axes=np.arange(dim)[::-1]).reshape(-1)))
            f.write("\n")

    # Write to the gridgen boundary file
    gridgen_filename = out_put_path + f"{name}.inp"
    with open(gridgen_filename, "w") as f:
        f.write("1\n")
        f.write("1\n")
        f.write(f"{shape_string}\n")
        f.write("blk-1\n")
        f.write(f"{dim * 2}\n")
        # bottom
        for d in range(dim):
            start = [1] * dim
            end = vertex_shape.copy()
            end[d] = 1
            s = list(chain(*[[start[i], end[i]] for i in range(dim)]))
            f.write(" ".join(str(item) for item in s) + " outflow\n")
        # top
        for d in range(dim-1, -1, -1):
            start = [1] * dim
            start[d] = vertex_shape[d]
            end = vertex_shape.copy()
            s = list(chain(*[[start[i], end[i]] for i in range(dim)]))
            f.write(" ".join(str(item) for item in s) + " outflow\n")

    return plot3d_filename, gridgen_filename



def generate_mesh(property_file_path, logger):
    with open(property_file_path, 'r') as json_file:
                data = json.load(json_file)
                logger.info("property.json loaded successfully")
                for key, value in data.items():
                    mesh_file_name_1 = value["mesh"]["file"]["gridfile"]
                    grid_name = mesh_file_name_1.split(".")[0]
    
    steps = [] 
    steps.append(value["field"]["fluid"]["TwoPhaseOilGasMultiComp"]["Reservoir"]["Grid"]["IVAR"])
    steps.append(value["field"]["fluid"]["TwoPhaseOilGasMultiComp"]["Reservoir"]["Grid"]["JVAR"])
    steps.append(value["field"]["fluid"]["TwoPhaseOilGasMultiComp"]["Reservoir"]["Grid"]["KVAR"])
    # for step in steps[1]:
    #      step = -step
    for step in steps[2]:
         step = -step

    grid_size = np.zeros(3, dtype=int)
    grid_size[0] = len(steps[0])
    grid_size[1] = len(steps[1])
    grid_size[2] = len(steps[2])

    domain_offset = np.zeros(3)
    plot3d_filename, gridgen_filename = generate_block(
        3, domain_offset, grid_size, steps, grid_name)
    logger.info(f"Generated files: {plot3d_filename}, {gridgen_filename}")


def mesh_generator_interface(property_file_path_rel, out_put_path_rel, new_logger):
    global out_put_path
    property_file_path = property_file_path_rel
    out_put_path = out_put_path_rel + "/"
    generate_mesh(property_file_path, new_logger)

if __name__ == "__main__":
    args = sys.argv
    property_file_path = args[1]
    out_put_path = args[2]
    generate_mesh(property_file_path)


