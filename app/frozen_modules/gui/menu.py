import lvgl as lv

def scroll_flex_label(parent, text):
    label = lv.label(parent)
    label.set_text(text)
    label.set_long_mode(lv.label.LONG_MODE.SCROLL_CIRCULAR)
    label.set_flex_grow(True)

class Menu:
    def __init__(self, menu_tree, parent=None):
        if not parent:
            parent = lv.screen_active()

        self.menu = lv.menu(parent)
        bg_color = self.menu.get_style_bg_color(0)
        if bg_color.brightness() > 127:
            self.menu.set_style_bg_color(bg_color.darken(15), 0)
        else:
            self.menu.set_style_bg_color(bg_color.darken(50), 0)
        self.menu.set_size(parent.get_width(), parent.get_height())
        self.menu.center()

        self.sidebar = lv.menu_page(self.menu, None)
        self.sidebar.set_style_pad_hor(
            self.menu.get_main_header().get_style_pad_left(0), 0
        )
        self.menu.set_sidebar_page(self.sidebar)

        first_section_cont = None
        for category in menu_tree:
            sidebar_cont = lv.menu_cont(self.sidebar)
            scroll_flex_label(sidebar_cont, category["name"])
            sidebar_section = lv.menu_section(self.sidebar)
            category_first_section_cont = self.create_pages(category["pages"], section=sidebar_section)
            if not first_section_cont and category_first_section_cont:
                first_section_cont = category_first_section_cont
        if first_section_cont:
            first_section_cont.send_event(lv.EVENT.CLICKED, None)

    def create_pages(self, pages, section, top_level=True):
        first_section_cont = None
        for page in pages:
            section_cont = lv.menu_cont(section)
            scroll_flex_label(section_cont, page["name"])
            if "icon" in page :
                lv.image(section_cont).set_src(page["icon"])
            # make clickable
            lv.group_get_default().add_obj(section_cont)

            menu_page = lv.menu_page(self.menu, None)
            menu_page.set_style_pad_hor(self.menu.get_main_header().get_style_pad_left(0), 0)
            if top_level:
                lv.menu_separator(menu_page)
            
            if "pages" in page:
                page_section = lv.menu_section(menu_page)
                # recurse throug sub pages
                self.create_pages(page["pages"], section=page_section, top_level=False)
            elif "class" in page:
                page["class"](menu_page)

            self.menu.set_load_page_event(section_cont, menu_page)
            if first_section_cont == None:
                first_section_cont = section_cont
        return first_section_cont
