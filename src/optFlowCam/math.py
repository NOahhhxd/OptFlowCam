import numpy as np
from mathutils import Vector, Matrix

from collections import namedtuple

AxisAngle = namedtuple("AxisAngle", "axis angle")

def make_lookAt_matrix(pos: Vector, forw: Vector, up: Vector) -> Matrix:
    # Vector and Matrix are Blenders own types and need to be used
    # instead of numpy types because typecasting them for just this
    # function would be pointless

    forw = -forw.normalized() # in look at matrix camera looks at negative forward
    right = up.cross(forw).normalized()
    up = forw.cross(right).normalized()

    forw.resize(4)
    right.resize(4)
    up.resize(4)
    pos.resize(4)
    pos[3] = 1

    lookAt = Matrix([right, up, forw, pos]).transposed()
    return lookAt

def normalized(a: np.ndarray) -> np.ndarray:
    '''
    Returns a normalized ndarray and prints a warning
    if the norm is close to zero
    '''

    l2 = np.linalg.norm(a)
    if l2 < 1e-15:
        print("Norm near zero for ", a)
        return a
    return a / l2

def get_orthonormal_basis(cam: dict) -> tuple:
    '''
    Returns an orthonormal basis for the given camera configuration.

    Input camera object needs to have a view and up vector.
    '''

    view = normalized(np.array(cam["view"]))
    up = normalized(np.array(cam["up"]))
    right = normalized(np.cross(up, view))
    up = normalized(np.cross(view, right))

    assert np.all([not np.isclose(np.linalg.norm(v), 0) for v in [view, up, right]]),\
        "Given vectors do not form a basis for camera orientation!"

    return view, up, right

def get_rotation(start: dict, end: dict) -> tuple:
    vecs1 = [start[key] for key in ["view", "right", "up"]]
    vecs2 = [end[key] for key in ["view", "right", "up"]]

    # basis matrix for start
    R1 = np.array([vecs1[1], vecs1[2], vecs1[0]]).T
    R2 = np.array([vecs2[1], vecs2[2], vecs2[0]]).T

    print("Rot1: ", R1@R1.T)
    print("Rot2: ", R2@R2.T)

    # rotation matrix around z-axis
    R_beta = lambda t, beta: np.array([[np.cos(t * beta), -np.sin(t * beta), 0.0],
                                       [np.sin(t * beta), np.cos(t * beta), 0.0],
                                       [0.0, 0.0, 1.0]], dtype=float)

    axis = None
    beta_end = None

    eigenvals, eigenvecs = np.linalg.eig(R2.T - R1.T)
    print(f"Eigenwerte: {eigenvals}\nEigenvektoren:{eigenvecs}")
    # tolerance has to be so high because some cases produce eigenvalues that are not zero
    indices = np.where(np.isclose(eigenvals.real, 0, atol=1e-3))

    if len(indices[0]) == 0:
        raise ValueError("Cannot determine axis of rotation")

    axis = eigenvecs[:, indices[0][0]].flatten()

    # need to normalize in case there was an imaginary part and
    # the real part alone is not unit length anymore
    axis = normalized(axis.real)

    # in case the chosen axis is identical to the view vector
    # we need to determine the rest of the matrix with another vector
    if np.isclose(np.linalg.norm(np.cross(axis, vecs1[0])), 0):
        c1 = normalized(np.cross(vecs1[1], axis))
        c2 = normalized(np.cross(axis, c1))
    else:
        c2 = normalized(np.cross(axis, vecs1[0]))
        c1 = normalized(np.cross(c2, axis))

    # matrix that rotates "axis" so that it is aligned with the z-axis
    # and v1 so that its y-coordinate is zero
    R_axis = np.array([c1, c2, axis]).T

    # can get angle of rotation by determining the angle of the transformed vector
    # projected to xy plane with the x-axis
    h = R_axis.T @ vecs2[0]

    # get the angle of rotation
    if beta_end == None:
        beta_end = np.arctan2(h[1], h[0])

    # interpolating rotation matrix
    R_f = lambda t: R_axis @ R_beta(t, beta_end) @ R_axis.T @ R1

    return AxisAngle(axis, beta_end), R_f
