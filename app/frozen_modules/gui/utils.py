import lvgl as lv

def init_indevs():
    g = lv.group_create()
    g.set_default()
    dev = lv.indev_create()
    while dev:
        # print(dev.get_type())
        if dev.get_type() == lv.INDEV_TYPE.ENCODER:
            dev.set_group(g)
        dev = dev.get_next()
