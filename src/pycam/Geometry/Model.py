# -*- coding: utf-8 -*-
"""
$Id$

Copyright 2008-2010 Lode Leroy
Copyright 2010 Lars Kruse <devel@sumpfralle.de>

This file is part of PyCAM.

PyCAM is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PyCAM is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyCAM.  If not, see <http://www.gnu.org/licenses/>.
"""

import pycam.Exporters.STLExporter
from pycam.Geometry.Triangle import Triangle
from pycam.Geometry.Line import Line, LineGroup
from pycam.Geometry.Point import Point
from pycam.Geometry.TriangleKdtree import TriangleKdtree
from pycam.Geometry.Matrix import TRANSFORMATIONS
from pycam.Toolpath import Bounds
from pycam.Geometry.utils import INFINITE
from pycam.Geometry import TransformableContainer



class BaseModel(TransformableContainer):
    id = 0

    def __init__(self):
        self.id = BaseModel.id
        BaseModel.id += 1
        self._item_groups = []
        self.name = "model%d" % self.id
        self.minx = None
        self.miny = None
        self.minz = None
        self.maxx = None
        self.maxy = None
        self.maxz = None
        # derived classes should override this
        self._export_function = None

    def __add__(self, other_model):
        """ combine two models """
        result = self.__class__()
        for item in self.next():
            result.append(item)
        for item in other_model.next():
            result.append(item)
        return result

    def next(self):
        for item_group in self._item_groups:
            for item in item_group:
                if isinstance(item, list):
                    for subitem in item:
                        yield subitem
                else:
                    yield item

    def to_OpenGL(self):
        for item in self.next():
            item.to_OpenGL()

    def is_export_supported(self):
        return not self._export_function is None

    def export(self, comment=None):
        if self.is_export_supported():
            return self._export_function(self, comment=comment)
        else:
            raise NotImplementedError(("This type of model (%s) does not " \
                    + "support the 'export' function.") % str(type(self)))

    def _update_limits(self, item):
        if callable(item.minx):
            minx, miny, minz = item.minx(), item.miny(), item.minz()
            maxx, maxy, maxz = item.maxx(), item.maxy(), item.maxz()
        else:
            minx, miny, minz = item.minx, item.miny, item.minz
            maxx, maxy, maxz = item.maxx, item.maxy, item.maxz
        if self.minx is None:
            self.minx = minx
            self.miny = miny
            self.minz = minz
            self.maxx = maxx
            self.maxy = maxy
            self.maxz = maxz
        else:
            self.minx = min(self.minx, minx)
            self.miny = min(self.miny, miny)
            self.minz = min(self.minz, minz)
            self.maxx = max(self.maxx, maxx)
            self.maxy = max(self.maxy, maxy)
            self.maxz = max(self.maxz, maxz)

    def append(self, item):
        self._update_limits(item)

    def maxsize(self):
        return max(abs(self.maxx), abs(self.minx), abs(self.maxy),
                abs(self.miny), abs(self.maxz), abs(self.minz))

    def subdivide(self, depth):
        model = self.__class__()
        for item in self.next():
            for s in item.subdivide(depth):
                model.append(s)
        return model

    def reset_cache(self):
        self.minx = None
        self.miny = None
        self.minz = None
        self.maxx = None
        self.maxy = None
        self.maxz = None
        for item in self.next():
            self._update_limits(item)

    def transform_by_template(self, direction="normal"):
        if direction in TRANSFORMATIONS.keys():
            self.transform_by_matrix(TRANSFORMATIONS[direction])

    def shift(self, shift_x, shift_y, shift_z):
        matrix = ((1, 0, 0, shift_x), (0, 1, 0, shift_y), (0, 0, 1, shift_z))
        self.transform_by_matrix(matrix)
        
    def scale(self, scale_x, scale_y=None, scale_z=None):
        if scale_y is None:
            scale_y = scale_x
        if scale_z is None:
            scale_z = scale_x
        matrix = ((scale_x, 0, 0, 0), (0, scale_y, 0, 0), (0, 0, scale_z, 0))
        self.transform_by_matrix(matrix)

    def get_bounds(self):
        return Bounds(Bounds.TYPE_CUSTOM, (self.minx, self.miny, self.minz),
                (self.maxx, self.maxy, self.maxz))


