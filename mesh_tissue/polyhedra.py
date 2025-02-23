# SPDX-FileCopyrightText: 2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

# ---------------------------- ADAPTIVE DUPLIFACES --------------------------- #
# ------------------------------- version 0.84 ------------------------------- #
#                                                                              #
# Creates duplicates of selected mesh to active morphing the shape according   #
# to target faces.                                                             #
#                                                                              #
#                    (c)  Alessandro Zomparelli                                #
#                             (2017)                                           #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
# ############################################################################ #


import bpy
from bpy.types import (
        Operator,
        Panel,
        PropertyGroup,
        )
from bpy.props import (
        BoolProperty,
        EnumProperty,
        FloatProperty,
        IntProperty,
        StringProperty,
        PointerProperty
        )
from mathutils import Vector, Quaternion, Matrix
import numpy as np
from math import *
import random, time, copy
import bmesh
from .utils import *

class polyhedra_wireframe(Operator):
    bl_idname = "object.polyhedra_wireframe"
    bl_label = "Tissue Polyhedra Wireframe"
    bl_description = "Generate wireframes around the faces.\
                      \nDoesn't works with boundary edges.\
                      \n(Experimental)"
    bl_options = {'REGISTER', 'UNDO'}

    thickness : FloatProperty(
        name="Thickness", default=0.1, min=0.001, soft_max=200,
        description="Wireframe thickness"
        )

    subdivisions : IntProperty(
        name="Segments", default=1, min=1, soft_max=10,
        description="Max sumber of segments, used for the longest edge"
        )

    #regular_sections : BoolProperty(
    #    name="Regular Sections", default=False,
    #    description="Turn inner loops into polygons"
    #    )

    dissolve_inners : BoolProperty(
        name="Dissolve Inners", default=False,
        description="Dissolve inner edges"
        )

    @classmethod
    def poll(cls, context):
        try:
            #bool_tessellated = context.object.tissue_tessellate.generator != None
            ob = context.object
            return ob.type == 'MESH' and ob.mode == 'OBJECT'# and bool_tessellated
        except:
            return False

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):

        merge_dist = self.thickness*0.001

        subs = self.subdivisions

        start_time = time.time()
        ob = context.object
        me = simple_to_mesh(ob)
        bm = bmesh.new()
        bm.from_mesh(me)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Subdivide edges
        proportional_subs = True
        if subs > 1 and proportional_subs:
            wire_length = [e.calc_length() for e in bm.edges]
            all_edges = list(bm.edges)
            max_segment = max(wire_length)/subs
            split_edges = [[] for i in range(subs+1)]
            for e, l in zip(all_edges, wire_length):
                split_edges[int(l//max_segment)].append(e)
            for i in range(2,subs):
                perc = {}
                for e in split_edges[i]:
                    perc[e]=0.1
                bmesh.ops.bisect_edges(bm, edges=split_edges[i], cuts=i, edge_percents=perc)

        ### Create double faces
        double_faces = []
        double_layer_edge = []
        double_layer_piece = []
        for f in bm.faces:
            verts0 = [v.co for v in f.verts]
            verts1 = [v.co for v in f.verts]
            verts1.reverse()
            double_faces.append(verts0)
            double_faces.append(verts1)

        # Create new bmesh object and data layers
        bm1 = bmesh.new()

        # Create faces and assign Edge Layers
        for verts in double_faces:
            new_verts = []
            for v in verts:
                vert = bm1.verts.new(v)
                new_verts.append(vert)
            bm1.faces.new(new_verts)

        bm1.verts.ensure_lookup_table()
        bm1.edges.ensure_lookup_table()
        bm1.faces.ensure_lookup_table()

        n_faces = len(bm.faces)
        n_doubles = len(bm1.faces)

        polyhedra = []

        for e in bm.edges:
            done = []

            # ERROR: Naked edges
            e_faces = len(e.link_faces)
            if e_faces < 2:
                bm.free()
                bm1.free()
                message = "Naked edges are not allowed"
                self.report({'ERROR'}, message)
                return {'CANCELLED'}

            edge_vec =  e.verts[1].co - e.verts[0].co

            # run first face
            for i1 in range(e_faces-1):
                f1 = e.link_faces[i1]
                #edge_verts1 = [v.index for v in f1.verts if v in e.verts]
                verts1 = [v.index for v in f1.verts]
                va1 = verts1.index(e.verts[0].index)
                vb1 = verts1.index(e.verts[1].index)
                # check if order of the edge matches the order of the face
                dir1 = va1 == (vb1+1)%len(verts1)
                edge_vec1 = edge_vec if dir1 else -edge_vec

                # run second face
                faces2 = []
                normals2 = []
                for i2 in range(i1+1,e_faces):
                #for i2 in range(n_faces):
                    if i1 == i2: continue
                    f2 = e.link_faces[i2]
                    f2.normal_update()
                    #edge_verts2 = [v.index for v in f2.verts if v in e.verts]
                    verts2 = [v.index for v in f2.verts]
                    va2 = verts2.index(e.verts[0].index)
                    vb2 = verts2.index(e.verts[1].index)
                    # check if order of the edge matches the order of the face
                    dir2 = va2 == (vb2+1)%len(verts2)
                    # check for normal consistency
                    if dir1 != dir2:
                        # add face
                        faces2.append(f2.index+1)
                        normals2.append(f2.normal)
                    else:
                        # add flipped face
                        faces2.append(-(f2.index+1))
                        normals2.append(-f2.normal)



                # find first polyhedra (positive)
                plane_x = f1.normal                     # normal
                plane_y = plane_x.cross(edge_vec1)      # tangent face perp edge
                id1 = (f1.index+1)

                min_angle0 = 10000

                # check consistent faces
                if id1 not in done:
                    id2 = None
                    min_angle = min_angle0
                    for i2, n2 in zip(faces2,normals2):
                        v2 = flatten_vector(-n2, plane_x, plane_y)
                        angle = vector_rotation(v2)
                        if angle < min_angle:
                            id2 = i2
                            min_angle = angle
                    if id2: done.append(id2)
                    new_poly = True
                    # add to existing polyhedron
                    for p in polyhedra:
                        if id1 in p or id2 in p:
                            new_poly = False
                            if id2 not in p: p.append(id2)
                            if id1 not in p: p.append(id1)
                            break
                    # start new polyhedron
                    if new_poly: polyhedra.append([id1, id2])

                # find second polyhedra (negative)
                plane_x = -f1.normal                    # normal
                plane_y = plane_x.cross(-edge_vec1)      # tangent face perp edge
                id1 = -(f1.index+1)

                if id1 not in done:
                    id2 = None
                    min_angle = min_angle0
                    for i2, n2 in zip(faces2, normals2):
                        v2 = flatten_vector(n2, plane_x, plane_y)
                        angle = vector_rotation(v2)
                        if angle < min_angle:
                            id2 = -i2
                            min_angle = angle
                    done.append(id2)
                    add = True
                    for p in polyhedra:
                        if id1 in p or id2 in p:
                            add = False
                            if id2 not in p: p.append(id2)
                            if id1 not in p: p.append(id1)
                            break
                    if add: polyhedra.append([id1, id2])

        for i in range(len(bm1.faces)):
            for j in (False,True):
                if j: id = i+1
                else: id = -(i+1)
                join = []
                keep = []
                for p in polyhedra:
                    if id in p: join += p
                    else: keep.append(p)
                if len(join) > 0:
                    keep.append(list(dict.fromkeys(join)))
                    polyhedra = keep

        for i, p in enumerate(polyhedra):
            for j in p:
                bm1.faces[j].material_index = i

        end_time = time.time()
        print('Tissue: Polyhedra wireframe, found {} polyhedra in {:.4f} sec'.format(len(polyhedra), end_time-start_time))


        delete_faces = []
        wireframe_faces = []
        not_wireframe_faces = []
        flat_faces = []

        bm.free()

        #bmesh.ops.bisect_edges(bm1, edges=bm1.edges, cuts=3)

        end_time = time.time()
        print('Tissue: Polyhedra wireframe, subdivide edges in {:.4f} sec'.format(end_time-start_time))

        bm1.faces.index_update()
        #merge_verts = []
        for p in polyhedra:
            delete_faces_poly = []
            wireframe_faces_poly = []
            faces_id = [(f-1)*2 if f > 0 else (-f-1)*2+1 for f in p]
            faces_id_neg = [(-f-1)*2 if -f > 0 else (f-1)*2+1 for f in p]
            merge_verts = []
            faces = [bm1.faces[f_id] for f_id in faces_id]
            for f in faces:
                delete = False
                if f.index in delete_faces: continue
                '''
                cen = f.calc_center_median()
                for e in f.edges:
                    mid = (e.verts[0].co + e.verts[1].co)/2
                    vec1 = e.verts[0].co - e.verts[1].co
                    vec2 = mid - cen
                    ang = Vector.angle(vec1,vec2)
                    length = vec2.length
                    #length = sin(ang)*length
                    if length < self.thickness/2:
                        delete = True
                '''
                if False:
                    sides = len(f.verts)
                    for i in range(sides):
                        v = f.verts[i].co
                        v0 = f.verts[(i-1)%sides].co
                        v1 = f.verts[(i+1)%sides].co
                        vec0 = v0 - v
                        vec1 = v1 - v
                        ang = (pi - vec0.angle(vec1))/2
                        length = min(vec0.length, vec1.length)*sin(ang)
                        if length < self.thickness/2:
                            delete = True
                            break

                if delete:
                    delete_faces_poly.append(f.index)
                else:
                    wireframe_faces_poly.append(f.index)
                merge_verts += [v for v in f.verts]
            if len(wireframe_faces_poly) < 2:
                delete_faces += faces_id
                not_wireframe_faces += faces_id_neg
            else:
                wireframe_faces += wireframe_faces_poly
                flat_faces += delete_faces_poly

            #wireframe_faces = list(dict.fromkeys(wireframe_faces))
            bmesh.ops.remove_doubles(bm1, verts=merge_verts, dist=merge_dist)
            bm1.edges.ensure_lookup_table()
            bm1.faces.ensure_lookup_table()
            bm1.faces.index_update()


        wireframe_faces = [i for i in wireframe_faces if i not in not_wireframe_faces]
        wireframe_faces = list(dict.fromkeys(wireframe_faces))

        flat_faces = list(dict.fromkeys(flat_faces))

        end_time = time.time()
        print('Tissue: Polyhedra wireframe, merge and delete in {:.4f} sec'.format(end_time-start_time))

        poly_me = me.copy()
        bm1.to_mesh(poly_me)
        poly_me.update()
        new_ob = bpy.data.objects.new("Polyhedra", poly_me)
        context.collection.objects.link(new_ob)

        ############# FRAME #############
        bm1.faces.index_update()
        wireframe_faces = [bm1.faces[i] for i in wireframe_faces]
        original_faces = wireframe_faces
        #bmesh.ops.remove_doubles(bm1, verts=merge_verts, dist=0.001)

        # detect edge loops

        loops = []
        boundaries_mat = []
        neigh_face_center = []
        face_normals = []

        # compute boundary frames
        new_faces = []
        wire_length = []
        vert_ids = []

        # append regular faces

        for f in original_faces:
            loop = list(f.verts)
            loops.append(loop)
            boundaries_mat.append([f.material_index for v in loop])
            f.normal_update()
            face_normals.append([f.normal for v in loop])

        push_verts = []
        inner_loops = []

        for loop_index, loop in enumerate(loops):
            is_boundary = loop_index < len(neigh_face_center)
            materials = boundaries_mat[loop_index]
            new_loop = []
            loop_ext = [loop[-1]] + loop + [loop[0]]

            # calc tangents
            tangents = []
            for i in range(len(loop)):
                # vertices
                vert0 = loop_ext[i]
                vert = loop_ext[i+1]
                vert1 = loop_ext[i+2]
                # edge vectors
                vec0 = (vert0.co - vert.co).normalized()
                vec1 = (vert.co - vert1.co).normalized()
                # tangent
                _vec1 = -vec1
                _vec0 = -vec0
                ang = (pi - vec0.angle(vec1))/2
                normal = face_normals[loop_index][i]
                tan0 = normal.cross(vec0)
                tan1 = normal.cross(vec1)
                tangent = (tan0 + tan1).normalized()/sin(ang)*self.thickness/2
                tangents.append(tangent)

            # calc correct direction for boundaries
            mult = -1
            if is_boundary:
                dir_val = 0
                for i in range(len(loop)):
                    surf_point = neigh_face_center[loop_index][i]
                    tangent = tangents[i]
                    vert = loop_ext[i+1]
                    dir_val += tangent.dot(vert.co - surf_point)
                if dir_val > 0: mult = 1

            # add vertices
            for i in range(len(loop)):
                vert = loop_ext[i+1]
                area = 1
                new_co = vert.co + tangents[i] * mult * area
                # add vertex
                new_vert = bm1.verts.new(new_co)
                new_loop.append(new_vert)
                vert_ids.append(vert.index)
            new_loop.append(new_loop[0])

            # add faces
            #materials += [materials[0]]
            for i in range(len(loop)):
                v0 = loop_ext[i+1]
                v1 = loop_ext[i+2]
                v2 = new_loop[i+1]
                v3 = new_loop[i]
                face_verts = [v1,v0,v3,v2]
                if mult == -1: face_verts = [v0,v1,v2,v3]
                new_face = bm1.faces.new(face_verts)
                # Material by original edges
                piece_id = 0
                new_face.select = True
                new_faces.append(new_face)
                wire_length.append((v0.co - v1.co).length)
            max_segment = max(wire_length)/self.subdivisions
            #for f,l in zip(new_faces,wire_length):
            #    f.material_index = min(int(l/max_segment), self.subdivisions-1)
            bm1.verts.ensure_lookup_table()
            push_verts += [v.index for v in loop_ext]

        # At this point topology han been build, but not yet thickened

        end_time = time.time()
        print('Tissue: Polyhedra wireframe, frames in {:.4f} sec'.format(end_time-start_time))

        bm1.verts.ensure_lookup_table()
        bm1.edges.ensure_lookup_table()
        bm1.faces.ensure_lookup_table()
        bm1.verts.index_update()

        ### Displace vertices ###

        circle_center = [0]*len(bm1.verts)
        circle_normal = [0]*len(bm1.verts)

        smooth_corners = [True] * len(bm1.verts)
        corners = [[] for i in range(len(bm1.verts))]
        normals = [0]*len(bm1.verts)
        vertices = [0]*len(bm1.verts)
        # Define vectors direction
        for f in new_faces:
            v0 = f.verts[0]
            v1 = f.verts[1]
            id = v0.index
            corners[id].append((v1.co - v0.co).normalized())
            normals[id] = v0.normal.copy()
            vertices[id] = v0
            smooth_corners[id] = False
        # Displace vertices
        for i, vecs in enumerate(corners):
            if len(vecs) > 0:
                v = vertices[i]
                nor = normals[i]
                ang = 0
                for vec in vecs:
                    ang += nor.angle(vec)
                ang /= len(vecs)
                div = sin(ang)
                if div == 0: div = 1
                v.co += nor*self.thickness/2/div

        end_time = time.time()
        print('Tissue: Polyhedra wireframe, corners displace in {:.4f} sec'.format(end_time-start_time))

        # Removing original flat faces

        flat_faces = [bm1.faces[i] for i in flat_faces]
        for f in flat_faces:
            f.material_index = self.subdivisions+1
            for v in f.verts:
                if smooth_corners[v.index]:
                    v.co += v.normal*self.thickness/2
                    smooth_corners[v.index] = False
        delete_faces = delete_faces + [f.index for f in original_faces]
        delete_faces = list(dict.fromkeys(delete_faces))
        delete_faces = [bm1.faces[i] for i in delete_faces]
        bmesh.ops.delete(bm1, geom=delete_faces, context='FACES')

        bmesh.ops.remove_doubles(bm1, verts=bm1.verts, dist=merge_dist)
        bm1.faces.ensure_lookup_table()
        bm1.edges.ensure_lookup_table()
        bm1.verts.ensure_lookup_table()

        if self.dissolve_inners:
            bm1.edges.index_update()
            dissolve_edges = []
            for f in bm1.faces:
                e = f.edges[2]
                if e not in dissolve_edges:
                    dissolve_edges.append(e)
            bmesh.ops.dissolve_edges(bm1, edges=dissolve_edges, use_verts=True, use_face_split=True)

        all_lines = [[] for e in me.edges]
        all_end_points = [[] for e in me.edges]
        for v in bm1.verts: v.select_set(False)
        for f in bm1.faces: f.select_set(False)

        _me = me.copy()
        bm1.to_mesh(me)
        me.update()
        new_ob = bpy.data.objects.new("Wireframe", me)
        context.collection.objects.link(new_ob)
        for o in context.scene.objects: o.select_set(False)
        new_ob.select_set(True)
        context.view_layer.objects.active = new_ob
        me = _me

        bm1.free()
        bpy.data.meshes.remove(_me)
        #new_ob.location = ob.location
        new_ob.matrix_world = ob.matrix_world

        end_time = time.time()
        print('Tissue: Polyhedra wireframe in {:.4f} sec'.format(end_time-start_time))
        return {'FINISHED'}
