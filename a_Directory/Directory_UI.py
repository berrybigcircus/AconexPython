from logging import Logger

from Setup.Project import getProjectsList
from Setup.config import createlogger #temp use of logger
import customtkinter as ctk
from PIL import Image

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.logger : Logger = createlogger()

        self.title("Project Invite")
        self.geometry("720x480")

        self.INPUT_COLOURSMAP = {"default" : '#DCE4EE',
                              "duplicate" : ['SteelBlue2', 'gold', 'sienna1', 'OliveDrab1', 'MediumPurple1', 'dark khaki'],
                              "disabled" : 'DimGrey'}

        self.frame_topbuttons = TopButtonsFrame(self)
        self.frame_topbuttons.grid(row=0, column=0, padx=10, pady=10, sticky="new")

        self.frame_searchclearrow = SearchClearFrame(self)
        self.frame_searchclearrow.grid(row=1, column=0, padx=10, pady=10, sticky="new")

        projects_dict: dict[str, list] = getProjectsList()
        project_values : list[str] = self.get_project_values(projects_dict)

        self.frame_tablerows = ctk.CTkScrollableFrame(self, height=30, width=680)
        self.frame_tablerows.grid(row=2, column=0, padx=10, pady=10, sticky="new")
        self.frame_tablerows.grid_columnconfigure(0, weight=1)

        INIT_ROWS : int = 7
        self.rows : set[RowFrame] = set()

        self.duplicaterows : dict = {
            "Company Name" : {},
            "Full Name": {},
            "Email Address": {},
            "Project": {}
        }
        self.duplicate_colours : dict = {
            "Company Name" : {},
            "Project": {}
        }

        self.next_colour_index = 0

        for i in range(0, INIT_ROWS):
            self.add_row(project_values)

        image_plus = ctk.CTkImage(dark_image=Image.open("a_Directory/GUI_files/plus.png"), size=(20,20))
        self.button_add = ctk.CTkButton(self, image=image_plus, text="", width=20, height=20, fg_color="gray30",
                                        command=lambda: self.add_row(project_values))

        self.button_add.grid(row=3,column=0,padx=10, pady=10, sticky="ws")


    def get_project_values(self, projects_dict) -> list[str]:
        # get just the project names
        return [name for name, code in projects_dict.values()][::-1]

    #Add a new row when + is clicked
    def add_row(self, project_values : list[str]):
        self.logger.debug("Adding row")
        self.frame_newrow = RowFrame(self.frame_tablerows, app=self, project_vals=project_values)
        self.frame_newrow.grid(row=len(self.rows), column=0, padx=10, sticky="sew")
        self.rows.add(self.frame_newrow)

    def get_colour(self, duplicate_type : str, value):
        duplicate_colours = self.duplicate_colours[duplicate_type]
        if value not in duplicate_colours:
            colours = self.INPUT_COLOURSMAP["duplicate"]
            colour = colours[self.next_colour_index % len(colours)]
            self.duplicate_colours[duplicate_type][value] = colour
            self.next_colour_index += 1

        return duplicate_colours[value]

    def check_for_duplicates(self, duplicate_type, current_row : RowFrame):
        COLUMN_MAP = {
            "Full Name": {
                "text": lambda r: r.entry_usertext.get().strip(),
                "default_text": lambda r: r.default_usertext,
                "handle_duplicate": lambda r, b: r.duplicate_user(b)
            },
            "Email Address": {
                "text": lambda r: r.entry_emailtext.get().strip(),
                "default_text": lambda r: r.default_emailtext,
                "handle_duplicate": lambda r, b: r.duplicate_user(b)
            },
            "Company Name": {
                "text": lambda r: r.entry_companytext.get().strip(),
                "default_text": lambda r: r.default_companytext,
                "handle_duplicate": lambda r, b: r.duplicate_company(b)
            },
            "Project": {
                "text": lambda r: r.combo_project.get().strip(),
                "default_text" : lambda r: "Project",
                "handle_duplicate": lambda r, b: r.duplicate_project(b)
            }
        }
        COLOUR_TYPES = ["Company Name", "Project"]
        text_get = COLUMN_MAP[duplicate_type]["text"]
        handle_duplicate = COLUMN_MAP[duplicate_type]["handle_duplicate"]
        default_text = COLUMN_MAP[duplicate_type]["default_text"]

        col_default_text = default_text(current_row)

        duplicate_sets: dict[RowFrame, set[RowFrame]] = {}

        for row in self.rows:
            row_text = text_get(row)
            if duplicate_type in COLOUR_TYPES:
                colour = ""
            else:
                colour = False

            handle_duplicate(row, colour)

            if not row_text or row_text == col_default_text:
                continue

            duplicate_sets.setdefault(row_text, set()).add(row)

        self.duplicaterows[duplicate_type] = {value: rows for value, rows in duplicate_sets.items() if len(rows) > 1}

        #Add colour mapping
        for value, rows in self.duplicaterows[duplicate_type].items():
            if duplicate_type in COLOUR_TYPES:
                colour = self.get_colour(duplicate_type, value)
            else:
                colour = True

            for row in rows:
                handle_duplicate(row, colour)

        self.check_output(self.duplicaterows[duplicate_type])


    def check_output(self, duplicate_rows):
        print("Duplicate rows:")
        for i, duplicate_dict in enumerate(duplicate_rows.values()):
            print("Set %d : %s" % (i, [r.id for r in duplicate_dict]))


