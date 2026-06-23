import bpy


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def set_scene_defaults():
    scene = bpy.context.scene
    scene.MPFB_NH_add_phenotype = True
    scene.MPFB_NH_phenotype_gender = "male"
    scene.MPFB_NH_phenotype_age = "young"
    scene.MPFB_NH_phenotype_muscle = "maxmuscle"
    scene.MPFB_NH_phenotype_weight = "averageweight"
    scene.MPFB_NH_phenotype_height = "maxheight"
    scene.MPFB_NH_phenotype_proportions = "max"
    scene.MPFB_NH_phenotype_race = "caucasian"
    scene.MPFB_NH_phenotype_influence = 0.85
    scene.MPFB_NH_scale_factor = "METER"
    scene.MPFB_NH_mask_helpers = True
    scene.MPFB_NH_detailed_helpers = False
    scene.MPFB_NH_extra_vertex_groups = True

    scene.MPFB_ADR_standard_rig = "mixamo"
    scene.MPFB_ADR_import_weights = True


def main():
    clear_scene()
    set_scene_defaults()
    print("CREATE_HUMAN_START")
    result = bpy.ops.mpfb.create_human()
    print("CREATE_HUMAN_RESULT", result)
    basemesh = bpy.context.active_object
    print("ACTIVE_AFTER_CREATE", basemesh.name, basemesh.type)

    result = bpy.ops.mpfb.add_standard_rig()
    print("ADD_RIG_RESULT", result)

    objects = list(bpy.data.objects)
    print("OBJECT_COUNT", len(objects))
    for obj in objects:
        print("OBJECT", obj.name, obj.type, "parent=", obj.parent.name if obj.parent else "")

    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    print("ARMATURE_COUNT", len(armatures))
    for arm in armatures:
        print("ARMATURE", arm.name)
        for bone in arm.data.bones[:80]:
            print("BONE", bone.name)


if __name__ == "__main__":
    main()
