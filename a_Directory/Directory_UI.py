import datetime
import re
from logging import Logger, Handler, Formatter, INFO

from Setup.APIcommon import et_findtagtext
from Setup.Project import getProjectsList
from Setup.config import createlogger, config  # temp use of logger
from Setup.Outlook import WrapperConfig
import customtkinter as ctk
from PIL import Image
from a_Directory.Directory import search_on_email, project_directory_search, search_on_name, global_directory_search, \
    api_project_directory_search, loadcsv

import xml.etree.ElementTree as ET

DEBUG : bool = False

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.logger : Logger = createlogger() #TODO this may need to change once config is added

        self.title("Project Invite")
        self.geometry("780x470")

        self.INPUT_COLOURSMAP = {"default" : '#DCE4EE',
                              "duplicate" : ['SteelBlue2', 'gold', 'sienna1', 'OliveDrab1', 'MediumPurple1', 'dark khaki'],
                              "disabled" : 'DimGrey',
                                'IDLE' : '#343638',
                                "INVALID": 'grey28',
                                 'GREEN': 'DarkGreen',
                                 'RED': 'DarkRed',
                                 'PURPLE': 'DarkOrchid4'}

        self.frame_topbuttons = TopButtonsFrame(self)
        self.frame_topbuttons.grid(row=0, column=0, padx=10, pady=10, sticky="new")

        self.frame_searchclearrow = SearchClearFrame(self, app=self)
        self.frame_searchclearrow.grid(row=1, column=0, padx=10, pady=10, sticky="new")

        self.frame_tablerows = ctk.CTkScrollableFrame(self, height=30, width=740)
        self.frame_tablerows.grid(row=2, column=0, padx=10, pady=10, sticky="new")
        self.frame_tablerows.grid_columnconfigure(0, weight=1)
        self.frame_tablerows.grid_rowconfigure(2, weight=1)

        self.rows: set[RowFrame] = set()
        self.projects_dict: dict[str, tuple[str, str]] = self.get_project_values(getProjectsList()) #in format name: (pid, code)
        self.project_values: list[str] = list(self.projects_dict.keys())[::-1]

        self.csvOrgAdmins : dict[str, tuple[str, str, datetime.datetime]]

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

        self.next_colour_index : dict[str, int] = {
            "Company Name": 0,
            "Project": 0
        }
        self.init_rows()

        image_plus = ctk.CTkImage(dark_image=Image.open("a_Directory/GUI_files/plus.png"), size=(20,20))
        self.button_add = ctk.CTkButton(self, image=image_plus, text="", width=20, height=20, fg_color="gray30",
                                        command=self.add_row)

        self.button_add.grid(row=3,column=0,padx=10, pady=10, sticky="ws")

    def init_rows(self):
        INIT_ROWS: int = 7

        for i in range(0, INIT_ROWS):
            self.add_row()

    def get_project_values(self, projects_dict) -> dict[str, tuple[str, str]]:
        # get just the project names
        return {
            name : (pid, code) for pid, (name, code) in projects_dict.items()
        }

    def get_orgadmincsv(self) -> dict[str, tuple[str, str, datetime.datetime]]:
        if not self.csvOrgAdmins:
            self.csvOrgAdmins = loadcsv()

        return self.csvOrgAdmins

    #Add a new row when + is clicked
    def add_row(self):
        self.logger.debug("Adding row")
        frame_newrow = RowFrame(self.frame_tablerows, app=self, project_vals=self.project_values)
        frame_newrow.grid(row=len(self.rows), column=0, padx=10, sticky="sew")
        self.rows.add(frame_newrow)

    def get_colour(self, duplicate_type : str, value):
        duplicate_colours = self.duplicate_colours[duplicate_type]
        if value not in duplicate_colours:
            colours = self.INPUT_COLOURSMAP["duplicate"]
            colour = colours[self.next_colour_index[duplicate_type] % len(colours)]
            self.duplicate_colours[duplicate_type][value] = colour
            self.next_colour_index[duplicate_type] += 1

        return duplicate_colours[value]

    def check_for_duplicates(self, duplicate_type, current_row : RowFrame):
        COLUMN_MAP = {
            "Full Name": {
                "text": lambda r: r.entry_usertext.get().strip().lower(),
                "default_text": lambda r: r.default_usertext(),
                "handle_duplicate": lambda r, b: r.duplicate_user(b)
            },
            "Email Address": {
                "text": lambda r: r.entry_emailtext.get().strip().lower(),
                "default_text": lambda r: r.default_emailtext(),
                "handle_duplicate": lambda r, b: r.duplicate_user(b)
            },
            "Company Name": {
                "text": lambda r: r.entry_companytext.get().strip().lower(),
                "default_text": lambda r: r.default_companytext(),
                "handle_duplicate": lambda r, b: r.duplicate_company(b)
            },
            "Project": {
                "text": lambda r: r.combo_project.get().strip(),
                "default_text": lambda r: "Project",
                "handle_duplicate": lambda r, b: r.duplicate_project(b)
            }
        }
        COLOUR_TYPES = ["Company Name", "Project"]
        text_get = COLUMN_MAP[duplicate_type]["text"]
        handle_duplicate = COLUMN_MAP[duplicate_type]["handle_duplicate"]
        default_text = COLUMN_MAP[duplicate_type]["default_text"]

        col_default_text = default_text(current_row).lower()

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

    #Debug
    def check_output(self, duplicate_rows):
        self.logger.debug("Duplicate rows:")
        for i, duplicate_dict in enumerate(duplicate_rows.values()):
            self.logger.debug("Set %d : %s" % (i, [r.id for r in duplicate_dict]))

    def clear_rows(self):
        for row in self.rows:
            row.destroy()

        self.rows = set()
        self.init_rows()