class SearchClearFrame(ctk.CTkFrame):
    def __init__(self, master=None):
        super().__init__(master)
        self.button_clear = ctk.CTkButton(self, text="Clear all", command=None)
        self.button_clear.grid(row=0, column=0, padx=10, pady=10, sticky="ws")

        self.tb_log = ctk.CTkTextbox(self, height=80)
        self.tb_log.grid(row=0, column=1, sticky="ew")
        self.grid_columnconfigure(1, weight=1)

        self.button_search = ctk.CTkButton(self, text="Search", command=None)
        self.button_search.grid(row=0, column=2, padx=10, pady=10, sticky="es")

class TopButtonsFrame(ctk.CTkFrame):
    def __init__(self, master=None):
        super().__init__(master)

        self.button_all = ctk.CTkButton(self, text="Add to 'all'", command=None)
        self.button_all.grid(row=0, column=0, padx=10, pady=10)

        self.button_mg = ctk.CTkButton(self, text="Add to company MG", command=None)
        self.button_mg.grid(row=0, column=1, padx=10, pady=10)

        self.button_transmittal = ctk.CTkButton(self, text="Draft transmittal", command=None)
        self.button_transmittal.grid(row=0, column=2, padx=10, pady=10)

        self.button_invite = ctk.CTkButton(self, text="Draft project invite", command=None)
        self.button_invite.grid(row=0, column=3, padx=10, pady=10)

class RowFrame(ctk.CTkFrame):
    __nextID = 1
    def __init__(self, master=None, app=None, project_vals : list[str]=None):
        super().__init__(master)
        self.app = app
        self.id = RowFrame.__nextID
        RowFrame.__nextID += 1

        for col in range(5):
            self.grid_columnconfigure(col, weight=0)

        self.default_usertext : str = "Full Name"
        self.default_emailtext : str = "Email Address"
        self.default_companytext : str = "Company Name"

        self.entry_usertext = ctk.StringVar(self, self.default_usertext)
        self.entry_user = ctk.CTkEntry(self, width=120, placeholder_text=self.entry_usertext.get(), textvariable=self.entry_usertext)
        self.entry_user.grid(row=0, column=0, sticky="n")
        self.entry_user.bind("<FocusOut>", lambda event: self.on_deselect(self.default_usertext))

        self.entry_emailtext = ctk.StringVar(self, self.default_emailtext)
        self.entry_email = ctk.CTkEntry(self, width=180, placeholder_text=self.entry_emailtext.get(), textvariable=self.entry_emailtext)
        self.entry_email.grid(row=0, column=1, sticky="n")
        self.entry_email.bind("<FocusOut>", lambda event: self.on_deselect(self.default_emailtext))

        self.combo_project = ctk.CTkComboBox(self, width=160, values=project_vals, command=lambda event: self.on_deselect("Project"))
        self.combo_project.grid(row=0, column=2, sticky="n")
        self.on_deselect("Project") #run once to make all project selectors same colour

        self.entry_companytext = ctk.StringVar(self, self.default_companytext)
        self.entry_company = ctk.CTkEntry(self, width=160, placeholder_text=self.entry_companytext.get(), textvariable=self.entry_companytext)
        self.entry_company.grid(row=0, column=3, sticky="n")
        self.entry_company.bind("<FocusOut>", lambda event: self.on_deselect(self.default_companytext))

        check_var = ctk.StringVar(value="on")
        self.cb_select = ctk.CTkCheckBox(self, text="", variable=check_var, width=10, command=None)
        self.cb_select.configure(state="disabled")
        self.cb_select.grid(row=0, column=4, padx=(10,0), sticky="ne")

    def on_deselect(self, duplicate_type : str):
        self.app.check_for_duplicates(duplicate_type, self)

    def duplicate_company(self, colour: str = ""):
        if colour:
            self.app.logger.info("Duplicate companies found")
            self.entry_company.configure(text_color=colour)

        else:
            self.entry_company.configure(text_color=self.app.INPUT_COLOURSMAP["default"])

    def duplicate_project(self, colour: str = ""):
        if colour:
            self.app.logger.info("Duplicate projects found")
            self.combo_project.configure(text_color=colour)

        else:
            self.combo_project.configure(text_color=self.app.INPUT_COLOURSMAP["default"])

    def duplicate_user(self, duplicate: bool = False):
        if duplicate:
            self.app.logger.info("Duplicate users found")

def main():
    app = App()
    app.mainloop()