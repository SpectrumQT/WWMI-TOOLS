
import bpy


def get_collection(col_name):
    return bpy.data.collections[col_name]


def get_layer_collection(col, layer_col=None):
    col_name = assert_collection(col).name
    if layer_col is None:
        #        layer_col = bpy.context.scene.collection
        layer_col = bpy.context.view_layer.layer_collection
    if layer_col.name == col_name:
        return layer_col
    for sublayer_col in layer_col.children:
        col = get_layer_collection(col_name, layer_col=sublayer_col)
        if col:
            return col


def collection_exists(col_name):
    return col_name in bpy.data.collections.keys()


def assert_collection(col):
    if isinstance(col, str):
        col = get_collection(col)
    elif col not in bpy.data.collections.values():
        raise ValueError('Not of collection type: %s' % str(col))
    return col


def get_collection_objects(col):
    col = assert_collection(col)
    return col.objects


def link_collection(col, col_parent):
    col = assert_collection(col)
    col_parent = assert_collection(col_parent)
    col_parent.children.link(col)


def new_collection(col_name, col_parent=None, allow_duplicate=True):
    if not allow_duplicate:
        try:
            col = get_collection(col_name)
            if col is not None:
                raise ValueError('Collection already exists: %s' % str(col_name))
        except Exception as e:
            pass
    new_col = bpy.data.collections.new(col_name)
    if col_parent:
        link_collection(new_col, col_parent)
    else:
        bpy.context.scene.collection.children.link(new_col)
    #    bpy.context.view_layer.layer_collection.children[col_name] = new_col
    #    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[-1]
    #    bpy.context.scene.collection.children.link(new_col)
    return new_col


def hide_collection(col):
    col = assert_collection(col)
    #    col.hide_viewport = True
    #    for k, v in bpy.context.view_layer.layer_collection.children.items():
    #        print(k, " ", v)
    #    bpy.context.view_layer.layer_collection.children.get(col.name).hide_viewport = True
    get_layer_collection(col).hide_viewport = True


def unhide_collection(col):
    col = assert_collection(col)
    #    col.hide_viewport = False
    #    bpy.context.view_layer.layer_collection.children.get(col.name).hide_viewport = False
    get_layer_collection(col).hide_viewport = False


def collection_is_hidden(col):
    col = assert_collection(col)
    return get_layer_collection(col).hide_viewport


def get_scene_collections():
    return bpy.context.scene.collection.children
