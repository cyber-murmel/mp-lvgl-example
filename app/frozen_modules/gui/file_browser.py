import lvgl as lv
import os

class FileBrowser:
    def __init__(self):
        self.quick_access = None
        self.path_label = None
        self.table = None
        self.path = ""
        self.last_row = 0

    @staticmethod
    def _path_join(base, name):
        """Join `base` and `name`, inserting a single separator as needed."""
        if base.endswith("/"):
            return base + name
        return base + "/" + name

    @staticmethod
    def _is_dir(path):
        try:
            # S_IFDIR == 0x4000
            return (os.stat(path)[0] & 0x4000) != 0
        except OSError:
            return False

    def open(self, path):
        """List the entries of `path` into the table. Does nothing if `path`
        is not a readable directory, so a failed navigation simply leaves the
        view unchanged."""
        try:
            entries = os.listdir(path)
        except OSError:
            return

        self.path = path
        self.path_label.set_text(path)

        self.table.set_row_count(0)

        # First row goes up to the parent directory
        row = 0
        self.table.set_cell_value(row, 0, lv.SYMBOL.LEFT)
        self.table.set_cell_value(row, 1, "..")
        row += 1

        # Directories first, then files; each group sorted by name
        entries.sort()
        dirs = []
        files = []
        for name in entries:
            if self._is_dir(self._path_join(path, name)):
                dirs.append(name)
            else:
                files.append(name)

        for name in dirs:
            self.table.set_cell_value(row, 0, lv.SYMBOL.DIRECTORY)
            self.table.set_cell_value(row, 1, name)
            row += 1
        for name in files:
            self.table.set_cell_value(row, 0, lv.SYMBOL.FILE)
            self.table.set_cell_value(row, 1, name)
            row += 1

    def up(self):
        """Navigate to the parent directory by dropping the last component."""
        buf = self.path
        if len(buf) > 1 and buf.endswith("/"):
            buf = buf[:-1]  # drop a trailing slash

        idx = buf.rfind("/")
        if idx < 0:
            return          # already at the drive root
        parent = buf[:idx + 1]  # keep the slash, cut the last component
        self.open(parent)

    def _table_event(self, e):
        row = lv.C_Pointer()
        col = lv.C_Pointer()
        self.table.get_selected_cell(row, col)
        row = row.uint_val
        col = col.uint_val

        if row == 0xFFFF or col == 0xFFFF:
            return

        code = e.get_code()

        if code in (lv.EVENT.KEY, lv.EVENT.VALUE_CHANGED) and col == 0:
            # detect going up by the movement stayin in the same row,
            # since the selectable cells are in the right column
            if row == self.last_row and row > 0:
                row = row - 1

            self.last_row = row
            self.table.set_selected_cell(row, 1)
            return
        if code == lv.EVENT.CLICKED:
            icon = self.table.get_cell_value(row, 0)
            name = self.table.get_cell_value(row, 1)
            if name == "..":
                self.up()
                return
            child = self._path_join(self.path, name)
            # Only folders can be opened; clicking a file just logs it
            if icon != lv.SYMBOL.DIRECTORY:
                print("Selected file:", child)
                return
            self.open(child)
            self.table.set_selected_cell(0, 1)

    def build(self, parent):
        parent.set_flex_grow(1)
        parent.set_flex_flow(lv.FLEX_FLOW.COLUMN)

        self.path_label = lv.label(parent)
        self.path_label.set_width(lv.pct(100))
        self.path_label.set_long_mode(lv.label.LONG_MODE.DOTS)

        self.table = lv.table(parent)
        self.table.set_width(lv.pct(100))
        self.table.set_flex_grow(1)
        # Tighten the cell padding; the theme default is large enough to clip the icon
        self.table.set_style_pad_hor(6, lv.PART.ITEMS)
        self.table.set_style_pad_ver(8, lv.PART.ITEMS)

        # Icon column fits a symbol; name column fills the rest of the browser area
        icon_col = 30
        # name_col = self.table.get_width() - icon_col - 16
        self.table.set_column_count(2)
        self.table.set_column_width(0, icon_col)
        # self.table.set_column_width(1, name_col)

        self.table.add_event_cb(self._table_event, lv.EVENT.VALUE_CHANGED, None)
        self.table.add_event_cb(self._table_event, lv.EVENT.CLICKED, None)
        self.table.add_event_cb(self._table_event, lv.EVENT.KEY, None)

        self.open("/")

def file_browser(parent=None):
    """File browser built from a table.

    A grey quick-access sidebar holds DEVICE/PLACES shortcuts; the white
    browser area shows the current path over an `lv.table` filled from a
    directory read with the `os` module. Clicking a folder row opens the child
    directory, the ".." row walks back up, and the sidebar shortcuts jump
    straight to a path.
    """
    if not parent:
        parent = lv.screen_active()
    browser = FileBrowser()
    browser.build(parent)
    # Keep a reference alive so the event callbacks are not garbage-collected.
    return browser