class Model(BaseModel):

    def __init__(self, use_kdtree=True):
        super(Model, self).__init__()
        self._triangles = []
        self._item_groups.append(self._triangles)
        self._export_function = pycam.Exporters.STLExporter.STLExporter
        # marker for state of kdtree
        self._kdtree_dirty = True
        # enable/disable kdtree
        self._use_kdtree = use_kdtree
        self._t_kdtree = None

    def append(self, item):
        super(Model, self).append(item)
        if isinstance(item, Triangle):
            self._triangles.append(item)
            # we assume, that the kdtree needs to be rebuilt again
            self._kdtree_dirty = True

    def reset_cache(self):
        super(Model, self).reset_cache()
        # the triangle kdtree needs to be reset after transforming the model
        self._update_kdtree()

    def _update_kdtree(self):
        if self._use_kdtree:
            self._t_kdtree = TriangleKdtree(self.triangles())
        # the kdtree is up-to-date again
        self._kdtree_dirty = False

    def triangles(self, minx=-INFINITE, miny=-INFINITE, minz=-INFINITE,
            maxx=+INFINITE, maxy=+INFINITE, maxz=+INFINITE):
        if (minx == miny == minz == -INFINITE) \
                and (maxx == maxy == maxz == +INFINITE):
            return self._triangles
        if self._use_kdtree:
            # update the kdtree, if new triangles were added meanwhile
            if self._kdtree_dirty:
                self._update_kdtree()
            return self._t_kdtree.Search(minx, maxx, miny, maxy)
        return self._triangles


class ContourModel(BaseModel):

    def __init__(self):
        super(ContourModel, self).__init__()
        self.name = "contourmodel%d" % self.id
        self._line_groups = []
        self._item_groups.append(self._line_groups)
        self._cached_offset_models = {}

    def reset_cache(self):
        super(ContourModel, self).reset_cache()
        # reset the offset model cache
        self._cached_offset_models = {}

    def append(self, item):
        super(ContourModel, self).append(item)
        if isinstance(item, Line):
            for line_group in self._line_groups:
                if line_group.is_connectable(item):
                    line_group.append(item)
                    break
            else:
                # add a single line as part of a new group
                new_line_group = LineGroup()
                new_line_group.append(item)
                self._line_groups.append(new_line_group)
        elif isinstance(item, LineGroup):
            self._line_groups.append(item)
        else:
            # ignore any non-supported items
            pass

    def get_lines(self):
        return sum([group.get_lines() for group in self._line_groups], [])

    def get_line_groups(self):
        return self._line_groups

    def get_offset_model(self, offset, callback=None):
        """ calculate a contour model that surrounds the current model with
        a given offset.
        This is mainly useful for engravings that should not proceed _on_ the
        lines but besides these.
        @value offset: shifting distance; positive values enlarge the model
        @type offset: float
        @value callback: function to call after finishing a single line.
            It should return True if the user interrupted the operation.
        @type callback: callable
        @returns: the new shifted model
        @rtype: pycam.Geometry.Model.Model
        """
        # use a cached offset model if it exists
        if offset in self._cached_offset_models:
            return self._cached_offset_models[offset]
        result = ContourModel()
        for group in self._line_groups:
            new_group = group.get_offset_line_group(offset)
            if not new_group is None:
                result.append(new_group)
            if callback and callback():
                return None
        # cache the result
        self._cached_offset_models[offset] = result
        return result

    def check_for_collisions(self, callback=None):
        """ check if lines in different line groups of this model collide

        Returns a pycam.Geometry.Point.Point instance in case of an
        intersection.
        Returns None if the optional "callback" returns True (e.g. the user
        interrupted the operation).
        Otherwise it returns False if no intersections were found.
        """
        def check_bounds_of_groups(g1, g2):
            if (g1.minx <= g2.minx <= g1.maxx) \
                    or (g1.minx <= g2.maxx <= g1.maxx) \
                    or (g2.minx <= g1.minx <= g2.maxx) \
                    or (g2.minx <= g1.maxx <= g2.maxx):
                # the x boundaries overlap
                if (g1.miny <= g2.miny <= g1.maxy) \
                        or (g1.miny <= g2.maxy <= g1.maxy) \
                        or (g2.miny <= g1.miny <= g2.maxy) \
                        or (g2.miny <= g1.maxy <= g2.maxy):
                    # also the y boundaries overlap
                    if (g1.minz <= g2.minz <= g1.maxz) \
                            or (g1.minz <= g2.maxz <= g1.maxz) \
                            or (g2.minz <= g1.minz <= g2.maxz) \
                            or (g2.minz <= g1.maxz <= g2.maxz):
                        # z overlaps as well
                        return True
            return False
        # check each pair of line groups for intersections
        for index, group1 in enumerate(self._line_groups[:-1]):
            for group2 in self._line_groups[index+1:]:
                # check if both groups overlap - otherwise skip this pair
                if check_bounds_of_groups(group1, group2):
                    # check each pair of lines for intersections
                    for line1 in group1.next():
                        for line2 in group2.next():
                            intersection = line1.get_intersection(line2)
                            if intersection:
                                return intersection
            # update the progress visualization and quit if requested
            if callback and callback():
                return None
        return False

