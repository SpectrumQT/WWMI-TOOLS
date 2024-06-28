from dataclasses import dataclass

import bpy
import bmesh

from .collections import assert_collection, unhide_collection


def assert_object(obj):
    if isinstance(obj, str):
        obj = get_object(obj)
    elif obj not in bpy.data.objects.values():
        raise ValueError('Not of object type: %s' % str(obj))
    return obj


def get_mode(context):
    if context.active_object:
        return context.active_object.mode


def set_mode(context, mode):
    active_object = get_active_object(context)
    if active_object is not None and mode is not None:
        if not object_is_hidden(active_object):
            bpy.ops.object.mode_set(mode=mode)


@dataclass
class UserContext:
    active_object: bpy.types.Object
    selected_objects: bpy.types.Object
    mode: str


def get_user_context(context):
    return UserContext(
        active_object = get_active_object(context),
        selected_objects = get_selected_objects(context),
        mode = get_mode(context),
    )


def set_user_context(context, user_context):
    deselect_all_objects()
    for object in user_context.selected_objects:
        try:
            select_object(object)
        except ReferenceError as e:
            pass
    if user_context.active_object:
        set_active_object(context, user_context.active_object)
        set_mode(context, user_context.mode)


def get_object(obj_name):
    return bpy.data.objects[obj_name]
        

def get_active_object(context):
    return context.view_layer.objects.active


def get_selected_objects(context):
    return context.selected_objects


def link_object_to_scene(context, obj):
    context.scene.collection.objects.link(obj)


def unlink_object_from_scene(context, obj):
    context.scene.collection.objects.unlink(obj)


def object_exists(obj_name):
    return obj_name in bpy.data.objects.keys()


def link_object_to_collection(obj, col):
    obj = assert_object(obj)
    col = assert_collection(col)
    col.objects.link(obj)


def unlink_object_from_collection(obj, col):
    obj = assert_object(obj)
    col = assert_collection(col)
    col.objects.unlink(obj) 


def rename_object(obj, obj_name):
    obj = assert_object(obj)
    obj.name = obj_name
    

def select_object(obj):
    obj = assert_object(obj)
    obj.select_set(True)


def deselect_object(obj):
    obj = assert_object(obj)
    obj.select_set(False)


def deselect_all_objects():
    for obj in bpy.context.selected_objects:
        deselect_object(obj)
    bpy.context.view_layer.objects.active = None


def object_is_selected(obj):
    return obj.select_get()


def set_active_object(context, obj):
    obj = assert_object(obj)
    context.view_layer.objects.active = obj


def object_is_hidden(obj):
    return obj.hide_get()


def hide_object(obj):
    obj = assert_object(obj)
    obj.hide_set(True)


def unhide_object(obj):
    obj = assert_object(obj)
    obj.hide_set(False)


def set_custom_property(obj, property, value):
    obj = assert_object(obj)
    obj[property] = value


def remove_object(obj):
    obj = assert_object(obj)
    bpy.data.objects.remove(obj, do_unlink=True)


def get_modifiers(obj):
    obj = assert_object(obj)
    return obj.modifiers


class OpenObject:
    def __init__(self, context, obj, mode='OBJECT'):
        self.mode = mode
        self.object = assert_object(obj)
        self.context = context
        self.user_context = get_user_context(context)
        self.was_hidden = object_is_hidden(self.object)

    def __enter__(self):
        deselect_all_objects()

        unhide_object(self.object)
        select_object(self.object)
        set_active_object(bpy.context, self.object)

        if self.object.mode == 'EDIT':
            self.object.update_from_editmode()

        set_mode(self.context, mode=self.mode)

        return self.object

    def __exit__(self, *args):
        if self.was_hidden:
            hide_object(self.object)
        else:
            unhide_object(self.object)
        set_user_context(self.context, self.user_context)


def copy_object(context, obj, name=None, collection=None):
    with OpenObject(context, obj, mode='OBJECT') as obj:
        new_obj = obj.copy()
        new_obj.data = obj.data.copy()
        if name:
            rename_object(new_obj, name)
        if collection:
            link_object_to_collection(new_obj, collection)
        return new_obj


def assert_vertex_group(obj, vertex_group):
    obj = assert_object(obj)
    if isinstance(vertex_group, bpy.types.VertexGroup):
        vertex_group = vertex_group.name
    return obj.vertex_groups[vertex_group]


def get_vertex_groups(obj):
    obj = assert_object(obj)
    return obj.vertex_groups


def remove_vertex_groups(obj, vertex_groups):
    obj = assert_object(obj)
    for vertex_group in vertex_groups:
        obj.vertex_groups.remove(assert_vertex_group(obj, vertex_group))


def normalize_all_weights(context, obj):
    with OpenObject(context, obj, mode='WEIGHT_PAINT') as obj:
        bpy.ops.object.vertex_group_normalize_all()


def triangulate_object(context, obj):
    with OpenObject(context, obj, mode='OBJECT') as obj:
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()


class OpenObjects:
    def __init__(self, context, objects, mode='OBJECT'):
        self.mode = mode
        self.objects = [assert_object(obj) for obj in objects]
        self.context = context
        self.user_context = get_user_context(context)

    def __enter__(self):

        deselect_all_objects()
        
        for obj in self.objects:
            unhide_object(obj)
            select_object(obj)
            if obj.mode == 'EDIT':
                obj.update_from_editmode()
            
        set_active_object(bpy.context, self.objects[0])

        set_mode(self.context, mode=self.mode)

        return self.objects

    def __exit__(self, *args):
        set_user_context(self.context, self.user_context)


def join_objects(context, objects):
    if len(objects) == 1:
        return
    with OpenObject(context, objects[0], mode='OBJECT'):
        for obj in objects[1:]:
            select_object(obj)  
            bpy.ops.object.join()