class SearchClearFrame(ctk.CTkFrame):
    def __init__(self, master=None, app=None):
        super().__init__(master)
        self.app = master if app is None else app
        self.button_clear = ctk.CTkButton(self, text="Clear all", command=None)
        self.button_clear.grid(row=0, column=0, padx=10, pady=10, sticky="ws")
        self.button_clear.bind("<Button-1>", self.clear_pressed)

        self.tb_log = ctk.CTkTextbox(self, height=80, state="disabled")
        self.tb_log.grid(row=0, column=1, sticky="ew")
        self.grid_columnconfigure(1, weight=1)
        log_handler = LogTBHandler(self.tb_log)
        lformat = Formatter(fmt="{asctime}: {levelname}: {message}", style="{", datefmt="%Y-%m-%d %H:%M")
        log_handler.setLevel(INFO)
        log_handler.setFormatter(lformat)
        self.app.logger.addHandler(log_handler)

        self.button_search = ctk.CTkButton(self, text="Search", command=None)
        self.button_search.grid(row=0, column=2, padx=10, pady=10, sticky="es")
        self.button_search.bind("<Button-1>", self.search_pressed)

    def clear_pressed(self, event):
        #Remove all rows and replace with default ones
        self.app.clear_rows()

        #Remove all text in logger
        self.tb_log.delete('1.0', "end")

    #TODO
    def search_pressed(self, event):
        self.app.logger.info("Search pressed")
        for row in self.app.rows:
            #if search is pressed, check the valid rows not yet selected
            if row.check_if_valid() and not row.is_selected():
                self.app.logger.info("Row %d %s" % (row.id, row.current_status()))
                match row.current_status():
                    case "IDLE":
                        # Get the project and init config based on the project
                        selected_project = row.combo_project.get()
                        projectid, projectcode = self.app.projects_dict[selected_project]
                        ui_config : WrapperConfig = WrapperConfig(DEBUG)
                        ui_config.initWrapper(debug=[selected_project, projectid, projectcode])

                        self.app.logger.info("Initialised project %s %s" % (config.project().projectCode(), config.project().projectName()))

                        # Search the project directory on email
                        username = row.entry_usertext.get().strip().lower()
                        email = row.entry_emailtext.get().strip().lower()
                        parameters = search_on_email(email)

                        num_users, usersXML = api_project_directory_search(parameters) # Search for this user on the project

                        # If user found on project:

                        if num_users > 1:
                            #Multiple users found on the project, allow user to choose
                            #config.logger.debug(rootXML)
                            #Convert user entry to combo box
                            row.user_selection(usersXML)

                        elif num_users == 1:
                            config.info("User has been found on %s" % selected_project)
                            row.update_status("GREEN") # turn fg green
                            # add company name in as in directory
                            aconex_company = et_findtagtext(usersXML, "OrganizationName")
                            row.widget_company.set(aconex_company)
                            # TODO update new user tracker
                            row.cb_select.configure(state="normal") # enable tickbox
                        # If user not found
                        else:
                            pass
                            # search name in global, include company if provided
                            config.info(
                                "User has NOT been found on %s. Searching global directory..." % selected_project)
                            parameters = search_on_name(username, project=False)
                            csvOrgAdminList = None #TODO
                            searchstatus, omail = global_directory_search(csvOrgAdminList, parameters)


                            # if found once
                                # fill in name and company
                                # turn green, open link
                            # if found >1
                                # show company selector
                                # turn purple if company selected
                                # turn red if N/A company
                                # if not found
                                    # if company provided
                                    # search for company
                                    # show company selector for companies with org admins
                                    # hover over for org admins?
                                    # turn purple if company selected
                                    # turn red if N/A company
                                # if no company
                                    # turn fg red
                                    # company = 'N/A (Register as new)'

                    case "GREEN":
                        pass  # TODO
                    case "PURPLE":
                        pass  # TODO
                    case "RED":
                        pass #TODO
                    case _:
                        raise Exception("Invalid row status '%s'" % row.current_status())

                #press search again
                    #if green
                        #search project again
                    #if purple
                        #send 'new user' email to org admins
                    #if red
                        #send 'new org' email to org admins
                    #update tracker




