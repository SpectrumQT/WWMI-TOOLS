from ..blender_interface.objects import *


def remove_all_vertex_groups(context, obj):
    if obj is None:
        return
    if obj.type != 'MESH':
        return
    for x in obj.vertex_groups:
        obj.vertex_groups.remove(x)


def remove_unused_vertex_groups(context, obj):
    # take from: https://blenderartists.org/t/batch-delete-vertex-groups-script/449881/23#:~:text=10%20MONTHS%20LATER-,AdenFlorian,-Jun%202021
    
    with OpenObject(context, obj) as obj:

        vgroup_used = {i: False for i, k in enumerate(obj.vertex_groups)}

        for v in obj.data.vertices:
            for g in v.groups:
                if g.weight > 0.0:
                    vgroup_used[g.group] = True
        
        for i, used in sorted(vgroup_used.items(), reverse=True):
            if not used:
                obj.vertex_groups.remove(obj.vertex_groups[i])


def fill_gaps_in_vertex_groups(context, obj):
    # Author: SilentNightSound#7430

    # Can change this to another number in order to generate missing groups up to that number
    # e.g. setting this to 130 will create 0,1,2...130 even if the active selected object only has 90
    # Otherwise, it will use the largest found group number and generate everything up to that number
    largest = 0

    with OpenObject(context, obj) as obj:

        for vg in obj.vertex_groups:
            try:
                if int(vg.name.split(".")[0])>largest:
                    largest = int(vg.name.split(".")[0])
            except ValueError:
                print(f"Vertex group {vg.name} not named as integer, skipping")

        missing = set([f"{i}" for i in range(largest+1)]) - set([x.name.split(".")[0] for x in obj.vertex_groups])

        for number in missing:
            obj.vertex_groups.new(name=f"{number}")

        bpy.ops.object.vertex_group_sort()