class LogTBHandler(Handler):
    def __init__(self, tb_output : ctk.CTkTextbox):
        super().__init__()
        self.tb_output = tb_output

    def emit(self, log_record):
        message = self.format(log_record)
        self.tb_output.configure(state="normal")
        self.tb_output.insert("end", message + "\n")
        self.tb_output.see("end") #scroll to end of message
        self.tb_output.configure(state="disabled")




class TopButtonsFrame(ctk.CTkFrame):
    def __init__(self, master=None):
        super().__init__(master)

        for i in range(0, 4):
            self.grid_columnconfigure(i, weight=1)

        self.button_all = ctk.CTkButton(self, text="Add to 'all'", command=None)
        self.button_all.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.button_mg = ctk.CTkButton(self, text="Add to company MG", command=None)
        self.button_mg.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.button_transmittal = ctk.CTkButton(self, text="Draft transmittal", command=None)
        self.button_transmittal.grid(row=0, column=2, padx=10, pady=10, sticky="ew")

        self.button_invite = ctk.CTkButton(self, text="Draft project invite", command=None)
        self.button_invite.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

USERLINEREGEX = r"([a-zA-Z ]*)[^a-zA-Z0-9]+(\S+@[^>\s]+)"

class RowFrame(ctk.CTkFrame):
    __nextID = 1
    def __init__(self, master=None, app=None, project_vals : list[str]=None):
        super().__init__(master)
        self.app = master if app is None else app
        self.id = RowFrame.__nextID
        RowFrame.__nextID += 1

        self.is_valid : bool = False #this is whether this row can be searched
        self.status : str = "IDLE"

        for col in range(5):
            self.grid_columnconfigure(col, weight=0)

        default_usertext : str = "Full Name"
        default_emailtext : str = "Email Address"
        default_companytext : str = "Company Name"

        self.user_is_duplicate : bool = False #check if two rows are the same person to prevent running twice

        #User widget starts as entry but could be a combo box
        self.entry_usertext = ctk.StringVar(self, default_usertext)
        self.widget_user = ctk.CTkEntry(self, width=120, placeholder_text=self.entry_usertext.get(), textvariable=self.entry_usertext)
        self.widget_user.grid(row=0, column=0, sticky="n")
        self.widget_user.bind("<FocusOut>", lambda event: self.on_deselect(default_usertext))
        self.widget_user.bind('<Control-v>', lambda event : self.paste_user(self.widget_user))

        self.entry_emailtext = ctk.StringVar(self, default_emailtext)
        self.entry_email = ctk.CTkEntry(self, width=240, placeholder_text=self.entry_emailtext.get(), textvariable=self.entry_emailtext)
        self.entry_email.grid(row=0, column=1, sticky="n")
        self.entry_email.bind("<FocusOut>", lambda event: self.on_deselect(default_emailtext))
        self.entry_email.bind('<Control-v>', lambda event : self.paste_user(self.entry_email))

        self.combo_project = ctk.CTkComboBox(self, width=160, values=project_vals, command=lambda event: self.on_deselect("Project"))
        self.combo_project.grid(row=0, column=2, sticky="n")
        self.app.check_for_duplicates("Project", self) #run once to make all project selectors same colour

        # Company widget starts as entry but could be a combo box
        self.entry_companytext = ctk.StringVar(self, default_companytext)
        self.widget_company = ctk.CTkEntry(self, width=160, placeholder_text=self.entry_companytext.get(), textvariable=self.entry_companytext)
        self.widget_company.grid(row=0, column=3, sticky="n")
        self.widget_company.bind("<FocusOut>", lambda event: self.on_deselect(default_companytext))

        self.default_map: dict[ctk.CTkEntry, str] = {
            self.widget_user: default_usertext,
            self.entry_email: default_emailtext,
            self.widget_company: default_companytext
        }

        self.input_columns = [self.widget_user, self.entry_email, self.combo_project, self.widget_company]

        check_var = ctk.StringVar(value="off")
        self.cb_select = ctk.CTkCheckBox(self, text="", variable=check_var, width=10, command=None, onvalue="on", offvalue="off")
        self.cb_select.configure(state="disabled")
        self.cb_select.grid(row=0, column=4, padx=(10,0), sticky="ne")

        self.app.logger.info(self.is_selected())

    def on_deselect(self, duplicate_type : str):
        self.app.check_for_duplicates(duplicate_type, self)

    def default_usertext(self) -> str:
        return self.default_map[self.widget_user]

    def default_emailtext(self) -> str:
        return self.default_map[self.entry_email]

    def default_companytext(self) -> str:
        return self.default_map[self.widget_company]

    # if paste pressed, split the name/email and put into the selected row
    def paste_user(self, entry : ctk.CTkEntry):
        self.after(1, self.get_paste, entry)

    def get_paste(self, entry : ctk.CTkEntry):
        pasted_text = entry.get()
        #Look for the format name <email> within one of the entry boxes
        lineSearchRes = re.search(USERLINEREGEX, pasted_text)
        if lineSearchRes:
            names = lineSearchRes.group(1).strip()
            email = lineSearchRes.group(2)

            self.entry_usertext.set(names)
            self.entry_emailtext.set(email)


    def duplicate_company(self, colour: str = ""):
        if colour:
            self.widget_company.configure(text_color=colour)

        else:
            self.widget_company.configure(text_color=self.app.INPUT_COLOURSMAP["default"])

    def duplicate_project(self, colour: str = ""):
        if colour:
            self.combo_project.configure(text_color=colour)

        else:
            self.combo_project.configure(text_color=self.app.INPUT_COLOURSMAP["default"])

    def duplicate_user(self, duplicate: bool = False):
        if duplicate:
            self.app.logger.info("Duplicate users found")
            self.user_is_duplicate = True

        else:
            self.user_is_duplicate = False

    #check if input value is still its default
    def check_is_default(self, entry : ctk.CTkEntry) -> bool:
        return entry.get() == self.default_map[entry]

    def check_if_valid(self) -> bool:
        #We need the name and email address, if theres no company, we can search for this later. we need email for the tracker/emailing, and the name for searching directory
        if self.user_is_duplicate or any(map(self.check_is_default, [self.widget_user, self.entry_email])):
            self.app.logger.info("Row %d is not valid" % self.id)
            self.is_valid = False
        else:
            self.app.logger.info("Row %d is valid" % self.id)
            self.is_valid = True
            self.status = "IDLE"

        self.change_row_colour()
        return self.is_valid

    #if tickbox is selected - this is only if row is valid and user is found on project
    def is_selected(self) -> bool:
        return self.cb_select.get() == "1"

    """
    The Rows status can be one of:
        INVALID = row isnt valid yet and cant be searched
        IDLE = row hasnt been searched yet within directory
        GREEN = user has been searched and found within global OR project directory
        PURPLE = user has NOT been found but has been matched to a valid aconex org
        RED = user has NOT been found, valid aconex org has NOT been found
    """
    def current_status(self) -> str:
        if not self.is_valid:
            return "INVALID"
        else:
            return self.status

    def update_status(self, status : str):
        self.status = status
        self.change_row_colour()

    def change_row_colour(self):
        self.set_fg(self.app.INPUT_COLOURSMAP[self.status])

    #set background colour for all columns in row
    def set_fg(self, colour: str):
        for cwidget in self.input_columns:
            cwidget.configure(fg_color=colour)

    #Convert user entry to combo box where users XML is the API directory info
    def user_selection(self, users : list[ET.Element]):
        uservals : list[str] = [] #list of values for combo box
        username : str
        for userXML in users:
            #print(userXML.text)
            username = et_findtagtext(userXML, "UserName")

            #if user is a guest
            if et_findtagtext(userXML, "SearchResultType") == "GUEST_TYPE":
                username += " (Guest)"

            uservals.append(username)

        self.widget_user.destroy() #destroy entry
        self.widget_user = ctk.CTkComboBox(self, width=120, values=uservals)
        self.widget_user.grid(row=0, column=0, sticky="n")
        self.app.logger.debug("Converted entry to combobox with values %s" % uservals)

def main():
    app = App()
    app.mainloop()